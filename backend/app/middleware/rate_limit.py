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
    """Return 429 with Retry-After header (integer seconds) and standard error body."""
    retry_after = 60
    detail = str(exc.detail)
    if "per" in detail:
        try:
            duration_str = detail.split("per")[1].strip()
            parts = duration_str.split()
            if len(parts) >= 2:
                count = int(parts[0])
                unit = parts[1].lower().rstrip("s")
                multipliers = {"second": 1, "minute": 60, "hour": 3600, "day": 86400}
                retry_after = count * multipliers.get(unit, 60)
        except (ValueError, IndexError):
            pass

    response = JSONResponse(
        status_code=429,
        content={
            "error": {
                "code": "RATE_LIMITED",
                "message": "Too many requests",
            }
        },
    )
    response.headers["Retry-After"] = str(retry_after)
    return response


limiter = Limiter(key_func=_get_user_or_ip, default_limits=["100/minute"])
