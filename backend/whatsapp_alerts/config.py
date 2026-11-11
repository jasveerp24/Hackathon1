"""Settings for the WhatsApp alerts module, read from environment variables (.env)."""
import os
from dataclasses import dataclass, field

from dotenv import load_dotenv

load_dotenv()


def _bool(name: str, default: bool) -> bool:
    return os.getenv(name, str(default)).strip().lower() in ("1", "true", "yes", "on")


@dataclass
class Settings:
    # --- Meta WhatsApp Cloud API ---
    access_token: str = field(default_factory=lambda: os.getenv("WA_ACCESS_TOKEN", ""))
    phone_number_id: str = field(default_factory=lambda: os.getenv("WA_PHONE_NUMBER_ID", ""))
    api_version: str = field(default_factory=lambda: os.getenv("WA_API_VERSION", "v21.0"))
    api_base: str = field(default_factory=lambda: os.getenv("WA_API_BASE", "https://graph.facebook.com"))
    # Token you invent; paste the same value into Meta's webhook settings.
    webhook_verify_token: str = field(default_factory=lambda: os.getenv("WA_WEBHOOK_VERIFY_TOKEN", ""))
    # Optional: App Secret (Meta app > Settings > Basic) to verify webhook signatures.
    app_secret: str = field(default_factory=lambda: os.getenv("WA_APP_SECRET", ""))
    # true  = send approved templates (works any time, needs Meta approval)
    # false = send plain text (only delivered if the family member messaged the
    #         business number in the last 24 h; good for testing before approval)
    use_templates: bool = field(default_factory=lambda: _bool("WA_USE_TEMPLATES", False))
    # Languages whose templates are APPROVED in WhatsApp Manager. Others fall back to English in template mode.
    template_langs: tuple = field(
        default_factory=lambda: tuple(
            x.strip().lower() for x in os.getenv("WA_TEMPLATE_LANGS", "en").split(",") if x.strip()
        )
    )
    # true = never call Meta, just log what would be sent (safe default with no keys)
    dry_run: bool = field(default_factory=lambda: _bool("WA_DRY_RUN", False))

    # --- App behaviour ---
    mongodb_uri: str = field(default_factory=lambda: os.getenv("MONGODB_URI", ""))
    mongodb_db: str = field(default_factory=lambda: os.getenv("MONGODB_DB", "hackathon"))
    timezone: str = field(default_factory=lambda: os.getenv("ALERTS_TIMEZONE", "Indian/Mauritius"))
    default_country_code: str = field(default_factory=lambda: os.getenv("ALERTS_DEFAULT_COUNTRY_CODE", "230"))
    grace_minutes: int = field(default_factory=lambda: int(os.getenv("ALERTS_GRACE_MINUTES", "30")))
    scheduler_interval_seconds: int = field(
        default_factory=lambda: int(os.getenv("ALERTS_SCHEDULER_INTERVAL_SECONDS", "30"))
    )
    # Shown in the custom alert ("Sent by the ... app"); set it to the day's app name.
    app_name: str = field(default_factory=lambda: os.getenv("ALERTS_APP_NAME", "Safe Check-in"))
    emergency_number: str = field(default_factory=lambda: os.getenv("ALERTS_EMERGENCY_NUMBER", "999"))
    # --- Security ---
    # Shared app key; the frontend sends it as X-Alerts-Key. Empty = no check (local dev only).
    api_key: str = field(default_factory=lambda: os.getenv("ALERTS_API_KEY", ""))
    rate_limit_per_user_per_minute: int = field(
        default_factory=lambda: int(os.getenv("ALERTS_RATE_LIMIT_PER_USER_PER_MINUTE", "10"))
    )
    rate_limit_global_per_minute: int = field(
        default_factory=lambda: int(os.getenv("ALERTS_RATE_LIMIT_GLOBAL_PER_MINUTE", "60"))
    )
    # The "Run missed check-in check now" demo route. Turn off after the demo.
    enable_dev_routes: bool = field(default_factory=lambda: _bool("ALERTS_ENABLE_DEV_ROUTES", False))
    # --- Governance ---
    # Closed trips and alert logs older than this are deleted automatically.
    retention_days: int = field(default_factory=lambda: int(os.getenv("ALERTS_RETENTION_DAYS", "30")))
    frontend_origin: str = field(default_factory=lambda: os.getenv("FRONTEND_ORIGIN", "http://localhost:5173"))

    @property
    def is_configured(self) -> bool:
        return bool(self.access_token and self.phone_number_id)

    @property
    def effective_dry_run(self) -> bool:
        # No keys -> dry run automatically, so the demo never crashes.
        return self.dry_run or not self.is_configured


settings = Settings()
