"""Mister Minit tenant detection, plan normalization, and product identity."""

from __future__ import annotations

from sqlmodel import Session

from .dependencies import normalize_plan_code
from .models import Tenant

MINIT_HQ_SLUG = "mmsupport"
MINIT_HQ_PLAN = "minit_hq"
MINIT_SHOP_PLAN = "booking_only"

# Plans that expose Mainspring repair POS; Minit retail/HQ must never keep these.
_MINIT_DISALLOWED_PLANS = frozenset(
    {
        "pro",
        "enterprise",
        "basic_watch",
        "basic_shoe",
        "basic_watch_shoe",
        "basic_watch_auto_key",
        "basic_shoe_auto_key",
        "basic_all_tabs",
    }
)


def is_minit_tenant_slug(slug: str | None) -> bool:
    """Whether a slug is in the Minit namespace. Only for reserving names at
    signup and for pre-login branding — identity comes from ``Tenant.is_minit``."""
    s = (slug or "").strip().lower()
    return s == MINIT_HQ_SLUG or s.startswith("minit-")


def is_minit_tenant(tenant: Tenant | None) -> bool:
    """Mister Minit network tenant, as stored at provisioning."""
    return bool(tenant is not None and getattr(tenant, "is_minit", False))


def tenant_product(tenant: Tenant | None) -> str:
    return "minit" if is_minit_tenant(tenant) else "mainspring"


def _is_minit_hq_tenant(tenant: Tenant) -> bool:
    return is_minit_tenant(tenant) and (tenant.slug or "").strip().lower() == MINIT_HQ_SLUG


def target_plan_for_minit_tenant(tenant: Tenant) -> str | None:
    """Return the plan code this Minit tenant should use, or None if no change."""
    if not is_minit_tenant(tenant):
        return None
    if _is_minit_hq_tenant(tenant):
        return MINIT_HQ_PLAN if normalize_plan_code(tenant.plan_code) != MINIT_HQ_PLAN else None
    normalized = normalize_plan_code(tenant.plan_code)
    if normalized in _MINIT_DISALLOWED_PLANS:
        return MINIT_SHOP_PLAN
    return None


def effective_plan_code(tenant: Tenant) -> str:
    """Plan used for features and UI without persisting."""
    override = target_plan_for_minit_tenant(tenant)
    if override:
        return override
    return normalize_plan_code(tenant.plan_code)


def is_minit_hq_ui(tenant: Tenant) -> bool:
    """True when the active tenant should see the six-item Minit HQ sidebar."""
    if _is_minit_hq_tenant(tenant):
        return True
    return effective_plan_code(tenant) == MINIT_HQ_PLAN


def ensure_minit_tenant_plan(session: Session, tenant: Tenant) -> Tenant:
    """Persist correct plan for Minit HQ and retail shops stuck on Mainspring plans."""
    target = target_plan_for_minit_tenant(tenant)
    if target and normalize_plan_code(tenant.plan_code) != target:
        tenant.plan_code = target
        session.add(tenant)
        session.flush()
    return tenant


def ensure_minit_corporate_plan(session: Session, tenant: Tenant) -> Tenant:
    """Backward-compatible alias for HQ plan fix."""
    return ensure_minit_tenant_plan(session, tenant)
