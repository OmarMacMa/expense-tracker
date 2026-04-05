import secrets

from fastapi import APIRouter, Depends, Request
from fastapi.responses import JSONResponse, RedirectResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.jwt import (
    COOKIE_HTTPONLY,
    COOKIE_MAX_AGE,
    COOKIE_NAME,
    COOKIE_SAMESITE,
    cookie_secure,
    create_access_token,
)
from app.auth.oauth import exchange_code_for_user, get_google_auth_url
from app.config import settings
from app.db.session import get_db
from app.middleware.auth import get_current_user
from app.middleware.rate_limit import limiter
from app.models import Space, SpaceMember, User

router = APIRouter(prefix="/api/v1/auth", tags=["auth"])

STATE_COOKIE_NAME = "oauth_state"
STATE_COOKIE_MAX_AGE = 300  # 5 minutes


@router.get("/google")
@limiter.limit("5/minute")
async def google_login(request: Request) -> RedirectResponse:
    """Redirect to Google OAuth consent page."""
    redirect_uri = str(request.url_for("google_callback"))
    state = secrets.token_urlsafe(32)
    auth_url = get_google_auth_url(redirect_uri, state)
    response = RedirectResponse(url=auth_url)
    response.set_cookie(
        key=STATE_COOKIE_NAME,
        value=state,
        max_age=STATE_COOKIE_MAX_AGE,
        httponly=True,
        samesite="lax",
        secure=cookie_secure(),
        path="/",
    )
    return response


@router.get("/google/callback")
@limiter.limit("5/minute")
async def google_callback(
    request: Request,
    code: str | None = None,
    state: str | None = None,
    error: str | None = None,
    db: AsyncSession = Depends(get_db),
) -> RedirectResponse:
    """Handle Google OAuth callback: upsert user, set JWT cookie, redirect."""
    if error:
        return RedirectResponse(
            url=f"{settings.FRONTEND_URL}/?error=oauth_failed",
            status_code=302,
        )

    if not code:
        return RedirectResponse(
            url=f"{settings.FRONTEND_URL}/?error=oauth_no_code",
            status_code=302,
        )

    # Validate state parameter (CSRF protection)
    stored_state = request.cookies.get(STATE_COOKIE_NAME)
    if not state or not stored_state or not secrets.compare_digest(state, stored_state):
        return RedirectResponse(
            url=f"{settings.FRONTEND_URL}/?error=oauth_invalid_state",
            status_code=302,
        )

    redirect_uri = str(request.url_for("google_callback"))
    try:
        google_user = await exchange_code_for_user(code, redirect_uri)
    except ValueError:
        return RedirectResponse(
            url=f"{settings.FRONTEND_URL}/?error=oauth_exchange_failed",
            status_code=302,
        )

    # Upsert user by google_id
    stmt = select(User).where(User.google_id == google_user["google_id"])
    result = await db.execute(stmt)
    user = result.scalar_one_or_none()

    if user is None:
        user = User(
            google_id=google_user["google_id"],
            email=google_user["email"],
            display_name=google_user["display_name"],
            avatar_url=google_user["avatar_url"],
        )
        db.add(user)
    else:
        user.email = google_user["email"]
        user.display_name = google_user["display_name"]
        user.avatar_url = google_user["avatar_url"]

    await db.commit()
    await db.refresh(user)

    # Check if user has any space
    membership_stmt = select(SpaceMember).where(SpaceMember.user_id == user.id)
    membership_result = await db.execute(membership_stmt)
    has_space = membership_result.scalar_one_or_none() is not None

    # Create JWT and set cookie
    token = create_access_token(user.id)
    redirect_url = (
        f"{settings.FRONTEND_URL}/home"
        if has_space
        else f"{settings.FRONTEND_URL}/onboarding"
    )
    response = RedirectResponse(url=redirect_url, status_code=302)
    response.set_cookie(
        key=COOKIE_NAME,
        value=token,
        max_age=COOKIE_MAX_AGE,
        httponly=COOKIE_HTTPONLY,
        samesite=COOKIE_SAMESITE,
        secure=cookie_secure(),
        path="/",
    )
    response.delete_cookie(key=STATE_COOKIE_NAME, path="/")
    return response


@router.post("/logout")
async def logout() -> JSONResponse:
    """Clear the auth cookie."""
    response = JSONResponse(content={"message": "logged out"})
    response.delete_cookie(
        key=COOKIE_NAME,
        path="/",
        httponly=COOKIE_HTTPONLY,
        samesite=COOKIE_SAMESITE,
        secure=cookie_secure(),
    )
    return response


@router.get("/me")
async def get_me(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Get current user info + their spaces."""
    # Get user's spaces
    spaces_stmt = (
        select(Space)
        .join(SpaceMember, SpaceMember.space_id == Space.id)
        .where(SpaceMember.user_id == current_user.id)
    )
    spaces_result = await db.execute(spaces_stmt)
    spaces = spaces_result.scalars().all()

    return {
        "id": str(current_user.id),
        "email": current_user.email,
        "display_name": current_user.display_name,
        "avatar_url": current_user.avatar_url,
        "spaces": [{"id": str(s.id), "name": s.name} for s in spaces],
    }
