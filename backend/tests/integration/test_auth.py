import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_unauthenticated_returns_401(unauth_client: AsyncClient):
    """Requests without auth cookie return 401."""
    response = await unauth_client.get("/api/v1/auth/me")
    assert response.status_code == 401
    body = response.json()
    assert body["detail"]["error"]["code"] == "UNAUTHORIZED"


@pytest.mark.asyncio
async def test_auth_me_returns_user(auth_client: AsyncClient, test_user_with_space):
    """Authenticated /auth/me returns user info."""
    response = await auth_client.get("/api/v1/auth/me")
    assert response.status_code == 200
    body = response.json()
    assert body["email"] == test_user_with_space["user"].email
    assert body["display_name"] == "Integration User"
    assert len(body["spaces"]) >= 1
