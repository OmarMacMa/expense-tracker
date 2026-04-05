import sentry_sdk
from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from slowapi.errors import RateLimitExceeded
from slowapi.middleware import SlowAPIMiddleware

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

app = FastAPI(
    title="Expense Tracker API",
    version="0.1.0",
    docs_url="/docs" if settings.ENVIRONMENT == "development" else None,
    redoc_url="/redoc" if settings.ENVIRONMENT == "development" else None,
    openapi_url="/openapi.json" if settings.ENVIRONMENT == "development" else None,
)


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(
    request: Request, exc: RequestValidationError
) -> JSONResponse:
    """Return validation errors in standard format, sanitized."""
    sanitized_errors = [
        {
            "field": ".".join(str(loc) for loc in e.get("loc", [])),
            "message": e.get("msg", ""),
        }
        for e in exc.errors()
    ]
    return JSONResponse(
        status_code=422,
        content={
            "error": {
                "code": "VALIDATION_ERROR",
                "message": "Request validation failed",
                "details": sanitized_errors,
            }
        },
    )


app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, rate_limit_exceeded_handler)
app.add_middleware(SlowAPIMiddleware)  # Added first → runs last (innermost: after auth)
app.add_middleware(RequestLoggingMiddleware)  # Added second → runs second (inner)
app.add_middleware(CorrelationIdMiddleware)  # Added third → runs first (outer)
app.add_middleware(
    CORSMiddleware,
    allow_origins=[settings.FRONTEND_URL],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

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
