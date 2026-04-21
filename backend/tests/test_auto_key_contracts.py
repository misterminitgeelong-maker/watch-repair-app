import os
from datetime import datetime, timedelta, timezone
from pathlib import Path
from uuid import UUID, uuid4

from sqlmodel import Session, select

_TEST_DB = Path(__file__).with_name(f"test_auto_key_contracts_{uuid4().hex}.db")
os.environ["DATABASE_URL"] = f"sqlite:///{_TEST_DB.as_posix()}"
os.environ.setdefault("APP_ENV", "test")

from fastapi.testclient import TestClient  # noqa: E402

from app.database import create_db_and_tables, engine  # noqa: E402
from app.main import app  # noqa: E402
from app.models import AutoKeyInvoice, AutoKeyJob  # noqa: E402

create_db_and_tables()
client = TestClient(app)


def _bootstrap_and_login(tenant_slug: str, email: str, password: str) -> str:
    bootstrap_payload = {
        "tenant_name": f"Tenant {tenant_slug}",
        "tenant_slug": tenant_slug,
        "owner_email": email,
        "owner_full_name": "Owner",
        "owner_password": password,
        "plan_code": "enterprise",
    }
    bootstrap_res = client.post("/v1/auth/bootstrap", json=bootstrap_payload)
    assert bootstrap_res.status_code == 200

    login_payload = {
        "tenant_slug": tenant_slug,
        "email": email,
        "password": password,
    }
    login_res = client.post("/v1/auth/login", json=login_payload)
    assert login_res.status_code == 200
    return login_res.json()["access_token"]


def _create_customer(headers: dict[str, str], *, full_name: str = "Contract Customer", phone: str = "0400000000") -> str:
    res = client.post("/v1/customers", headers=headers, json={"full_name": full_name, "phone": phone})
    assert res.status_code == 201
    return res.json()["id"]


def test_quick_intake_contract_and_public_intake_page():
    suffix = uuid4().hex[:8]
    token = _bootstrap_and_login(
        tenant_slug=f"contract-intake-{suffix}",
        email=f"owner-{suffix}@contracts.test",
        password="pass123456",
    )
    headers = {"Authorization": f"Bearer {token}"}

    quick = client.post(
        "/v1/auto-key-jobs/quick-intake",
        headers=headers,
        json={"full_name": "Quick Intake Customer", "phone": "0400123456"},
    )
    assert quick.status_code == 201
    quick_job = quick.json()
    assert quick_job["status"] == "awaiting_customer_details"

    with Session(engine) as s:
        row = s.exec(select(AutoKeyJob).where(AutoKeyJob.id == UUID(quick_job["id"]))).first()
        assert row is not None
        assert row.customer_intake_token
        intake_token = row.customer_intake_token

    intake = client.get(f"/v1/public/auto-key-intake/{intake_token}")
    assert intake.status_code == 200
    payload = intake.json()
    assert payload["job_id"] == quick_job["id"]
    assert payload["job_number"] == quick_job["job_number"]


def test_auto_key_contract_routes_for_sms_and_invoice_update():
    suffix = uuid4().hex[:8]
    token = _bootstrap_and_login(
        tenant_slug=f"contract-routes-{suffix}",
        email=f"owner-{suffix}@contracts.test",
        password="pass123456",
    )
    headers = {"Authorization": f"Bearer {token}"}
    customer_id = _create_customer(headers, full_name="Route Customer", phone="0411222333")

    job = client.post(
        "/v1/auto-key-jobs",
        headers=headers,
        json={
            "customer_id": customer_id,
            "title": "Route contract job",
            "status": "booked",
            "programming_status": "pending",
            "key_quantity": 1,
            "cost_cents": 8800,
            "scheduled_at": (datetime.now(timezone.utc) + timedelta(days=1)).isoformat(),
        },
    )
    assert job.status_code == 201
    job_id = job.json()["id"]

    arrival = client.post(
        f"/v1/auto-key-jobs/{job_id}/arrival-sms",
        headers=headers,
        json={"time_window": "9:00 AM - 11:00 AM"},
    )
    assert arrival.status_code == 200
    assert arrival.json()["ok"] is True

    reminders = client.post("/v1/auto-key-jobs/day-before-reminders", headers=headers)
    assert reminders.status_code == 200
    assert isinstance(reminders.json()["sent"], int)

    complete = client.post(
        f"/v1/auto-key-jobs/{job_id}/status",
        headers=headers,
        json={"status": "work_completed"},
    )
    assert complete.status_code == 200

    invoices = client.get(f"/v1/auto-key-jobs/{job_id}/invoices", headers=headers)
    assert invoices.status_code == 200
    inv_id = invoices.json()[0]["id"]
    patch = client.patch(
        f"/v1/auto-key-jobs/invoices/{inv_id}",
        headers=headers,
        json={"status": "paid", "payment_method": "cash"},
    )
    assert patch.status_code == 200
    assert patch.json()["status"] == "paid"


def test_public_booking_and_invoice_singular_routes():
    suffix = uuid4().hex[:8]
    token = _bootstrap_and_login(
        tenant_slug=f"contract-public-{suffix}",
        email=f"owner-{suffix}@contracts.test",
        password="pass123456",
    )
    headers = {"Authorization": f"Bearer {token}"}
    customer_id = _create_customer(headers, full_name="Public Contract", phone="0400555666")

    create_job = client.post(
        "/v1/auto-key-jobs",
        headers=headers,
        json={
            "customer_id": customer_id,
            "title": "Public contract job",
            "status": "pending_booking",
            "programming_status": "pending",
            "key_quantity": 1,
            "cost_cents": 9900,
        },
    )
    assert create_job.status_code == 201
    job_id = create_job.json()["id"]

    booking_token = uuid4().hex
    with Session(engine) as s:
        job = s.exec(select(AutoKeyJob).where(AutoKeyJob.id == UUID(job_id))).first()
        assert job is not None
        job.booking_confirmation_token = booking_token
        s.add(job)
        s.commit()

    booking = client.get(f"/v1/public/auto-key-booking/{booking_token}")
    assert booking.status_code == 200
    assert booking.json()["job_id"] == job_id

    confirm = client.post(f"/v1/public/auto-key-booking/{booking_token}/confirm")
    assert confirm.status_code == 200

    complete = client.post(
        f"/v1/auto-key-jobs/{job_id}/status",
        headers=headers,
        json={"status": "work_completed"},
    )
    assert complete.status_code == 200

    with Session(engine) as s:
        invoice = s.exec(select(AutoKeyInvoice).where(AutoKeyInvoice.auto_key_job_id == UUID(job_id))).first()
        assert invoice is not None
        assert invoice.customer_view_token
        view_token = invoice.customer_view_token

    public_invoice = client.get(f"/v1/public/auto-key-invoice/{view_token}")
    assert public_invoice.status_code == 200
