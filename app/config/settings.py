from pathlib import Path
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    APP_NAME: str = "Fasly - Sunday School API"
    APP_VERSION: str = "1.0.0"
    APP_DESCRIPTION: str = "Church Sunday school follow-up: boys, attendance, teachers, follow-ups."
    CORS_ORIGINS: str = "*"

    SECRET_KEY: str = "change-me-in-production"
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60

    ADMIN_MAIL: str | None = None
    ADMIN_PASSWORD: str | None = None
    ADMIN_USER_NAME: str = "Admin"

    FIREBASE_CREDENTIALS: str

    COLLECTION_USER: str
    COLLECTION_BOY: str
    COLLECTION_TEACHER: str
    COLLECTION_ATTEND: str
    COLLECTION_FOLLOWUP: str
    COLLECTION_TEACHER_CHECK: str

    @property
    def ALL_COLLECTIONS(self) -> list[str]:
        """Every Firestore collection the app uses — checked at startup."""
        return [
            self.COLLECTION_USER,
            self.COLLECTION_BOY,
            self.COLLECTION_TEACHER,
            self.COLLECTION_ATTEND,
            self.COLLECTION_FOLLOWUP,
            self.COLLECTION_TEACHER_CHECK,
        ]

    @property
    def CREDENTIALS_PATH(self) -> Path:
        return Path(self.FIREBASE_CREDENTIALS)

    @property
    def SERVICE_ACCOUNT(self) -> dict | None:
        if not self.FIREBASE_CREDENTIALS:
            return None

        import json

        with open(self.CREDENTIALS_PATH, "r", encoding="utf-8") as f:
            return json.load(f)

    class Config:
        env_file = ".env"


settings = Settings()

def get_settings():
    return settings