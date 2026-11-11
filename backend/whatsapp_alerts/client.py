"""Thin client for the Meta WhatsApp Cloud API. Never raises: always returns a result dict."""
import logging
import re

import httpx

from .config import settings
from .templates import LANG_CODES, TEMPLATES, AlertEvent, ordered_params, render_text

log = logging.getLogger("whatsapp_alerts")

# Common Meta error codes -> a hint you can act on during the hackathon.
ERROR_HINTS = {
    190: "Access token expired or invalid. Temporary tokens last ~24h: create a System User token.",
    131030: "Recipient is not in the test number's allowed list. Add it in Meta > WhatsApp > API Setup.",
    131047: "More than 24h since this person messaged you. Use an approved template (WA_USE_TEMPLATES=true).",
    131026: "Message undeliverable: the number may not be on WhatsApp.",
    132001: "Template name/language not found or not approved yet in WhatsApp Manager.",
    132000: "Template parameter count does not match the approved template.",
    131056: "Too many messages to this number too quickly. Wait a little.",
    100: "Invalid parameter (often a wrong phone number id or bad phone format).",
}


def normalize_phone(raw: str, default_cc: str | None = None) -> str:
    """Return digits only in international format, e.g. '5 712 3456' -> '23057123456'."""
    cc = default_cc or settings.default_country_code
    s = (raw or "").strip()
    digits = re.sub(r"\D", "", s)
    if s.startswith("00"):
        digits = digits[2:]
    elif not s.startswith("+") and cc and len(digits) <= 8:
        # Local Mauritian number (8 digits mobile, 7 digits landline).
        digits = cc + digits
    return digits


def _url() -> str:
    return f"{settings.api_base}/{settings.api_version}/{settings.phone_number_id}/messages"


def _payload(to: str, event: AlertEvent, lang: str, values: dict) -> dict:
    lang = lang if lang in LANG_CODES else "en"
    if settings.use_templates:
        return {
            "messaging_product": "whatsapp",
            "to": to,
            "type": "template",
            "template": {
                "name": TEMPLATES[event]["name"],
                "language": {"code": LANG_CODES[lang]},
                "components": [
                    {
                        "type": "body",
                        "parameters": [{"type": "text", "text": v} for v in ordered_params(event, values)],
                    }
                ],
            },
        }
    return {
        "messaging_product": "whatsapp",
        "to": to,
        "type": "text",
        "text": {"preview_url": True, "body": render_text(event, lang, values)},
    }


async def send_alert(to_raw: str, event: AlertEvent, lang: str, values: dict) -> dict:
    to = normalize_phone(to_raw)
    if settings.use_templates and lang not in settings.template_langs:
        lang = "en"  # no approved template in this language: send the English one instead of failing (132001)
    text = render_text(event, lang, values)
    base = {"to": to, "event": event.value, "lang": lang, "text": text}

    if not to or not (8 <= len(to) <= 15):  # E.164: max 15 digits
        return {**base, "ok": False, "mode": "invalid", "error": "Invalid phone number"}

    if settings.effective_dry_run:
        from .governance import mask_phone

        log.info("[DRY RUN] WhatsApp to %s (%s)", mask_phone(to), event.value)
        return {**base, "ok": True, "mode": "dry_run", "message_id": None}

    mode = "template" if settings.use_templates else "text"
    try:
        async with httpx.AsyncClient(timeout=10) as http:
            r = await http.post(
                _url(),
                headers={"Authorization": f"Bearer {settings.access_token}"},
                json=_payload(to, event, lang, values),
            )
        data = r.json() if r.content else {}
    except Exception as e:  # network down, DNS, timeout...
        log.warning("WhatsApp send failed (network): %s", e)
        return {**base, "ok": False, "mode": mode, "error": f"Network error: {e}"}

    if r.status_code == 200 and data.get("messages"):
        return {**base, "ok": True, "mode": mode, "message_id": data["messages"][0].get("id")}

    err = data.get("error", {}) if isinstance(data, dict) else {}
    code = err.get("code")
    msg = err.get("message") or f"HTTP {r.status_code}"
    hint = ERROR_HINTS.get(code, "")
    log.warning("WhatsApp send failed (%s): %s %s", code, msg, hint)  # no phone/text in logs
    return {**base, "ok": False, "mode": mode, "error": msg, "error_code": code, "hint": hint}
