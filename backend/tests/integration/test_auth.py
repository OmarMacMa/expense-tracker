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


@pytest.mark.asyncio
async def test_oauth_callback_redirects_to_frontend_auth_callback(
    monkeypatch, unauth_client: AsyncClient
):
    """OAuth callback always redirects to /auth/callback (no longer branches
    to /home or /onboarding on the backend). The frontend route handles the
    routing decision, including pending invite token recovery.
    """
    from app.auth import router as auth_router_module
    from app.config import settings

    async def fake_exchange(code: str, redirect_uri: str) -> dict:
        return {
            "google_id": f"google_{code}",
            "email": "oauth-redirect-test@example.com",
            "display_name": "OAuth Redirect Test",
            "avatar_url": None,
        }

    monkeypatch.setattr(auth_router_module, "exchange_code_for_user", fake_exchange)

    # Set the state cookie that the callback validates
    state_value = "test-state-value"
    unauth_client.cookies.set("oauth_state", state_value)

    response = await unauth_client.get(
        "/api/v1/auth/google/callback",
        params={"code": "any-code", "state": state_value},
        follow_redirects=False,
    )

    assert response.status_code == 302
    assert response.headers["location"] == f"{settings.FRONTEND_URL}/auth/callback"
