import logging
import sys
import time
import traceback

import structlog
from fastapi.responses import JSONResponse
from starlette.requests import Request
from starlette.types import ASGIApp, Receive, Scope, Send

from app.config import settings


def setup_logging() -> None:
    """Configure structlog for JSON logging."""
    log_level = getattr(logging, settings.LOG_LEVEL.upper(), logging.INFO)

    structlog.configure(
        processors=[
            structlog.contextvars.merge_contextvars,
            structlog.processors.add_log_level,
            structlog.processors.TimeStamper(fmt="iso", utc=True),
            structlog.processors.StackInfoRenderer(),
            structlog.processors.format_exc_info,
            structlog.processors.JSONRenderer(),
        ],
        wrapper_class=structlog.make_filtering_bound_logger(log_level),
        context_class=dict,
        logger_factory=structlog.PrintLoggerFactory(file=sys.stdout),
        cache_logger_on_first_use=True,
    )


class RequestLoggingMiddleware:
    """Log every request/response with timing. Catches unhandled exceptions."""

    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        start_time = time.perf_counter()
        logger = structlog.get_logger()
        request = Request(scope)
        status_code: int | None = None

        async def send_wrapper(message: dict) -> None:
            nonlocal status_code
            if message["type"] == "http.response.start":
                status_code = message["status"]
            await send(message)

        structlog.contextvars.clear_contextvars()

        try:
            await self.app(scope, receive, send_wrapper)
        except Exception as exc:
            # Log the full traceback server-side, return safe error to client
            duration_ms = round((time.perf_counter() - start_time) * 1000, 2)
            await logger.aerror(
                "unhandled_exception",
                error_type=type(exc).__name__,
                error_message=str(exc),
                traceback=traceback.format_exc(),
                path=str(request.url.path),
                method=request.method,
                duration_ms=duration_ms,
            )
            response = JSONResponse(
                status_code=500,
                content={
                    "error": {
                        "code": "INTERNAL_ERROR",
                        "message": "An unexpected error occurred",
                    }
                },
            )
            await response(scope, receive, send)
            return

        duration_ms = round((time.perf_counter() - start_time) * 1000, 2)
        await logger.ainfo(
            "api_request",
            method=request.method,
            path=str(request.url.path),
            status_code=status_code,
            duration_ms=duration_ms,
        )
