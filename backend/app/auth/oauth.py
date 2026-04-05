from urllib.parse import urlencode

import httpx

from app.config import settings

GOOGLE_AUTH_URL = "https://accounts.google.com/o/oauth2/v2/auth"
GOOGLE_TOKEN_URL = "https://oauth2.googleapis.com/token"
GOOGLE_USERINFO_URL = "https://www.googleapis.com/oauth2/v3/userinfo"


def get_google_auth_url(redirect_uri: str, state: str) -> str:
    """Build Google OAuth consent URL."""
    params = {
        "client_id": settings.GOOGLE_CLIENT_ID,
        "redirect_uri": redirect_uri,
        "response_type": "code",
        "scope": "openid email profile",
        "access_type": "offline",
        "prompt": "consent",
        "state": state,
    }
    return f"{GOOGLE_AUTH_URL}?{urlencode(params)}"


async def exchange_code_for_user(code: str, redirect_uri: str) -> dict:
    """Exchange authorization code for user info.

    Returns dict with: google_id, email, display_name, avatar_url
    """
    async with httpx.AsyncClient() as client:
        # Exchange code for tokens
        token_response = await client.post(
            GOOGLE_TOKEN_URL,
            data={
                "code": code,
                "client_id": settings.GOOGLE_CLIENT_ID,
                "client_secret": settings.GOOGLE_CLIENT_SECRET,
                "redirect_uri": redirect_uri,
                "grant_type": "authorization_code",
            },
        )
        try:
            token_response.raise_for_status()
        except httpx.HTTPStatusError as e:
            raise ValueError(
                f"Failed to exchange OAuth code: {e.response.status_code}"
            ) from e
        tokens = token_response.json()

        # Fetch user info
        userinfo_response = await client.get(
            GOOGLE_USERINFO_URL,
            headers={"Authorization": f"Bearer {tokens['access_token']}"},
        )
        try:
            userinfo_response.raise_for_status()
        except httpx.HTTPStatusError as e:
            raise ValueError(
                f"Failed to fetch user info: {e.response.status_code}"
            ) from e
        userinfo = userinfo_response.json()

    if not userinfo.get("email_verified", False):
        raise ValueError("Google email is not verified")

    return {
        "google_id": userinfo["sub"],
        "email": userinfo["email"],
        "display_name": userinfo.get("name", userinfo["email"]),
        "avatar_url": userinfo.get("picture"),
    }
