from dataclasses import dataclass
from typing import Callable
from uuid import UUID

from fastapi import Depends, HTTPException
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlmodel import Session, select

from .security import decode_access_token

bearer_scheme = HTTPBearer(auto_error=True)

# Roles ordered from least to most privileged for reference:
# intake < tech < manager < owner
ROLE_HIERARCHY: dict[str, int] = {
    "intake": 1,
    "tech": 2,
    "manager": 3,
    "owner": 4,
}


@dataclass
class AuthContext:
    tenant_id: UUID
    user_id: UUID
    role: str = "owner"


def get_auth_context(
    credentials: HTTPAuthorizationCredentials = Depends(bearer_scheme),
) -> AuthContext:
    if credentials.scheme.lower() != "bearer":
        raise HTTPException(status_code=401, detail="Invalid auth scheme")

    try:
        subject = decode_access_token(credentials.credentials)
        parts = subject.split(":", maxsplit=2)
        tenant_id_str, user_id_str = parts[0], parts[1]
        role = parts[2] if len(parts) > 2 else "owner"
        return AuthContext(tenant_id=UUID(tenant_id_str), user_id=UUID(user_id_str), role=role)
    except Exception as exc:
        raise HTTPException(status_code=401, detail="Invalid token") from exc


def require_roles(*allowed_roles: str) -> Callable[[AuthContext], AuthContext]:
    """Return a FastAPI dependency that enforces role membership."""

    def _check(auth: AuthContext = Depends(get_auth_context)) -> AuthContext:
        if auth.role not in allowed_roles:
            raise HTTPException(status_code=403, detail="Insufficient permissions")
        return auth

    return _check


# Convenience aliases
require_owner = require_roles("owner")
require_manager_or_above = require_roles("owner", "manager")
require_tech_or_above = require_roles("owner", "manager", "tech")
