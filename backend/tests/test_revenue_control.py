from datetime import datetime, timedelta, timezone
from uuid import UUID, uuid4

import pytest
from sqlmodel import Session, select

from app.database import engine
from app.models import AutoKeyJob, AutoKeyInvoice, AutoKeyQuote, Customer, TenantEventLog, User
from app.routes.revenue_control import _items


@pytest.fixture
def revenue_shop(client, bootstrap_and_login, make_customer):
    auth_headers = {"Authorization": f"Bearer {bootstrap_and_login(plan_code='pro')}"}
    customer_id = UUID(make_customer(auth_headers))
    with Session(engine) as session:
        tenant_id = session.get(Customer, customer_id).tenant_id
        owner = session.exec(select(User).where(User.tenant_id == tenant_id)).first()
        owner_id = owner.id
    return auth_headers, tenant_id, customer_id, owner_id


def job(session, tenant, customer, status="work_completed", **kwargs):
    row = AutoKeyJob(tenant_id=tenant, customer_id=customer, job_number=f"AK-{uuid4().hex[:8]}",
                     title="Revenue test", status=status, **kwargs)
    session.add(row)
    session.flush()
    return row


def invoice(session, tenant, j, amount=50000, **kwargs):
    row = AutoKeyInvoice(tenant_id=tenant, auto_key_job_id=j.id, invoice_number=f"AKI-{uuid4().hex[:8]}", total_cents=amount, **kwargs)
    session.add(row)
    session.flush()
    return row


def test_unpaid_values_do_not_subtract_unallocated_deposits_or_count_paid(client, revenue_shop):
    headers, tenant, customer, _ = revenue_shop
    with Session(engine) as session:
        j = job(session, tenant, customer, deposit_cents=10000)
        invoice(session, tenant, j)
        paid_job = job(session, tenant, customer)
        invoice(session, tenant, paid_job, status="paid")
        session.commit()
    data = client.get("/v1/revenue-control", headers=headers).json()
    assert data["total"] == 1
    assert data["items"][0]["amount_cents"] == 50000
    assert data["items"][0]["deposit_cents"] == 10000
    assert "reconciled" in data["warnings"][0]


def test_followup_schedules_reappears_and_resolves_from_invoice(client, revenue_shop):
    headers, tenant, customer, owner = revenue_shop
    with Session(engine) as session:
        j = job(session, tenant, customer)
        inv = invoice(session, tenant, j)
        inv_id, job_id = inv.id, j.id
        session.commit()
    item = client.get("/v1/revenue-control", headers=headers).json()["items"][0]
    future = datetime.now(timezone.utc) + timedelta(days=2)
    body = dict(expected_version=0, owner_user_id=str(owner), next_follow_up_at=future.isoformat(), note="Customer will pay Friday", contacted=True)
    result = client.put(f"/v1/revenue-control/{item['key']}/follow-up", headers=headers, json=body)
    assert result.status_code == 200, result.text
    assert result.json()["last_contact_at"]
    assert result.json()["version"] == 1
    due = client.get("/v1/revenue-control", headers=headers).json()
    assert due["total"] == 0
    assert next(b for b in due["buckets"] if b["kind"] == "unpaid")["amount_cents"] == 50000
    assert client.get("/v1/revenue-control?state=scheduled", headers=headers).json()["total"] == 1
    # Duplicate/stale save must not overwrite the user's work.
    assert client.put(f"/v1/revenue-control/{item['key']}/follow-up", headers=headers, json=body).status_code == 409
    with Session(engine) as session:
        future_items, _, _ = _items(session, tenant, future + timedelta(minutes=1))
        assert future_items[0].due
        event = session.exec(select(TenantEventLog).where(TenantEventLog.entity_id == job_id, TenantEventLog.event_type == "revenue_follow_up")).one()
        assert "Customer will pay Friday" in event.event_summary
        inv = session.get(AutoKeyInvoice, inv_id)
        inv.status = "paid"
        session.add(inv)
        session.commit()
    assert client.get("/v1/revenue-control?state=all", headers=headers).json()["total"] == 0
    assert client.put(f"/v1/revenue-control/{item['key']}/follow-up", headers=headers, json={**body, "expected_version": 1}).status_code == 404


def test_tenant_isolation_and_owner_validation(client, revenue_shop, bootstrap_and_login):
    headers, tenant, customer, _ = revenue_shop
    other_headers = {"Authorization": f"Bearer {bootstrap_and_login(plan_code='pro')}"}
    with Session(engine) as session:
        job(session, tenant, customer)
        session.commit()
    item = client.get("/v1/revenue-control", headers=headers).json()["items"][0]
    assert client.get("/v1/revenue-control", headers=other_headers).json()["total"] == 0
    assert client.put(f"/v1/revenue-control/{item['key']}/follow-up", headers=other_headers, json={"expected_version": 0}).status_code == 404
    invalid_owner = {"expected_version": 0, "owner_user_id": str(uuid4())}
    assert client.put(f"/v1/revenue-control/{item['key']}/follow-up", headers=headers, json=invalid_owner).status_code == 422
    assert client.get("/v1/revenue-control?owner=bad-id", headers=headers).status_code == 422


def test_latest_quote_and_unknown_amounts_are_explicit(client, revenue_shop):
    headers, tenant, customer, _ = revenue_shop
    now = datetime.now(timezone.utc)
    with Session(engine) as session:
        j = job(session, tenant, customer, status="quote_sent")
        session.add(AutoKeyQuote(tenant_id=tenant, auto_key_job_id=j.id, status="sent", total_cents=90000, created_at=now - timedelta(days=8), sent_at=now - timedelta(days=8)))
        session.add(AutoKeyQuote(tenant_id=tenant, auto_key_job_id=j.id, status="sent", total_cents=40000, created_at=now - timedelta(days=4), sent_at=now - timedelta(days=4)))
        job(session, tenant, customer)
        session.commit()
    data = client.get("/v1/revenue-control?state=all", headers=headers).json()
    quote_items = [i for i in data["items"] if i["kind"] == "quote_followup"]
    assert len(quote_items) == 1
    assert quote_items[0]["amount_cents"] == 40000
    assert next(b for b in data["buckets"] if b["kind"] == "uninvoiced")["unknown_amount_count"] == 1


def test_filters_pagination_and_multiple_exceptions_do_not_duplicate_invoice_value(client, revenue_shop):
    headers, tenant, customer, _ = revenue_shop
    with Session(engine) as session:
        j = job(session, tenant, customer, status="booked")
        invoice(session, tenant, j)
        session.commit()
    data = client.get("/v1/revenue-control?state=all&limit=1", headers=headers).json()
    assert data["total"] == 3
    assert len(data["items"]) == 1
    assert next(b for b in data["buckets"] if b["kind"] == "unpaid")["count"] == 1
    filtered = client.get("/v1/revenue-control?kind=unpaid&state=all", headers=headers).json()
    assert filtered["total"] == 1
    assert client.get("/v1/revenue-control?search=doesnotexist", headers=headers).json()["total"] == 0


def test_calendar_age_and_currency_exclusion(revenue_shop):
    _, tenant, customer, _ = revenue_shop
    # Sep 17 Sydney, but Sep 16 UTC. One local day old despite <24h elapsed.
    now = datetime(2026, 9, 16, 14, 30, tzinfo=timezone.utc)
    with Session(engine) as session:
        j = job(session, tenant, customer)
        invoice(session, tenant, j, created_at=datetime(2026, 9, 16, 13, 30), currency="USD")
        session.commit()
        items, _, warnings = _items(session, tenant, now)
    assert items[0].age_days == 1
    assert items[0].amount_cents is None
    assert any("Non-AUD" in w for w in warnings)


def test_invalid_schedule_and_role_feature_protection(client, revenue_shop, bootstrap_and_login):
    headers, tenant, customer, owner = revenue_shop
    with Session(engine) as session:
        job(session, tenant, customer)
        session.commit()
    item = client.get("/v1/revenue-control", headers=headers).json()["items"][0]
    assert client.put(f"/v1/revenue-control/{item['key']}/follow-up", headers=headers,
                      json={"expected_version": 0, "next_follow_up_at": "2000-01-01T00:00:00Z"}).status_code == 422
    token = bootstrap_and_login(plan_code="basic_watch")
    assert client.get("/v1/revenue-control", headers={"Authorization": f"Bearer {token}"}).status_code == 403
    with Session(engine) as session:
        user = session.get(User, owner)
        user.role = "intake"
        session.add(user)
        session.commit()
    from app.dependencies import invalidate_auth_cache
    invalidate_auth_cache()
    assert client.get("/v1/revenue-control", headers=headers).status_code in {401, 403}
