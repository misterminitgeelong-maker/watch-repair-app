"""Taking payment in person (EFTPOS / cash) when a Mobile Services job is completed."""
import os
from pathlib import Path
from uuid import uuid4

_TEST_DB = Path(__file__).with_name(f"test_ak_paid_{uuid4().hex}.db")
os.environ.setdefault("DATABASE_URL", f"sqlite:///{_TEST_DB.as_posix()}")

from fastapi.testclient import TestClient

from app.database import create_db_and_tables
from app.main import app

create_db_and_tables()
client = TestClient(app)


def _setup() -> tuple[dict[str, str], str]:
    sfx = uuid4().hex[:8]
    slug = f"akpaid-{sfx}"
    assert client.post("/v1/auth/bootstrap", json={
        "tenant_name": "AK Paid", "tenant_slug": slug, "owner_email": f"o-{sfx}@akpaid.test",
        "owner_full_name": "Owner", "owner_password": "pass123456", "plan_code": "enterprise",
    }).status_code == 200
    token = client.post("/v1/auth/login", json={
        "tenant_slug": slug, "email": f"o-{sfx}@akpaid.test", "password": "pass123456",
    }).json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}
    customer = client.post("/v1/customers", headers=headers, json={"full_name": "Pay Customer", "phone": "0400000000"})
    assert customer.status_code == 201
    job = client.post("/v1/auto-key-jobs", headers=headers, json={
        "customer_id": customer.json()["id"], "title": "Spare key", "key_quantity": 1, "priority": "normal",
        "status": "awaiting_quote", "programming_status": "pending", "deposit_cents": 0, "cost_cents": 15000,
    })
    assert job.status_code == 201
    return headers, job.json()["id"]


def _invoices(headers, job_id):
    return client.get(f"/v1/auto-key-jobs/{job_id}/invoices", headers=headers).json()


def test_completing_with_eftpos_marks_invoice_paid_and_job_invoice_paid():
    headers, job_id = _setup()
    res = client.post(f"/v1/auto-key-jobs/{job_id}/status", headers=headers,
                      json={"status": "work_completed", "payment_method": "eftpos"})
    assert res.status_code == 200, res.text
    assert res.json()["invoice_created"] is True
    assert res.json()["status"] == "invoice_paid"
    (inv,) = _invoices(headers, job_id)
    assert inv["status"] == "paid"
    assert inv["payment_method"] == "eftpos"
    assert inv["paid_at"]


def test_completing_without_payment_method_stays_unpaid():
    headers, job_id = _setup()
    res = client.post(f"/v1/auto-key-jobs/{job_id}/status", headers=headers, json={"status": "work_completed"})
    assert res.status_code == 200
    assert res.json()["status"] == "work_completed"
    assert _invoices(headers, job_id)[0]["status"] == "unpaid"


def test_marking_invoice_paid_moves_job_on_and_keeps_original_paid_date():
    headers, job_id = _setup()
    client.post(f"/v1/auto-key-jobs/{job_id}/status", headers=headers, json={"status": "work_completed"})
    (inv,) = _invoices(headers, job_id)

    paid = client.patch(f"/v1/auto-key-jobs/invoices/{inv['id']}", headers=headers,
                        json={"status": "paid", "payment_method": "cash"})
    assert paid.status_code == 200, paid.text
    first_paid_at = paid.json()["paid_at"]
    assert first_paid_at
    assert client.get(f"/v1/auto-key-jobs/{job_id}", headers=headers).json()["status"] == "invoice_paid"

    again = client.patch(f"/v1/auto-key-jobs/invoices/{inv['id']}", headers=headers, json={"status": "paid"})
    assert again.json()["paid_at"] == first_paid_at


def test_invalid_payment_method_rejected():
    headers, job_id = _setup()
    res = client.post(f"/v1/auto-key-jobs/{job_id}/status", headers=headers,
                      json={"status": "work_completed", "payment_method": "bitcoin"})
    assert res.status_code == 422
