"""Service meta endpoints - who the API is and whether it is alive."""

from fastapi import APIRouter

from app.config import settings

router = APIRouter(tags=["Meta"])


@router.get("/", include_in_schema=False)
def root() -> dict:
    """The API's front door: where things are."""
    return {
        "app": settings.APP_NAME,
        "version": settings.APP_VERSION,
        "docs": "/docs",
    }


@router.get("/health", include_in_schema=False)
def health() -> dict:
    """Unauthenticated liveness probe."""
    return {"status": "ok"}