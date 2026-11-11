import os
import pytest
from datetime import datetime, timezone
from pathlib import Path
from uuid import UUID, uuid4

_TEST_DB = Path(__file__).with_name(f"test_ak_book_{uuid4().hex}.db")
os.environ.setdefault("DATABASE_URL", f"sqlite:///{_TEST_DB.as_posix()}")

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


@pytest.mark.parametrize(
    "scheduled,utc,changed,changed_utc,local_day",
    [
        ("2026-11-11T09:30:00+11:00", "2026-11-10T22:30:00+00:00", "2026-11-11T14:15:00+11:00", "2026-11-11T03:15:00+00:00", "2026-11-11"),
        ("2026-07-15T09:30:00+10:00", "2026-07-14T23:30:00+00:00", "2026-07-15T14:15:00+10:00", "2026-07-15T04:15:00+00:00", "2026-07-15"),
    ],
)
def test_local_offset_schedule_survives_create_patch_and_shop_day_filter(scheduled, utc, changed, changed_utc, local_day):
    headers, customer = _auth_and_customer()
    response = client.post("/v1/auto-key-jobs", headers=headers, json={
        "customer_id": customer, "title": "Offset scheduling regression", "scheduled_at": scheduled,
    })
    assert response.status_code == 201, response.text
    job = response.json()
    assert datetime.fromisoformat(job["scheduled_at"].replace("Z", "+00:00")) == datetime.fromisoformat(utc)
    fetched = client.get(f"/v1/auto-key-jobs/{job['id']}", headers=headers)
    assert datetime.fromisoformat(fetched.json()["scheduled_at"].replace("Z", "+00:00")) == datetime.fromisoformat(utc)
    page = client.get("/v1/auto-key-jobs/page", headers=headers, params={
        "directory": "all", "date_field": "scheduled", "date_from": local_day, "date_to": local_day,
    })
    assert page.status_code == 200, page.text
    assert job["id"] in {row["id"] for row in page.json()["items"]}
    updated = client.patch(f"/v1/auto-key-jobs/{job['id']}", headers=headers, json={"scheduled_at": changed})
    assert updated.status_code == 200, updated.text
    assert datetime.fromisoformat(updated.json()["scheduled_at"].replace("Z", "+00:00")) == datetime.fromisoformat(changed_utc)
    fetched = client.get(f"/v1/auto-key-jobs/{job['id']}", headers=headers)
    assert datetime.fromisoformat(fetched.json()["scheduled_at"].replace("Z", "+00:00")) == datetime.fromisoformat(changed_utc)


def test_naive_schedule_remains_utc_and_explicit_null_still_clears_it():
    headers, customer = _auth_and_customer()
    response = client.post("/v1/auto-key-jobs", headers=headers, json={
        "customer_id": customer, "title": "UTC scheduling contract", "scheduled_at": "2026-11-10T22:30:00",
    })
    assert response.status_code == 201, response.text
    job = response.json()
    assert job["scheduled_at"] == "2026-11-10T22:30:00Z"
    changed = client.patch(f"/v1/auto-key-jobs/{job['id']}", headers=headers, json={"scheduled_at": "2026-11-11T01:00:00"})
    assert changed.status_code == 200, changed.text
    assert changed.json()["scheduled_at"] == "2026-11-11T01:00:00Z"
    cleared = client.patch(f"/v1/auto-key-jobs/{job['id']}", headers=headers, json={"scheduled_at": None})
    assert cleared.status_code == 200, cleared.text
    assert cleared.json()["scheduled_at"] is None


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
    assert job["status"] == "awaiting_booking_confirmation"
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
    assert conf.json()["status"] == "booking_confirmed"

    job2 = client.get(f"/v1/auto-key-jobs/{jid}", headers=h)
    assert job2.json()["status"] == "booking_confirmed"


def test_public_confirm_accepts_legacy_pending_booking_rows():
    """Rows written before the vocabulary tidy-up (pending_booking) still confirm."""
    h, cid = _auth_and_customer()
    r = client.post(
        "/v1/auto-key-jobs",
        headers=h,
        json={
            "customer_id": cid,
            "title": "Legacy pending",
            "key_quantity": 1,
            "priority": "normal",
            "status": "awaiting_quote",
            "programming_status": "pending",
            "deposit_cents": 0,
            "cost_cents": 0,
            "send_booking_sms": True,
        },
    )
    assert r.status_code == 201, r.text
    from app.database import engine
    from sqlmodel import Session, select
    from app.models import AutoKeyJob

    with Session(engine) as s:
        j = s.exec(select(AutoKeyJob).where(AutoKeyJob.id == UUID(r.json()["id"]))).one()
        j.status = "pending_booking"  # what an un-migrated deployment would have stored
        s.add(j)
        s.commit()
        token = j.booking_confirmation_token

    pub = client.get(f"/v1/public/auto-key-booking/{token}")
    assert pub.status_code == 200
    assert pub.json()["awaiting_confirmation"] is True
    assert pub.json()["already_confirmed"] is False

    conf = client.post(f"/v1/public/auto-key-booking/{token}/confirm")
    assert conf.status_code == 200, conf.text
    assert conf.json()["status"] == "booking_confirmed"
    again = client.get(f"/v1/public/auto-key-booking/{token}")
    assert again.json()["already_confirmed"] is True
