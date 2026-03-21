from fastapi import Request
from fastapi.responses import JSONResponse
from slowapi import Limiter
from slowapi.errors import RateLimitExceeded
from slowapi.util import get_remote_address

from app.auth.jwt import COOKIE_NAME, decode_access_token


def _get_user_or_ip(request) -> str:
    """Rate limit key: user ID if authenticated, IP otherwise."""
    token = request.cookies.get(COOKIE_NAME)
    if token:
        payload = decode_access_token(token)
        if payload and "sub" in payload:
            return payload["sub"]
    return get_remote_address(request)


def rate_limit_exceeded_handler(
    request: Request, exc: RateLimitExceeded
) -> JSONResponse:
    """Return 429 with Retry-After header and standard error body."""
    detail = str(exc.detail)
    retry_after = detail.split("per")[1].strip() if "per" in detail else "60"
    response = JSONResponse(
        status_code=429,
        content={
            "error": {
                "code": "RATE_LIMIT_EXCEEDED",
                "message": f"Rate limit exceeded: {exc.detail}",
            }
        },
    )
    response.headers["Retry-After"] = retry_after
    return response


limiter = Limiter(key_func=_get_user_or_ip, default_limits=["100/minute"])
