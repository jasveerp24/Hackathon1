"""Governance shell: audit trail, consent, retention, data-subject rights.

Mapped to ISO/IEC 27001:2022 Annex A, ISO/IEC 27701 (privacy) and the Mauritius
Data Protection Act 2017 in GOVERNANCE.md. This is good practice for a demo, not a
certification: certification needs an audited management system (policies, risk
assessment, internal audit), not just code.

* Audit log: append-only and hash-chained. Each entry stores the SHA-256 of the
  previous one, so editing or deleting any past entry breaks the chain, and
  /governance/audit/verify shows where.
* Phone numbers are masked in the audit log and in server logs.
* Consent: each family contact records when and to which wording consent was given.
* Retention: closed trips and alert logs older than ALERTS_RETENTION_DAYS are deleted.
* Rights: export everything about a user (access/portability) or erase it.
"""
import asyncio
import hashlib
import json
import logging
from datetime import timedelta

from .config import settings
from .store import get_store, utcnow

log = logging.getLogger("whatsapp_alerts")

CONSENT_VERSION = "2026-11-09"
CONSENT_TEXT = (
    "The contact agreed to receive automatic WhatsApp safety alerts (trip start, missed "
    "check-in, SOS with location, hazard warnings, safe return) about this user, and knows "
    "they can ask to be removed at any time."
)

_lock = asyncio.Lock()
GENESIS = "0" * 64


def mask_phone(phone: str) -> str:
    """'23057123456' -> '2305****456' (enough to recognise, not enough to misuse)."""
    d = "".join(ch for ch in str(phone or "") if ch.isdigit())
    if len(d) <= 6:
        return "*" * len(d)
    return d[:4] + "*" * (len(d) - 7) + d[-3:]


def _digest(prev_hash: str, body: dict) -> str:
    canonical = json.dumps(body, sort_keys=True, separators=(",", ":"), ensure_ascii=False, default=str)
    return hashlib.sha256((prev_hash + canonical).encode()).hexdigest()


def _body(entry: dict) -> dict:
    return {k: v for k, v in entry.items() if k not in ("_id", "hash")}


async def audit(action: str, owner_id: str | None, actor: str, details: dict | None = None, outcome: str = "ok"):
    """Append one audit entry. Never raises: auditing must not break an SOS."""
    try:
        async with _lock:
            store = get_store()
            last = await store.audit_last()
            seq = (last["seq"] + 1) if last else 1
            prev_hash = last["hash"] if last else GENESIS
            body = {
                "seq": seq,
                "at": utcnow().isoformat(),
                "action": action,
                "owner_id": owner_id,
                "actor": actor,
                "outcome": outcome,
                "details": details or {},
                "prev_hash": prev_hash,
            }
            entry = {"_id": f"audit-{seq}", **body, "hash": _digest(prev_hash, body)}
            await store.audit_append(entry)
    except Exception:
        log.exception("Audit write failed for action %s", action)


async def verify_chain() -> dict:
    entries = await get_store().audit_all()
    prev = GENESIS
    for i, e in enumerate(entries, start=1):
        body = _body(e)
        if e.get("seq") != i or e.get("prev_hash") != prev or _digest(prev, body) != e.get("hash"):
            return {"ok": False, "entries": len(entries), "broken_at_seq": e.get("seq", i)}
        prev = e["hash"]
    return {"ok": True, "entries": len(entries), "last_hash": prev}


async def run_retention() -> dict:
    cutoff = utcnow() - timedelta(days=settings.retention_days)
    removed = await get_store().purge_before(cutoff)
    if removed["trips"] or removed["alerts"]:
        await audit("retention_purge", None, "system", {**removed, "older_than_days": settings.retention_days})
    return removed


def _masked_export(data: dict) -> dict:
    """Export is for the user themself, so numbers stay readable; ids/datetimes made JSON-safe."""
    out = {}
    for key, docs in data.items():
        out[key] = []
        for d in docs:
            d = dict(d)
            d["id"] = d.pop("_id", None)
            out[key].append(json.loads(json.dumps(d, default=str)))
    return out


async def export_owner(owner_id: str, actor: str) -> dict:
    data = _masked_export(await get_store().export_owner(owner_id))
    await audit("data_exported", owner_id, actor, {k: len(v) for k, v in data.items()})
    return {
        "owner_id": owner_id,
        "exported_at": utcnow().isoformat(),
        "retention_days": settings.retention_days,
        "consent_version": CONSENT_VERSION,
        **data,
    }


async def erase_owner(owner_id: str, actor: str) -> dict:
    removed = await get_store().erase_owner(owner_id)
    # The audit trail keeps the fact of erasure (no personal data), as proof it was done.
    await audit("data_erased", owner_id, actor, removed)
    return {"erased": removed}


def policy() -> dict:
    return {
        "retention_days": settings.retention_days,
        "consent_version": CONSENT_VERSION,
        "consent_text": CONSENT_TEXT,
        "audit": "append-only, SHA-256 hash-chained, phone numbers masked",
        "max_contacts": 5,
        "rate_limits_per_minute": {
            "per_user": settings.rate_limit_per_user_per_minute,
            "global": settings.rate_limit_global_per_minute,
        },
        "data_location": "MongoDB Atlas" if settings.mongodb_uri else "server memory (lost on restart)",
    }
