from datetime import datetime, timedelta, timezone

import bcrypt
from jose import JWTError, jwt

from .config import settings

REFRESH_TOKEN_TYP = "refresh"


def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()


def verify_password(plain_password: str, password_hash: str) -> bool:
    return bcrypt.checkpw(plain_password.encode(), password_hash.encode())


def create_access_token(subject: str) -> tuple[str, int]:
    expires_delta = timedelta(minutes=settings.jwt_expire_minutes)
    expire = datetime.now(timezone.utc) + expires_delta
    payload = {"sub": subject, "exp": expire}
    encoded_jwt = jwt.encode(payload, settings.jwt_secret, algorithm=settings.jwt_algorithm)
    return encoded_jwt, int(expires_delta.total_seconds())


def create_refresh_token(subject: str) -> tuple[str, int]:
    expires_delta = timedelta(days=settings.jwt_refresh_expire_days)
    expire = datetime.now(timezone.utc) + expires_delta
    payload = {"sub": subject, "exp": expire, "typ": REFRESH_TOKEN_TYP}
    encoded_jwt = jwt.encode(payload, settings.jwt_secret, algorithm=settings.jwt_algorithm)
    return encoded_jwt, int(expires_delta.total_seconds())


def decode_access_token(token: str) -> str:
    try:
        payload = jwt.decode(token, settings.jwt_secret, algorithms=[settings.jwt_algorithm])
        if payload.get("typ") == REFRESH_TOKEN_TYP:
            raise ValueError("Expected access token, got refresh token")
        subject = payload.get("sub")
        if not isinstance(subject, str) or subject.count(":") < 1:
            raise ValueError("Invalid token subject")
        return subject
    except (JWTError, ValueError) as exc:
        raise ValueError("Invalid token") from exc


def decode_refresh_token(token: str) -> str:
    try:
        payload = jwt.decode(token, settings.jwt_secret, algorithms=[settings.jwt_algorithm])
        if payload.get("typ") != REFRESH_TOKEN_TYP:
            raise ValueError("Invalid refresh token")
        subject = payload.get("sub")
        if not isinstance(subject, str) or subject.count(":") < 1:
            raise ValueError("Invalid token subject")
        return subject
    except (JWTError, ValueError) as exc:
        raise ValueError("Invalid refresh token") from exc
