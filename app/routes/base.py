"""Service meta endpoints - who the API is and whether it is alive."""

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.config import settings
from app.core.auth.deps import get_current_user
from app.features.seed.services import SeedService
from app.db.database import get_db
from app.features.user.models.user import User

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


@router.post("/seed", include_in_schema=True)
def seed_demo_data(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Create idempotent demo data for exactly two isolated churches."""
    return SeedService(db, current_user).seed()