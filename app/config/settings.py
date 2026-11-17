"""
Configuration management using pydantic-settings.
"""

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    # App Settings
    APP_NAME: str = "Fasly - Sunday School API"
    APP_VERSION: str = "1.0.0"
    APP_DESCRIPTION: str = (
        "Church Sunday school follow-up: boys, attendance, teachers, follow-ups."
    )
    CORS_ORIGINS: str = "*"

    HOST: str = "0.0.0.0"
    PORT: int = 9001

    # PostgreSQL
    DATABASE_URL: str

    # Auth / JWT
    SECRET_KEY: str = "change-me-in-production"
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60

    # Default tenant (created on startup if missing). Every seeded admin and
    # every legacy row is assigned to this church; the platform owner can add
    # more churches later from the /churches endpoints or in pgAdmin.
    DEFAULT_CHURCH_NAME: str = "الكنيسة الافتراضية"
    DEFAULT_CHURCH_REGION: str | None = None
    DEFAULT_CHURCH_ADDRESS: str | None = None
    DEFAULT_CHURCH_PHONE: str | None = None
    DEFAULT_CHURCH_PHONE_2: str | None = None

    # Bootstrap first Admin (created on startup if no Admin exists)
    ADMIN_PHONE: str | None = None
    ADMIN_PASSWORD: str | None = None

    # Extra church admins (أبونا), seeded on startup from a JSON array
    # (idempotent). Each entry becomes a servant and an ``abona`` login scoped
    # to one church. ``church_id`` (or ``church`` by name) picks the tenant;
    # missing values fall back to the default church above.
    #   [
    #     {"name": "كيرلس اشرف فخري", "phone": "01281875199",
    #      "church": "كنيسة الشهيد مار جرجس"},
    #     {"name": "مينا فوزي", "phone": "01000000000", "church_id": 2}
    #   ]
    SEED_SUPER_ADMINS_JSON: str | None = None

    # Web Push (إشعارات على تليفونات الخدام)
    # VAPID keys from scripts/make_vapid_keys.py. Without both, push stays off
    # and /notifications/vapid-key answers 503 so the app hides the banner.
    VAPID_PUBLIC_KEY: str | None = None
    VAPID_PRIVATE_KEY: str | None = None
    VAPID_CLAIMS_EMAIL: str | None = None
    # The church day: reminders fire in this zone, not the server's.
    PUSH_TIMEZONE: str = "Africa/Cairo"
    # Hour of the daily «افحص مجموعتك» reminder, 24h in PUSH_TIMEZONE.
    FOLLOW_UP_REMINDER_HOUR: int = 15
    # Hour of the birthday and Wednesday nudges; a birthday is news for the
    # morning, and a Wednesday needs telling before the evening meeting.
    BIRTHDAY_REMINDER_HOUR: int = 9
    WEDNESDAY_REMINDER_HOUR: int = 10

    model_config = SettingsConfigDict(
        env_file=".env", env_file_encoding="utf-8", case_sensitive=True, extra="ignore"
    )


# Create singleton instance
settings = Settings()


def get_settings():
    return settings
