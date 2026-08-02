"""GST summary report: GST collected on paid watch + mobile invoices."""
import os
from datetime import datetime, timezone
from pathlib import Path
from uuid import UUID, uuid4

_TEST_DB = Path(__file__).with_name(f"test_gst_summary_{uuid4().hex}.db")
os.environ["DATABASE_URL"] = f"sqlite:///{_TEST_DB.as_posix()}"

from fastapi.testclient import TestClient
from sqlmodel import Session

from app.database import create_db_and_tables, engine
from app.main import app
from app.models import AutoKeyInvoice, AutoKeyJob, Customer, Invoice, RepairJob, Watch

create_db_and_tables()
client = TestClient(app)


def _bootstrap() -> tuple[str, str]:
    suffix = uuid4().hex[:8]
    slug = f"gst-{suffix}"
    bootstrap = client.post(
        "/v1/auth/bootstrap",
        json={
            "tenant_name": "GST Reports Co",
            "tenant_slug": slug,
            "owner_email": f"owner-{suffix}@test.com",
            "owner_full_name": "Owner",
            "owner_password": "pass123456",
            "plan_code": "enterprise",
        },
    )
    assert bootstrap.status_code == 200
    tenant_id = bootstrap.json()["tenant_id"]
    login = client.post(
        "/v1/auth/login",
        json={"tenant_slug": slug, "email": f"owner-{suffix}@test.com", "password": "pass123456"},
    )
    assert login.status_code == 200
    return login.json()["access_token"], tenant_id


def _seed(tenant_id: str) -> None:
    tid = UUID(tenant_id)
    with Session(engine) as session:
        customer = Customer(tenant_id=tid, full_name="GST Customer")
        session.add(customer)
        session.commit()
        session.refresh(customer)

        watch = Watch(tenant_id=tid, customer_id=customer.id, brand="Omega")
        session.add(watch)
        session.commit()
        session.refresh(watch)
        job = RepairJob(tenant_id=tid, watch_id=watch.id, job_number="W-GST", title="Service")
        session.add(job)
        session.commit()
        session.refresh(job)

        # Paid watch invoice with GST: $100 + 10% = $110
        session.add(Invoice(
            tenant_id=tid, repair_job_id=job.id, invoice_number="INV-GST-PAID", status="paid",
            subtotal_cents=10000, tax_cents=1000, total_cents=11000, gst_enabled=True,
        ))
        # Unpaid invoice — should be excluded (not a completed sale yet)
        session.add(Invoice(
            tenant_id=tid, repair_job_id=job.id, invoice_number="INV-GST-UNPAID", status="unpaid",
            subtotal_cents=5000, tax_cents=500, total_cents=5500, gst_enabled=True,
        ))
        # Void invoice — should be excluded
        session.add(Invoice(
            tenant_id=tid, repair_job_id=job.id, invoice_number="INV-GST-VOID", status="void",
            subtotal_cents=20000, tax_cents=2000, total_cents=22000, gst_enabled=True,
        ))

        ak_job = AutoKeyJob(tenant_id=tid, customer_id=customer.id, job_number="AK-GST", title="Key cut")
        session.add(ak_job)
        session.commit()
        session.refresh(ak_job)
        # Paid mobile invoice with GST: $200 + 10% = $220
        session.add(AutoKeyInvoice(
            tenant_id=tid, auto_key_job_id=ak_job.id, invoice_number="AKI-GST-PAID", status="paid",
            subtotal_cents=20000, tax_cents=2000, total_cents=22000, gst_enabled=True,
        ))
        session.commit()


def test_gst_summary_sums_paid_invoices_only():
    token, tenant_id = _bootstrap()
    headers = {"Authorization": f"Bearer {token}"}
    _seed(tenant_id)

    res = client.get("/v1/reports/gst-summary", headers=headers)
    assert res.status_code == 200, res.text
    body = res.json()

    assert body["watch"] == {
        "invoice_count": 1, "subtotal_cents": 10000, "gst_cents": 1000, "total_cents": 11000,
    }
    assert body["mobile"] == {
        "invoice_count": 1, "subtotal_cents": 20000, "gst_cents": 2000, "total_cents": 22000,
    }
    assert body["combined"] == {
        "invoice_count": 2, "subtotal_cents": 30000, "gst_cents": 3000, "total_cents": 33000,
    }


def test_gst_summary_filters_by_date_range():
    token, tenant_id = _bootstrap()
    headers = {"Authorization": f"Bearer {token}"}
    tid = UUID(tenant_id)
    with Session(engine) as session:
        customer = Customer(tenant_id=tid, full_name="Dated GST Customer")
        session.add(customer)
        session.commit()
        session.refresh(customer)
        watch = Watch(tenant_id=tid, customer_id=customer.id, brand="Rolex")
        session.add(watch)
        session.commit()
        session.refresh(watch)
        job = RepairJob(tenant_id=tid, watch_id=watch.id, job_number="W-GST-DATED", title="Service")
        session.add(job)
        session.commit()
        session.refresh(job)

        session.add(Invoice(
            tenant_id=tid, repair_job_id=job.id, invoice_number="INV-OLD", status="paid",
            subtotal_cents=1000, tax_cents=100, total_cents=1100, gst_enabled=True,
            created_at=datetime(2026, 1, 5, tzinfo=timezone.utc),
        ))
        session.add(Invoice(
            tenant_id=tid, repair_job_id=job.id, invoice_number="INV-MAY", status="paid",
            subtotal_cents=2000, tax_cents=200, total_cents=2200, gst_enabled=True,
            created_at=datetime(2026, 5, 16, tzinfo=timezone.utc),
        ))
        session.commit()

    res = client.get(
        "/v1/reports/gst-summary",
        headers=headers,
        params={"period": "month", "reference_date": "2026-05-16"},
    )
    assert res.status_code == 200, res.text
    watch = res.json()["watch"]
    assert watch == {"invoice_count": 1, "subtotal_cents": 2000, "gst_cents": 200, "total_cents": 2200}
