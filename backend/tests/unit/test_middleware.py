import uuid

import pytest
from httpx import ASGITransport, AsyncClient

from app.main import app


@pytest.mark.asyncio
async def test_correlation_id_in_response():
    """Every response must include X-Correlation-ID header with UUID format."""
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        response = await client.get("/api/v1/health")
    # Status may be 503 without DB — we're testing the correlation header
    correlation_id = response.headers.get("x-correlation-id")
    assert correlation_id is not None
    # Validate it's a valid UUID
    uuid.UUID(correlation_id)


@pytest.mark.asyncio
async def test_correlation_id_unique():
    """Two requests get different correlation IDs."""
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        r1 = await client.get("/api/v1/health")
        r2 = await client.get("/api/v1/health")
    id1 = r1.headers.get("x-correlation-id")
    id2 = r2.headers.get("x-correlation-id")
    assert id1 != id2


@pytest.mark.asyncio
async def test_rate_limit_returns_429():
    """Exceeding rate limit returns 429 with Retry-After header."""
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        # Auth endpoints have 10/min limit
        responses = []
        for _ in range(15):
            r = await client.get("/api/v1/auth/google")
            responses.append(r)

        # At least one should be 429 (after 10 requests)
        status_codes = [r.status_code for r in responses]
        assert 429 in status_codes, f"Expected 429 in {status_codes}"

        # The 429 response should have Retry-After header
        rate_limited = [r for r in responses if r.status_code == 429]
        assert rate_limited[0].headers.get("retry-after") is not None
