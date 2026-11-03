"""The VAPID pair: how a push service knows the server is allowed to send.

Generated once with ``python scripts/make_vapid_keys.py`` and kept in ``.env``.
Only the public half ever reaches a browser.
"""

import base64

from cryptography.hazmat.primitives.serialization import load_pem_private_key

from app.config import settings


def push_enabled() -> bool:
    """Push is off until both halves of the pair are configured."""
    return bool(settings.VAPID_PUBLIC_KEY and settings.VAPID_PRIVATE_KEY)


def vapid_public_key() -> str:
    return settings.VAPID_PUBLIC_KEY or ""


def vapid_private_key() -> str:
    """The private half in the only form pywebpush can read.

    ``py_vapid`` parses a key string as the raw 32-byte scalar - or as DER - and
    never as PEM, so the PEM that ``make_vapid_keys.py`` prints is unwrapped
    here. A value already in raw form passes through untouched.

    ``.env`` holds a PEM on one line with ``\\n`` escapes, because a real
    multi-line value would be cut at its first newline by dotenv parsing.
    """
    raw = (settings.VAPID_PRIVATE_KEY or "").replace("\\n", "\n")
    if "-----BEGIN" not in raw:
        return raw.strip()

    key = load_pem_private_key(raw.encode(), password=None)
    scalar = key.private_numbers().private_value.to_bytes(32, "big")
    return base64.urlsafe_b64encode(scalar).decode().rstrip("=")


def claims() -> dict:
    """The VAPID ``sub`` claim: a contact the push service can reach if we abuse it."""
    return {"sub": settings.VAPID_CLAIMS_EMAIL or "mailto:admin@fasly.app"}
