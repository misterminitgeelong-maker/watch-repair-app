from dataclasses import dataclass
from typing import Callable
from uuid import UUID

from fastapi import Depends, HTTPException, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlmodel import Session

from .config import settings
from .database import get_session
from .models import Tenant, User
from .security import decode_access_token


def stripe_billing_configured() -> bool:
    return bool(settings.stripe_secret_key)


def _path_allowed_during_signup_payment_pending(url_path: str) -> bool:
    """Routes that must keep working before the first subscription webhook."""
    p = (url_path or "").rstrip("/") or "/"
    if p == "/v1/auth/session":
        return True
    billing_allow = (
        "/v1/billing/checkout",
        "/v1/billing/limits",
        "/v1/billing/portal-url",
    )
    for pref in billing_allow:
        if p == pref or p.startswith(pref + "/"):
            return True
    if p.startswith("/v1/billing/connect/"):
        return True
    return False

# ── Plan codes and aliases ────────────────────────────────────────────────────
VALID_PLAN_CODES: set[str] = {
    "basic_watch",
    "basic_shoe",
    "basic_auto_key",
    "basic_watch_shoe",
    "basic_watch_auto_key",
    "basic_shoe_auto_key",
    "basic_all_tabs",
    "pro",
}

# Backward compatibility for existing tenants and old API payloads.
PLAN_CODE_ALIASES: dict[str, str] = {
    "watch": "basic_watch",
    "shoe": "basic_shoe",
    "auto_key": "basic_auto_key",
    "enterprise": "pro",
}


def normalize_plan_code(plan_code: str | None, *, default_if_empty: str = "pro") -> str:
    if plan_code is None:
        return default_if_empty

    normalized = plan_code.strip().lower()
    if not normalized:
        return default_if_empty

    normalized = PLAN_CODE_ALIASES.get(normalized, normalized)
    if normalized in VALID_PLAN_CODES:
        return normalized
    return default_if_empty


# ── Plan limits (0 = unlimited) ───────────────────────────────────────────────
PLAN_LIMITS: dict[str, dict[str, int]] = {
    "basic_watch": {"max_users": 5, "max_repair_jobs": 2000, "max_shoe_jobs": 0, "max_auto_key_jobs": 0},
    "basic_shoe": {"max_users": 5, "max_repair_jobs": 0, "max_shoe_jobs": 2000, "max_auto_key_jobs": 0},
    "basic_auto_key": {"max_users": 5, "max_repair_jobs": 0, "max_shoe_jobs": 0, "max_auto_key_jobs": 1000},
    "basic_watch_shoe": {"max_users": 8, "max_repair_jobs": 2000, "max_shoe_jobs": 2000, "max_auto_key_jobs": 0},
    "basic_watch_auto_key": {"max_users": 8, "max_repair_jobs": 2000, "max_shoe_jobs": 0, "max_auto_key_jobs": 1000},
    "basic_shoe_auto_key": {"max_users": 8, "max_repair_jobs": 0, "max_shoe_jobs": 2000, "max_auto_key_jobs": 1000},
    "basic_all_tabs": {"max_users": 10, "max_repair_jobs": 2000, "max_shoe_jobs": 2000, "max_auto_key_jobs": 1000},
    "pro": {"max_users": 0, "max_repair_jobs": 0, "max_shoe_jobs": 0, "max_auto_key_jobs": 0},
}

_PLAN_LIMIT_LABELS: dict[str, str] = {
    "max_users":        "team accounts",
    "max_repair_jobs":  "watch repair jobs",
    "max_shoe_jobs":    "shoe repair jobs",
    "max_auto_key_jobs": "auto key jobs",
}

_RESOURCE_TO_LIMIT_KEY: dict[str, str] = {
    "user":         "max_users",
    "repair_job":   "max_repair_jobs",
    "shoe_job":     "max_shoe_jobs",
    "auto_key_job": "max_auto_key_jobs",
}

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

ALL_PLAN_FEATURES = {
    "watch",
    "shoe",
    "auto_key",
    "customer_accounts",
    "multi_site",
    "rego_lookup",
}

PLAN_FEATURES: dict[str, set[str]] = {
    "basic_watch": {"watch"},
    "basic_shoe": {"shoe"},
    "basic_auto_key": {"auto_key"},
    "basic_watch_shoe": {"watch", "shoe"},
    "basic_watch_auto_key": {"watch", "auto_key"},
    "basic_shoe_auto_key": {"shoe", "auto_key"},
    "basic_all_tabs": {"watch", "shoe", "auto_key"},
    "pro": set(ALL_PLAN_FEATURES),
}


@dataclass
class AuthContext:
    tenant_id: UUID
    user_id: UUID
    role: str = "owner"
    plan_code: str = "pro"


def get_auth_context(
    request: Request,
    credentials: HTTPAuthorizationCredentials = Depends(bearer_scheme),
    session: Session = Depends(get_session),
) -> AuthContext:
    if credentials.scheme.lower() != "bearer":
        raise HTTPException(status_code=401, detail="Invalid auth scheme")

    try:
        claims = decode_access_token(credentials.credentials)
        tenant_id = claims.tenant_id
        user_id = claims.user_id

        user = session.get(User, user_id)
        if not user or user.tenant_id != tenant_id or not user.is_active:
            raise HTTPException(status_code=401, detail="Invalid token")
        if claims.role != user.role:
            raise HTTPException(status_code=401, detail="Invalid token")

        tenant = session.get(Tenant, tenant_id)
        if not tenant:
            raise HTTPException(status_code=401, detail="Invalid token")

        plan_code = normalize_plan_code(tenant.plan_code, default_if_empty="pro")

        if (
            user.role != "platform_admin"
            and getattr(tenant, "signup_payment_pending", False)
            and stripe_billing_configured()
            and not _path_allowed_during_signup_payment_pending(request.url.path)
        ):
            raise HTTPException(
                status_code=403,
                detail="subscription_required",
            )

        return AuthContext(tenant_id=tenant_id, user_id=user_id, role=user.role, plan_code=plan_code)
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=401, detail="Invalid token") from exc


def require_roles(*allowed_roles: str) -> Callable[[AuthContext], AuthContext]:
    """Return a FastAPI dependency that enforces role membership."""

    def _check(auth: AuthContext = Depends(get_auth_context)) -> AuthContext:
        if auth.role not in allowed_roles:
            raise HTTPException(status_code=403, detail="Insufficient permissions")
        return auth

    return _check


def enforce_plan_limit(auth: "AuthContext", resource: str, current_count: int) -> None:
    """Raise HTTP 402 if *current_count* is at or above the per-plan maximum.

    Pass the count *before* the new record is created.
    0 means unlimited — no check is performed.
    """
    if auth.role == "platform_admin":
        return
    limit_key = _RESOURCE_TO_LIMIT_KEY.get(resource)
    if not limit_key:
        return
    plan_limits = PLAN_LIMITS.get(auth.plan_code, PLAN_LIMITS["pro"])
    max_allowed = plan_limits.get(limit_key, 0)
    if max_allowed == 0:
        return  # unlimited
    if current_count >= max_allowed:
        label = _PLAN_LIMIT_LABELS.get(limit_key, resource)
        raise HTTPException(
            status_code=402,
            detail=(
                f"Plan limit reached: your '{auth.plan_code}' plan allows up to {max_allowed} {label}. "
                "Upgrade to Pro for unlimited access."
            ),
        )


# Convenience aliases
require_owner = require_roles("owner", "platform_admin")
require_manager_or_above = require_roles("owner", "manager", "platform_admin")
require_tech_or_above = require_roles("owner", "manager", "tech", "platform_admin")
require_platform_admin = require_roles("platform_admin")


def require_feature(feature_key: str) -> Callable[[AuthContext], AuthContext]:
    """Return a FastAPI dependency that enforces tenant plan feature access."""

    def _check(auth: AuthContext = Depends(get_auth_context)) -> AuthContext:
        if auth.role == "platform_admin":
            return auth

        enabled = PLAN_FEATURES.get(auth.plan_code, PLAN_FEATURES["pro"])
        if feature_key not in enabled:
            raise HTTPException(
                status_code=403,
                detail=f"Current plan '{auth.plan_code}' does not include '{feature_key}'",
            )
        return auth

    return _check
