from datetime import datetime, timedelta
from typing import Any, Union

import bcrypt
import jwt

from app.config.logger import get_logger
from app.config.settings import settings

logger = get_logger(__name__)


def get_password_hash(password: str) -> str:
    """Hash a plain-text password with a per-password salt."""
    salt = bcrypt.gensalt()
    return bcrypt.hashpw(password.encode("utf-8"), salt).decode("utf-8")


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verify a plain-text password against a bcrypt hash."""
    try:
        return bcrypt.checkpw(
            plain_password.encode("utf-8"), hashed_password.encode("utf-8")
        )
    except (ValueError, TypeError):
        return False


def create_access_token(subject: Union[str, Any], expires_delta: timedelta = None) -> str:
    """Create a signed JWT carrying the user id as `sub`."""
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(
            minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES
        )

    to_encode = {"exp": expire, "sub": str(subject)}
    encoded_jwt = jwt.encode(
        to_encode, settings.SECRET_KEY, algorithm=settings.ALGORITHM
    )
    logger.debug(f"Access token created for subject={subject}")
    return encoded_jwt


def decode_access_token(token: str) -> dict:
    """Decode and validate a JWT, returning its payload."""
    return jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
