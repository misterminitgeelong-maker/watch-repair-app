"""Resolve testing-mode intake to one active Support office site, without dispatch."""
from sqlmodel import Session, select

from .models import ParentAccountSite, Tenant
from .tenant_scope import without_scope


def testing_inbox_tenant_id(session: Session, parent_id):
    # Do not reuse the production escalation selector: it can name an operator.
    # Ambiguous/missing HQ membership must fail explicitly rather than pick a shop.
    with without_scope(session):
        tenants = session.exec(select(Tenant).join(ParentAccountSite, ParentAccountSite.tenant_id == Tenant.id)
            .where(ParentAccountSite.parent_account_id == parent_id)
            .where(ParentAccountSite.network_role == "hq")
            .where(Tenant.is_active == True).where(Tenant.merged_into_tenant_id == None)).all()  # noqa: E711, E712
    return tenants[0].id if len(tenants) == 1 else None
