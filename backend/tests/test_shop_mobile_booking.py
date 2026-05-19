import os
from datetime import datetime, timedelta, timezone
from pathlib import Path
from uuid import UUID, uuid4

from sqlmodel import Session

_TEST_DB = Path(__file__).with_name(f"test_shop_mobile_{uuid4().hex}.db")
os.environ["DATABASE_URL"] = f"sqlite:///{_TEST_DB.as_posix()}"
os.environ.setdefault("JWT_SECRET", "test-secret-not-for-production")
os.environ.setdefault("APP_ENV", "test")

from fastapi.testclient import TestClient

from app.database import create_db_and_tables, engine
from app.main import app
from app.models import ShopMobileBookingRequest, Tenant

create_db_and_tables()
client = TestClient(app)


def _bootstrap(slug: str, email: str, plan_code: str) -> dict:
    res = client.post(
        "/v1/auth/bootstrap",
        json={
            "tenant_name": f"Tenant {slug}",
            "tenant_slug": slug,
            "owner_email": email,
            "owner_full_name": "Owner",
            "owner_password": "pass123456",
            "plan_code": plan_code,
        },
    )
    assert res.status_code == 200, res.text
    return res.json()


def _login(slug: str, email: str) -> dict:
    res = client.post(
        "/v1/auth/login",
        json={"tenant_slug": slug, "email": email, "password": "pass123456"},
    )
    assert res.status_code == 200, res.text
    return res.json()


def _headers(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def _setup_parent_network(suffix: str) -> tuple[dict[str, str], dict[str, str], str, str]:
    """HQ (enterprise) links operator + booking_only shop under one parent account."""
    hq_email = f"hq-{suffix}@test.local"
    op_email = f"op-{suffix}@test.local"
    hq_slug = f"hq-{suffix}"
    op_slug = f"op-{suffix}"
    shop_slug = f"shop-{suffix}"

    _bootstrap(hq_slug, hq_email, "enterprise")
    op_boot = _bootstrap(op_slug, op_email, "basic_auto_key")

    hq_h = _headers(_login(hq_slug, hq_email)["access_token"])

    create_shop = client.post(
        "/v1/parent-accounts/me/create-tenant",
        headers=hq_h,
        json={
            "tenant_name": f"Retail Shop {suffix}",
            "tenant_slug": shop_slug,
            "plan_code": "booking_only",
        },
    )
    assert create_shop.status_code == 200, create_shop.text
    shop_site = next(s for s in create_shop.json()["sites"] if s["tenant_slug"] == shop_slug)

    link = client.post(
        "/v1/parent-accounts/me/link-tenant",
        headers=hq_h,
        json={"tenant_slug": op_slug, "owner_email": op_email},
    )
    assert link.status_code == 200, link.text

    shop_h = _headers(_login(shop_slug, hq_email)["access_token"])
    op_h = _headers(_login(op_slug, op_email)["access_token"])
    return shop_h, op_h, shop_site["tenant_id"], op_boot["tenant_id"]


def test_booking_lifecycle_accept_decline_and_cross_parent_forbidden():
    suffix = uuid4().hex[:8]
    shop_h, op_h, _shop_tid, op_tid = _setup_parent_network(suffix)

    outsider_boot = _bootstrap(f"out-{suffix}", f"out-{suffix}@test.local", "basic_auto_key")

    operators = client.get("/v1/shop-mobile-bookings/operators", headers=shop_h)
    assert operators.status_code == 200
    op_list = operators.json()
    assert len(op_list) == 1
    assert op_list[0]["tenant_id"] == op_tid

    create = client.post(
        "/v1/shop-mobile-bookings",
        headers=shop_h,
        json={
            "target_operator_tenant_id": op_tid,
            "customer_name": "Jane Driver",
            "phone": "0411222333",
            "visit_location_type": "customer_site",
            "job_address": "10 George St, Sydney NSW",
            "job_type": "Lockout – Car",
            "notes": "Urgent",
        },
    )
    assert create.status_code == 201, create.text
    booking_id = create.json()["id"]
    assert create.json()["status"] == "pending"

    incoming = client.get("/v1/shop-mobile-bookings", headers=op_h)
    assert incoming.status_code == 200
    assert len(incoming.json()) == 1
    assert incoming.json()[0]["id"] == booking_id

    accept = client.post(f"/v1/shop-mobile-bookings/{booking_id}/accept", headers=op_h)
    assert accept.status_code == 200, accept.text
    body = accept.json()
    assert body["status"] == "accepted"
    assert body["resulting_auto_key_job_id"]
    assert body["resulting_job_number"]

    jobs = client.get("/v1/auto-key-jobs", headers=op_h)
    assert jobs.status_code == 200
    job = next(j for j in jobs.json() if j["id"] == body["resulting_auto_key_job_id"])
    assert job["commission_lead_source"] == "shop_referred"
    assert job["referring_shop_tenant_id"] == create.json()["requesting_tenant_id"]
    assert job["shop_mobile_booking_request_id"] == booking_id

    create2 = client.post(
        "/v1/shop-mobile-bookings",
        headers=shop_h,
        json={
            "target_operator_tenant_id": op_tid,
            "customer_name": "Bob",
            "visit_location_type": "at_shop",
            "job_address": "Shop front",
        },
    )
    assert create2.status_code == 201
    bid2 = create2.json()["id"]
    decline = client.post(
        f"/v1/shop-mobile-bookings/{bid2}/decline",
        headers=op_h,
        json={"decline_reason": "Fully booked"},
    )
    assert decline.status_code == 200
    assert decline.json()["status"] == "declined"
    assert decline.json()["decline_reason"] == "Fully booked"

    forbidden = client.post(
        "/v1/shop-mobile-bookings",
        headers=shop_h,
        json={
            "target_operator_tenant_id": outsider_boot["tenant_id"],
            "customer_name": "X",
            "job_address": "1 Test St",
        },
    )
    assert forbidden.status_code == 403


def test_cancel_pending():
    suffix = uuid4().hex[:8]
    shop_h, op_h, _shop_tid, op_tid = _setup_parent_network(suffix)

    create = client.post(
        "/v1/shop-mobile-bookings",
        headers=shop_h,
        json={
            "target_operator_tenant_id": op_tid,
            "customer_name": "Cancel Me",
            "job_address": "1 Main St",
        },
    )
    assert create.status_code == 201
    bid = create.json()["id"]
    cancel = client.post(f"/v1/shop-mobile-bookings/{bid}/cancel", headers=shop_h)
    assert cancel.status_code == 200
    assert cancel.json()["status"] == "cancelled"

    incoming = client.get("/v1/shop-mobile-bookings?status=pending", headers=op_h)
    assert incoming.status_code == 200
    assert all(r["id"] != bid for r in incoming.json())


def test_shop_booking_usage_endpoint():
    suffix = uuid4().hex[:8]
    shop_h, op_h, shop_tid, op_tid = _setup_parent_network(suffix)
    hq_email = f"hq-{suffix}@test.local"
    hq_h = _headers(_login(f"hq-{suffix}", hq_email)["access_token"])

    month = datetime.now(timezone.utc).strftime("%Y-%m")
    usage_before = client.get(
        f"/v1/parent-accounts/me/shop-booking-usage?month={month}",
        headers=hq_h,
    )
    assert usage_before.status_code == 200, usage_before.text
    assert usage_before.json()["booking_tenant_count"] >= 1

    create = client.post(
        "/v1/shop-mobile-bookings",
        headers=shop_h,
        json={
            "target_operator_tenant_id": op_tid,
            "customer_name": "Usage Test",
            "job_address": "1 Billing St",
        },
    )
    assert create.status_code == 201
    accept = client.post(f"/v1/shop-mobile-bookings/{create.json()['id']}/accept", headers=op_h)
    assert accept.status_code == 200

    usage_after = client.get(
        f"/v1/parent-accounts/me/shop-booking-usage?month={month}",
        headers=hq_h,
    )
    assert usage_after.status_code == 200
    shop_row = next(s for s in usage_after.json()["shops"] if s["tenant_id"] == shop_tid)
    assert shop_row["accepted_bookings_count"] >= 1


def test_pending_booking_expires_after_seven_days():
    suffix = uuid4().hex[:8]
    shop_h, op_h, _shop_tid, op_tid = _setup_parent_network(suffix)

    create = client.post(
        "/v1/shop-mobile-bookings",
        headers=shop_h,
        json={
            "target_operator_tenant_id": op_tid,
            "customer_name": "Stale Request",
            "job_address": "1 Old St",
        },
    )
    assert create.status_code == 201
    booking_id = create.json()["id"]

    with Session(engine) as session:
        row = session.get(ShopMobileBookingRequest, UUID(booking_id))
        assert row is not None
        row.created_at = datetime.now(timezone.utc) - timedelta(days=8)
        session.add(row)
        session.commit()

    listed = client.get("/v1/shop-mobile-bookings", headers=op_h)
    assert listed.status_code == 200
    expired = next(r for r in listed.json() if r["id"] == booking_id)
    assert expired["status"] == "expired"

    accept = client.post(f"/v1/shop-mobile-bookings/{booking_id}/accept", headers=op_h)
    assert accept.status_code == 400


def test_at_shop_uses_tenant_business_address():
    suffix = uuid4().hex[:8]
    shop_h, op_h, shop_tid, op_tid = _setup_parent_network(suffix)

    with Session(engine) as session:
        tenant = session.get(Tenant, UUID(shop_tid))
        assert tenant is not None
        tenant.business_address = "100 Retail Parade, Chadstone VIC"
        session.add(tenant)
        session.commit()

    create = client.post(
        "/v1/shop-mobile-bookings",
        headers=shop_h,
        json={
            "target_operator_tenant_id": op_tid,
            "customer_name": "At Shop Guest",
            "visit_location_type": "at_shop",
            "job_address": "ignored if business address set",
        },
    )
    assert create.status_code == 201
    assert create.json()["job_address"] == "100 Retail Parade, Chadstone VIC"
