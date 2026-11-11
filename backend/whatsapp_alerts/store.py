"""Storage for contacts, trips and the alert log.

MongoDB when MONGODB_URI is set, otherwise an in-memory store (fine for a demo,
lost on restart). Both expose the same async methods. Ids are uuid strings so
they go straight to JSON without ObjectId conversion.
"""
import logging
import uuid
from datetime import datetime, timezone

from .config import settings

log = logging.getLogger("whatsapp_alerts")


def new_id() -> str:
    return uuid.uuid4().hex


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class MemoryStore:
    def __init__(self):
        self.contacts: dict[str, dict] = {}
        self.trips: dict[str, dict] = {}
        self.alerts: list[dict] = []
        self.audit: list[dict] = []

    async def setup(self):
        log.warning("MONGODB_URI not set: using in-memory store (data lost on restart).")

    # contacts
    async def list_contacts(self, owner_id: str) -> list[dict]:
        return [c for c in self.contacts.values() if c["owner_id"] == owner_id]

    async def add_contact(self, doc: dict) -> dict:
        self.contacts[doc["_id"]] = doc
        return doc

    async def delete_contact(self, owner_id: str, contact_id: str) -> bool:
        c = self.contacts.get(contact_id)
        if c and c["owner_id"] == owner_id:
            del self.contacts[contact_id]
            return True
        return False

    # trips
    async def create_trip(self, doc: dict) -> dict:
        self.trips[doc["_id"]] = doc
        return doc

    async def get_trip(self, trip_id: str) -> dict | None:
        return self.trips.get(trip_id)

    async def update_trip(self, trip_id: str, fields: dict, only_if_status: list[str] | None = None) -> bool:
        t = self.trips.get(trip_id)
        if not t or (only_if_status and t["status"] not in only_if_status):
            return False
        t.update(fields)
        return True

    async def list_trips(self, owner_id: str, limit: int = 20) -> list[dict]:
        ts = [t for t in self.trips.values() if t["owner_id"] == owner_id]
        return sorted(ts, key=lambda t: t["created_at"], reverse=True)[:limit]

    async def open_trips_for_owner(self, owner_id: str) -> list[dict]:
        return [t for t in self.trips.values() if t["owner_id"] == owner_id and t["status"] in OPEN_STATUSES]

    async def due_trips(self, now: datetime) -> list[dict]:
        return [t for t in self.trips.values() if t["status"] == "active" and t["alert_at"] <= now]

    async def open_trip_by_phone(self, phone: str) -> dict | None:
        ts = [t for t in self.trips.values() if t.get("person_phone") == phone and t["status"] in OPEN_STATUSES]
        return max(ts, key=lambda t: t["created_at"]) if ts else None

    # alert log
    async def log_alert(self, doc: dict):
        self.alerts.append(doc)

    async def list_alerts(self, owner_id: str, limit: int = 50) -> list[dict]:
        a = [x for x in self.alerts if x["owner_id"] == owner_id]
        return sorted(a, key=lambda x: x["created_at"], reverse=True)[:limit]

    async def update_alert_status(self, message_id: str, status: str):
        for a in self.alerts:
            for r in a.get("results", []):
                if r.get("message_id") == message_id:
                    r["delivery"] = status

    # ---------- governance: audit, retention, export, erasure ----------
    async def audit_append(self, entry: dict):
        self.audit.append(entry)

    async def audit_last(self) -> dict | None:
        return self.audit[-1] if self.audit else None

    async def audit_list(self, owner_id: str | None, limit: int) -> list[dict]:
        a = [x for x in self.audit if owner_id is None or x.get("owner_id") == owner_id]
        return a[-limit:][::-1]

    async def audit_all(self) -> list[dict]:
        return list(self.audit)

    async def purge_before(self, cutoff: datetime) -> dict:
        closed = {"checked_in", "cancelled"}
        old_trips = [k for k, t in self.trips.items() if t["created_at"] < cutoff and t["status"] in closed]
        for k in old_trips:
            del self.trips[k]
        before = len(self.alerts)
        self.alerts = [a for a in self.alerts if a["created_at"] >= cutoff]
        return {"trips": len(old_trips), "alerts": before - len(self.alerts)}

    async def export_owner(self, owner_id: str) -> dict:
        return {
            "contacts": [c for c in self.contacts.values() if c["owner_id"] == owner_id],
            "trips": [t for t in self.trips.values() if t["owner_id"] == owner_id],
            "alerts": [a for a in self.alerts if a["owner_id"] == owner_id],
        }

    async def erase_owner(self, owner_id: str) -> dict:
        c = [k for k, v in self.contacts.items() if v["owner_id"] == owner_id]
        t = [k for k, v in self.trips.items() if v["owner_id"] == owner_id]
        for k in c:
            del self.contacts[k]
        for k in t:
            del self.trips[k]
        before = len(self.alerts)
        self.alerts = [a for a in self.alerts if a["owner_id"] != owner_id]
        return {"contacts": len(c), "trips": len(t), "alerts": before - len(self.alerts)}


# A trip still needs the person to check in while it is in one of these states.
OPEN_STATUSES = ["active", "overdue_alerted", "sos"]


class MongoStore:
    def __init__(self, uri: str, db_name: str):
        from pymongo import AsyncMongoClient  # pymongo >= 4.13

        self.client = AsyncMongoClient(uri, tz_aware=True, serverSelectionTimeoutMS=5000)
        db = self.client[db_name]
        self.contacts = db["wa_contacts"]
        self.trips = db["wa_trips"]
        self.alerts = db["wa_alert_log"]
        self.audit = db["wa_audit_log"]

    async def setup(self):
        await self.contacts.create_index("owner_id")
        await self.trips.create_index([("status", 1), ("alert_at", 1)])
        await self.trips.create_index([("person_phone", 1), ("status", 1)])
        await self.alerts.create_index([("owner_id", 1), ("created_at", -1)])
        await self.alerts.create_index("results.message_id")
        await self.audit.create_index("seq", unique=True)
        await self.audit.create_index([("owner_id", 1), ("seq", -1)])
        log.info("MongoDB store ready (%s)", settings.mongodb_db)

    async def list_contacts(self, owner_id):
        return await self.contacts.find({"owner_id": owner_id}).to_list(100)

    async def add_contact(self, doc):
        await self.contacts.insert_one(doc)
        return doc

    async def delete_contact(self, owner_id, contact_id):
        r = await self.contacts.delete_one({"_id": contact_id, "owner_id": owner_id})
        return r.deleted_count == 1

    async def create_trip(self, doc):
        await self.trips.insert_one(doc)
        return doc

    async def get_trip(self, trip_id):
        return await self.trips.find_one({"_id": trip_id})

    async def update_trip(self, trip_id, fields, only_if_status=None):
        q = {"_id": trip_id}
        if only_if_status:
            q["status"] = {"$in": only_if_status}
        r = await self.trips.update_one(q, {"$set": fields})
        return r.modified_count == 1

    async def list_trips(self, owner_id, limit=20):
        return await self.trips.find({"owner_id": owner_id}).sort("created_at", -1).to_list(limit)

    async def open_trips_for_owner(self, owner_id):
        return await self.trips.find({"owner_id": owner_id, "status": {"$in": OPEN_STATUSES}}).to_list(20)

    async def due_trips(self, now):
        return await self.trips.find({"status": "active", "alert_at": {"$lte": now}}).to_list(100)

    async def open_trip_by_phone(self, phone):
        return await self.trips.find_one(
            {"person_phone": phone, "status": {"$in": OPEN_STATUSES}}, sort=[("created_at", -1)]
        )

    async def log_alert(self, doc):
        await self.alerts.insert_one(doc)

    async def list_alerts(self, owner_id, limit=50):
        return await self.alerts.find({"owner_id": owner_id}).sort("created_at", -1).to_list(limit)

    async def update_alert_status(self, message_id, status):
        await self.alerts.update_one(
            {"results.message_id": message_id}, {"$set": {"results.$.delivery": status}}
        )


    # ---------- governance ----------
    async def audit_append(self, entry):
        await self.audit.insert_one(entry)

    async def audit_last(self):
        return await self.audit.find_one({}, sort=[("seq", -1)])

    async def audit_list(self, owner_id, limit):
        q = {} if owner_id is None else {"owner_id": owner_id}
        return await self.audit.find(q).sort("seq", -1).to_list(limit)

    async def audit_all(self):
        return await self.audit.find({}).sort("seq", 1).to_list(None)

    async def purge_before(self, cutoff):
        t = await self.trips.delete_many({"created_at": {"$lt": cutoff}, "status": {"$in": ["checked_in", "cancelled"]}})
        a = await self.alerts.delete_many({"created_at": {"$lt": cutoff}})
        return {"trips": t.deleted_count, "alerts": a.deleted_count}

    async def export_owner(self, owner_id):
        q = {"owner_id": owner_id}
        return {
            "contacts": await self.contacts.find(q).to_list(None),
            "trips": await self.trips.find(q).to_list(None),
            "alerts": await self.alerts.find(q).to_list(None),
        }

    async def erase_owner(self, owner_id):
        q = {"owner_id": owner_id}
        c = await self.contacts.delete_many(q)
        t = await self.trips.delete_many(q)
        a = await self.alerts.delete_many(q)
        return {"contacts": c.deleted_count, "trips": t.deleted_count, "alerts": a.deleted_count}


_store = None


def get_store():
    """The active store. Call init_store() once at startup."""
    global _store
    if _store is None:
        _store = MemoryStore()
    return _store


async def init_store():
    """Connect to MongoDB; if that fails, fall back to memory so the demo still runs."""
    global _store
    if settings.mongodb_uri:
        try:
            s = MongoStore(settings.mongodb_uri, settings.mongodb_db)
            await s.setup()
            _store = s
            return _store
        except Exception as e:
            log.error("MongoDB unavailable (%s). Falling back to in-memory store.", e)
    _store = MemoryStore()
    await _store.setup()
    return _store
