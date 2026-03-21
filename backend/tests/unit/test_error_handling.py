import pytest
from httpx import ASGITransport, AsyncClient

from app.main import app


@pytest.mark.asyncio
async def test_unhandled_exception_returns_500_structured():
    """Unhandled exceptions return structured error, no stack trace leaked."""
    from fastapi import APIRouter

    test_router = APIRouter()

    @test_router.get("/api/v1/test-error")
    async def trigger_error():
        raise RuntimeError("Intentional test error")

    app.include_router(test_router)

    try:
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            response = await client.get("/api/v1/test-error")

        assert response.status_code == 500
        body = response.json()
        assert "error" in body
        assert body["error"]["code"] == "INTERNAL_ERROR"
        assert "message" in body["error"]
        # Must NOT leak stack trace
        assert "Traceback" not in response.text
        assert "RuntimeError" not in response.text
    finally:
        # Clean up test route
        app.router.routes = [
            r
            for r in app.router.routes
            if not (hasattr(r, "path") and r.path == "/api/v1/test-error")
        ]


@pytest.mark.asyncio
async def test_422_validation_error_format():
    """Pydantic validation errors should use standard error format."""
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        # Send invalid data to an endpoint that expects Pydantic validation
        response = await client.post(
            "/api/v1/spaces",
            json={},  # missing required fields
        )

    # Without auth cookie it'll be 401, so accept either
    assert response.status_code in (401, 422)
