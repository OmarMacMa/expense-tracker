import uuid

from fastapi import Depends, HTTPException, Request, Response
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.jwt import (
    COOKIE_HTTPONLY,
    COOKIE_MAX_AGE,
    COOKIE_NAME,
    COOKIE_SAMESITE,
    cookie_secure,
    create_access_token,
    decode_access_token,
    should_refresh_token,
)
from app.db.session import get_db
from app.models import User


async def get_current_user(
    request: Request,
    response: Response,
    db: AsyncSession = Depends(get_db),
) -> User:
    """Extract and validate JWT from cookie. Returns the User.

    - Missing cookie → 401
    - Invalid/expired token → 401
    - User not found in DB → 401
    - Token near expiry → re-issues cookie (sliding window)
    """
    token = request.cookies.get(COOKIE_NAME)
    if not token:
        raise HTTPException(
            status_code=401,
            detail={"error": {"code": "UNAUTHORIZED", "message": "Not authenticated"}},
        )

    payload = decode_access_token(token)
    if payload is None:
        raise HTTPException(
            status_code=401,
            detail={
                "error": {
                    "code": "UNAUTHORIZED",
                    "message": "Invalid or expired token",
                }
            },
        )

    try:
        user_id = uuid.UUID(payload["sub"])
    except (KeyError, ValueError):
        raise HTTPException(
            status_code=401,
            detail={
                "error": {
                    "code": "UNAUTHORIZED",
                    "message": "Invalid token payload",
                }
            },
        )

    stmt = select(User).where(User.id == user_id)
    result = await db.execute(stmt)
    user = result.scalar_one_or_none()

    if user is None:
        raise HTTPException(
            status_code=401,
            detail={"error": {"code": "UNAUTHORIZED", "message": "User not found"}},
        )

    # Sliding window: re-issue token if near expiry
    if should_refresh_token(payload):
        new_token = create_access_token(user.id)
        response.set_cookie(
            key=COOKIE_NAME,
            value=new_token,
            max_age=COOKIE_MAX_AGE,
            httponly=COOKIE_HTTPONLY,
            samesite=COOKIE_SAMESITE,
            secure=cookie_secure(),
            path="/",
        )

    return user
