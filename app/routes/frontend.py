from pathlib import Path

from fastapi import APIRouter
from fastapi.responses import FileResponse

STATIC_DIR = Path(__file__).resolve().parent.parent / "static"

router = APIRouter(tags=["frontend"])


@router.get("/app", include_in_schema=False)
def serve_frontend():
    """Entry point of the bundled single-page UI.

    The hash router needs one real HTML document; everything under
    ``/app/`` (css, js, feature partials) is served by the StaticFiles
    mount registered in :mod:`app.app`.
    """
    return FileResponse(STATIC_DIR / "index.html")
