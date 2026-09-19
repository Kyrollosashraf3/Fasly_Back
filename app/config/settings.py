from pathlib import Path
from pydantic_settings import BaseSettings


def _parse_service_account_json(raw: str) -> dict | None:
    """Parse a service-account JSON string into a dict.

    Handles the two formats you get from hosting providers (Render, etc.):
    1. Raw JSON pasted as-is.
    2. JSON where newlines inside private_key were escaped twice (\\n).
    Returns None if parsing fails.
    """
    import json

    text = (raw or "").strip().strip("'\"")
    if not text.startswith("{"):
        return None
    try:
        data = json.loads(text)
    except ValueError:
        return None
    if isinstance(data.get("private_key"), str):
        # Render env vars often store "\n" as literal "\\n" — restore real newlines.
        data["private_key"] = data["private_key"].replace("\\n", "\n")
    return data if data.get("client_email") else None


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

    # Local dev: path to the service-account file, e.g. ./test.json
    # Render/prod: either paste the whole JSON here, or use
    # FIREBASE_CREDENTIALS_JSON with the whole JSON.
    FIREBASE_CREDENTIALS: str = "./test.json"
    # Preferred on hosting: full service-account JSON as one env var.
    FIREBASE_CREDENTIALS_JSON: str | None = None

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
    def CREDENTIALS_PATH(self) -> Path | None:
        """Filesystem path when FIREBASE_CREDENTIALS points to a file, else None."""
        raw = (self.FIREBASE_CREDENTIALS or "").strip()
        if not raw or raw.startswith("{"):
            return None
        return Path(raw)

    @property
    def SERVICE_ACCOUNT(self) -> dict | None:
        """Service-account dict from env var (Render) or file (local).

        Priority:
        1. FIREBASE_CREDENTIALS_JSON env var (Render — recommended).
        2. FIREBASE_CREDENTIALS containing inline JSON.
        3. FIREBASE_CREDENTIALS as a file path (local dev, ./test.json).
        """
        import json

        if self.FIREBASE_CREDENTIALS_JSON:
            parsed = _parse_service_account_json(self.FIREBASE_CREDENTIALS_JSON)
            if parsed is not None:
                return parsed

        raw = (self.FIREBASE_CREDENTIALS or "").strip()
        if raw.startswith("{"):
            parsed = _parse_service_account_json(raw)
            if parsed is not None:
                return parsed

        path = self.CREDENTIALS_PATH
        if path is not None and path.is_file():
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
            if isinstance(data.get("private_key"), str):
                data["private_key"] = data["private_key"].replace("\\n", "\n")
            return data

        return None

    class Config:
        env_file = ".env"


settings = Settings()

def get_settings():
    return settings