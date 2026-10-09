"""Who counts as an HQ, and which HQ modules they may use.

Replaces the Minit-only gate that sat in front of every HQ route. A tenant is
an HQ when it holds the HQ plan and is the HQ site of a parent account with an
``HqSettings`` row; the row's modules say which HQ areas it may open. Minit's
HQ passes exactly as before: its row (seeded to match today's behaviour, with a
code fallback for databases that predate the row) enables every area it used.

The HQ plan code is still spelled ``minit_hq``; it is the one HQ plan for every
company, so the name is historical and renaming it is a separate migration.
"""

from __future__ import annotations

from fastapi import HTTPException
from sqlmodel import Session, select

from .dependencies import AuthContext, normalize_plan_code
from .hq_settings import MINIT_DEFAULTS, HqConfig, get_hq_config
from .minit_branding import MINIT_HQ_PLAN, is_minit_tenant
from .models import NETWORK_ROLE_HQ, ParentAccountSite, Tenant
from .tenant_scope import without_scope


def hq_config_for_tenant(session: Session, tenant: Tenant) -> HqConfig | None:
    """Settings of the HQ this tenant is the HQ site of; None if it isn't one."""
    with without_scope(session):
        parent_ids = session.exec(
            select(ParentAccountSite.parent_account_id)
            .where(ParentAccountSite.tenant_id == tenant.id)
            .where(ParentAccountSite.network_role == NETWORK_ROLE_HQ)
            .order_by(ParentAccountSite.created_at.asc(), ParentAccountSite.id.asc())
        ).all()
    for parent_id in parent_ids:
        config = get_hq_config(session, parent_id)
        if config is not None:
            return config
    # Databases that predate the settings row: Minit's HQ keeps working.
    if is_minit_tenant(tenant):
        return MINIT_DEFAULTS
    return None


def require_hq(auth: AuthContext, session: Session, module: str | None = None) -> Tenant:
    """The signed-in HQ tenant, or 403. ``module`` limits it to HQs with that area on."""
    tenant = session.get(Tenant, auth.tenant_id)
    if not tenant:
        raise HTTPException(status_code=401, detail="Invalid token")
    if normalize_plan_code(auth.plan_code) != MINIT_HQ_PLAN:
        raise HTTPException(status_code=403, detail="HQ plan required")
    config = hq_config_for_tenant(session, tenant)
    if config is None:
        raise HTTPException(status_code=403, detail="HQ account required")
    if module is not None and not config.has_module(module):
        raise HTTPException(status_code=403, detail=f"This HQ does not have the '{module}' module")
    return tenant


def allowed_plans_for_hq_network_tenant(session: Session, tenant: Tenant) -> frozenset[str] | None:
    """Plans a platform admin may set on a tenant that belongs to a company HQ
    (other than Minit's, which ``allowed_plans_for_minit_tenant`` covers).

    The HQ itself stays on the HQ plan. A shop in exactly one company network
    is limited to that HQ's shop plans; a shop in several networks, or one whose
    HQ lists no plans, is left unrestricted rather than guessing.
    """
    if is_minit_tenant(tenant):
        return None
    with without_scope(session):
        sites = session.exec(select(ParentAccountSite).where(ParentAccountSite.tenant_id == tenant.id)).all()
    hq_parents = [s.parent_account_id for s in sites if s.network_role == NETWORK_ROLE_HQ]
    for parent_id in hq_parents:
        if get_hq_config(session, parent_id) is not None:
            return frozenset({MINIT_HQ_PLAN})
    configs = []
    for site in sites:
        config = get_hq_config(session, site.parent_account_id)
        if config is not None:
            configs.append(config)
    if len(configs) == 1 and configs[0].site_plans:
        return configs[0].site_plans
    return None
