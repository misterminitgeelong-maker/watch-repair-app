"""Safety contracts for consolidating imported vans without moving business records."""
import json
from datetime import date
from uuid import uuid4

import pytest
from sqlalchemy.exc import IntegrityError
from sqlalchemy.sql.dml import Update
from sqlmodel import Session, select

from app.database import engine
from app.models import (Tenant, User, ParentAccount, ParentAccountSite, ParentAccountEventLog,
                        MobileSuburbRoute, MobileKpiDailySnapshot, ProspectLead, Customer,
                        MobileLeadDispatch, ShopMobileBookingRequest)
from app.minit_mv_merge import (find_mv_merge_candidates, merge_mv_into_operator,
                                update_mv_operator, MvMergeError)
from app.parent_network import dispatch_operators_for_parent, operator_tenants_for_parent, link_site
from app.minit_mobile_routing import rank_mobile_operator_candidates


@pytest.fixture
def pair():
    suffix = uuid4().hex[:10]
    with Session(engine) as db:
        parent = ParentAccount(name=f"Network {suffix}", owner_email=f"hq{suffix}@example.test")
        source = Tenant(name=f"Mobile Services {suffix}", slug=f"minit-mobile-{suffix}",
                        plan_code="basic_auto_key", mobile_dispatch_phone="0412345678",
                        shop_phone="0499999999", shop_email="old@example.test", base_lat=-33, base_lng=151)
        mv = Tenant(name=f"{suffix} (MV)", slug=f"minit-{suffix}", plan_code="booking_only",
                    shop_phone="0400000000", shop_email="franchisee@example.test")
        db.add_all([parent, source, mv])
        db.flush()
        actor = User(tenant_id=mv.id, email=f"owner{suffix}@example.test", full_name="Franchisee", role="owner", password_hash="unused")
        db.add(actor)
        db.add(User(tenant_id=source.id, email=f"legacy{suffix}@example.test", full_name="Legacy owner",
                    role="owner", password_hash="unused"))
        db.add_all([ParentAccountSite(parent_account_id=parent.id, tenant_id=source.id, network_role="operator"),
                    ParentAccountSite(parent_account_id=parent.id, tenant_id=mv.id, network_role="retail")])
        route = MobileSuburbRoute(parent_account_id=parent.id, target_tenant_id=source.id,
                                  state_code="NSW", suburb_normalized=suffix)
        db.add(route)
        db.commit()
        from network_link_helpers import mark_owner_accepted
        mark_owner_accepted(source.id)
        mark_owner_accepted(mv.id)
        yield db, parent, source, mv, actor, route


def candidate(pair):
    db, parent, _, mv, _, _ = pair
    return next(c for c in find_mv_merge_candidates(db, parent.id) if c.mv_tenant_id == mv.id)


def merge(pair, **kwargs):
    db, parent, source, mv, actor, _ = pair
    return merge_mv_into_operator(db, parent=parent, mv_tenant_id=mv.id, operator_tenant_id=source.id,
                                  actor=actor, expected_preview_token=candidate(pair).preview_token, **kwargs)


def test_merge_preserves_directory_contacts_and_overlapping_frozen_snapshots(pair):
    db, parent, source, mv, _, route = pair
    snapshots = [MobileKpiDailySnapshot(parent_account_id=parent.id, operator_tenant_id=t.id,
                 trade_date=day, payload_json=json.dumps({"operator_tenant_id": str(t.id), "sales_cents": 100}))
                 for t, day in [(source, date(2026, 9, 28)), (source, date(2026, 9, 29)), (mv, date(2026, 9, 29))]]
    db.add_all(snapshots)
    db.commit()
    original = {s.id: (s.operator_tenant_id, s.payload_json) for s in snapshots}
    merge(pair)
    db.refresh(route)
    assert route.target_tenant_id == mv.id
    assert mv.shop_phone == "0400000000" and mv.shop_email == "franchisee@example.test"
    assert mv.mobile_dispatch_phone == "0412345678" and mv.mobile_dispatch_paused
    assert mv.base_lat == -33 and mv.base_lng == 151
    assert not source.is_active and source.merged_into_tenant_id == mv.id
    assert [t.id for t in operator_tenants_for_parent(db, parent.id)] == [mv.id]
    for sid, values in original.items():
        snapshot = db.get(MobileKpiDailySnapshot, sid)
        db.refresh(snapshot)
        assert (snapshot.operator_tenant_id, snapshot.payload_json) == values
    event = db.exec(select(ParentAccountEventLog).where(ParentAccountEventLog.tenant_id == mv.id)).one()
    manifest = json.loads(event.details_json)
    assert manifest["references"][0]["ids"] == [str(route.id)]
    assert manifest["tenant_before"][str(mv.id)]["shop_email"] == "franchisee@example.test"
    assert manifest["deleted_links"][0]["tenant_id"] == str(source.id)


@pytest.mark.parametrize("kind", ["prospect", "customer", "booking", "json_dispatch", "other_network"])
def test_existing_work_and_foreign_network_references_block_merge(pair, kind):
    db, parent, source, mv, actor, route = pair
    if kind == "prospect":
        db.add(ProspectLead(tenant_id=source.id, name="Unanswered website enquiry"))
    elif kind == "customer":
        db.add(Customer(tenant_id=source.id, full_name="Existing customer"))
    elif kind == "booking":
        db.add(ShopMobileBookingRequest(parent_account_id=parent.id, requesting_tenant_id=mv.id,
               target_operator_tenant_id=source.id, created_by_user_id=actor.id, customer_name="Pending",
               visit_location_type="customer_site", job_address="1 Test Street"))
    elif kind == "json_dispatch":
        db.add(MobileLeadDispatch(parent_account_id=parent.id, suburb="Test", state_code="NSW",
               suburb_normalized="test", payload_json="{}", candidate_operator_ids_json=json.dumps([str(source.id)])))
    else:
        db.add(ParentAccount(name="Other network", owner_email="other@example.test", mobile_lead_default_tenant_id=source.id))
    db.commit()
    assert candidate(pair).blocked
    with pytest.raises(MvMergeError):
        merge(pair)
    db.rollback()
    assert source.is_active and route.target_tenant_id == source.id
    assert mv.plan_code == "booking_only"


def test_stale_preview_is_rejected_without_changing_either_shop(pair):
    db, parent, source, mv, actor, route = pair
    token = candidate(pair).preview_token
    mv.shop_email = "updated@example.test"
    db.add(mv)
    db.commit()
    with pytest.raises(MvMergeError, match="Preview changed"):
        merge_mv_into_operator(db, parent=parent, mv_tenant_id=mv.id, operator_tenant_id=source.id,
                               actor=actor, expected_preview_token=token)
    assert source.is_active and route.target_tenant_id == source.id


def test_classification_is_reported_but_not_routed_or_pool_alerted(pair):
    from app.services.pool_alerts import _eligible_operators
    db, parent, source, mv, actor, route = pair
    mv.base_lat, mv.base_lng = -33, 151
    db.add(mv)
    db.commit()
    update_mv_operator(db, parent=parent, tenant_id=mv.id, actor=actor,
                       expected_preview_token=candidate(pair).preview_token)
    assert mv.plan_code == "booking_only" and mv.mobile_dispatch_paused
    assert {t.id for t in operator_tenants_for_parent(db, parent.id)} == {source.id, mv.id}
    assert [t.id for t in dispatch_operators_for_parent(db, parent.id)] == [source.id]
    assert mv.id not in {t.id for t in _eligible_operators(db)}
    assert rank_mobile_operator_candidates(db, parent_id=parent.id, suburb=route.suburb_normalized,
                                          state_code="NSW") == [source.id]
    with pytest.raises(MvMergeError, match="Resolve the matching"):
        update_mv_operator(db, parent=parent, tenant_id=mv.id, actor=actor, activate=True,
                           dispatch_phone="0400000000", expected_preview_token=candidate(pair).preview_token)


def test_missing_dispatch_is_not_silently_replaced_by_directory_phone(pair):
    db, parent, source, mv, actor, route = pair
    source.mobile_dispatch_phone = None
    db.add(source)
    db.commit()
    c = candidate(pair)
    assert c.dispatch_phone is None and c.shop_phone == "0400000000"
    assert any("dispatch mobile" in issue for issue in c.readiness_issues)
    with pytest.raises(MvMergeError, match="dispatch mobile"):
        merge(pair, activate_dispatch=True)
    merge(pair)
    assert mv.mobile_dispatch_paused
    update_mv_operator(db, parent=parent, tenant_id=mv.id, actor=actor, activate=True,
                       dispatch_phone="0400000000", expected_preview_token=candidate(pair).preview_token)
    assert not mv.mobile_dispatch_paused and mv.mobile_dispatch_phone == "0400000000"
    assert [t.id for t in dispatch_operators_for_parent(db, parent.id)] == [mv.id]


def test_confirmed_merge_enables_only_surviving_mv(pair):
    db, parent, source, mv, _, route = pair
    merge(pair, activate_dispatch=True, dispatch_phone="0400000000")
    assert [t.id for t in dispatch_operators_for_parent(db, parent.id)] == [mv.id]
    assert rank_mobile_operator_candidates(db, parent_id=parent.id, suburb=route.suburb_normalized,
                                          state_code="NSW") == [mv.id]


def test_reference_constraint_failure_rolls_back_without_deleting_rows(pair, monkeypatch):
    db, parent, source, mv, _, route = pair
    parent.mobile_lead_default_tenant_id = source.id
    db.add(parent)
    db.commit()
    execute = db.execute

    def conflict(statement, *args, **kwargs):
        if isinstance(statement, Update) and statement.table.name == "mobilesuburbroute":
            raise IntegrityError("route constraint", {}, Exception("conflict"))
        return execute(statement, *args, **kwargs)

    monkeypatch.setattr(db, "execute", conflict)
    with pytest.raises(MvMergeError, match="no changes saved"):
        merge(pair)
    db.refresh(parent)
    db.refresh(route)
    assert parent.mobile_lead_default_tenant_id == source.id
    assert route.target_tenant_id == source.id and source.is_active
    assert not db.exec(select(ParentAccountEventLog).where(ParentAccountEventLog.tenant_id == mv.id)).all()


def test_retired_operator_cannot_be_relinked_or_reimported(pair):
    from app.minit_provision import import_minit_mobile_operators
    from app.minit_mobile_operators import MobileOperatorSeed, ResolvedMobileOperator
    from app.minit_shops import MinitShopRow
    db, parent, source, mv, actor, _ = pair
    imported = ResolvedMobileOperator(seed=MobileOperatorSeed(shop_number="1234", operator_label=source.name,
              dispatch_phone="0412345678"), tss=MinitShopRow(shop_number="1234", name=source.name, area="NSW", region="NSW"),
              tenant_name=source.name, tenant_slug=source.slug, dispatch_phone="0412345678")
    merge(pair)
    assert link_site(db, parent_id=parent.id, tenant=source) is None
    for apply in (False, True):
        result = import_minit_mobile_operators(db, parent_id=parent.id, hq_owner=actor, operators=[imported], apply=apply)
        assert result["would_create_count"] == 0 and result["would_update_count"] == 0
        assert result["would_skip"][0]["skip_reason"] == "merged_operator"
    assert not source.is_active and mv.name.endswith("(MV)")
