"""The parent-account network model: sites, HQ roles, support access into
shops, network_role, and regions.

Each test here is one of the findings from the cold review of the HQ surface,
written as the behaviour that was missing:

1. HQ can still get into a shop after that shop takes its own login.
2. A (parent, tenant) link is unique and parent resolution is deterministic.
3. More than one person can be HQ, with different access, without sharing an email.
4. Sites and access are separate tables — deleting a user does not unlink a shop.
5. A shop's place in the network survives a plan change.
6. Regions are rows, not strings — "VIC South" and "VIC SOUTH" are one region.
"""

import os
from pathlib import Path
from uuid import UUID, uuid4

_TEST_DB = Path(__file__).with_name(f"test_parent_network_{uuid4().hex}.db")
os.environ.setdefault("DATABASE_URL", f"sqlite:///{_TEST_DB.as_posix()}")
os.environ.setdefault("JWT_SECRET", "test-secret-not-for-production")
os.environ.setdefault("APP_ENV", "test")

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.exc import IntegrityError
from sqlmodel import Session, select

from app.database import create_db_and_tables, engine
from app.main import app
from app.models import (
    ParentAccount,
    ParentAccountEventLog,
    ParentAccountSite,
    ParentAccountUser,
    Region,
    Tenant,
    TenantEventLog,
    User,
)
from app.parent_network import parent_role_for_user, parents_for_user, resolve_common_parent_id
from network_link_helpers import link_and_accept

create_db_and_tables()
client = TestClient(app)

PASSWORD = "pass123456"


def _bootstrap(slug: str, email: str, plan_code: str) -> dict:
    res = client.post(
        "/v1/auth/bootstrap",
        json={
            "tenant_name": f"Tenant {slug}",
            "tenant_slug": slug,
            "owner_email": email,
            "owner_full_name": "Owner",
            "owner_password": PASSWORD,
            "plan_code": plan_code,
        },
    )
    assert res.status_code == 200, res.text
    return res.json()


def _login(slug: str, email: str, password: str = PASSWORD) -> str:
    res = client.post("/v1/auth/login", json={"tenant_slug": slug, "email": email, "password": password})
    assert res.status_code == 200, res.text
    return res.json()["access_token"]


def _h(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def _network(suffix: str) -> dict:
    """A pro-plan HQ tenant (multi_site), one provisioned retail shop sharing HQ's
    login, and one bootstrapped operator linked in."""
    hq_slug = f"hq-{suffix}"
    hq_email = f"hq-{suffix}@net.test"
    hq = _bootstrap(hq_slug, hq_email, "pro")
    hq_h = _h(_login(hq_slug, hq_email))

    shop_slug = f"shop-{suffix}"
    created = client.post(
        "/v1/parent-accounts/me/create-tenant",
        headers=hq_h,
        json={"tenant_name": f"Retail {suffix}", "tenant_slug": shop_slug, "plan_code": "booking_only"},
    )
    assert created.status_code == 200, created.text

    op_slug = f"op-{suffix}"
    op_email = f"op-{suffix}@net.test"
    op = _bootstrap(op_slug, op_email, "basic_auto_key")
    linked = link_and_accept(client,
        "/v1/parent-accounts/me/link-tenant",
        headers=hq_h,
        json={"tenant_slug": op_slug, "owner_email": op_email},
    )
    assert linked.status_code == 200, linked.text

    sites = client.get("/v1/parent-accounts/me/sites", headers=hq_h).json()["sites"]
    by_slug = {s["tenant_slug"]: s for s in sites}
    return {
        "hq": hq_h,
        "hq_slug": hq_slug,
        "hq_email": hq_email,
        "hq_tenant_id": hq["tenant_id"],
        "shop_slug": shop_slug,
        "shop_id": by_slug[shop_slug]["tenant_id"],
        "op_slug": op_slug,
        "op_email": op_email,
        "op_id": op["tenant_id"],
        "sites": by_slug,
    }


# ── 1. HQ support access into a shop that has its own login ──────────────────


def test_hq_can_enter_a_shop_after_it_takes_its_own_login():
    suffix = uuid4().hex[:8]
    net = _network(suffix)

    invite = client.post(f"/v1/parent-accounts/me/sites/{net['shop_id']}/invite", headers=net["hq"])
    assert invite.status_code == 200, invite.text
    token = invite.json()["invite_url"].rsplit("/", 1)[-1]
    new_email = f"franchisee-{suffix}@net.test"
    done = client.post(
        f"/v1/public/shop-invite/{token}/complete",
        json={"full_name": "Real Owner", "email": new_email, "password": "brandnewpass1!"},
    )
    assert done.status_code == 200, done.text

    # The shared login is gone from the switcher — that used to be the end of HQ's access.
    session_info = client.get("/v1/auth/session", headers=net["hq"]).json()
    assert net["shop_slug"] not in {s["tenant_slug"] for s in session_info["available_sites"]}

    # ...but the shop is still a site, and HQ can enter it.
    entered = client.post(f"/v1/parent-accounts/me/sites/{net['shop_id']}/enter", headers=net["hq"])
    assert entered.status_code == 200, entered.text
    body = entered.json()
    assert body["tenant_slug"] == net["shop_slug"]
    assert body["acting_as_email"] == new_email
    assert body["expires_in_seconds"] == 30 * 60
    assert "refresh_token" not in body

    # The token actually works against the shop (unlike the platform-admin one).
    inside = client.get("/v1/auth/session", headers=_h(body["access_token"]))
    assert inside.status_code == 200, inside.text
    assert inside.json()["tenant_slug"] == net["shop_slug"]
    assert inside.json()["user"]["email"] == new_email

    # And it cannot be extended: there is no refresh token to present.
    with Session(engine) as db:
        shop_event = db.exec(
            select(TenantEventLog)
            .where(TenantEventLog.tenant_id == UUID(net["shop_id"]))
            .where(TenantEventLog.event_type == "hq_enter_shop")
        ).first()
        assert shop_event is not None
        assert shop_event.actor_email == net["hq_email"]
        network_event = db.exec(
            select(ParentAccountEventLog).where(ParentAccountEventLog.event_type == "enter_shop")
        ).first()
        assert network_event is not None
        assert network_event.tenant_id == UUID(net["shop_id"])


def test_enter_shop_is_limited_to_linked_sites_and_hq_admins():
    suffix = uuid4().hex[:8]
    net = _network(suffix)

    # An unrelated tenant is not a site of this network.
    other = _bootstrap(f"other-{suffix}", f"other-{suffix}@net.test", "basic_watch")
    res = client.post(f"/v1/parent-accounts/me/sites/{other['tenant_id']}/enter", headers=net["hq"])
    assert res.status_code == 404

    # A viewer can read the network but not walk into its shops.
    viewer_email = f"viewer-{suffix}@net.test"
    made = client.post(
        "/v1/users",
        headers=net["hq"],
        json={"email": viewer_email, "full_name": "Viewer", "password": PASSWORD, "role": "manager"},
    )
    assert made.status_code == 201, made.text
    granted = client.put(
        "/v1/parent-accounts/me/users",
        headers=net["hq"],
        json={"email": viewer_email, "role": "hq_viewer"},
    )
    assert granted.status_code == 200, granted.text
    viewer_h = _h(_login(net["hq_slug"], viewer_email))
    assert client.get("/v1/parent-accounts/me/sites", headers=viewer_h).status_code == 200
    denied = client.post(f"/v1/parent-accounts/me/sites/{net['shop_id']}/enter", headers=viewer_h)
    assert denied.status_code == 403, denied.text


# ── 2. Unique link, deterministic resolution ─────────────────────────────────


def test_a_tenant_cannot_be_linked_to_the_same_parent_twice():
    suffix = uuid4().hex[:8]
    net = _network(suffix)
    with Session(engine) as db:
        parent = db.exec(select(ParentAccount).where(ParentAccount.owner_email == net["hq_email"])).one()
        before = len(db.exec(select(ParentAccountSite).where(ParentAccountSite.parent_account_id == parent.id)).all())
        db.add(ParentAccountSite(parent_account_id=parent.id, tenant_id=UUID(net["shop_id"])))
        with pytest.raises(IntegrityError):
            db.commit()
        db.rollback()
        after = len(db.exec(select(ParentAccountSite).where(ParentAccountSite.parent_account_id == parent.id)).all())
        assert after == before

    # Linking through the API is idempotent rather than duplicating.
    again = link_and_accept(client,
        "/v1/parent-accounts/me/link-tenant",
        headers=net["hq"],
        json={"tenant_slug": net["op_slug"], "owner_email": net["op_email"]},
    )
    assert again.status_code == 200, again.text
    assert again.json()["site_count"] == 3


def test_parent_resolution_is_ordered_when_a_user_is_in_two_networks():
    suffix = uuid4().hex[:8]
    net = _network(suffix)
    with Session(engine) as db:
        hq_user = db.exec(
            select(User).where(User.tenant_id == UUID(net["hq_tenant_id"])).where(User.email == net["hq_email"])
        ).one()
        first = db.exec(select(ParentAccount).where(ParentAccount.owner_email == net["hq_email"])).one()
        # A second, later network that explicitly grants the same person access.
        second = ParentAccount(name=f"Second {suffix}", owner_email=f"someone-else-{suffix}@net.test")
        db.add(second)
        db.flush()
        db.add(ParentAccountUser(parent_account_id=second.id, user_id=hq_user.id, role="hq_admin"))
        db.commit()

        ordered = parents_for_user(db, hq_user)
        # Bootstrap granted hq_admin on the first network; the second grant is
        # newer. Oldest grant first, and every call agrees.
        assert [p.id for p in ordered] == [first.id, second.id]
        assert [p.id for p in parents_for_user(db, hq_user)] == [first.id, second.id]


def test_booking_between_shop_and_operator_is_attributed_to_the_hq_network():
    """A shop can sit in both HQ's network and its franchisee's own group; a
    booking with an HQ-linked operator belongs to HQ's network, not whichever
    parent a set happened to iterate first."""
    suffix = uuid4().hex[:8]
    net = _network(suffix)
    with Session(engine) as db:
        hq_parent = db.exec(select(ParentAccount).where(ParentAccount.owner_email == net["hq_email"])).one()
        hq_site = db.exec(
            select(ParentAccountSite)
            .where(ParentAccountSite.parent_account_id == hq_parent.id)
            .where(ParentAccountSite.tenant_id == UUID(net["hq_tenant_id"]))
        ).one()
        hq_site.network_role = "hq"
        db.add(hq_site)
        # Franchisee group created *earlier* than HQ's parent, containing both tenants.
        fran = ParentAccount(name=f"Fran {suffix}", owner_email=f"fran-{suffix}@net.test")
        db.add(fran)
        db.flush()
        from datetime import datetime, timedelta, timezone

        fran.created_at = hq_parent.created_at - timedelta(days=1)
        db.add(fran)
        for tid in (net["shop_id"], net["op_id"]):
            db.add(ParentAccountSite(parent_account_id=fran.id, tenant_id=UUID(tid)))
        db.commit()

        assert resolve_common_parent_id(db, UUID(net["shop_id"]), UUID(net["op_id"])) == hq_parent.id


# ── 3. Roles: several HQ people, different access, revocation ────────────────


def test_hq_staff_roles_are_implicit_for_the_hq_tenant_and_explicit_elsewhere():
    suffix = uuid4().hex[:8]
    net = _network(suffix)
    with Session(engine) as db:
        parent = db.exec(select(ParentAccount).where(ParentAccount.owner_email == net["hq_email"])).one()
        hq_site = db.exec(
            select(ParentAccountSite)
            .where(ParentAccountSite.parent_account_id == parent.id)
            .where(ParentAccountSite.tenant_id == UUID(net["hq_tenant_id"]))
        ).one()
        hq_site.network_role = "hq"
        db.add(hq_site)
        db.commit()

    me = client.get("/v1/parent-accounts/me", headers=net["hq"]).json()
    assert me["my_role"] == "hq_admin"

    # A manager in the HQ tenant reads but cannot restructure the network.
    mgr_email = f"mgr-{suffix}@net.test"
    made = client.post(
        "/v1/users",
        headers=net["hq"],
        json={"email": mgr_email, "full_name": "Ops Manager", "password": PASSWORD, "role": "manager"},
    )
    assert made.status_code == 201, made.text
    mgr_h = _h(_login(net["hq_slug"], mgr_email))
    assert client.get("/v1/parent-accounts/me", headers=mgr_h).json()["my_role"] == "hq_viewer"
    assert client.get("/v1/parent-accounts/me/sites", headers=mgr_h).status_code == 200
    denied = client.delete(f"/v1/parent-accounts/me/sites/{net['op_id']}", headers=mgr_h)
    assert denied.status_code == 403, denied.text

    # A second *owner* in the HQ tenant is a full admin without sharing an email.
    finance_email = f"finance-{suffix}@net.test"
    made = client.post(
        "/v1/users",
        headers=net["hq"],
        json={"email": finance_email, "full_name": "Finance", "password": PASSWORD, "role": "owner"},
    )
    assert made.status_code == 201, made.text
    finance_h = _h(_login(net["hq_slug"], finance_email))
    assert client.get("/v1/parent-accounts/me", headers=finance_h).json()["my_role"] == "hq_admin"

    # ...and can be demoted to a viewer explicitly, then have that override removed.
    demoted = client.put(
        "/v1/parent-accounts/me/users",
        headers=net["hq"],
        json={"email": finance_email, "role": "hq_viewer"},
    )
    assert demoted.status_code == 200, demoted.text
    assert client.get("/v1/parent-accounts/me", headers=finance_h).json()["my_role"] == "hq_viewer"
    listing = {u["email"]: u for u in demoted.json()}
    assert listing[finance_email]["source"] == "explicit"
    assert listing[mgr_email]["source"] == "hq_site"

    finance_id = listing[finance_email]["user_id"]
    revoked = client.delete(f"/v1/parent-accounts/me/users/{finance_id}", headers=net["hq"])
    assert revoked.status_code == 200, revoked.text
    assert client.get("/v1/parent-accounts/me", headers=finance_h).json()["my_role"] == "hq_admin"

    # A shop's owner can be granted read access to the network from outside HQ.
    op_h = _h(_login(net["op_slug"], net["op_email"]))
    # (basic_auto_key has no multi_site feature, so the router gate stops them regardless)
    assert client.get("/v1/parent-accounts/me", headers=op_h).status_code == 403


def test_changing_the_hq_owners_email_does_not_move_the_network():
    suffix = uuid4().hex[:8]
    net = _network(suffix)
    with Session(engine) as db:
        parent = db.exec(select(ParentAccount).where(ParentAccount.owner_email == net["hq_email"])).one()
        hq_user = db.exec(
            select(User).where(User.tenant_id == UUID(net["hq_tenant_id"])).where(User.email == net["hq_email"])
        ).one()
        hq_site = db.exec(
            select(ParentAccountSite)
            .where(ParentAccountSite.parent_account_id == parent.id)
            .where(ParentAccountSite.tenant_id == UUID(net["hq_tenant_id"]))
        ).one()
        hq_site.network_role = "hq"
        hq_user.email = f"renamed-{suffix}@net.test"
        db.add(hq_site)
        db.add(hq_user)
        db.commit()
        db.refresh(hq_user)
        # No longer matches owner_email, still resolves — by being in the HQ site.
        assert [p.id for p in parents_for_user(db, hq_user)] == [parent.id]
        assert parent_role_for_user(db, parent, hq_user) == "hq_admin"


# ── 4. Sites and access are separate ─────────────────────────────────────────


def test_deleting_a_shop_user_does_not_unlink_the_shop():
    suffix = uuid4().hex[:8]
    net = _network(suffix)
    with Session(engine) as db:
        parent = db.exec(select(ParentAccount).where(ParentAccount.owner_email == net["hq_email"])).one()
        # Add a second user to the shop, then delete them via the users API.
        shop_h = _h(_login(net["shop_slug"], net["hq_email"]))
    made = client.post(
        "/v1/users",
        headers=shop_h,
        json={"email": f"tech-{suffix}@net.test", "full_name": "Tech", "password": PASSWORD, "role": "tech"},
    )
    assert made.status_code == 201, made.text
    gone = client.delete(f"/v1/users/{made.json()['id']}", headers=shop_h)
    assert gone.status_code in (200, 204), gone.text

    with Session(engine) as db:
        site = db.exec(
            select(ParentAccountSite)
            .where(ParentAccountSite.parent_account_id == parent.id)
            .where(ParentAccountSite.tenant_id == UUID(net["shop_id"]))
        ).first()
        assert site is not None
    assert client.get("/v1/parent-accounts/me", headers=net["hq"]).json()["site_count"] == 3


# ── 5. network_role, not plan ────────────────────────────────────────────────


def test_plan_change_does_not_move_a_shop_between_retail_and_operator():
    suffix = uuid4().hex[:8]
    net = _network(suffix)
    assert net["sites"][net["shop_slug"]]["network_role"] == "retail"
    assert net["sites"][net["op_slug"]]["network_role"] == "operator"

    # Bill the operator for something else entirely.
    with Session(engine) as db:
        op = db.get(Tenant, UUID(net["op_id"]))
        op.plan_code = "basic_watch"
        db.add(op)
        db.commit()

    sites = {s["tenant_slug"]: s for s in client.get("/v1/parent-accounts/me/sites", headers=net["hq"]).json()["sites"]}
    assert sites[net["op_slug"]]["plan_code"] == "basic_watch"
    assert sites[net["op_slug"]]["network_role"] == "operator"
    ops = client.get("/v1/parent-accounts/me/sites", headers=net["hq"], params={"plan_kind": "operator"}).json()
    assert {s["tenant_slug"] for s in ops["sites"]} == {net["op_slug"]}

    # And HQ can change what a site is, explicitly, with an audit trail.
    changed = client.patch(
        f"/v1/parent-accounts/me/sites/{net['op_id']}",
        headers=net["hq"],
        json={"network_role": "retail"},
    )
    assert changed.status_code == 200, changed.text
    assert changed.json()["network_role"] == "retail"
    activity = client.get("/v1/parent-accounts/me/activity", headers=net["hq"]).json()
    assert any(e["event_type"] == "site_updated" and "role operator -> retail" in e["event_summary"] for e in activity)


# ── 6. Regions are rows ──────────────────────────────────────────────────────


def test_regions_normalise_tss_strings_and_carry_a_manager():
    suffix = uuid4().hex[:8]
    net = _network(suffix)
    hq_h = net["hq"]

    # Provision two shops whose TSS region strings differ only in case/whitespace.
    for n, region in (("1", "VIC South"), ("2", " vic  south ")):
        with Session(engine) as db:
            pass
        num = str(int(suffix[:4], 16) % 8000 + 1000 + int(n))
        made = client.post(
            "/v1/parent-accounts/me/provision-shop",
            headers=hq_h,
            json={"shop_number": num, "tenant_name": f"Shop {n} {suffix}"},
        )
        assert made.status_code == 200, made.text
        tid = next(s["tenant_id"] for s in made.json()["sites"] if s["shop_number"] == num)
        with Session(engine) as db:
            t = db.get(Tenant, UUID(tid))
            t.minit_region = region
            db.add(t)
            db.commit()
        # Re-linking via PATCH is not how imports set regions; call the import sync directly.
        with Session(engine) as db:
            from app.parent_network import sync_site_region_from_tenant

            parent = db.exec(select(ParentAccount).where(ParentAccount.owner_email == net["hq_email"])).one()
            sync_site_region_from_tenant(db, parent_id=parent.id, tenant=db.get(Tenant, UUID(tid)))
            db.commit()

    regions = client.get("/v1/parent-accounts/me/regions", headers=hq_h).json()
    codes = {r["code"]: r for r in regions}
    assert "VIC SOUTH" in codes
    assert codes["VIC SOUTH"]["site_count"] == 2
    assert len([r for r in regions if r["code"].startswith("VIC")]) == 1

    region_id = codes["VIC SOUTH"]["id"]
    updated = client.patch(
        f"/v1/parent-accounts/me/regions/{region_id}",
        headers=hq_h,
        json={"name": "Victoria South", "manager_name": "Dana", "manager_email": "dana@net.test"},
    )
    assert updated.status_code == 200, updated.text
    assert updated.json()["manager_name"] == "Dana"

    # Sites filter by region code, id or name; the dashboard groups by the row.
    for key in ("VIC SOUTH", region_id, "Victoria South"):
        page = client.get("/v1/parent-accounts/me/sites", headers=hq_h, params={"region": key}).json()
        assert page["total"] == 2, key
        assert all(s["region"] == "Victoria South" for s in page["sites"])
    unassigned = client.get("/v1/parent-accounts/me/sites", headers=hq_h, params={"region": "unassigned"}).json()
    assert net["shop_slug"] in {s["tenant_slug"] for s in unassigned["sites"]}

    # Reassign one site to a new region and delete it: the site becomes unassigned.
    made = client.post("/v1/parent-accounts/me/regions", headers=hq_h, json={"name": "QLD West"})
    assert made.status_code == 200, made.text
    assert made.json()["code"] == "QLD WEST"
    dup = client.post("/v1/parent-accounts/me/regions", headers=hq_h, json={"name": "qld  west"})
    assert dup.status_code == 409
    moved_tid = page["sites"][0]["tenant_id"]
    moved = client.patch(
        f"/v1/parent-accounts/me/sites/{moved_tid}", headers=hq_h, json={"region_id": made.json()["id"]}
    )
    assert moved.status_code == 200, moved.text
    assert moved.json()["region_code"] == "QLD WEST"
    deleted = client.delete(f"/v1/parent-accounts/me/regions/{made.json()['id']}", headers=hq_h)
    assert deleted.status_code == 200, deleted.text
    assert "QLD WEST" not in {r["code"] for r in deleted.json()}
    with Session(engine) as db:
        site = db.exec(select(ParentAccountSite).where(ParentAccountSite.tenant_id == UUID(moved_tid))).one()
        assert site.region_id is None
        assert db.exec(select(Region).where(Region.code == "QLD WEST")).first() is None


# ── 7. "+ Add shop" makes a mobile shop as well as a physical one ────────────


def test_provision_shop_creates_a_mobile_operator_or_a_physical_shop():
    suffix = uuid4().hex[:8]
    net = _network(suffix)
    hq_h = net["hq"]
    base = int(suffix[:4], 16) % 8000 + 1000

    physical_num = str(base + 11)
    made = client.post(
        "/v1/parent-accounts/me/provision-shop",
        headers=hq_h,
        json={"shop_number": physical_num, "tenant_name": f"Shopfront {suffix}"},
    )
    assert made.status_code == 200, made.text
    physical = next(s for s in made.json()["sites"] if s["shop_number"] == physical_num)
    assert physical["network_role"] == "retail"
    assert physical["plan_code"] == "booking_only"

    mobile_num = str(base + 12)
    made = client.post(
        "/v1/parent-accounts/me/provision-shop",
        headers=hq_h,
        json={"shop_number": mobile_num, "tenant_name": f"Van {suffix}", "shop_type": "mobile"},
    )
    assert made.status_code == 200, made.text
    mobile = next(s for s in made.json()["sites"] if s["shop_number"] == mobile_num)
    assert mobile["network_role"] == "operator"
    assert mobile["plan_code"] == "basic_auto_key"

    # The two shops land in the lists HQ browses them by.
    retail = client.get("/v1/parent-accounts/me/sites", headers=hq_h, params={"plan_kind": "retail"}).json()
    operators = client.get("/v1/parent-accounts/me/sites", headers=hq_h, params={"plan_kind": "operator"}).json()
    assert physical_num in {s["shop_number"] for s in retail["sites"]}
    assert mobile_num in {s["shop_number"] for s in operators["sites"]}

    bad = client.post(
        "/v1/parent-accounts/me/provision-shop",
        headers=hq_h,
        json={"shop_number": str(base + 13), "tenant_name": "Nope", "shop_type": "franchise"},
    )
    assert bad.status_code == 400


# ── 8. Owner contact details are visible without opening each shop ───────────


def test_sites_carry_owner_contact_and_flag_the_shared_hq_login():
    suffix = uuid4().hex[:8]
    net = _network(suffix)
    hq_h = net["hq"]

    # A shop provisioned by HQ shares HQ's login — there is no franchisee to invite.
    num = str(int(suffix[:4], 16) % 8000 + 1000 + 21)
    made = client.post(
        "/v1/parent-accounts/me/provision-shop",
        headers=hq_h,
        json={"shop_number": num, "tenant_name": f"Shared {suffix}"},
    )
    assert made.status_code == 200, made.text
    shared = next(s for s in made.json()["sites"] if s["shop_number"] == num)
    assert shared["owner_email"] == net["hq_email"]
    assert shared["owner_is_shared_hq_login"] is True

    # A shop with its own franchisee login reports that owner's email and mobile.
    with Session(engine) as db:
        owner = db.exec(select(User).where(User.tenant_id == UUID(net["op_id"]))).first()
        owner.mobile = "0412 345 678"
        db.add(owner)
        db.commit()

    operators = client.get(
        "/v1/parent-accounts/me/sites", headers=hq_h, params={"plan_kind": "operator"}
    ).json()
    op = next(s for s in operators["sites"] if s["tenant_id"] == net["op_id"])
    assert op["owner_email"] == net["op_email"]
    assert op["owner_mobile"] == "0412 345 678"
    assert op["owner_is_shared_hq_login"] is False


# ── 9. HQ can give a new shop its own owner contact ──────────────────────────


def test_provision_shop_can_take_the_owner_s_own_contact_details():
    suffix = uuid4().hex[:8]
    net = _network(suffix)
    hq_h = net["hq"]
    base = int(suffix[:4], 16) % 8000 + 1000

    num = str(base + 31)
    made = client.post(
        "/v1/parent-accounts/me/provision-shop",
        headers=hq_h,
        json={
            "shop_number": num,
            "tenant_name": f"Owned {suffix}",
            "owner_email": f"Jane.{suffix}@Franchise.test",
            "owner_full_name": "Jane Smith",
            "owner_mobile": "0412 345 678",
        },
    )
    assert made.status_code == 200, made.text
    site = next(s for s in made.json()["sites"] if s["shop_number"] == num)
    assert site["owner_email"] == f"jane.{suffix}@franchise.test"
    assert site["owner_full_name"] == "Jane Smith"
    assert site["owner_mobile"] == "0412 345 678"
    # The whole point: an invite for this shop goes to the operator, not to HQ.
    assert site["owner_is_shared_hq_login"] is False

    # The shop cannot be logged into with HQ's password — it is claimed by invite.
    with Session(engine) as db:
        owner = db.exec(
            select(User).where(User.tenant_id == UUID(site["tenant_id"]))
        ).one()
        hq_owner = db.exec(
            select(User).where(User.email == net["hq_email"]).where(User.tenant_id == UUID(net["hq_tenant_id"]))
        ).one()
        assert owner.password_hash != hq_owner.password_hash

    # Without contact details it still falls back to the shared HQ login.
    plain_num = str(base + 32)
    plain = client.post(
        "/v1/parent-accounts/me/provision-shop",
        headers=hq_h,
        json={"shop_number": plain_num, "tenant_name": f"Plain {suffix}"},
    )
    assert plain.status_code == 200, plain.text
    plain_site = next(s for s in plain.json()["sites"] if s["shop_number"] == plain_num)
    assert plain_site["owner_is_shared_hq_login"] is True

    bad = client.post(
        "/v1/parent-accounts/me/provision-shop",
        headers=hq_h,
        json={"shop_number": str(base + 33), "tenant_name": "Bad", "owner_email": "not-an-email"},
    )
    assert bad.status_code == 400


def test_hq_can_edit_shop_identity_contact_and_viewers_cannot():
    suffix = uuid4().hex[:8]
    net = _network(suffix)
    hq_h = net["hq"]
    shop_email = f"chadstone-{suffix}@minit.test"
    shop_phone = "03 9000 1000"

    patched = client.patch(
        f"/v1/parent-accounts/me/sites/{net['shop_id']}",
        headers=hq_h,
        json={"shop_email": shop_email, "shop_phone": shop_phone},
    )
    assert patched.status_code == 200, patched.text
    assert patched.json()["shop_email"] == shop_email
    assert patched.json()["shop_phone"] == shop_phone

    listed = client.get("/v1/parent-accounts/me/sites", headers=hq_h, params={"plan_kind": "retail"}).json()
    site = next(s for s in listed["sites"] if s["tenant_id"] == net["shop_id"])
    assert site["shop_email"] == shop_email
    assert site["shop_phone"] == shop_phone

    with Session(engine) as db:
        tenant = db.get(Tenant, UUID(net["shop_id"]))
        assert tenant.shop_email == shop_email
        assert tenant.shop_phone == shop_phone

    viewer_email = f"viewer-contact-{suffix}@net.test"
    made = client.post(
        "/v1/users",
        headers=hq_h,
        json={"email": viewer_email, "full_name": "Viewer", "password": PASSWORD, "role": "manager"},
    )
    assert made.status_code == 201, made.text
    granted = client.put(
        "/v1/parent-accounts/me/users",
        headers=hq_h,
        json={"email": viewer_email, "role": "hq_viewer"},
    )
    assert granted.status_code == 200, granted.text
    viewer_h = _h(_login(net["hq_slug"], viewer_email))
    denied = client.patch(
        f"/v1/parent-accounts/me/sites/{net['shop_id']}",
        headers=viewer_h,
        json={"shop_email": "other@minit.test"},
    )
    assert denied.status_code == 403, denied.text


# ── 11. HQ can see whether an invited shop has accepted and is live ─────────


def test_sites_show_whether_the_owner_invite_was_accepted():
    suffix = uuid4().hex[:8]
    net = _network(suffix)
    hq_h = net["hq"]
    num = str(int(suffix[:4], 16) % 8000 + 1000 + 41)

    made = client.post(
        "/v1/parent-accounts/me/provision-shop",
        headers=hq_h,
        json={
            "shop_number": num,
            "tenant_name": f"Invited {suffix}",
            "owner_email": f"owner.{suffix}@franchise.test",
            "owner_full_name": "Owner Person",
        },
    )
    assert made.status_code == 200, made.text
    site = next(s for s in made.json()["sites"] if s["shop_number"] == num)
    assert site["owner_invite_status"] is None
    assert site["owner_last_sign_in_at"] is None

    def current_site():
        sites = client.get("/v1/parent-accounts/me/sites", headers=hq_h, params={"search": num}).json()["sites"]
        return next(s for s in sites if s["tenant_id"] == site["tenant_id"])

    invite = client.post(f"/v1/parent-accounts/me/sites/{site['tenant_id']}/invite", headers=hq_h)
    assert invite.status_code == 200, invite.text
    token = invite.json()["invite_url"].rsplit("/", 1)[-1]

    waiting = current_site()
    assert waiting["owner_invite_status"] == "pending"
    assert waiting["owner_invite_sent_at"] and waiting["owner_invite_expires_at"]
    assert waiting["owner_invite_completed_at"] is None

    done = client.post(
        f"/v1/public/shop-invite/{token}/complete",
        json={"full_name": "Owner Person", "email": f"owner.{suffix}@franchise.test", "password": "Str0ng!Passw0rd"},
    )
    assert done.status_code == 200, done.text

    live = current_site()
    assert live["owner_invite_status"] == "completed"
    assert live["owner_invite_completed_at"]
    # Accepting signs the owner straight in, so the shop shows as used.
    assert live["owner_last_sign_in_at"]
