import jwt
from fastapi import Depends, HTTPException, Request, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.orm import Session

from app.config.logger import get_logger
from app.core.auth.security import decode_access_token
from app.db.database import get_db
from app.models.enums import RoleEnum
from app.models.user import User
from app.schemas.user import UserResponse

logger = get_logger(__name__)

reusable_oauth2 = OAuth2PasswordBearer(tokenUrl="/auth/login")


def get_current_user(
    request: Request,
    db: Session = Depends(get_db),
    token: str = Depends(reusable_oauth2),
) -> UserResponse:
    """Resolve the authenticated user from the Bearer token."""
    try:
        payload = decode_access_token(token)
        user_id = payload.get("sub")
        if user_id is None:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Could not validate credentials",
                headers={"WWW-Authenticate": "Bearer"},
            )
    except jwt.PyJWTError:
        logger.warning("Invalid or expired token presented")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Could not validate credentials",
            headers={"WWW-Authenticate": "Bearer"},
        )

    try:
        pk = int(user_id)
    except (TypeError, ValueError):
        pk = None

    user = db.get(User, pk) if pk is not None else None
    if user is None:
        logger.warning(f"Token references unknown user id={user_id}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User no longer exists",
            headers={"WWW-Authenticate": "Bearer"},
        )
    request.state.user_info = f"{user.mail} (id={user.id})"
    logger.debug(f"Authenticated request as {user.mail} (id={user.id}, role={user.role})")
    return UserResponse.model_validate(user)


class RoleChecker:
    """Dependency factory restricting access to the given roles."""

    def __init__(self, allowed_roles: list[RoleEnum]):
        self.allowed_roles = allowed_roles

    def __call__(self, user: UserResponse = Depends(get_current_user)) -> UserResponse:
        if user.role not in self.allowed_roles:
            logger.warning(
                f"Access denied for user={user.mail} role={user.role} "
                f"(allowed={[r.value for r in self.allowed_roles]})"
            )
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You do not have permission to perform this operation.",
            )
        return user


require_admin = RoleChecker([RoleEnum.ADMIN])
