from datetime import datetime, timedelta, timezone
from dataclasses import dataclass
from uuid import UUID

import bcrypt
from jose import JWTError, jwt

from .config import settings

REFRESH_TOKEN_TYP = "refresh"


@dataclass
class TokenClaims:
    sub: str
    tenant_id: UUID
    user_id: UUID
    role: str


def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()


def verify_password(plain_password: str, password_hash: str) -> bool:
    return bcrypt.checkpw(plain_password.encode(), password_hash.encode())


def create_access_token(tenant_id: UUID | str, user_id: UUID | str, role: str) -> tuple[str, int]:
    expires_delta = timedelta(minutes=settings.jwt_expire_minutes)
    expire = datetime.now(timezone.utc) + expires_delta
    payload = {
        "sub": str(user_id),
        "tenant_id": str(tenant_id),
        "user_id": str(user_id),
        "role": role,
        "exp": expire,
    }
    encoded_jwt = jwt.encode(payload, settings.jwt_secret, algorithm=settings.jwt_algorithm)
    return encoded_jwt, int(expires_delta.total_seconds())


def create_refresh_token(tenant_id: UUID | str, user_id: UUID | str, role: str) -> tuple[str, int]:
    expires_delta = timedelta(days=settings.jwt_refresh_expire_days)
    expire = datetime.now(timezone.utc) + expires_delta
    payload = {
        "sub": str(user_id),
        "tenant_id": str(tenant_id),
        "user_id": str(user_id),
        "role": role,
        "exp": expire,
        "typ": REFRESH_TOKEN_TYP,
    }
    encoded_jwt = jwt.encode(payload, settings.jwt_secret, algorithm=settings.jwt_algorithm)
    return encoded_jwt, int(expires_delta.total_seconds())


def _parse_claims(payload: dict, *, expect_refresh: bool) -> TokenClaims:
    token_type = payload.get("typ")
    if expect_refresh:
        if token_type != REFRESH_TOKEN_TYP:
            raise ValueError("Invalid refresh token")
    else:
        if token_type == REFRESH_TOKEN_TYP:
            raise ValueError("Expected access token, got refresh token")

    sub = payload.get("sub")
    tenant_id_raw = payload.get("tenant_id")
    user_id_raw = payload.get("user_id")
    role = payload.get("role")

    if not isinstance(sub, str) or not sub:
        raise ValueError("Invalid token claims")
    if not isinstance(tenant_id_raw, str) or not isinstance(user_id_raw, str) or not isinstance(role, str):
        raise ValueError("Invalid token claims")

    try:
        tenant_id = UUID(tenant_id_raw)
        user_id = UUID(user_id_raw)
    except Exception as exc:
        raise ValueError("Invalid token claims") from exc

    return TokenClaims(sub=sub, tenant_id=tenant_id, user_id=user_id, role=role)


def decode_access_token(token: str) -> TokenClaims:
    try:
        payload = jwt.decode(token, settings.jwt_secret, algorithms=[settings.jwt_algorithm])
        return _parse_claims(payload, expect_refresh=False)
    except (JWTError, ValueError) as exc:
        raise ValueError("Invalid token") from exc


def decode_refresh_token(token: str) -> TokenClaims:
    try:
        payload = jwt.decode(token, settings.jwt_secret, algorithms=[settings.jwt_algorithm])
        return _parse_claims(payload, expect_refresh=True)
    except (JWTError, ValueError) as exc:
        raise ValueError("Invalid refresh token") from exc
