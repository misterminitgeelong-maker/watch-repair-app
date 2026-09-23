"""Test helper: HQ asks to link a shop, and the shop's owner accepts.

Linking needs the shop's consent (see routes/parent_accounts.py). Most tests
only care about the linked end state, so this goes through the real request
and accept code paths and hands back the same response shape a direct link
used to return.
"""
from sqlmodel import Session, select

from app.database import engine
from app.dependencies import AuthContext
from app.models import ParentLinkRequest, Tenant, User
from app.routes.parent_accounts import _decide_link_request
from app.tenant_scope import scope_to_tenant


def accept_pending_link(tenant_slug: str) -> None:
    with Session(engine) as session:
        tenant = session.exec(select(Tenant).where(Tenant.slug == tenant_slug.strip().lower())).one()
        owner = session.exec(
            select(User).where(User.tenant_id == tenant.id).where(User.role == "owner").order_by(User.created_at)
        ).first()
        pending = session.exec(
            select(ParentLinkRequest)
            .where(ParentLinkRequest.tenant_id == tenant.id)
            .where(ParentLinkRequest.status == "pending")
        ).all()
        scope_to_tenant(session, tenant.id)
        auth = AuthContext(tenant_id=tenant.id, user_id=owner.id, role="owner")
        for row in pending:
            _decide_link_request(session, auth, row.id, accept=True)


def link_and_accept(client, url, *, headers, json):
    first = client.post(url, headers=headers, json=json)
    if first.status_code != 200:
        return first
    accept_pending_link(json["tenant_slug"])
    return client.post(url, headers=headers, json=json)
