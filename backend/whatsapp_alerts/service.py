"""Core logic (theme-agnostic: a "trip" is any activity with a check-in time).
Teammates' Python code can import these functions directly, e.g.

    from whatsapp_alerts.service import notify_contacts
    from whatsapp_alerts.templates import AlertEvent
    await notify_contacts("user-123", AlertEvent.HAZARD_WARNING,
                          {"person": "Ravi", "plan": "Fishing at Le Morne", "warning": "High waves 3.5 m"})
"""
import asyncio
import logging
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

from .client import normalize_phone, send_alert
from .config import settings
from .store import OPEN_STATUSES, get_store, new_id, utcnow
from .templates import AlertEvent

log = logging.getLogger("whatsapp_alerts")


def fmt_time(dt: datetime) -> str:
    """'14:30, 03/11' in local Mauritius time (same format in EN and FR)."""
    return dt.astimezone(ZoneInfo(settings.timezone)).strftime("%H:%M, %d/%m")


def maps_link(lat: float | None, lng: float | None, fallback: str = "") -> str:
    if lat is not None and lng is not None:
        return f"https://maps.google.com/?q={lat:.5f},{lng:.5f}"
    return fallback or "unknown"


def _public(doc: dict | None) -> dict | None:
    if doc is None:
        return None
    d = dict(doc)
    d["id"] = d.pop("_id")
    for k, v in list(d.items()):
        if isinstance(v, datetime):
            d[k] = v.isoformat()
    return d


async def notify_contacts(
    owner_id: str, event: AlertEvent, values: dict, trip_id: str | None = None
) -> dict:
    """Send one alert to every family contact of owner_id, each in their own language."""
    store = get_store()
    contacts = await store.list_contacts(owner_id)
    values = {"emergency_number": settings.emergency_number, "app_name": settings.app_name, **values}
    if contacts:
        results = await asyncio.gather(
            *(send_alert(c["phone"], event, c.get("lang", "en"), values) for c in contacts)
        )
    else:
        results = []
    for c, r in zip(contacts, results):
        r["contact_name"] = c["name"]
    entry = {
        "_id": new_id(),
        "owner_id": owner_id,
        "trip_id": trip_id,
        "event": event.value,
        "results": list(results),
        "sent": sum(1 for r in results if r["ok"]),
        "failed": sum(1 for r in results if not r["ok"]),
        "created_at": utcnow(),
    }
    await store.log_alert(entry)
    if not contacts:
        log.warning("No family contacts for owner %s; nothing sent for %s", owner_id, event.value)
    return _public(entry)


# ---------- contacts ----------
async def add_contact(owner_id: str, name: str, phone: str, lang: str) -> dict:
    from .governance import CONSENT_TEXT, CONSENT_VERSION

    doc = {
        "consent": {"given_at": utcnow(), "version": CONSENT_VERSION, "text": CONSENT_TEXT},
        "_id": new_id(),
        "owner_id": owner_id,
        "name": name.strip(),
        "phone": normalize_phone(phone),
        "lang": lang if lang in ("en", "fr") else "en",
        "created_at": utcnow(),
    }
    return _public(await get_store().add_contact(doc))


async def list_contacts(owner_id: str) -> list[dict]:
    return [_public(c) for c in await get_store().list_contacts(owner_id)]


async def delete_contact(owner_id: str, contact_id: str) -> bool:
    return await get_store().delete_contact(owner_id, contact_id)


# ---------- trips / check-ins ----------
def _trip_values(trip: dict) -> dict:
    return {"person": trip["person_name"], "plan": trip["plan"], "due_time": fmt_time(trip["due_at"])}


async def start_trip(
    owner_id: str,
    person_name: str,
    plan: str,
    due_at: datetime,
    person_phone: str = "",
    grace_minutes: int | None = None,
    notify_start: bool = True,
    extra: dict | None = None,
) -> dict:
    grace = settings.grace_minutes if grace_minutes is None else grace_minutes
    trip = {
        "_id": new_id(),
        "owner_id": owner_id,
        "person_name": person_name.strip(),
        "person_phone": normalize_phone(person_phone) if person_phone else "",
        "plan": plan.strip(),
        "due_at": due_at,
        "grace_minutes": grace,
        "alert_at": due_at + timedelta(minutes=grace),
        "status": "active",
        "created_at": utcnow(),
        "extra": extra or {},  # e.g. {"boat": "...", "sea_state": "..."} from the idea using this module
    }
    await get_store().create_trip(trip)
    alert = None
    if notify_start:
        alert = await notify_contacts(owner_id, AlertEvent.TRIP_STARTED, _trip_values(trip), trip["_id"])
    return {"trip": _public(trip), "alert": alert}


async def check_in(trip_id: str) -> dict | None:
    """Person is back: close the trip and reassure the family."""
    store = get_store()
    trip = await store.get_trip(trip_id)
    if not trip:
        return None
    now = utcnow()
    changed = await store.update_trip(trip_id, {"status": "checked_in", "checked_in_at": now}, OPEN_STATUSES)
    if not changed:
        return {"trip": _public(trip), "alert": None, "note": "Trip was already closed"}
    trip = await store.get_trip(trip_id)
    alert = await notify_contacts(
        trip["owner_id"], AlertEvent.CHECKED_IN, {"person": trip["person_name"], "time": fmt_time(now)}, trip_id
    )
    return {"trip": _public(trip), "alert": alert}


async def cancel_trip(trip_id: str) -> bool:
    return await get_store().update_trip(trip_id, {"status": "cancelled"}, OPEN_STATUSES)


async def sos(owner_id: str, person_name: str, lat=None, lng=None, location_text: str = "", trip_id=None) -> dict:
    if trip_id:
        await get_store().update_trip(trip_id, {"status": "sos", "sos_at": utcnow()}, ["active", "overdue_alerted"])
    return await notify_contacts(
        owner_id,
        AlertEvent.SOS,
        {"person": person_name, "location": maps_link(lat, lng, location_text)},
        trip_id,
    )


async def hazard_warning(owner_id: str, person_name: str, plan: str, warning: str, trip_id=None) -> dict:
    """Call this from any data/weather agent when a hazard is found for this user."""
    return await notify_contacts(
        owner_id, AlertEvent.HAZARD_WARNING, {"person": person_name, "plan": plan, "warning": warning}, trip_id
    )


async def run_overdue_check(now: datetime | None = None) -> int:
    """Alert family for every active trip past due + grace. Returns how many trips were alerted."""
    store = get_store()
    now = now or utcnow()
    count = 0
    for trip in await store.due_trips(now):
        # Claim the trip first so two workers/ticks can never double-send.
        if not await store.update_trip(trip["_id"], {"status": "overdue_alerted", "overdue_at": now}, ["active"]):
            continue
        entry = await notify_contacts(trip["owner_id"], AlertEvent.MISSED_CHECKIN, _trip_values(trip), trip["_id"])
        from .governance import audit

        await audit("missed_checkin_alert", trip["owner_id"], "system:scheduler",
                    {"trip_id": trip["_id"], "sent": entry["sent"], "failed": entry["failed"]})
        count += 1
    return count


async def scheduler_loop():
    """Background task started by the router's lifespan. Checks every N seconds."""
    from .governance import run_retention

    log.info("Missed check-in scheduler running every %ss", settings.scheduler_interval_seconds)
    last_purge = 0.0
    while True:
        if asyncio.get_running_loop().time() - last_purge > 3600:  # retention check hourly
            try:
                await run_retention()
            except Exception:
                log.exception("Retention purge failed; will retry")
            last_purge = asyncio.get_running_loop().time()
        try:
            n = await run_overdue_check()
            if n:
                log.warning("Sent missed check-in alerts for %d trip(s)", n)
        except Exception:
            log.exception("Overdue check failed; will retry")
        await asyncio.sleep(settings.scheduler_interval_seconds)


# ---------- inbound WhatsApp replies ----------
CHECKIN_WORDS = {"safe", "back", "ok", "home", "rentre", "rentré", "bien", "arrive", "arrivé", "check in", "checkin"}


async def handle_inbound_text(from_phone: str, text: str) -> str | None:
    """If the person themselves replies e.g. 'SAFE' on WhatsApp, check them in. Returns trip id."""
    word = (text or "").strip().lower()
    if word not in CHECKIN_WORDS:
        return None
    trip = await get_store().open_trip_by_phone(normalize_phone(from_phone))
    if not trip:
        return None
    await check_in(trip["_id"])
    return trip["_id"]
