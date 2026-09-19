"""frontend.py - Serves the bundled frontend (static SPA) under /app.

The whole frontend (HTML/CSS/JS) lives in app/static/ (moved from the old
front_fasly folder so backend + frontend ship as ONE repo / one server).
The SPA uses hash routing (#/login, #/home, ...), so no server-side
fallback is needed — StaticFiles with html=True serves index.html.
"""

from pathlib import Path

from fastapi import APIRouter
from fastapi.responses import FileResponse

STATIC_DIR = Path(__file__).resolve().parent.parent / "static"

router = APIRouter(tags=["frontend"])


@router.get("/app", include_in_schema=False)
def serve_frontend():
    """Root of the frontend app -> index.html (the real UI entry)."""
    return FileResponse(STATIC_DIR / "index.html")
