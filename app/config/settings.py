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

    # Bootstrap first Admin (created on startup if no Admin exists)
    ADMIN_MAIL: str | None = None
    ADMIN_PASSWORD: str | None = None
    ADMIN_USER_NAME: str = "Admin"

    model_config = SettingsConfigDict(
        env_file=".env", env_file_encoding="utf-8", case_sensitive=True, extra="ignore"
    )


# Create singleton instance
settings = Settings()


def get_settings():
    return settings
