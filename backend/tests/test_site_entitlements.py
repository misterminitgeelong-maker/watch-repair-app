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
