"""main.py - Application entry point.

Run:
    uvicorn app.main:app --reload --port 9001
"""

from app.app import app

__all__ = ["app"]


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("app.main:app", host="0.0.0.0", port=9001, reload=True)
