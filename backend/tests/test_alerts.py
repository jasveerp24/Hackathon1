"""Run: pytest -q   (no keys, no MongoDB, no network needed)"""
import hashlib
import hmac
import json
from datetime import datetime, timedelta, timezone

import httpx
import pytest
from fastapi.testclient import TestClient

from whatsapp_alerts import client as wa_client
from whatsapp_alerts.client import normalize_phone
from whatsapp_alerts.config import settings
from whatsapp_alerts.security import reset_rate_limits

KEY = "test-app-key"
SECRET = "test-app-secret"

OWNER = "fisher-1"


@pytest.fixture
def meta(monkeypatch):
    """Fake Meta Graph API. Records requests; set .fail_code to simulate an error."""
    state = {"requests": [], "fail_code": None}

    def handler(request: httpx.Request):
        body = json.loads(request.content)
        state["requests"].append({"url": str(request.url), "auth": request.headers["authorization"], "body": body})
        if state["fail_code"]:
            return httpx.Response(400, json={"error": {"code": state["fail_code"], "message": "fake error"}})
        return httpx.Response(200, json={"messages": [{"id": f"wamid.{len(state['requests'])}"}]})

    real = httpx.AsyncClient
    monkeypatch.setattr(wa_client.httpx, "AsyncClient", lambda **kw: real(transport=httpx.MockTransport(handler), **kw))
    monkeypatch.setattr(settings, "access_token", "test-token")
    monkeypatch.setattr(settings, "phone_number_id", "12345")
    monkeypatch.setattr(settings, "dry_run", False)
    monkeypatch.setattr(settings, "mongodb_uri", "")
    monkeypatch.setattr(settings, "webhook_verify_token", "verify-me")
    monkeypatch.setattr(settings, "app_secret", SECRET)
    monkeypatch.setattr(settings, "api_key", KEY)
    monkeypatch.setattr(settings, "enable_dev_routes", True)
    monkeypatch.setattr(settings, "rate_limit_per_user_per_minute", 10)
    monkeypatch.setattr(settings, "rate_limit_global_per_minute", 60)
    reset_rate_limits()
    return state


@pytest.fixture
def api(meta):
    from main import app

    with TestClient(app, headers={"X-Alerts-Key": KEY}) as c:
        yield c


def signed_post(api, payload: dict, secret: str = SECRET):
    raw = json.dumps(payload).encode()
    sig = "sha256=" + hmac.new(secret.encode(), raw, hashlib.sha256).hexdigest()
    return api.post("/api/alerts/webhook", content=raw,
                    headers={"Content-Type": "application/json", "X-Hub-Signature-256": sig})


def add_family(api):
    api.post("/api/alerts/contacts", json={"owner_id": OWNER, "name": "Priya", "phone": "5712 3456", "lang": "en", "consent": True})
    api.post("/api/alerts/contacts", json={"owner_id": OWNER, "name": "Jean", "phone": "+230 5798 0000", "lang": "fr", "consent": True})


def test_normalize_phone():
    assert normalize_phone("5712 3456") == "23057123456"
    assert normalize_phone("+230 5712-3456") == "23057123456"
    assert normalize_phone("0044 7700 900123") == "447700900123"


def test_trip_start_overdue_and_checkin(api, meta, monkeypatch):
    monkeypatch.setattr(settings, "use_templates", False)
    add_family(api)
    due = (datetime.now(timezone.utc) - timedelta(minutes=5)).isoformat()
    r = api.post("/api/alerts/trips", json={
        "owner_id": OWNER, "person_name": "Ravi", "plan": "Fishing off Le Morne, 2 km out",
        "due_at": due, "grace_minutes": 0, "person_phone": "5700 1111",
    }).json()
    trip_id = r["trip"]["id"]
    assert r["alert"]["sent"] == 2
    assert "Ravi" in meta["requests"][0]["body"]["text"]["body"]
    assert meta["requests"][0]["auth"] == "Bearer test-token"
    # French contact got French text
    fr = [q for q in meta["requests"] if q["body"]["to"] == "23057980000"][0]
    assert "est parti" in fr["body"]["text"]["body"]

    assert api.post("/api/alerts/dev/run-overdue-check").json() == {"alerted_trips": 1}
    assert api.post("/api/alerts/dev/run-overdue-check").json() == {"alerted_trips": 0}  # no double send
    assert "URGENT" in meta["requests"][2]["body"]["text"]["body"]

    # Ravi replies SAFE on WhatsApp -> checked in, family reassured
    wh = {"entry": [{"changes": [{"value": {"messages": [
        {"from": "23057001111", "type": "text", "text": {"body": "Safe"}}]}}]}]}
    assert signed_post(api, wh).status_code == 200
    trips = api.get("/api/alerts/trips", params={"owner_id": OWNER}).json()
    assert trips[0]["status"] == "checked_in"
    assert "checked in safely" in meta["requests"][-2]["body"]["text"]["body"] or \
           "checked in safely" in meta["requests"][-1]["body"]["text"]["body"]
    log = api.get("/api/alerts/log", params={"owner_id": OWNER}).json()
    assert [e["event"] for e in log] == ["checked_in", "missed_checkin", "trip_started"]


def test_template_payload_and_error_hint(api, meta, monkeypatch):
    monkeypatch.setattr(settings, "use_templates", True)
    add_family(api)
    meta["fail_code"] = 131030
    r = api.post("/api/alerts/sos", json={"owner_id": OWNER, "person_name": "Ravi", "lat": -20.45, "lng": 57.31}).json()
    assert r["failed"] == 2
    res = r["results"][0]
    assert "allowed list" in res["hint"]
    assert "maps.google.com" in res["text"]  # text kept for the wa.me fallback
    tpl = meta["requests"][0]["body"]["template"]
    assert tpl["name"] == "safety_sos"
    assert len(tpl["components"][0]["parameters"]) == 3


def test_webhook_verify(api):
    ok = api.get("/api/alerts/webhook", params={"hub.mode": "subscribe", "hub.verify_token": "verify-me", "hub.challenge": "42"})
    assert ok.text == "42"
    bad = api.get("/api/alerts/webhook", params={"hub.mode": "subscribe", "hub.verify_token": "nope", "hub.challenge": "42"})
    assert bad.status_code == 403


def test_dry_run_without_keys(api, meta, monkeypatch):
    monkeypatch.setattr(settings, "access_token", "")
    add_family(api)
    r = api.post("/api/alerts/hazard", json={"owner_id": OWNER, "person_name": "Ravi", "plan": "Le Morne",
                                              "warning": "High waves up to 3.5 m"}).json()
    assert r["sent"] == 2 and r["results"][0]["mode"] == "dry_run"
    assert meta["requests"] == []


def test_app_key_required(api):
    r = api.get("/api/alerts/status", headers={"X-Alerts-Key": "wrong"})
    assert r.status_code == 401
    r = api.post("/api/alerts/sos", json={"owner_id": OWNER, "person_name": "x"}, headers={"X-Alerts-Key": ""})
    assert r.status_code == 401
    assert api.get("/api/alerts/status").status_code == 200


def test_rate_limit(api, monkeypatch):
    monkeypatch.setattr(settings, "rate_limit_per_user_per_minute", 3)
    add_family(api)  # uses 2
    assert api.post("/api/alerts/sos", json={"owner_id": OWNER, "person_name": "Ravi"}).status_code == 200
    r = api.post("/api/alerts/sos", json={"owner_id": OWNER, "person_name": "Ravi"})
    assert r.status_code == 429
    # another user is not blocked
    assert api.post("/api/alerts/sos", json={"owner_id": "other", "person_name": "Ana"}).status_code == 200


def test_dev_route_can_be_switched_off(api, monkeypatch):
    monkeypatch.setattr(settings, "enable_dev_routes", False)
    assert api.post("/api/alerts/dev/run-overdue-check").status_code == 404


def test_webhook_rejects_unsigned_and_fake(api, meta):
    add_family(api)
    due = (datetime.now(timezone.utc) + timedelta(hours=2)).isoformat()
    api.post("/api/alerts/trips", json={"owner_id": OWNER, "person_name": "Ravi", "plan": "Blue Bay",
                                        "due_at": due, "person_phone": "5700 1111"})
    wh = {"entry": [{"changes": [{"value": {"messages": [
        {"from": "23057001111", "type": "text", "text": {"body": "SAFE"}}]}}]}]}
    assert api.post("/api/alerts/webhook", json=wh).status_code == 401          # no signature
    assert signed_post(api, wh, secret="attacker").status_code == 401           # wrong signature
    trips = api.get("/api/alerts/trips", params={"owner_id": OWNER}).json()
    assert trips[0]["status"] == "active"                                       # not checked in


def test_webhook_without_app_secret_ignores_safe_replies(api, monkeypatch):
    monkeypatch.setattr(settings, "app_secret", "")
    add_family(api)
    due = (datetime.now(timezone.utc) + timedelta(hours=2)).isoformat()
    api.post("/api/alerts/trips", json={"owner_id": OWNER, "person_name": "Ravi", "plan": "Blue Bay",
                                        "due_at": due, "person_phone": "5700 1111"})
    wh = {"entry": [{"changes": [{"value": {"messages": [
        {"from": "23057001111", "type": "text", "text": {"body": "SAFE"}}]}}]}]}
    assert api.post("/api/alerts/webhook", json=wh).status_code == 200
    trips = api.get("/api/alerts/trips", params={"owner_id": OWNER}).json()
    assert trips[0]["status"] == "active"


def test_rejects_too_long_phone(api):
    r = api.post("/api/alerts/contacts", json={"owner_id": OWNER, "name": "X", "phone": "+1234567890123456789", "consent": True})
    assert r.status_code == 422


# ---------- governance ----------
def test_consent_required_and_recorded(api):
    r = api.post("/api/alerts/contacts", json={"owner_id": OWNER, "name": "A", "phone": "57123456", "consent": False})
    assert r.status_code == 422
    add_family(api)
    exp = api.get("/api/alerts/privacy/export", params={"owner_id": OWNER}).json()
    assert exp["contacts"][0]["consent"]["version"]
    assert exp["contacts"][0]["phone"] == "23057123456"  # the user's own export is readable


def test_audit_chain_masks_phones_and_detects_tampering(api):
    from whatsapp_alerts.store import get_store

    add_family(api)
    api.post("/api/alerts/sos", json={"owner_id": OWNER, "person_name": "Ravi", "lat": -20.4, "lng": 57.3})
    api.get("/api/alerts/status", headers={"X-Alerts-Key": "wrong"})
    log = api.get("/api/alerts/governance/audit").json()
    actions = [e["action"] for e in log]
    assert actions[:4] == ["auth_failed", "sos", "contact_added", "contact_added"]
    text = json.dumps(log)
    assert "23057123456" not in text and "2305****456" in text   # masked
    assert "-20.4" not in text                                   # no GPS in audit
    assert api.get("/api/alerts/governance/audit/verify").json()["ok"] is True
    get_store().audit[1]["details"]["sent"] = 99                 # tamper with entry 2
    v = api.get("/api/alerts/governance/audit/verify").json()
    assert v == {"ok": False, "entries": 4, "broken_at_seq": 2}


def test_erase_and_retention(api):
    from datetime import datetime, timedelta, timezone
    from whatsapp_alerts.store import get_store

    add_family(api)
    due = (datetime.now(timezone.utc) + timedelta(hours=1)).isoformat()
    tid = api.post("/api/alerts/trips", json={"owner_id": OWNER, "person_name": "Ravi", "plan": "x",
                                              "due_at": due}).json()["trip"]["id"]
    api.post(f"/api/alerts/trips/{tid}/checkin")
    # age everything by 40 days -> retention (30 days) removes closed trip + alerts, keeps contacts
    old = datetime.now(timezone.utc) - timedelta(days=40)
    st = get_store()
    for t in st.trips.values():
        t["created_at"] = old
    for a in st.alerts:
        a["created_at"] = old
    assert api.post("/api/alerts/governance/run-retention").json() == {"trips": 1, "alerts": 2}
    assert len(api.get("/api/alerts/contacts", params={"owner_id": OWNER}).json()) == 2

    assert api.delete("/api/alerts/privacy/erase", params={"owner_id": OWNER}).status_code == 400
    r = api.delete("/api/alerts/privacy/erase", params={"owner_id": OWNER, "confirm": "true"}).json()
    assert r["erased"]["contacts"] == 2
    assert api.get("/api/alerts/contacts", params={"owner_id": OWNER}).json() == []
    actions = [e["action"] for e in api.get("/api/alerts/governance/audit").json()]
    assert actions[0] == "data_erased" and "retention_purge" in actions
    assert api.get("/api/alerts/governance/audit/verify").json()["ok"] is True


def test_custom_alert_any_theme(api, meta, monkeypatch):
    monkeypatch.setattr(settings, "use_templates", True)
    monkeypatch.setattr(settings, "app_name", "Granmoun Check-in")
    add_family(api)
    r = api.post("/api/alerts/send", json={"owner_id": OWNER, "event": "custom",
                                           "values": {"person": "Mamie Lise", "message": "Missed the morning medication"}}).json()
    assert r["sent"] == 2
    assert "Sent by the Granmoun Check-in app" in r["results"][0]["text"]
    tpl = meta["requests"][0]["body"]["template"]
    assert tpl["name"] == "safety_custom_alert"
    assert [p["text"] for p in tpl["components"][0]["parameters"]] == ["Mamie Lise", "Missed the morning medication", "Granmoun Check-in"]


def test_unapproved_language_falls_back_to_english_template(api, meta, monkeypatch):
    monkeypatch.setattr(settings, "use_templates", True)
    monkeypatch.setattr(settings, "template_langs", ("en",))
    add_family(api)  # one EN and one FR contact
    r = api.post("/api/alerts/sos", json={"owner_id": OWNER, "person_name": "Ravi", "location_text": "Blue Bay"}).json()
    assert r["sent"] == 2
    assert {q["body"]["template"]["language"]["code"] for q in meta["requests"]} == {"en"}
    assert all(res["text"].startswith("SOS: Ravi") for res in r["results"])
    # With French approved too, the French contact gets the French template.
    meta["requests"].clear()
    monkeypatch.setattr(settings, "template_langs", ("en", "fr"))
    api.post("/api/alerts/sos", json={"owner_id": OWNER, "person_name": "Ravi", "location_text": "Blue Bay"})
    assert {q["body"]["template"]["language"]["code"] for q in meta["requests"]} == {"en", "fr"}
