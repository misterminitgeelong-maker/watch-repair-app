"""Minit HQ support access into a linked shop.

The capability exists because HQ *loses* a shop the moment that shop accepts its
invite: ``complete_shop_owner_invite`` rewrites the shared owner row's email, and
the shop drops out of HQ's site list. The better onboarding went, the less of the
network HQ could see, and the only way in was ``platform_admin``.

These tests are mostly about the boundaries rather than the happy path, because
this is an impersonation endpoint. The interesting cases are all the ones where
it must refuse.
"""
from __future__ import annotations

from uuid import uuid4

import pytest
from sqlmodel import Session, select

from app.database import engine
from app.minit_branding import MINIT_HQ_PLAN, MINIT_HQ_SLUG
from app.minit_provision import ensure_minit_pilot_account, import_minit_shops
from app.minit_shops import MinitShopRow
from app.models import ParentAccount, ParentAccountMembership, Tenant, TenantEventLog, User
from app.security import decode_access_token, hash_password

HQ_EMAIL = "hq-enter@test.mainspring.au"
HQ_PASSWORD = "MinitPilot2026!"


@pytest.fixture
def minit_network(client):
    """An HQ with two linked Minit shops, one of which has its own login."""
    with Session(engine) as session:
        ensure_minit_pilot_account(
            session,
            parent_name="Mister Minit",
            hq_tenant_slug=MINIT_HQ_SLUG,
            hq_tenant_name="Mister Minit HQ",
            hq_owner_email=HQ_EMAIL,
            hq_owner_password=HQ_PASSWORD,
        )
        import_minit_shops(
            session,
            parent_name="Mister Minit",
            hq_owner_email=HQ_EMAIL,
            shops=[
                MinitShopRow(shop_number="8001", name="Shop A", area="AREA 1", region="VIC"),
                MinitShopRow(shop_number="8002", name="Shop B", area="AREA 1", region="VIC"),
            ],
            apply=True,
        )
        shop_a = session.exec(select(Tenant).where(Tenant.slug == "minit-8001")).first()
        shop_b = session.exec(select(Tenant).where(Tenant.slug == "minit-8002")).first()

        # Shop B accepts its invite: the shared owner row now has its own email,
        # which is exactly what used to remove HQ's access.
        owner_b = session.exec(select(User).where(User.tenant_id == shop_b.id)).first()
        owner_b.email = "shop-b-owner@example.com"
        owner_b.password_hash = hash_password("ShopOwner2026!")
        session.add(owner_b)

        # The conftest truncates per *module*, not per test, and this fixture is
        # idempotent, so a test that deactivates a shop would otherwise leak into
        # every test after it. Put both shops back in service each time.
        for shop in (shop_a, shop_b):
            shop.is_active = True
            session.add(shop)
        session.commit()
        ids = (shop_a.id, shop_b.id)
    return ids


def _enter_event_count(tenant_id) -> int:
    with Session(engine) as session:
        return len(session.exec(
            select(TenantEventLog)
            .where(TenantEventLog.tenant_id == tenant_id)
            .where(TenantEventLog.event_type == "minit_hq_enter_shop")
        ).all())


def _hq_headers(client) -> dict[str, str]:
    res = client.post(
        "/v1/auth/login",
        json={"tenant_slug": MINIT_HQ_SLUG, "email": HQ_EMAIL, "password": HQ_PASSWORD},
    )
    assert res.status_code == 200, res.text
    return {"Authorization": f"Bearer {res.json()['access_token']}"}


def _enter(client, headers, tenant_id):
    return client.post(f"/v1/parent-accounts/me/sites/{tenant_id}/enter", headers=headers)


# ── the capability ────────────────────────────────────────────────────────────


def test_hq_can_open_a_shop_that_has_taken_its_own_login(client, minit_network):
    """The regression this endpoint exists for."""
    _shop_a, shop_b = minit_network
    res = _enter(client, _hq_headers(client), shop_b)

    assert res.status_code == 200, res.text
    body = res.json()
    assert body["tenant_id"] == str(shop_b)
    assert body["tenant_slug"] == "minit-8002"
    assert body["shop_number"] == "8002"


def test_the_issued_token_is_scoped_to_the_shop_not_to_hq(client, minit_network):
    _shop_a, shop_b = minit_network
    body = _enter(client, _hq_headers(client), shop_b).json()

    claims = decode_access_token(body["access_token"])
    assert claims.tenant_id == shop_b, "token must be scoped to the shop being supported"


def test_the_session_is_short_lived_and_cannot_be_extended(client, minit_network):
    """No refresh token, so the 30-minute window is the whole window."""
    _shop_a, shop_b = minit_network
    body = _enter(client, _hq_headers(client), shop_b).json()

    assert body["refresh_token"] == ""
    assert body["refresh_expires_in_seconds"] == 0
    assert 0 < body["expires_in_seconds"] <= 30 * 60


def test_the_token_actually_works_against_the_shops_data(client, minit_network):
    _shop_a, shop_b = minit_network
    body = _enter(client, _hq_headers(client), shop_b).json()
    headers = {"Authorization": f"Bearer {body['access_token']}"}

    me = client.get("/v1/auth/session", headers=headers)
    assert me.status_code == 200, me.text
    assert me.json()["tenant_id"] == str(shop_b)


# ── the boundaries ────────────────────────────────────────────────────────────


def test_entering_is_written_to_the_shops_own_event_log(client, minit_network):
    """Support access the supported party cannot see is surveillance."""
    _shop_a, shop_b = minit_network
    before = _enter_event_count(shop_b)
    _enter(client, _hq_headers(client), shop_b)

    with Session(engine) as session:
        events = session.exec(
            select(TenantEventLog)
            .where(TenantEventLog.tenant_id == shop_b)
            .where(TenantEventLog.event_type == "minit_hq_enter_shop")
            .order_by(TenantEventLog.created_at)
        ).all()
    # One event per entry, counted as a delta: module-scoped truncation means
    # earlier tests in this file have already entered this shop.
    assert len(events) == before + 1
    assert HQ_EMAIL in (events[-1].actor_email or "")
    assert "minit-8002" in (events[-1].event_summary or "")


def test_hq_cannot_enter_a_shop_in_someone_elses_network(client, minit_network):
    """Linked to *a* parent account is not the same as linked to mine."""
    shop_a, _shop_b = minit_network
    with Session(engine) as session:
        rival = ParentAccount(id=uuid4(), name="Rival Group", owner_email="rival@example.com")
        session.add(rival)
        session.commit()
        outsider = Tenant(name="Outsider", slug=f"minit-9{uuid4().hex[:4]}", plan_code="booking_only")
        session.add(outsider)
        session.commit()
        session.refresh(outsider)
        owner = User(
            tenant_id=outsider.id, email=f"outsider-{uuid4().hex[:6]}@example.com",
            full_name="Outsider", role="owner", password_hash=hash_password("x" * 12),
        )
        session.add(owner)
        session.commit()
        session.refresh(owner)
        session.add(ParentAccountMembership(
            parent_account_id=rival.id, tenant_id=outsider.id, user_id=owner.id))
        session.commit()
        outsider_id = outsider.id

    res = _enter(client, _hq_headers(client), outsider_id)
    # 404 rather than 403: HQ should not learn that the shop exists.
    assert res.status_code == 404, res.text


def test_hq_cannot_enter_a_tenant_that_is_not_a_minit_shop(client, minit_network):
    """This is deliberately a Minit capability, not a general parent-account one."""
    shop_a, _shop_b = minit_network
    with Session(engine) as session:
        # A non-Minit tenant linked into the same parent account.
        parent = session.exec(
            select(ParentAccount).where(ParentAccount.owner_email == HQ_EMAIL)
        ).first()
        other = Tenant(name="Regular Shop", slug=f"regular-{uuid4().hex[:6]}", plan_code="pro")
        session.add(other)
        session.commit()
        session.refresh(other)
        owner = User(
            tenant_id=other.id, email=f"regular-{uuid4().hex[:6]}@example.com",
            full_name="Owner", role="owner", password_hash=hash_password("x" * 12),
        )
        session.add(owner)
        session.commit()
        session.refresh(owner)
        session.add(ParentAccountMembership(
            parent_account_id=parent.id, tenant_id=other.id, user_id=owner.id))
        session.commit()
        other_id = other.id

    res = _enter(client, _hq_headers(client), other_id)
    assert res.status_code == 403
    assert "Minit" in res.json()["detail"]


def test_a_shop_owner_cannot_use_this_to_enter_another_shop(client, minit_network):
    """The gate is Minit HQ, not merely being an owner somewhere in the network."""
    shop_a, _shop_b = minit_network
    res = client.post(
        "/v1/auth/login",
        json={
            "tenant_slug": "minit-8002",
            "email": "shop-b-owner@example.com",
            "password": "ShopOwner2026!",
        },
    )
    assert res.status_code == 200, res.text
    headers = {"Authorization": f"Bearer {res.json()['access_token']}"}

    assert _enter(client, headers, shop_a).status_code in (403, 404)


def test_a_multi_site_operator_who_is_not_minit_hq_cannot_enter_a_minit_shop(
    client, minit_network
):
    """The gate that is actually load-bearing here.

    A shop owner is already stopped one layer earlier: the router requires the
    ``multi_site`` feature and Minit shops are ``booking_only``. ``pro`` has every
    feature, so a generic multi-site operator sails through that gate and reaches
    the endpoint -- they are what ``_require_minit_hq`` is for. Removing that call
    leaves every other test in this file passing; this one is the test that bites.
    """
    shop_a, _shop_b = minit_network
    email = f"rival-hq-{uuid4().hex[:6]}@example.com"
    password = "RivalGroup2026!"
    with Session(engine) as session:
        rival_tenant = Tenant(
            name="Rival Multi-Site", slug=f"rival-{uuid4().hex[:6]}", plan_code="pro"
        )
        session.add(rival_tenant)
        session.commit()
        session.refresh(rival_tenant)
        rival_owner = User(
            tenant_id=rival_tenant.id, email=email, full_name="Rival HQ",
            role="owner", password_hash=hash_password(password),
        )
        session.add(rival_owner)
        session.commit()
        session.refresh(rival_owner)
        parent = ParentAccount(id=uuid4(), name="Rival Multi-Site Group", owner_email=email)
        session.add(parent)
        session.commit()
        session.add(ParentAccountMembership(
            parent_account_id=parent.id, tenant_id=rival_tenant.id, user_id=rival_owner.id))
        session.commit()
        rival_slug = rival_tenant.slug

    res = client.post(
        "/v1/auth/login",
        json={"tenant_slug": rival_slug, "email": email, "password": password},
    )
    assert res.status_code == 200, res.text
    headers = {"Authorization": f"Bearer {res.json()['access_token']}"}

    entered = _enter(client, headers, shop_a)
    assert entered.status_code == 403, entered.text
    assert "Minit" in entered.json()["detail"]


def test_entering_an_unknown_shop_is_a_404(client, minit_network):
    assert _enter(client, _hq_headers(client), uuid4()).status_code == 404


def test_a_deactivated_shop_cannot_be_entered(client, minit_network):
    shop_a, _shop_b = minit_network
    with Session(engine) as session:
        t = session.get(Tenant, shop_a)
        t.is_active = False
        session.add(t)
        session.commit()

    res = _enter(client, _hq_headers(client), shop_a)
    assert res.status_code == 400
    assert "deactivated" in res.json()["detail"].lower()
