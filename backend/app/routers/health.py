from fastapi import APIRouter, Request
from sqlalchemy import text

from app.db.session import async_session_factory
from app.middleware.rate_limit import limiter

router = APIRouter(prefix="/api/v1", tags=["health"])


@router.get("/health")
@limiter.exempt
async def health_check(request: Request) -> dict:
    """Health check with database connectivity test."""
    try:
        async with async_session_factory() as session:
            await session.execute(text("SELECT 1"))
        return {"status": "ok", "db": "connected"}
    except Exception:
        from fastapi.responses import JSONResponse

        return JSONResponse(
            status_code=503,
            content={"status": "degraded", "db": "disconnected"},
        )
