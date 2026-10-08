"""Authentication: password hashing, the Bearer token and the request-scoped
identity that every route depends on."""

from app.core.auth.bootstrap import (
    ensure_bootstrap_admin,
    ensure_default_classes,
    ensure_seeded_super_admins,
)
from app.core.auth.deps import get_current_user, require_admin
from app.core.auth.security import (
    create_access_token,
    decode_access_token,
    get_password_hash,
    verify_password,
)

__all__ = [
    "create_access_token",
    "decode_access_token",
    "get_password_hash",
    "verify_password",
    "get_current_user",
    "require_admin",
    "ensure_bootstrap_admin",
    "ensure_default_classes",
    "ensure_seeded_super_admins",
]