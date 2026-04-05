import sentry_sdk
from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from slowapi.errors import RateLimitExceeded

from app.auth.router import router as auth_router
from app.config import settings
from app.middleware.correlation import CorrelationIdMiddleware
from app.middleware.logging import RequestLoggingMiddleware, setup_logging
from app.middleware.rate_limit import limiter, rate_limit_exceeded_handler
from app.routers.categories import router as categories_router
from app.routers.expenses import router as expenses_router
from app.routers.health import router as health_router
from app.routers.insights import router as insights_router
from app.routers.limits import router as limits_router
from app.routers.merchants import router as merchants_router
from app.routers.payment_methods import router as payment_methods_router
from app.routers.spaces import router as spaces_router
from app.routers.tags import router as tags_router

setup_logging()

if settings.SENTRY_DSN:
    sentry_sdk.init(
        dsn=settings.SENTRY_DSN,
        traces_sample_rate=0.1,
        environment=settings.ENVIRONMENT,
    )

app = FastAPI(title="Expense Tracker API", version="0.1.0")


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(
    request: Request, exc: RequestValidationError
) -> JSONResponse:
    """Return validation errors in standard format."""
    return JSONResponse(
        status_code=422,
        content={
            "error": {
                "code": "VALIDATION_ERROR",
                "message": "Request validation failed",
                "details": exc.errors(),
            }
        },
    )


app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, rate_limit_exceeded_handler)
app.add_middleware(RequestLoggingMiddleware)  # Added first → runs second (inner)
app.add_middleware(CorrelationIdMiddleware)  # Added second → runs first (outer)

app.include_router(health_router)
app.include_router(auth_router)
app.include_router(spaces_router)
app.include_router(categories_router)
app.include_router(tags_router)
app.include_router(merchants_router)
app.include_router(payment_methods_router)
app.include_router(expenses_router)
app.include_router(limits_router)
app.include_router(insights_router)
