"""Test helper: HQ asks to link a shop, and the shop's owner accepts.

Linking needs the shop's consent (see routes/parent_accounts.py). Most tests
only care about the linked end state, so this goes through the real request
and accept code paths and hands back the same response shape a direct link
used to return.
"""
import itertools

from sqlmodel import Session, select

from app.database import engine
from app.dependencies import AuthContext
from datetime import datetime, timedelta, timezone

from app.models import ParentAccountSite, ParentLinkRequest, ShopOwnerInvite, Tenant, User
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


def mark_owner_accepted(tenant_id) -> None:
    """Make a linked shop "live": its owner has been invited and accepted."""
    with Session(engine) as session:
        owner = session.exec(
            select(User).where(User.tenant_id == tenant_id).where(User.role == "owner").order_by(User.created_at)
        ).first()
        site = session.exec(select(ParentAccountSite).where(ParentAccountSite.tenant_id == tenant_id)).first()
        now = datetime.now(timezone.utc)
        session.add(
            ShopOwnerInvite(
                tenant_id=tenant_id,
                parent_account_id=site.parent_account_id,
                owner_user_id=owner.id,
                created_by_user_id=owner.id,
                status="completed",
                expires_at=now + timedelta(days=7),
                completed_at=now,
            )
        )
        session.commit()


# Shop numbers become tenant slugs (minit-{number}), which are unique across the
# whole test database. Picking them at random made two tests collide now and then
# ("Shop slug already exists"), so hand out non-overlapping blocks instead.
_shop_number_blocks = itertools.count(1000, 150)


def unique_shop_base() -> int:
    """Start of a block of 150 shop numbers no other test in this run will use."""
    return next(_shop_number_blocks)


def put_operators_in_new_network(*tenant_ids, live: bool = True, lat: float = -37.8136, lng: float = 144.9631):
    """New HQ network containing these tenants as operators (live = invite accepted), each with a
    base location so the Dispatch Pool ring maths includes them. Returns the parent account id."""
    from uuid import uuid4

    from app.models import NETWORK_ROLE_HQ, NETWORK_ROLE_OPERATOR, ParentAccount
    from app.parent_network import link_site

    with Session(engine) as session:
        parent = ParentAccount(name=f"Pool HQ {uuid4().hex[:6]}", owner_email=f"pool-{uuid4().hex[:6]}@test.local")
        session.add(parent)
        session.flush()
        # An HQ-anchored network resolves the operators' role from this network, not
        # from the single-shop network every signup is also placed in.
        hq = Tenant(name="Pool HQ", slug=f"pool-hq-{uuid4().hex[:8]}")
        session.add(hq)
        session.flush()
        link_site(session, parent_id=parent.id, tenant=hq, network_role=NETWORK_ROLE_HQ)
        for tid in tenant_ids:
            tenant = session.get(Tenant, tid)
            tenant.base_lat, tenant.base_lng, tenant.ring_radius_km = lat, lng, 50
            session.add(tenant)
            link_site(session, parent_id=parent.id, tenant=tenant, network_role=NETWORK_ROLE_OPERATOR)
        session.commit()
        parent_id = parent.id
    if live:
        for tid in tenant_ids:
            mark_owner_accepted(tid)
    return parent_id
