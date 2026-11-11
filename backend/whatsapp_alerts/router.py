"""FastAPI router. Plug into any app with two lines:

    from whatsapp_alerts import alerts_router, alerts_lifespan
    app = FastAPI(lifespan=alerts_lifespan)
    app.include_router(alerts_router)

All routes live under /api/alerts.
"""
import asyncio
import json
import logging
from contextlib import asynccontextmanager
from datetime import datetime
from typing import Literal
from zoneinfo import ZoneInfo

from fastapi import APIRouter, Depends, HTTPException, Query, Request, Response
from pydantic import BaseModel, Field

from . import service
from .client import normalize_phone
from .config import settings
from . import governance
from .governance import audit, mask_phone
from .security import actor_of, check_rate, require_app_key, valid_meta_signature
from .store import MemoryStore, get_store, init_store
from .templates import AlertEvent

log = logging.getLogger("whatsapp_alerts")
alerts_router = APIRouter(prefix="/api/alerts", tags=["whatsapp-alerts"])
# App routes need the app key; the webhook is called by Meta and checks Meta's signature instead.
api_router = APIRouter(dependencies=[Depends(require_app_key)])
webhook_router = APIRouter()


@asynccontextmanager
async def alerts_lifespan(app=None):
    """Connects storage and starts the missed check-in scheduler. Use as (or inside) your app lifespan."""
    await init_store()
    task = asyncio.create_task(service.scheduler_loop())
    mode = "DRY RUN (no messages really sent)" if settings.effective_dry_run else (
        "templates" if settings.use_templates else "plain text (24h window only)"
    )
    log.warning("WhatsApp alerts ready. Mode: %s", mode)
    if not settings.api_key:
        log.warning("ALERTS_API_KEY is empty: the API is open to anyone who can reach it. Set it before deploying.")
    if settings.enable_dev_routes:
        log.warning("Dev route /dev/run-overdue-check is ON (ALERTS_ENABLE_DEV_ROUTES=true).")
    try:
        yield
    finally:
        task.cancel()


# ---------- request models ----------
Lang = Literal["en", "fr"]


class ContactIn(BaseModel):
    owner_id: str = Field(min_length=1)
    name: str = Field(min_length=1, max_length=60)
    phone: str = Field(min_length=7, max_length=20)
    lang: Lang = "en"
    consent: bool = Field(description="The contact agreed to receive WhatsApp safety alerts")


class TripIn(BaseModel):
    owner_id: str = Field(min_length=1)
    person_name: str = Field(min_length=1, max_length=60)
    plan: str = Field(min_length=1, max_length=300, description="Where they are going / what they are doing")
    due_at: datetime = Field(description="ISO time they should be back. No offset = Mauritius time.")
    person_phone: str = ""
    grace_minutes: int | None = Field(default=None, ge=0, le=24 * 60)
    notify_start: bool = True
    extra: dict = {}


class SosIn(BaseModel):
    owner_id: str
    person_name: str
    lat: float | None = None
    lng: float | None = None
    location_text: str = ""
    trip_id: str | None = None


class HazardIn(BaseModel):
    owner_id: str
    person_name: str
    plan: str
    warning: str = Field(min_length=1, max_length=300)
    trip_id: str | None = None


class SendIn(BaseModel):
    owner_id: str
    event: AlertEvent
    values: dict[str, str]
    trip_id: str | None = None


# ---------- routes ----------
@api_router.get("/status")
async def status():
    return {
        "configured": settings.is_configured,
        "dry_run": settings.effective_dry_run,
        "use_templates": settings.use_templates,
        "store": "memory" if isinstance(get_store(), MemoryStore) else "mongodb",
        "grace_minutes": settings.grace_minutes,
        "emergency_number": settings.emergency_number,
        "dev_routes": settings.enable_dev_routes,
    }


@api_router.get("/contacts")
async def get_contacts(owner_id: str):
    return await service.list_contacts(owner_id)


@api_router.post("/contacts")
async def post_contact(body: ContactIn, request: Request):
    if not body.consent:
        raise HTTPException(422, "Consent is required before adding a family contact")
    digits = normalize_phone(body.phone)
    if not (8 <= len(digits) <= 15):
        raise HTTPException(422, "Phone number must be 8 to 15 digits incl. country code")
    check_rate(body.owner_id)
    contacts = await service.list_contacts(body.owner_id)
    if len(contacts) >= 5:
        # Meta's test number can only message 5 verified numbers anyway.
        raise HTTPException(400, "Maximum 5 family contacts")
    c = await service.add_contact(body.owner_id, body.name, body.phone, body.lang)
    await audit("contact_added", body.owner_id, actor_of(request),
                {"contact_id": c["id"], "phone": mask_phone(c["phone"]), "consent_version": governance.CONSENT_VERSION})
    return c


@api_router.delete("/contacts/{contact_id}")
async def remove_contact(contact_id: str, owner_id: str, request: Request):
    if not await service.delete_contact(owner_id, contact_id):
        raise HTTPException(404, "Contact not found")
    await audit("contact_removed", owner_id, actor_of(request), {"contact_id": contact_id})
    return {"ok": True}


@api_router.post("/trips")
async def post_trip(body: TripIn, request: Request):
    check_rate(body.owner_id)
    due = body.due_at
    if due.tzinfo is None:
        due = due.replace(tzinfo=ZoneInfo(settings.timezone))
    r = await service.start_trip(
        body.owner_id, body.person_name, body.plan, due, body.person_phone,
        body.grace_minutes, body.notify_start, body.extra,
    )
    await audit("trip_started", body.owner_id, actor_of(request), {"trip_id": r["trip"]["id"], **_sent(r["alert"])})
    return r


@api_router.get("/trips")
async def get_trips(owner_id: str, limit: int = Query(20, le=100)):
    return [service._public(t) for t in await get_store().list_trips(owner_id, limit)]


@api_router.post("/trips/{trip_id}/checkin")
async def post_checkin(trip_id: str, request: Request):
    trip = await get_store().get_trip(trip_id)
    if trip is None:
        raise HTTPException(404, "Trip not found")
    check_rate(trip["owner_id"])
    r = await service.check_in(trip_id)
    if r is None:
        raise HTTPException(404, "Trip not found")
    await audit("checked_in", trip["owner_id"], actor_of(request), {"trip_id": trip_id, **_sent(r["alert"])})
    return r


@api_router.post("/trips/{trip_id}/cancel")
async def post_cancel(trip_id: str, request: Request):
    trip = await get_store().get_trip(trip_id)
    ok = await service.cancel_trip(trip_id)
    if ok and trip:
        await audit("trip_cancelled", trip["owner_id"], actor_of(request), {"trip_id": trip_id})
    return {"ok": ok}


@api_router.post("/sos")
async def post_sos(body: SosIn, request: Request):
    check_rate(body.owner_id)
    r = await service.sos(body.owner_id, body.person_name, body.lat, body.lng, body.location_text, body.trip_id)
    # Location itself is not copied into the audit trail (data minimisation).
    await audit("sos", body.owner_id, actor_of(request), {"trip_id": body.trip_id, "gps": body.lat is not None, **_sent(r)})
    return r


@api_router.post("/hazard")
async def post_hazard(body: HazardIn, request: Request):
    check_rate(body.owner_id)
    r = await service.hazard_warning(body.owner_id, body.person_name, body.plan, body.warning, body.trip_id)
    await audit("hazard_warning", body.owner_id, actor_of(request), {"trip_id": body.trip_id, **_sent(r)})
    return r


@api_router.post("/send")
async def post_send(body: SendIn, request: Request):
    """Generic: send any event with your own values (see templates.py for the keys)."""
    check_rate(body.owner_id)
    r = await service.notify_contacts(body.owner_id, body.event, body.values, body.trip_id)
    await audit("alert_sent", body.owner_id, actor_of(request), {"event": body.event.value, **_sent(r)})
    return r


@api_router.get("/log")
async def get_log(owner_id: str, limit: int = Query(50, le=200)):
    return [service._public(a) for a in await get_store().list_alerts(owner_id, limit)]


@api_router.post("/dev/run-overdue-check")
async def dev_run_check():
    """Demo helper: run the missed check-in check right now instead of waiting for the next tick."""
    if not settings.enable_dev_routes:
        raise HTTPException(404, "Not found")
    return {"alerted_trips": await service.run_overdue_check()}


# ---------- governance & privacy ----------
@api_router.get("/governance/policy")
async def get_policy():
    """What data we keep, for how long, and on what consent (show this in the app / to judges)."""
    return governance.policy()


@api_router.get("/governance/audit")
async def get_audit(owner_id: str | None = None, limit: int = Query(50, le=500)):
    return [{k: v for k, v in e.items() if k != "_id"} for e in await get_store().audit_list(owner_id, limit)]


@api_router.get("/governance/audit/verify")
async def get_audit_verify():
    """Re-computes the hash chain. ok=false means a past audit entry was changed or removed."""
    return await governance.verify_chain()


@api_router.get("/privacy/export")
async def privacy_export(owner_id: str, request: Request):
    """Right of access / portability: everything stored about this user, as JSON."""
    return await governance.export_owner(owner_id, actor_of(request))


@api_router.delete("/privacy/erase")
async def privacy_erase(owner_id: str, request: Request, confirm: bool = False):
    """Right to erasure: deletes the user's contacts, trips and alerts. Needs ?confirm=true."""
    if not confirm:
        raise HTTPException(400, "Add ?confirm=true to erase all data for this user")
    return await governance.erase_owner(owner_id, actor_of(request))


@api_router.post("/governance/run-retention")
async def post_run_retention(request: Request):
    """Run the retention purge now (normally hourly)."""
    if not settings.enable_dev_routes:
        raise HTTPException(404, "Not found")
    return await governance.run_retention()


def _sent(entry: dict | None) -> dict:
    return {"sent": entry["sent"], "failed": entry["failed"]} if entry else {"sent": 0, "failed": 0}


# ---------- Meta webhook (optional: delivery ticks + 'SAFE' replies) ----------
@webhook_router.get("/webhook")
async def verify_webhook(request: Request):
    p = request.query_params
    if (
        p.get("hub.mode") == "subscribe"
        and settings.webhook_verify_token
        and p.get("hub.verify_token") == settings.webhook_verify_token
    ):
        return Response(content=p.get("hub.challenge", ""), media_type="text/plain")
    raise HTTPException(403, "Verification failed")


@webhook_router.post("/webhook")
async def receive_webhook(request: Request):
    raw = await request.body()
    if len(raw) > 512_000:
        raise HTTPException(413, "Payload too large")
    signed = valid_meta_signature(raw, request.headers.get("X-Hub-Signature-256", ""))
    if settings.app_secret and not signed:
        raise HTTPException(401, "Bad signature")
    try:
        data = json.loads(raw or b"{}")
    except ValueError:
        return {"ok": True}
    store = get_store()
    # Always answer 200 quickly, or Meta keeps retrying.
    for entry in data.get("entry", []):
        for change in entry.get("changes", []):
            value = change.get("value", {})
            for st in value.get("statuses", []):  # sent / delivered / read / failed
                await store.update_alert_status(st.get("id"), st.get("status"))
            if not signed:
                # Without WA_APP_SECRET anyone could fake a "SAFE" reply and cancel an alert,
                # so inbound check-ins are only accepted from verified Meta calls.
                if value.get("messages"):
                    log.warning("Ignoring inbound WhatsApp message: set WA_APP_SECRET to enable SAFE replies.")
                continue
            for msg in value.get("messages", []):
                if msg.get("type") == "text":
                    trip_id = await service.handle_inbound_text(msg.get("from", ""), msg["text"].get("body", ""))
                    if trip_id:
                        log.info("Checked in trip %s via WhatsApp reply", trip_id)
                        trip = await store.get_trip(trip_id)
                        await audit("checked_in", trip["owner_id"] if trip else None, "whatsapp:signed-reply",
                                    {"trip_id": trip_id, "from": mask_phone(msg.get("from", ""))})
    return {"ok": True}


alerts_router.include_router(api_router)
alerts_router.include_router(webhook_router)
