"""Message wording for every alert, in English and French.

Each event has:
  * a Meta template name (create it in WhatsApp Manager with the SAME name and
    the body text below, once in English "en" and once in French "fr");
  * the ordered list of parameters that fill {{1}}, {{2}}, ...

The same text is used for plain-text sends and for the free wa.me fallback,
so what the family reads is identical whichever path delivers it.
Wording is generic ("activity", not "fishing") so any theme can reuse it.
CUSTOM lets a theme send its own short text (flood warning, scam alert, health
reminder...) inside one approved template, so no new Meta approval is needed.
"""
from enum import Enum


class AlertEvent(str, Enum):
    TRIP_STARTED = "trip_started"
    MISSED_CHECKIN = "missed_checkin"
    SOS = "sos"
    HAZARD_WARNING = "hazard_warning"
    CHECKED_IN = "checked_in"
    CUSTOM = "custom"  # any theme: your own short alert text


# Meta language codes. Make sure the template in WhatsApp Manager uses these.
LANG_CODES = {"en": "en", "fr": "fr"}

TEMPLATES: dict[AlertEvent, dict] = {
    AlertEvent.TRIP_STARTED: {
        "name": "safety_trip_started",
        "params": ["person", "plan", "due_time"],
        "en": (
            "Safety alert: {{1}} has started: {{2}}. Expected back by {{3}}. "
            "You will get a WhatsApp alert if they do not check in on time."
        ),
        "fr": (
            "Alerte sécurité : {{1}} est parti(e) : {{2}}. Retour prévu avant {{3}}. "
            "Vous recevrez une alerte WhatsApp si le retour n'est pas confirmé à temps."
        ),
    },
    AlertEvent.MISSED_CHECKIN: {
        "name": "safety_missed_checkin",
        "params": ["person", "plan", "due_time", "emergency_number"],
        "en": (
            "URGENT: {{1}} has not checked in. Plan: {{2}}. They were due back by {{3}}. "
            "Please call them now. If you cannot reach them, call {{4}} for help."
        ),
        "fr": (
            "URGENT : {{1}} n'a pas confirmé son retour. Prévu : {{2}}. Retour prévu avant {{3}}. "
            "Appelez-le/la maintenant. Si vous n'arrivez pas à le/la joindre, appelez le {{4}} pour obtenir de l'aide."
        ),
    },
    AlertEvent.SOS: {
        "name": "safety_sos",
        "params": ["person", "location", "emergency_number"],
        "en": (
            "SOS: {{1}} pressed the emergency button. Last location: {{2}}. "
            "Call them now and call {{3}} if needed."
        ),
        "fr": (
            "SOS : {{1}} a appuyé sur le bouton d'urgence. Dernière position : {{2}}. "
            "Appelez-le/la maintenant et appelez le {{3}} si nécessaire."
        ),
    },
    AlertEvent.HAZARD_WARNING: {
        "name": "safety_hazard_warning",
        "params": ["person", "plan", "warning"],
        "en": "Safety warning for {{1}} ({{2}}): {{3}}. Please check on them.",
        "fr": "Avertissement sécurité pour {{1}} ({{2}}) : {{3}}. Merci de prendre de ses nouvelles.",
    },
    AlertEvent.CHECKED_IN: {
        "name": "safety_checked_in",
        "params": ["person", "time"],
        "en": "Good news: {{1}} checked in safely at {{2}}. No action needed.",
        "fr": "Bonne nouvelle : {{1}} a confirmé son retour à {{2}}. Aucune action nécessaire.",
    },
    AlertEvent.CUSTOM: {
        "name": "safety_custom_alert",
        "params": ["person", "message", "app_name"],
        "en": "Safety alert about {{1}}: {{2}}. Sent by the {{3}} app. Please contact them if you are worried.",
        "fr": (
            "Alerte sécurité concernant {{1}} : {{2}}. Envoyé par l'application {{3}}. "
            "Contactez-le/la si vous êtes inquiet."
        ),
    },
}


def ordered_params(event: AlertEvent, values: dict[str, str]) -> list[str]:
    """Return the parameter values in template order. Missing ones become '-'."""
    out = []
    for key in TEMPLATES[event]["params"]:
        v = str(values.get(key, "") or "").strip()
        # Meta rejects empty params and params containing newlines/tabs or 4+ spaces.
        v = " ".join(v.split()) or "-"
        out.append(v[:900])
    return out


def render_text(event: AlertEvent, lang: str, values: dict[str, str]) -> str:
    """Fill the template body locally (plain-text sends and wa.me fallback)."""
    lang = lang if lang in LANG_CODES else "en"
    text = TEMPLATES[event][lang]
    for i, v in enumerate(ordered_params(event, values), start=1):
        text = text.replace("{{%d}}" % i, v)
    return text
