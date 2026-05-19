"""Mister Minit tenant detection and plan normalization."""

from __future__ import annotations

from sqlmodel import Session

from .models import Tenant


def is_minit_tenant_slug(slug: str | None) -> bool:
    s = (slug or "").strip().lower()
    return s == "mmsupport" or s.startswith("minit-")


def ensure_minit_corporate_plan(session: Session, tenant: Tenant) -> Tenant:
    """HQ slug mmsupport must use minit_hq (mobile network UI only)."""
    if tenant.slug == "mmsupport" and tenant.plan_code != "minit_hq":
        tenant.plan_code = "minit_hq"
        session.add(tenant)
        session.flush()
    return tenant
