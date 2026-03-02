import uuid
from datetime import UTC, datetime, timedelta

from jose import JWTError, jwt

from app.config import settings

ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_DAYS = 7
REFRESH_THRESHOLD_DAYS = 1

COOKIE_NAME = "access_token"
COOKIE_MAX_AGE = ACCESS_TOKEN_EXPIRE_DAYS * 24 * 60 * 60
COOKIE_HTTPONLY = True
COOKIE_SAMESITE = "lax"


def cookie_secure() -> bool:
    """Secure flag: True in non-development environments."""
    return settings.ENVIRONMENT != "development"


def create_access_token(user_id: uuid.UUID) -> str:
    """Create a JWT with 7-day expiry."""
    now = datetime.now(UTC)
    payload = {
        "sub": str(user_id),
        "iat": now,
        "exp": now + timedelta(days=ACCESS_TOKEN_EXPIRE_DAYS),
    }
    return jwt.encode(payload, settings.JWT_SECRET, algorithm=ALGORITHM)


def decode_access_token(token: str) -> dict | None:
    """Decode JWT, trying current secret then previous (rotation support).

    Returns decoded payload or None if invalid/expired.
    """
    for secret in _get_secrets():
        try:
            payload = jwt.decode(token, secret, algorithms=[ALGORITHM])
            return payload
        except JWTError:
            continue
    return None


def should_refresh_token(payload: dict) -> bool:
    """Returns True if token expires in less than 1 day (sliding window)."""
    exp = datetime.fromtimestamp(payload["exp"], tz=UTC)
    remaining = exp - datetime.now(UTC)
    return remaining < timedelta(days=REFRESH_THRESHOLD_DAYS)


def _get_secrets() -> list[str]:
    """Return list of secrets to try (current first, then previous if set)."""
    secrets = [settings.JWT_SECRET]
    if settings.JWT_SECRET_PREVIOUS:
        secrets.append(settings.JWT_SECRET_PREVIOUS)
    return secrets
