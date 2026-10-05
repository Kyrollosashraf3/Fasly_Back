"""HTTP request logging: one console line per request."""

import time
from typing import Any

from starlette.requests import Request

from app.config.logger import get_logger

logger = get_logger(__name__)

# Endpoints that would only fill the log with noise.
QUIET_PATHS = ("/docs", "/redoc", "/openapi.json", "/favicon.ico")


class RequestLogMiddleware:
    """Log method, path, status, duration and the acting user of every request.

    ``app.core.auth.deps.get_current_user`` writes ``user_info`` onto
    ``request.state``, which is what the ``user=`` suffix comes from.
    """

    def __init__(self, app) -> None:
        self.app = app

    async def __call__(self, scope: Any, receive: Any, send: Any) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        request = Request(scope)
        if request.method == "OPTIONS" or request.url.path.startswith(QUIET_PATHS):
            await self.app(scope, receive, send)
            return

        start = time.perf_counter()
        status_code = 500

        async def send_wrapper(message: dict) -> None:
            nonlocal status_code
            if message["type"] == "http.response.start":
                status_code = message["status"]
            await send(message)

        try:
            await self.app(scope, receive, send_wrapper)
        finally:
            user = getattr(request.state, "user_info", "")
            logger.info(
                "%s %s -> %d (%.0fms)%s",
                request.method,
                request.url.path,
                status_code,
                (time.perf_counter() - start) * 1000,
                f" | user={user}" if user else "",
            )