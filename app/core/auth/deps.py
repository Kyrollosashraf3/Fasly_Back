from typing import List

import jwt
from fastapi import Depends, HTTPException, Request, status
from fastapi.security import OAuth2PasswordBearer

from app.config.logger import get_logger
from app.config.settings import settings
from app.core.auth.security import decode_access_token
from app.db.firebase import get_db
from app.models.enums import RoleEnum
from app.models.user import UserResponse

logger = get_logger(__name__)

reusable_oauth2 = OAuth2PasswordBearer(tokenUrl="/auth/login")


def _doc_to_user(doc_id: str, data: dict) -> UserResponse:
    """Build a safe user shape from a Firestore document."""
    kwargs: dict = {
        "id": doc_id,
        "user_name": data.get("user_name", ""),
        "mail": data.get("mail", ""),
        "phone": data.get("phone"),
        "role": data.get("role", RoleEnum.USER),
        "class_name": data.get("class_name"),
    }
    if data.get("created_at"):
        kwargs["created_at"] = data["created_at"]
    return UserResponse(**kwargs)


def get_current_user(
    request: Request,
    db=Depends(get_db),
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

    doc = db.collection(settings.COLLECTION_USER).document(str(user_id)).get()
    if not doc.exists:
        logger.warning(f"Token references unknown user id={user_id}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User no longer exists",
            headers={"WWW-Authenticate": "Bearer"},
        )
    user = _doc_to_user(doc.id, doc.to_dict())
    request.state.user_info = f"{user.mail} (id={user.id})"
    logger.debug(f"Authenticated request as {user.mail} (id={user.id}, role={user.role})")
    return user


class RoleChecker:
    """Dependency factory restricting access to the given roles."""

    def __init__(self, allowed_roles: List[RoleEnum]):
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
