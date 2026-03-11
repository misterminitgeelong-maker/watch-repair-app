from dataclasses import dataclass
from typing import Callable
from uuid import UUID

from fastapi import Depends, HTTPException
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlmodel import Session

from .database import get_session
from .models import User
from .security import decode_access_token

bearer_scheme = HTTPBearer(auto_error=True)

# Roles ordered from least to most privileged for reference:
# intake < tech < manager < owner < platform_admin
ROLE_HIERARCHY: dict[str, int] = {
    "intake": 1,
    "tech": 2,
    "manager": 3,
    "owner": 4,
    "platform_admin": 5,
}


@dataclass
class AuthContext:
    tenant_id: UUID
    user_id: UUID
    role: str = "owner"


def get_auth_context(
    credentials: HTTPAuthorizationCredentials = Depends(bearer_scheme),
    session: Session = Depends(get_session),
) -> AuthContext:
    if credentials.scheme.lower() != "bearer":
        raise HTTPException(status_code=401, detail="Invalid auth scheme")

    try:
        subject = decode_access_token(credentials.credentials)
        parts = subject.split(":", maxsplit=2)
        tenant_id = UUID(parts[0])
        user_id = UUID(parts[1])

        user = session.get(User, user_id)
        if not user or user.tenant_id != tenant_id or not user.is_active:
            raise HTTPException(status_code=401, detail="Invalid token")

        return AuthContext(tenant_id=tenant_id, user_id=user_id, role=user.role)
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
require_owner = require_roles("owner", "platform_admin")
require_manager_or_above = require_roles("owner", "manager", "platform_admin")
require_tech_or_above = require_roles("owner", "manager", "tech", "platform_admin")
require_platform_admin = require_roles("platform_admin")
