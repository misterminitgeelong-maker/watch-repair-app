import os
from datetime import datetime, timezone
from pathlib import Path
from uuid import UUID, uuid4

_TEST_DB = Path(__file__).with_name(f"test_ak_book_{uuid4().hex}.db")
os.environ["DATABASE_URL"] = f"sqlite:///{_TEST_DB.as_posix()}"

from fastapi.testclient import TestClient

from app.database import create_db_and_tables
from app.main import app

create_db_and_tables()
client = TestClient(app)


def _auth_and_customer():
    suffix = uuid4().hex[:8]
    slug = f"akb-{suffix}"
    assert client.post(
        "/v1/auth/bootstrap",
        json={
            "tenant_name": "AK Booking",
            "tenant_slug": slug,
            "owner_email": f"o{suffix}@ak.test",
            "owner_full_name": "Owner",
            "owner_password": "pass123456",
            "plan_code": "basic_auto_key",
        },
    ).status_code == 200
    login = client.post(
        "/v1/auth/login",
        json={"tenant_slug": slug, "email": f"o{suffix}@ak.test", "password": "pass123456"},
    )
    assert login.status_code == 200
    h = {"Authorization": f"Bearer {login.json()['access_token']}"}
    c = client.post("/v1/customers", headers=h, json={"full_name": "Pat", "phone": "0411999888"})
    assert c.status_code == 201
    return h, c.json()["id"]


def test_create_job_with_booking_sms_creates_quote_and_pending_status():
    h, cid = _auth_and_customer()
    when = datetime(2026, 7, 15, 14, 30, tzinfo=timezone.utc).isoformat()
    r = client.post(
        "/v1/auto-key-jobs",
        headers=h,
        json={
            "customer_id": cid,
            "title": "Duplicate key",
            "job_type": "Duplicate Key",
            "scheduled_at": when,
            "job_address": "123 Test St",
            "key_quantity": 1,
            "priority": "normal",
            "status": "awaiting_quote",
            "programming_status": "pending",
            "deposit_cents": 0,
            "cost_cents": 0,
            "apply_suggested_quote": True,
            "send_booking_sms": True,
        },
    )
    assert r.status_code == 201
    job = r.json()
    assert job["status"] == "pending_booking"
    jid = job["id"]
    quotes = client.get(f"/v1/auto-key-jobs/{jid}/quotes", headers=h)
    assert quotes.status_code == 200
    assert len(quotes.json()) == 1


def test_public_confirm_booking():
    h, cid = _auth_and_customer()
    when = datetime(2026, 8, 1, 9, 0, tzinfo=timezone.utc).isoformat()
    r = client.post(
        "/v1/auto-key-jobs",
        headers=h,
        json={
            "customer_id": cid,
            "title": "AKL",
            "job_type": "All Keys Lost",
            "scheduled_at": when,
            "key_quantity": 1,
            "priority": "normal",
            "status": "awaiting_quote",
            "programming_status": "pending",
            "deposit_cents": 0,
            "cost_cents": 0,
            "apply_suggested_quote": True,
            "send_booking_sms": True,
        },
    )
    assert r.status_code == 201
    # Dig token from DB via public GET — need token. Use list jobs? Not exposed.
    from app.database import engine
    from sqlmodel import Session, select
    from app.models import AutoKeyJob

    with Session(engine) as s:
        j = s.exec(select(AutoKeyJob).where(AutoKeyJob.customer_id == UUID(cid))).first()
        token = j.booking_confirmation_token
        jid = str(j.id)
    assert token

    pub = client.get(f"/v1/public/auto-key-booking/{token}")
    assert pub.status_code == 200
    assert pub.json()["job_number"]
    assert pub.json()["quote_total_cents"] > 0

    conf = client.post(f"/v1/public/auto-key-booking/{token}/confirm")
    assert conf.status_code == 200
    assert conf.json()["status"] == "booked"

    job2 = client.get(f"/v1/auto-key-jobs/{jid}", headers=h)
    assert job2.json()["status"] == "booked"
