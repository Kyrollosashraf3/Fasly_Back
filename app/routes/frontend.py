from pathlib import Path

from fastapi import APIRouter

STATIC_DIR = Path(__file__).resolve().parent.parent / "static"

router = APIRouter(tags=["frontend"])


@router.get("/app", include_in_schema=False)
def serve_frontend():
    pass
