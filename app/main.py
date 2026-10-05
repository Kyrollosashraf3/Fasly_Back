"""Application entry point.

Only exposes the ASGI app; all wiring lives in ``app.core.app``.

Run:  uvicorn app.main:app --reload --port 9001
Docs: /docs  /redoc  /openapi.json
"""

from app.core.app import create_app

app = create_app()