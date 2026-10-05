"""Who is calling - resolved once per request and handed to every service."""

import jwt
from fastapi import Depends, HTTPException, Request, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.orm import Session

from app.config.logger import get_logger
from app.core.auth.security import decode_access_token
from app.core.data.common import MANAGERS, ensure_roles
from app.db.database import get_db
from app.models.user import User

logger = get_logger(__name__)

reusable_oauth2 = OAuth2PasswordBearer(tokenUrl="/auth/login")

_401 = {
    "detail": "Could not validate credentials",
    "headers": {"WWW-Authenticate": "Bearer"},
}


def get_current_user(
    request: Request,
    db: Session = Depends(get_db),
    token: str = Depends(reusable_oauth2),
) -> User:
    """The ORM row behind the Bearer token.

    Services receive the live ``User`` so ``role``, ``teacher_id`` and
    ``boy_id`` are always the truth in the database - not a copy that could
    go stale.
    """
    try:
        user_id = decode_access_token(token).get("sub")
    except jwt.PyJWTError:
        logger.warning("Invalid or expired token presented")
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, **_401) from None
    if user_id is None:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, **_401)

    try:
        user = db.get(User, int(user_id))
    except (TypeError, ValueError):
        user = None
    if user is None:
        logger.warning("Token references unknown user id=%s", user_id)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User no longer exists",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # The logging middleware reads this back for the access log line.
    request.state.user_info = f"{user.phone} (id={user.id})"
    return user


def require_admin(current_user: User = Depends(get_current_user)) -> User:
    """Class amin or church-wide amin. Used by the few routes whose *whole*
    payload must be restricted before a service ever sees it."""
    ensure_roles(current_user, *MANAGERS)
    return current_user