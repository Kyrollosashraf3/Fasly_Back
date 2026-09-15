"""routes package - each file groups related endpoints."""

from .attend import router
from .auth import router as auth_router

__all__ = ["router", "auth_router"]
