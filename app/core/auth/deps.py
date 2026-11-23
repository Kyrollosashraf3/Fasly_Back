"""Who is calling - resolved once per request and handed to every service."""

import jwt
from fastapi import Depends, HTTPException, Request, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.orm import Session

from app.config.logger import get_logger
from app.core.auth.security import decode_access_token
from app.core.data.common import MANAGERS, ensure_roles
from app.db.database import get_db
from app.models.enums import RoleEnum
from app.features.user.models.user import User

logger = get_logger(__name__)

reusable_oauth2 = OAuth2PasswordBearer(tokenUrl="/auth/login")

_401 = {
    "detail": "Could not validate credentials",
    "headers": {"WWW-Authenticate": "Bearer"},
}


def _requested_church_id(request: Request) -> int | None:
    """The tenant the UI is currently looking at (``?church_id=`` or header).

    The header filter sends it on every request. Only the platform owner may
    use it to narrow his view; a tenant login is always pinned to its own
    church, so a stale value in localStorage is simply ignored instead of
    breaking the request.
    """
    raw = request.query_params.get("church_id") or request.headers.get("x-church-id")
    if raw is None or str(raw).strip() == "":
        return None
    try:
        return int(raw)
    except (TypeError, ValueError):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="church_id must be an integer.",
        ) from None


def get_current_user(
    request: Request,
    db: Session = Depends(get_db),
    token: str = Depends(reusable_oauth2),
) -> User:
    """The ORM row behind the Bearer token.

    Services receive the live ``User`` so ``role``, ``teacher_id`` and
    ``boy_id`` are always the truth in the database - not a copy that could
    go stale. When the platform owner has a church selected in the header,
    ``selected_church_id`` narrows every scoped read (see ``my_church_ids``).
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

    # The header's church picker is a view filter for the platform owner only.
    # A tenant login stays pinned to users.church_id, so a leftover value in
    # the browser cannot move him to another church.
    selected = _requested_church_id(request)
    if selected is not None and user.role == RoleEnum.SUPER_ADMIN:
        user.selected_church_id = selected

    # The logging middleware reads this back for the access log line.
    request.state.user_info = f"{user.phone} (id={user.id})"
    return user


def require_admin(current_user: User = Depends(get_current_user)) -> User:
    """Class amin or church-wide amin. Used by the few routes whose *whole*
    payload must be restricted before a service ever sees it."""
    ensure_roles(current_user, *MANAGERS)
    return current_user