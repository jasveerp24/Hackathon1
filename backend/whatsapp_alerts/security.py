"""Light security for a hackathon backend.

1. App key: every /api/alerts request must send header `X-Alerts-Key` matching ALERTS_API_KEY.
   Note: a key shipped in a web app's JavaScript can be read by anyone who opens the app.
   It stops random people/bots who find the URL, it is NOT a real login. Add proper
   user login (e.g. JWT) if the team builds one, and take owner_id from it.
2. Rate limits: per user and global, so nobody can spam families or burn the Meta quota.
3. Webhook signature check: helper used by the router.
"""
import hashlib
import hmac
import time
from collections import defaultdict, deque

from fastapi import Header, HTTPException, Request

from .config import settings


async def require_app_key(request: Request, x_alerts_key: str | None = Header(default=None)):
    if not settings.api_key:
        return  # no key configured -> open (local dev only; a warning is logged at startup)
    if not x_alerts_key or not hmac.compare_digest(x_alerts_key, settings.api_key):
        from .governance import audit

        await audit("auth_failed", None, actor_of(request), {"path": request.url.path}, outcome="denied")
        raise HTTPException(401, "Missing or wrong app key")


def actor_of(request: Request) -> str:
    return f"api:{request.client.host if request.client else 'unknown'}"


class _Window:
    """Sliding 60-second window counter, in memory (fine for one backend process)."""

    def __init__(self):
        self.hits: dict[str, deque] = defaultdict(deque)

    def allow(self, key: str, limit: int, now: float) -> bool:
        q = self.hits[key]
        while q and now - q[0] > 60:
            q.popleft()
        if len(q) >= limit:
            return False
        q.append(now)
        return True

    def reset(self):
        self.hits.clear()


_window = _Window()


def check_rate(owner_id: str):
    """Call before any user-triggered action that sends WhatsApp messages or adds contacts."""
    now = time.monotonic()
    if not _window.allow("__global__", settings.rate_limit_global_per_minute, now):
        raise HTTPException(429, "Too many alerts right now. Wait a minute and try again.")
    if not _window.allow(f"owner:{owner_id}", settings.rate_limit_per_user_per_minute, now):
        raise HTTPException(429, "Too many alerts from this user. Wait a minute and try again.")


def reset_rate_limits():
    _window.reset()


def valid_meta_signature(raw: bytes, header: str) -> bool:
    if not settings.app_secret:
        return False
    expected = "sha256=" + hmac.new(settings.app_secret.encode(), raw, hashlib.sha256).hexdigest()
    return hmac.compare_digest(header or "", expected)
