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
    assert kinds(plan_backfill(db, parent)["rows"]) == sorted([
        ("Shop", "booking", "parent"), ("Pro", "booking", "parent"), ("Pro", "pro", "tenant"),
        ("Van", "mobile_services", "parent")])


def test_apply_needs_matching_token_and_is_idempotent(network):
    db, parent, actor, *_ = network
    with pytest.raises(ValueError):
        apply_backfill(db, parent=parent, actor=actor, expected_token="0" * 64)
    proposal = plan_backfill(db, parent)
    assert apply_backfill(db, parent=parent, actor=actor, expected_token=backfill_token(proposal)) == 4
    assert plan_backfill(db, parent)["rows"] == []
    assert usage(db, parent.id) == {"booking": {"parent": 2}, "mobile_services": {"parent": 1}, "pro": {"tenant": 1}}


def test_non_minit_network_gets_no_proposal():
    s = uuid4().hex[:8]
    with Session(engine) as db:
        parent = ParentAccount(name=f"Other {s}", owner_email=f"o{s}@example.test")
        hq = Tenant(name=f"Other HQ {s}", slug=f"other-{s}", plan_code="pro")
        db.add_all([parent, hq]); db.flush()
        db.add(ParentAccountSite(parent_account_id=parent.id, tenant_id=hq.id, network_role="hq")); db.commit()
        assert plan_backfill(db, parent)["rows"] == []


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


def test_rules_by_plan_with_skips_comp_and_flags():
    s = uuid4().hex[:8]
    with Session(engine) as db:
        parent = ParentAccount(name=f"Net {s}", owner_email=f"hq{s}@example.test")
        hq = Tenant(name=f"HQ {s}", slug=f"minit-hq-{s}", plan_code="minit_hq")
        van_as_retail = Tenant(name=f"Glendale (MV) {s}", slug=f"mv-{s}", plan_code="basic_auto_key", shop_number="2915")
        placeholder = Tenant(name=f"Mobile Services Baldivis {s}", slug=f"minit-mobile-{s}", plan_code="basic_auto_key", shop_number="6441")
        comped = Tenant(name=f"Baldivis {s}", slug="minit-6441", plan_code="pro", shop_number="6441")
        ignored = Tenant(name=f"MinitR {s}", slug=f"minitr-{s}", plan_code="booking_only", shop_number="0101")
        corporate = Tenant(name=f"Corporate (MV) {s}", slug=f"corp-{s}", plan_code="basic_auto_key", shop_number="4903")
        db.add_all([parent, hq, van_as_retail, placeholder, ignored, corporate])
        existing = db.exec(select(Tenant).where(Tenant.slug == "minit-6441")).first()
        if existing is None:
            db.add(comped)
        db.flush()
        comp_tenant = existing or comped
        for t, r in [(hq, "hq"), (van_as_retail, "retail"), (placeholder, "operator"), (comp_tenant, "retail"),
                     (ignored, "retail"), (corporate, "retail")]:
            db.add(ParentAccountSite(parent_account_id=parent.id, tenant_id=t.id, network_role=r))
        db.commit()
        plan = plan_backfill(db, parent)
        got = sorted((r["shop_number"], r["kind"], r["payer"]) for r in plan["rows"])
        assert ("2915", "mobile_services", "parent") in got and ("2915", "booking", "parent") not in got
        assert ("6441", "booking", "parent") in got and ("6441", "pro", "comp") in got
        assert ("4903", "mobile_services", "parent") in got and ("4903", "booking", "parent") not in got
        skipped = {r["name"] for r in plan["skipped"]}
        assert any("Mobile Services Baldivis" in n for n in skipped) and any(n.startswith("MinitR") for n in skipped)
        assert any(f["shop_number"] == "2915" for f in plan["flagged"])  # role retail, plan operator



# Regression coverage for the 4 Nov reviewed starting grants.
def add_site(db, parent, *, number, plan, role="retail", slug=None, name=None):
    s = uuid4().hex[:8]
    tenant = Tenant(name=name or f"Site {s}", slug=slug or f"site-{s}",
                    plan_code=plan, shop_number=number)
    db.add(tenant); db.flush()
    site = ParentAccountSite(parent_account_id=parent.id, tenant_id=tenant.id, network_role=role)
    db.add(site); db.commit()
    return tenant, site


@pytest.mark.parametrize("number", ["6902", "6903", "8905", "4903", "2915", "8901"])
@pytest.mark.parametrize("plan", ["basic_auto_key", "minit_operator"])
def test_retail_list_vans_only_get_mobile_services(network, number, plan):
    db, parent, *_ = network
    tenant, _ = add_site(db, parent, number=number, plan=plan)
    rows = [r for r in plan_backfill(db, parent)["rows"] if r["tenant_id"] == str(tenant.id)]
    assert [(r["kind"], r["payer"]) for r in rows] == [("mobile_services", "parent")]


@pytest.mark.parametrize("plan", ["basic_watch_auto_key", "basic_shoe_auto_key", "basic_all_tabs"])
def test_dispatch_capable_plans_do_not_imply_mobile_billing(network, plan):
    db, parent, *_ = network
    tenant, _ = add_site(db, parent, number="9876", plan=plan)
    rows = [r for r in plan_backfill(db, parent)["rows"] if r["tenant_id"] == str(tenant.id)]
    assert [(r["kind"], r["payer"]) for r in rows] == [("booking", "parent")]


@pytest.mark.parametrize("number", ["0101", "01111", "3904", "2300"])
def test_ignored_and_unconfirmed_sites_never_granted(network, number):
    db, parent, actor, *_ = network
    tenant, site = add_site(db, parent, number=number, plan="basic_auto_key")
    proposal = plan_backfill(db, parent)
    assert any(r["tenant_id"] == str(tenant.id) for r in proposal["skipped"])
    assert not any(r["tenant_id"] == str(tenant.id) for r in proposal["rows"])
    apply_backfill(db, parent=parent, actor=actor, expected_token=backfill_token(proposal))
    assert not db.exec(select(SiteEntitlement).where(SiteEntitlement.site_id == site.id)).all()


@pytest.mark.parametrize("number", ["2311", "6441", "8833", "8829"])
def test_placeholder_slugs_never_granted(network, number):
    db, parent, *_ = network
    tenant, _ = add_site(db, parent, number=number, plan="pro", slug=f"minit-mobile-{number}",
                         name="Mobile Services placeholder")
    proposal = plan_backfill(db, parent)
    assert not any(r["tenant_id"] == str(tenant.id) for r in proposal["rows"])
    assert any(r["tenant_id"] == str(tenant.id) for r in proposal["skipped"])


def test_pending_review_change_invalidates_confirmation(network):
    db, parent, actor, *_ = network
    tenant, _ = add_site(db, parent, number="2300", plan="basic_auto_key")
    proposal = plan_backfill(db, parent)
    tenant.plan_code = "booking_only"
    db.add(tenant); db.commit()
    updated = plan_backfill(db, parent)
    assert updated["rows"] == proposal["rows"]  # only the review context changed
    with pytest.raises(ValueError, match="Preview changed"):
        apply_backfill(db, parent=parent, actor=actor, expected_token=backfill_token(proposal))
    db.rollback()
    assert not db.exec(select(SiteEntitlement).where(SiteEntitlement.parent_account_id == parent.id)).all()


def test_comped_pro_is_recorded_separately_from_paid_usage(network):
    db, parent, actor, *_ = network
    comped = db.exec(select(Tenant).where(Tenant.slug == "minit-6441")).first()
    if comped is None:
        comped, _ = add_site(db, parent, number="6441", plan="pro", slug="minit-6441")
    else:
        db.add(ParentAccountSite(parent_account_id=parent.id, tenant_id=comped.id, network_role="retail"))
        db.commit()
    proposal = plan_backfill(db, parent)
    apply_backfill(db, parent=parent, actor=actor, expected_token=backfill_token(proposal))
    assert usage(db, parent.id)["pro"] == {"tenant": 1, "comp": 1}
    assert usage(db, parent.id)["booking"]["parent"] == 3


@pytest.mark.parametrize("van_mode", [False, True])
def test_support_office_cannot_be_folded_through_either_route(pair, van_mode):
    from app.shop_duplicates import duplicate_blockers, van_blockers
    db, parent, shop, van, actor, *_ = pair
    shop.shop_number = "4903"
    van.shop_number = "4903"
    db.add_all([shop, van]); db.commit()
    blockers = (van_blockers(db, parent.id, shop, van, allow_other_networks=True) if van_mode
                else duplicate_blockers(db, parent.id, shop, van))
    assert any("Support office van" in b for b in blockers)
    from app.minit_mv_merge import preview_token
    with pytest.raises(MvMergeError, match="Support office van"):
        retire_duplicate(db, parent=parent, keep_tenant_id=shop.id, retire_tenant_id=van.id, actor=actor,
                         expected_preview_token=preview_token(db, parent.id, shop, van, blockers=blockers),
                         van_mode=van_mode, allow_other_networks=True)
    db.rollback(); db.refresh(van)
    assert van.is_active
