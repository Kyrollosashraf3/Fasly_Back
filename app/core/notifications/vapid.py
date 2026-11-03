"""The VAPID pair: how a push service knows the server is allowed to send.

Generated once with ``python scripts/make_vapid_keys.py`` and kept in ``.env``.
Only the public half ever reaches a browser.
"""

from app.config import settings


def push_enabled() -> bool:
    """Push is off until both halves of the pair are configured."""
    return bool(settings.VAPID_PUBLIC_KEY and settings.VAPID_PRIVATE_KEY)


def vapid_public_key() -> str:
    return settings.VAPID_PUBLIC_KEY or ""


def vapid_private_key_pem() -> str:
    """The private half as PEM.

    ``.env`` holds it on one line with ``\\n`` escapes - a real multi-line PEM
    would be cut at its first newline by dotenv parsing - so unescape here. A
    key mounted from a file still arrives as a plain PEM and passes through.
    """
    raw = settings.VAPID_PRIVATE_KEY or ""
    return raw.replace("\\n", "\n")


def claims() -> dict:
    """The VAPID ``sub`` claim: a contact the push service can reach if we abuse it."""
    return {"sub": settings.VAPID_CLAIMS_EMAIL or "mailto:admin@fasly.app"}
