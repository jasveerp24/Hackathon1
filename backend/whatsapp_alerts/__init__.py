"""Reusable WhatsApp family-alert module (Meta WhatsApp Cloud API + FastAPI)."""
from .router import alerts_lifespan, alerts_router
from .templates import AlertEvent

__all__ = ["alerts_router", "alerts_lifespan", "AlertEvent"]
