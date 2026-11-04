"""Resolve testing-mode intake to one active Support office site, without dispatch."""
from sqlmodel import Session, col, select

from .models import ParentAccountSite, ParentAccountUser, Tenant, User
from .tenant_scope import without_scope


def testing_inbox_tenant_id(session: Session, parent_id):
    # Do not reuse the production escalation selector: it can name an operator.
    # Ambiguous/missing HQ membership must fail explicitly rather than pick a shop.
    with without_scope(session):
        sites = session.exec(select(ParentAccountSite).where(ParentAccountSite.parent_account_id == parent_id)).all()
        hq_sites = [s for s in sites if s.network_role == "hq"]
        if hq_sites:
            ids = {s.tenant_id for s in hq_sites}
        else:
            # Legacy multi-site owners have an explicit HQ admin grant but a
            # retail site identity. Recognise that grant, never email matches.
            admin_ids = set(session.exec(select(User.tenant_id).join(ParentAccountUser, ParentAccountUser.user_id == User.id)
                .where(ParentAccountUser.parent_account_id == parent_id)
                .where(ParentAccountUser.role == "hq_admin")
                .where(ParentAccountUser.region_id == None).where(User.is_active == True)).all())  # noqa: E711, E712
            ids = {s.tenant_id for s in sites if s.network_role == "retail" and s.tenant_id in admin_ids}
        tenants = session.exec(select(Tenant).where(col(Tenant.id).in_(ids))
            .where(Tenant.is_active == True).where(Tenant.merged_into_tenant_id == None)).all() if ids else []  # noqa: E711, E712
        if not hq_sites:
            from .dependencies import normalize_plan_code

            tenants = [t for t in tenants if normalize_plan_code(t.plan_code) not in {"basic_auto_key", "minit_operator"}]
    return tenants[0].id if len(tenants) == 1 else None
