"""The network administration report.

HQ's existing reporting answers commercial questions -- bookings, leads, jobs.
None of it answers the administrative ones: which shops have taken their own
login, which are still signing in with HQ's shared credential, where an invite
is sitting unused, and who has been into which shop. That is what this report is.

The shared-credential count is the number that matters most: every shop still on
it is one HQ has not actually handed over, and one more site that a single
leaked credential would open.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from uuid import uuid4

import pytest
from sqlalchemy import event
from sqlmodel import Session, select

from app.database import engine
from app.minit_branding import MINIT_HQ_PLAN, MINIT_HQ_SLUG
from app.minit_provision import ensure_minit_pilot_account, import_minit_shops
from app.minit_shops import MinitShopRow
from app.models import ParentAccount, ShopOwnerInvite, Tenant, User
from app.security import hash_password

HQ_EMAIL = "hq-admin-report@test.mainspring.au"
HQ_PASSWORD = "MinitPilot2026!"

ADMIN_URL = "/v1/parent-accounts/me/operations/administration"


def _seed(shop_count: int) -> list[Tenant]:
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
                MinitShopRow(
                    shop_number=str(9100 + i), name=f"Shop {i}", area="AREA 1", region="VIC"
                )
                for i in range(shop_count)
            ],
            apply=True,
        )
        return list(
            session.exec(select(Tenant).where(Tenant.slug.like("minit-91%"))).all()  # type: ignore[attr-defined]
        )


@pytest.fixture
def network(client):
    return _seed(3)


def _headers(client) -> dict[str, str]:
    res = client.post(
        "/v1/auth/login",
        json={"tenant_slug": MINIT_HQ_SLUG, "email": HQ_EMAIL, "password": HQ_PASSWORD},
    )
    assert res.status_code == 200, res.text
    return {"Authorization": f"Bearer {res.json()['access_token']}"}


def _row(body, slug: str):
    return next(r for r in body["shops"] if r["tenant_slug"] == slug)


# ── what it reports ───────────────────────────────────────────────────────────


def test_a_freshly_provisioned_network_is_entirely_on_hqs_credential(client, network):
    """The state the review found: onboarding has not happened yet."""
    body = client.get(ADMIN_URL, headers=_headers(client)).json()

    assert body["shop_total"] == len(body["shops"])
    assert body["own_login_count"] == 0
    assert body["shared_credential_count"] == body["shop_total"]
    assert all(r["has_own_login"] is False for r in body["shops"])


def test_hq_is_not_listed_as_one_of_its_own_shops(client, network):
    """The HQ tenant is linked to its own parent account like any site.

    Its plan carries ``shop_mobile_booking``, so a role derived from billing
    features counted HQ as a retail shop -- and it would have shown up here as a
    shop "still on HQ's credential", which is true and meaningless.
    """
    body = client.get(ADMIN_URL, headers=_headers(client)).json()

    assert all(r["tenant_slug"] != MINIT_HQ_SLUG for r in body["shops"])


def test_a_shop_that_has_taken_its_own_login_is_counted_as_such(client, network):
    shop = network[0]
    with Session(engine) as session:
        owner = session.exec(select(User).where(User.tenant_id == shop.id)).first()
        owner.email = "independent@example.com"
        session.add(owner)
        session.commit()

    body = client.get(ADMIN_URL, headers=_headers(client)).json()

    assert body["own_login_count"] == 1
    assert body["shared_credential_count"] == body["shop_total"] - 1
    assert _row(body, shop.slug)["has_own_login"] is True


def test_the_shop_that_took_its_own_login_is_still_in_the_report(client, network):
    """The regression the whole review turned on.

    HQ's *site list* is resolved by owner email, so a handed-over shop used to
    vanish from it. An administration report that inherited that behaviour would
    hide precisely the shops it exists to report on.
    """
    shop = network[0]
    with Session(engine) as session:
        owner = session.exec(select(User).where(User.tenant_id == shop.id)).first()
        owner.email = "gone-independent@example.com"
        session.add(owner)
        session.commit()

    before = client.get(ADMIN_URL, headers=_headers(client)).json()["shop_total"]
    body = client.get(ADMIN_URL, headers=_headers(client)).json()

    assert body["shop_total"] == before, "handing a shop over must not shrink the network"
    assert any(r["tenant_slug"] == shop.slug for r in body["shops"])


def test_an_expired_invite_is_reported_as_expired_not_pending(client, network):
    """Stored status is only updated when something loads the invite."""
    shop = network[0]
    with Session(engine) as session:
        parent = session.exec(
            select(ParentAccount).where(ParentAccount.owner_email == HQ_EMAIL)
        ).first()
        owner = session.exec(select(User).where(User.tenant_id == shop.id)).first()
        session.add(ShopOwnerInvite(
            tenant_id=shop.id, parent_account_id=parent.id, owner_user_id=owner.id,
            created_by_user_id=owner.id, status="pending",
            expires_at=datetime.now(timezone.utc) - timedelta(days=1),
        ))
        session.commit()

    body = client.get(ADMIN_URL, headers=_headers(client)).json()

    assert _row(body, shop.slug)["invite_status"] == "expired"
    assert body["invite_expired_count"] == 1
    assert body["invite_pending_count"] == 0


def test_a_live_invite_is_reported_as_pending(client, network):
    shop = network[1]
    with Session(engine) as session:
        parent = session.exec(
            select(ParentAccount).where(ParentAccount.owner_email == HQ_EMAIL)
        ).first()
        owner = session.exec(select(User).where(User.tenant_id == shop.id)).first()
        session.add(ShopOwnerInvite(
            tenant_id=shop.id, parent_account_id=parent.id, owner_user_id=owner.id,
            created_by_user_id=owner.id, status="pending",
            expires_at=datetime.now(timezone.utc) + timedelta(days=3),
        ))
        session.commit()

    body = client.get(ADMIN_URL, headers=_headers(client)).json()

    assert _row(body, shop.slug)["invite_status"] == "pending"
    assert body["invite_pending_count"] == 1


def test_only_the_latest_invite_for_a_shop_is_reported(client, network):
    """Reissuing an invite should not leave the old one speaking for the shop."""
    shop = network[0]
    with Session(engine) as session:
        parent = session.exec(
            select(ParentAccount).where(ParentAccount.owner_email == HQ_EMAIL)
        ).first()
        owner = session.exec(select(User).where(User.tenant_id == shop.id)).first()
        now = datetime.now(timezone.utc)
        session.add(ShopOwnerInvite(
            tenant_id=shop.id, parent_account_id=parent.id, owner_user_id=owner.id,
            created_by_user_id=owner.id, status="revoked",
            created_at=now - timedelta(days=5), expires_at=now + timedelta(days=1),
        ))
        session.add(ShopOwnerInvite(
            tenant_id=shop.id, parent_account_id=parent.id, owner_user_id=owner.id,
            created_by_user_id=owner.id, status="pending",
            created_at=now, expires_at=now + timedelta(days=7),
        ))
        session.commit()

    body = client.get(ADMIN_URL, headers=_headers(client)).json()
    assert _row(body, shop.slug)["invite_status"] == "pending"


def test_a_deactivated_shop_is_counted(client, network):
    shop = network[2]
    with Session(engine) as session:
        t = session.get(Tenant, shop.id)
        t.is_active = False
        session.add(t)
        session.commit()

    body = client.get(ADMIN_URL, headers=_headers(client)).json()

    assert body["inactive_count"] == 1
    assert _row(body, shop.slug)["is_active"] is False


def test_support_entries_are_reported_against_the_shop_they_touched(client, network):
    shop = network[0]
    headers = _headers(client)
    entered = client.post(f"/v1/parent-accounts/me/sites/{shop.id}/enter", headers=headers)
    assert entered.status_code == 200, entered.text

    body = client.get(ADMIN_URL, headers=_headers(client)).json()

    assert _row(body, shop.slug)["last_support_entry_at"] is not None
    recent = body["recent_support_sessions"]
    assert recent, "an entry that happened should be visible to an administrator"
    assert recent[0]["tenant_id"] == str(shop.id)
    assert recent[0]["actor_email"] == HQ_EMAIL


def test_shops_are_ordered_by_shop_number_numerically(client, network):
    body = client.get(ADMIN_URL, headers=_headers(client)).json()
    numbers = [int(r["shop_number"]) for r in body["shops"] if (r["shop_number"] or "").isdigit()]
    assert len(numbers) >= 3
    assert numbers == sorted(numbers), "shop 10 must not sort before shop 9"


# ── the boundaries ────────────────────────────────────────────────────────────


def test_a_non_minit_multi_site_operator_cannot_read_the_report(client, network):
    email = f"rival-{uuid4().hex[:6]}@example.com"
    password = "RivalGroup2026!"
    with Session(engine) as session:
        tenant = Tenant(name="Rival", slug=f"rival-{uuid4().hex[:6]}", plan_code="pro")
        session.add(tenant)
        session.commit()
        session.refresh(tenant)
        session.add(User(
            tenant_id=tenant.id, email=email, full_name="Rival",
            role="owner", password_hash=hash_password(password),
        ))
        session.commit()
        slug = tenant.slug

    res = client.post(
        "/v1/auth/login", json={"tenant_slug": slug, "email": email, "password": password}
    )
    assert res.status_code == 200, res.text
    headers = {"Authorization": f"Bearer {res.json()['access_token']}"}

    assert client.get(ADMIN_URL, headers=headers).status_code == 403


def test_the_report_does_not_n_plus_one_across_shops(client):
    """The flat query count is a property of this dashboard worth keeping.

    Measured rather than asserted from reading the code: the same report over a
    3-shop and a 25-shop network must issue the same number of queries.
    """
    def count_queries(headers) -> int:
        # Warm the connection pool first: a fresh connection runs its own
        # ``SET TIME ZONE`` through the same hook, which otherwise shows up as
        # two phantom queries on whichever measurement happens to open one.
        assert client.get(ADMIN_URL, headers=headers).status_code == 200
        seen = []

        def before(conn, cursor, statement, params, ctx, many):
            seen.append(statement)

        event.listen(engine, "before_cursor_execute", before)
        try:
            res = client.get(ADMIN_URL, headers=headers)
            assert res.status_code == 200, res.text
        finally:
            event.remove(engine, "before_cursor_execute", before)
        return len(seen)

    _seed(3)
    small_headers = _headers(client)
    small_total = client.get(ADMIN_URL, headers=small_headers).json()["shop_total"]
    small = count_queries(small_headers)

    _seed(25)
    headers = _headers(client)
    large_total = client.get(ADMIN_URL, headers=headers).json()["shop_total"]
    assert large_total >= small_total + 20, "the larger network must actually be larger"
    large = count_queries(headers)

    assert large == small, f"query count grew with shop count: {small} -> {large}"


def test_hq_is_not_counted_as_a_retail_shop_on_the_dashboard(client, network):
    """A pre-existing miscount, found while building the report above.

    ``_is_retail_shop`` derives a shop's role from its billing plan, and the
    ``minit_hq`` plan carries ``shop_mobile_booking`` -- so the HQ tenant, which
    is linked to its own parent account like any site, was counted among the
    retail shops. Every network shop count and the VIC region stat were one too
    high, and HQ appeared in its own region breakdown.
    """
    from app.routes.parent_operations import _is_retail_shop

    assert _is_retail_shop(MINIT_HQ_PLAN) is False
    assert _is_retail_shop("booking_only") is True, "real shops must still count"

    body = client.get(
        "/v1/parent-accounts/me/operations/overview", headers=_headers(client)
    ).json()
    admin = client.get(ADMIN_URL, headers=_headers(client)).json()

    # The administration report covers every site with a login -- retail shops
    # and mobile operators alike -- so the two must agree once both are counted.
    assert body["retail_shop_count"] + body["operator_count"] == admin["shop_total"]
