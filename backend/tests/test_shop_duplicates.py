"""One site per shop number: listing, retiring and the guardrails."""
import json
from uuid import uuid4

import pytest
from fastapi import HTTPException
from sqlmodel import Session, select

from app.database import engine
from app.minit_mv_merge import MvMergeError
from app.models import (Customer, MobileSuburbRoute, ParentAccount, ParentAccountEventLog, ParentAccountSite,
                        ParentMobileReportingSource, Tenant, User)
from app.shop_duplicates import find_duplicate_groups, retire_duplicate, shop_number_conflict
from app.shop_number import assert_shop_number_unique_in_parent


@pytest.fixture
def dup():
    suffix = uuid4().hex[:10]
    number = str(int(suffix[:6], 16))
    with Session(engine) as db:
        parent = ParentAccount(name=f"Network {suffix}", owner_email=f"hq{suffix}@example.test")
        keep = Tenant(name=f"Pro {suffix}", slug=f"pro-{suffix}", plan_code="pro", shop_number=number)
        gone = Tenant(name=f"Operator {suffix}", slug=f"op-{suffix}", plan_code="basic_auto_key", shop_number=number)
        db.add_all([parent, keep, gone])
        db.flush()
        actor = User(tenant_id=keep.id, email=f"sam{suffix}@example.test", full_name="Sam", role="owner", password_hash="x")
        dave = User(tenant_id=gone.id, email=f"dave{suffix}@bad.test", full_name="Dave", role="owner", password_hash="x")
        db.add_all([actor, dave,
                    ParentAccountSite(parent_account_id=parent.id, tenant_id=keep.id, network_role="retail"),
                    ParentAccountSite(parent_account_id=parent.id, tenant_id=gone.id, network_role="operator")])
        route = MobileSuburbRoute(parent_account_id=parent.id, target_tenant_id=gone.id, state_code="VIC",
                                  suburb_normalized=suffix)
        db.add(route)
        db.commit()
        yield db, parent, keep, gone, actor, dave, route


def token(db, parent, gone, keep):
    group = find_duplicate_groups(db, parent, {keep.id})[0]
    return next(m for m in group["members"] if m["tenant_id"] == gone.id)["preview_token"]


def test_group_listed_with_one_row_per_site(dup):
    db, parent, keep, gone, *_ = dup
    groups = find_duplicate_groups(db, parent)
    assert len(groups) == 1 and {m["tenant_id"] for m in groups[0]["members"]} == {keep.id, gone.id}


def test_retire_moves_routes_and_users_and_keeps_everything(dup):
    db, parent, keep, gone, actor, dave, route = dup
    result = retire_duplicate(db, parent=parent, keep_tenant_id=keep.id, retire_tenant_id=gone.id, actor=actor,
                              expected_preview_token=token(db, parent, gone, keep), move_user_ids=[dave.id],
                              user_email_overrides={dave.id: "Dave@Good.test"})
    assert result["users_moved"] == 1
    db.refresh(route); db.refresh(gone); db.refresh(dave)
    assert route.target_tenant_id == keep.id
    assert not gone.is_active and gone.merged_into_tenant_id == keep.id
    assert dave.tenant_id == keep.id and dave.email == "dave@good.test" and dave.role == "manager"
    assert db.get(Tenant, gone.id) is not None
    assert find_duplicate_groups(db, parent) == []
    event = db.exec(select(ParentAccountEventLog).where(ParentAccountEventLog.event_type == "duplicate_shop_retired")).one()
    assert json.loads(event.details_json)["moved_users"][0]["to_email"] == "dave@good.test"


def test_duplicate_with_real_records_is_blocked(dup):
    db, parent, keep, gone, actor, *_ = dup
    db.add(Customer(tenant_id=gone.id, full_name="Real customer"))
    db.commit()
    member = next(m for m in find_duplicate_groups(db, parent, {keep.id})[0]["members"] if m["tenant_id"] == gone.id)
    assert member["blockers"]
    with pytest.raises(MvMergeError):
        retire_duplicate(db, parent=parent, keep_tenant_id=keep.id, retire_tenant_id=gone.id, actor=actor,
                         expected_preview_token=member["preview_token"])
    db.rollback(); db.refresh(gone)
    assert gone.is_active


def test_stale_token_rejected(dup):
    db, parent, keep, gone, actor, *_ = dup
    with pytest.raises(MvMergeError, match="Preview changed"):
        retire_duplicate(db, parent=parent, keep_tenant_id=keep.id, retire_tenant_id=gone.id, actor=actor,
                         expected_preview_token="0" * 64)


def test_kept_account_may_be_reporting_linked_only(dup):
    """Chadstone shape: the account that stays is a reporting link, the operator site is retired."""
    db, parent, keep, gone, actor, *_ = dup
    db.add(ParentMobileReportingSource(parent_account_id=parent.id, tenant_id=keep.id, enabled=True))
    db.commit()
    retire_duplicate(db, parent=parent, keep_tenant_id=keep.id, retire_tenant_id=gone.id, actor=actor,
                     expected_preview_token=token(db, parent, gone, keep))
    src = db.exec(select(ParentMobileReportingSource).where(ParentMobileReportingSource.tenant_id == keep.id)).one()
    assert src.enabled
    assert find_duplicate_groups(db, parent) == []


def test_retiring_a_reporting_linked_record_is_blocked(dup):
    db, parent, keep, gone, actor, *_ = dup
    db.add(ParentMobileReportingSource(parent_account_id=parent.id, tenant_id=gone.id, enabled=True))
    db.commit()
    member = next(m for m in find_duplicate_groups(db, parent, {keep.id})[0]["members"] if m["tenant_id"] == gone.id)
    assert member["blockers"]


def test_conflict_guard_and_message(dup):
    db, parent, keep, gone, *_ = dup
    assert shop_number_conflict(db, parent.id, keep.shop_number, ignore_tenant_id=keep.id)
    with pytest.raises(HTTPException) as exc:
        assert_shop_number_unique_in_parent(db, parent_id=parent.id, shop_number=keep.shop_number)
    assert exc.value.status_code == 409 and "Duplicate shop numbers" in exc.value.detail
