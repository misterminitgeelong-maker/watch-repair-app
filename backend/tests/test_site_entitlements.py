"""Entitlements: preview, token-guarded apply, idempotence, usage."""
from uuid import uuid4

import pytest
from sqlmodel import Session, select

from app.database import engine
from app.models import ParentAccount, ParentAccountSite, SiteEntitlement, Tenant, User
from app.site_entitlements import apply_backfill, backfill_token, plan_backfill, usage


@pytest.fixture
def network():
    s = uuid4().hex[:8]
    with Session(engine) as db:
        parent = ParentAccount(name=f"Net {s}", owner_email=f"hq{s}@example.test")
        hq = Tenant(name=f"HQ {s}", slug=f"minit-hq-{s}", plan_code="minit_hq")
        shop = Tenant(name=f"Shop {s}", slug=f"shop-{s}", plan_code="booking_only", shop_number="1111")
        pro = Tenant(name=f"Pro {s}", slug=f"pro-{s}", plan_code="pro", shop_number="2222")
        van = Tenant(name=f"Van {s}", slug=f"van-{s}", plan_code="basic_auto_key", shop_number="3333")
        db.add_all([parent, hq, shop, pro, van])
        db.flush()
        actor = User(tenant_id=hq.id, email=f"a{s}@example.test", full_name="A", role="owner", password_hash="x")
        db.add_all([actor] + [ParentAccountSite(parent_account_id=parent.id, tenant_id=t.id, network_role=r)
                              for t, r in [(hq, "hq"), (shop, "retail"), (pro, "retail"), (van, "operator")]])
        db.commit()
        yield db, parent, actor, shop, pro, van


def kinds(rows):
    return sorted((r["name"].split()[0], r["kind"], r["payer"]) for r in rows)


def test_proposal_follows_plans(network):
    db, parent, *_ = network
    assert kinds(plan_backfill(db, parent)) == sorted([
        ("Shop", "booking", "parent"), ("Pro", "booking", "parent"), ("Pro", "pro", "tenant"),
        ("Van", "mobile_services", "parent")])


def test_apply_needs_matching_token_and_is_idempotent(network):
    db, parent, actor, *_ = network
    with pytest.raises(ValueError):
        apply_backfill(db, parent=parent, actor=actor, expected_token="0" * 64)
    rows = plan_backfill(db, parent)
    assert apply_backfill(db, parent=parent, actor=actor, expected_token=backfill_token(rows)) == 4
    assert plan_backfill(db, parent) == []
    assert usage(db, parent.id) == {"booking": {"parent": 2}, "mobile_services": {"parent": 1}, "pro": {"tenant": 1}}


def test_non_minit_network_gets_no_proposal():
    s = uuid4().hex[:8]
    with Session(engine) as db:
        parent = ParentAccount(name=f"Other {s}", owner_email=f"o{s}@example.test")
        hq = Tenant(name=f"Other HQ {s}", slug=f"other-{s}", plan_code="pro")
        db.add_all([parent, hq]); db.flush()
        db.add(ParentAccountSite(parent_account_id=parent.id, tenant_id=hq.id, network_role="hq")); db.commit()
        assert plan_backfill(db, parent) == []


# ── folding a van into its franchisee's shop ────────────────────────────────

from app.minit_mv_merge import MvMergeError
from app.models import MobileSuburbRoute, ParentAccountEventLog
from app.parent_network import mobile_reporting_tenants_for_parent
from app.shop_duplicates import retire_duplicate, van_preview
import json


@pytest.fixture
def pair():
    s = uuid4().hex[:8]
    n1, n2 = str(int(s[:5], 16) + 100000), str(int(s[3:], 16) + 200000)
    with Session(engine) as db:
        parent = ParentAccount(name=f"Net {s}", owner_email=f"hq{s}@example.test")
        other = ParentAccount(name=f"Franchisee group {s}", owner_email=f"fg{s}@example.test")
        shop = Tenant(name=f"Shop {s}", slug=f"shop-{s}", plan_code="booking_only", shop_number=n1,
                      base_lat=None, shop_phone="")
        van = Tenant(name=f"Mobile Services {s}", slug=f"van-{s}", plan_code="basic_auto_key", shop_number=n2,
                     shop_phone="0400111222", base_lat=-37.8, base_lng=145.0, ring_radius_km=20)
        db.add_all([parent, other, shop, van]); db.flush()
        actor = User(tenant_id=shop.id, email=f"o{s}@example.test", full_name="O", role="owner", password_hash="x")
        dave = User(tenant_id=van.id, email=f"dave{s}@typo.test", full_name="Dave", role="owner", password_hash="x")
        shop_site = ParentAccountSite(parent_account_id=parent.id, tenant_id=shop.id, network_role="retail")
        van_site = ParentAccountSite(parent_account_id=parent.id, tenant_id=van.id, network_role="operator")
        db.add_all([actor, dave, shop_site, van_site,
                    ParentAccountSite(parent_account_id=other.id, tenant_id=van.id, network_role="operator"),
                    MobileSuburbRoute(parent_account_id=parent.id, target_tenant_id=van.id, state_code="VIC",
                                      suburb_normalized=s)])
        db.flush()
        db.add(SiteEntitlement(site_id=van_site.id, parent_account_id=parent.id, kind="mobile_services", payer="parent"))
        db.commit()
        yield db, parent, shop, van, actor, dave, shop_site, n1, n2


def test_van_merge_moves_identity_and_entitlement(pair):
    db, parent, shop, van, actor, dave, shop_site, n1, n2 = pair
    pv = van_preview(db, parent, n1, n2)
    assert any("another network" in b for b in pv["blockers"])  # blocked until Sam allows it
    pv = van_preview(db, parent, n1, n2, allow_other_networks=True)
    assert pv["blockers"] == [] and pv["other_networks"]
    retire_duplicate(db, parent=parent, keep_tenant_id=shop.id, retire_tenant_id=van.id, actor=actor,
                     expected_preview_token=pv["preview_token"], van_mode=True, allow_other_networks=True,
                     move_user_ids=[dave.id], user_email_overrides={dave.id: "Dave@Right.test"})
    db.refresh(shop); db.refresh(van); db.refresh(shop_site); db.refresh(dave)
    assert shop_site.mv_number == n2 and shop.shop_number == n1
    assert shop.base_lat == -37.8 and shop.shop_phone == "0400111222"
    assert not van.is_active and van.merged_into_tenant_id == shop.id
    assert dave.tenant_id == shop.id and dave.email == "dave@right.test" and dave.role == "manager"
    assert db.exec(select(MobileSuburbRoute).where(MobileSuburbRoute.parent_account_id == parent.id)).one().target_tenant_id == shop.id
    assert usage(db, parent.id)["mobile_services"] == {"parent": 1}
    assert shop.id in {t.id for t in mobile_reporting_tenants_for_parent(db, parent.id)}
    ev = db.exec(select(ParentAccountEventLog).where(ParentAccountEventLog.event_type == "van_merged_into_shop")).one()
    assert json.loads(ev.details_json)["ended_entitlements"]


def test_van_with_records_stays_blocked(pair):
    from app.models import Customer
    db, parent, shop, van, actor, *_ , n1, n2 = pair
    db.add(Customer(tenant_id=van.id, full_name="Real")); db.commit()
    pv = van_preview(db, parent, n1, n2, allow_other_networks=True)
    assert pv["blockers"]
    with pytest.raises(MvMergeError):
        retire_duplicate(db, parent=parent, keep_tenant_id=shop.id, retire_tenant_id=van.id, actor=actor,
                         expected_preview_token=pv["preview_token"], van_mode=True, allow_other_networks=True)
    db.rollback(); db.refresh(van)
    assert van.is_active
