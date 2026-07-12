from datetime import datetime, timedelta, timezone

import jwt
from passlib.context import CryptContext

from app.core.config import settings
from app.core.exceptions import unauthorized
from app.utils.uuidv7 import uuid7

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


def hash_password(raw: str) -> str:
    return pwd_context.hash(raw)


def verify_password(raw: str, hashed: str) -> bool:
    return pwd_context.verify(raw, hashed)


def new_jti() -> str:
    return uuid7()


def _encode(sub: str, token_type: str, expires_delta: timedelta) -> tuple[str, str, int]:
    now = datetime.now(timezone.utc)
    jti = new_jti()
    payload = {
        "sub": sub,
        "jti": jti,
        "type": token_type,
        "iat": int(now.timestamp()),
        "exp": int((now + expires_delta).timestamp()),
    }
    token = jwt.encode(payload, settings.jwt_secret, algorithm=settings.jwt_alg)
    return token, jti, int(expires_delta.total_seconds())


def create_access_token(sub: str) -> tuple[str, str, int]:
    return _encode(sub, "access", timedelta(minutes=settings.access_token_minutes))


def create_refresh_token(sub: str) -> tuple[str, str]:
    token, jti, _ = _encode(sub, "refresh", timedelta(days=settings.refresh_token_days))
    return token, jti


def decode_token(token: str) -> dict:
    try:
        return jwt.decode(token, settings.jwt_secret, algorithms=[settings.jwt_alg])
    except jwt.PyJWTError:
        raise unauthorized()


def password_changed_after_issue(iat: int, pwd_updated_at) -> bool:
    """True if the account password was changed at/after a token with this iat was issued.
    Handles MySQL naive DATETIMEs (stored UTC) and JWT's 1-second iat granularity."""
    if pwd_updated_at is None:
        return False
    ts = pwd_updated_at
    if ts.tzinfo is None:
        ts = ts.replace(tzinfo=timezone.utc)
    return iat < int(ts.timestamp()) + 1
