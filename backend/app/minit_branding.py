"""Mister Minit tenant detection, plan normalization, and product identity."""

from __future__ import annotations

from pathlib import Path

from sqlmodel import Session

from .config import settings
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


# ── Customer-facing branding ──────────────────────────────────────────────────
# Everything a Mister Minit shop's customers see (portal, status pages, invoices,
# quotes) carries the Mister Minit logo, whatever the shop has set for itself.

#: Served by the frontend from ``frontend/public``.
MINIT_LOGO_PUBLIC_PATH = "/minit-logo-cropped.jpg"
#: The same file, bundled with the backend so PDFs never fetch it over HTTP.
MINIT_LOGO_ASSET = Path(__file__).parent / "assets" / "minit-logo.jpg"
#: Mister Minit red — the portal accent for Minit shops with no colour of their own.
MINIT_ACCENT_COLOR = "#E31837"
#: Mister Minit navy — the accent on Minit invoices and quotes.
MINIT_DOCUMENT_COLOR = "#2B3990"


def customer_logo_url(tenant: Tenant | None) -> str | None:
    """Absolute logo URL to show customers (emails, portal, public pages)."""
    if is_minit_tenant(tenant):
        return f"{settings.public_base_url.rstrip('/')}{MINIT_LOGO_PUBLIC_PATH}"
    return (tenant.logo_url or None) if tenant else None


def customer_brand_color(tenant: Tenant | None) -> str | None:
    if tenant is None:
        return None
    if is_minit_tenant(tenant):
        return tenant.brand_color or MINIT_ACCENT_COLOR
    return tenant.brand_color


def document_branding(tenant: Tenant | None) -> dict:
    """Logo and accent keyword arguments for ``pdf_invoice`` builders."""
    if is_minit_tenant(tenant):
        return {
            "logo_url": None,
            "logo_path": str(MINIT_LOGO_ASSET),
            "brand_color": MINIT_DOCUMENT_COLOR,
        }
    return {
        "logo_url": tenant.logo_url if tenant else None,
        "logo_path": None,
        "brand_color": tenant.brand_color if tenant else None,
    }


def public_shop_branding(tenant: Tenant | None) -> dict:
    """Branding fields merged into public (customer-facing) API responses."""
    return {
        "is_minit": is_minit_tenant(tenant),
        "logo_url": customer_logo_url(tenant),
        "brand_color": customer_brand_color(tenant),
    }


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


#: Plans a Minit shop can hold without being switched on its next sign-in.
#: HQ is kept on minit_hq; ``minit_hq`` on any other shop would hand it HQ's nav.
MINIT_SITE_PLANS: frozenset[str] = frozenset({MINIT_SHOP_PLAN, "basic_auto_key"})


def allowed_plans_for_minit_tenant(tenant: Tenant) -> frozenset[str] | None:
    """Plans a platform admin may set on this tenant, or None when any plan goes."""
    if not is_minit_tenant(tenant):
        return None
    if _is_minit_hq_tenant(tenant):
        return frozenset({MINIT_HQ_PLAN})
    return MINIT_SITE_PLANS


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


def public_shop_branding_fields(tenant: Tenant | None) -> dict:
    """``public_shop_branding`` as flat ``shop_*`` keys, for responses that
    describe the shop with top-level ``shop_name``/``shop_phone`` fields."""
    return {f"shop_{k}": v for k, v in public_shop_branding(tenant).items()}
