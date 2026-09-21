"""Rate limiting foundation built on top of slowapi.

"""

from slowapi import Limiter
from slowapi.errors import RateLimitExceeded
from slowapi.util import get_remote_address
from fastapi import Request
from fastapi.responses import JSONResponse


# Shared limiter instance tracking requests by remote IP address.
limiter = Limiter(key_func=get_remote_address)

# --- Login limits -----------------------------------------------------
# Per-IP: max attempts on the login endpoint from one client address.
LOGIN_IP_LIMIT = "5 per minute"
# Per-account: max attempts targeting a single e-mail, regardless of source
# IP. This is the "account lockout" layer that stops a distributed brute-force
# against one account, while the per-IP layer already throttles a single host.
LOGIN_EMAIL_LIMIT = "10 per hour"


def login_email_key(request: Request) -> str:
    """Rate-limit key for the account layer: the submitted e-mail address.

    Keyed purely on the e-mail so the limit follows the account regardless of
    which IP address the attempts come from.
    """
    email = ""
    # The login endpoint is a sync route that depends on
    # OAuth2PasswordRequestForm, so the parsed form is already cached on the
    # request by the time the limiter key is evaluated.
    form = getattr(request, "_form", None)
    if form is not None:
        email = str(form.get("username", "") or "").strip().lower()
    return email or get_remote_address(request)


async def rate_limit_exceeded_handler(
    request: Request, exc: Exception
) -> JSONResponse:
    """Return a clean JSON response when a client exceeds a rate limit."""
    if isinstance(exc, RateLimitExceeded):
        return JSONResponse(
            status_code=429,
            content={
                "detail": "Too many requests. Please try again later.",
                "limit": str(getattr(exc, "limit", "")),
            },
            headers={"Retry-After": str(getattr(exc, "retry_after", ""))},
        )
    return JSONResponse(status_code=500, content={"detail": "Internal error"})


__all__ = [
    "limiter",
    "rate_limit_exceeded_handler",
    "login_email_key",
    "LOGIN_IP_LIMIT",
    "LOGIN_EMAIL_LIMIT",
]
