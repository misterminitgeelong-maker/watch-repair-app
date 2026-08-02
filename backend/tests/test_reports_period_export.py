"""Period report summary and CSV export (day / week / month / quarter)."""
import os
from datetime import date, datetime, timezone
from pathlib import Path
from uuid import UUID, uuid4

_TEST_DB = Path(__file__).with_name(f"test_period_rpt_{uuid4().hex}.db")
os.environ["DATABASE_URL"] = f"sqlite:///{_TEST_DB.as_posix()}"

from fastapi.testclient import TestClient
from sqlmodel import Session

from app.database import create_db_and_tables, engine
from app.main import app
from app.models import AutoKeyInvoice, AutoKeyJob, Customer, Invoice, RepairJob, Shoe, ShoeRepairJob, ShoeRepairJobItem, Watch
from app.report_periods import resolve_period_bounds

create_db_and_tables()
client = TestClient(app)


def _bootstrap() -> tuple[str, str]:
    suffix = uuid4().hex[:8]
    slug = f"prpt-{suffix}"
    bootstrap = client.post(
        "/v1/auth/bootstrap",
        json={
            "tenant_name": "Period Reports",
            "tenant_slug": slug,
            "owner_email": f"owner-{suffix}@test.com",
            "owner_full_name": "Owner",
            "owner_password": "pass123456",
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


def test_resolve_period_bounds_calendar_week_and_quarter():
    ref = date(2026, 5, 16)  # Saturday
    _, _, start, end = resolve_period_bounds("week", ref)
    assert start == "2026-05-11"
    assert end == "2026-05-17"

    _, _, m_start, m_end = resolve_period_bounds("month", ref)
    assert m_start == "2026-05-01"
    assert m_end == "2026-05-31"

    _, _, q_start, q_end = resolve_period_bounds("quarter", ref)
    assert q_start == "2026-04-01"
    assert q_end == "2026-06-30"

    _, _, d_start, d_end = resolve_period_bounds("day", ref)
    assert d_start == d_end == "2026-05-16"


def test_period_summary_json_and_csv():
    token, _tenant_id = _bootstrap()
    headers = {"Authorization": f"Bearer {token}"}

    res = client.get(
        "/v1/reports/period-summary",
        headers=headers,
        params={"period": "week", "reference_date": "2026-05-16"},
    )
    assert res.status_code == 200, res.text
    body = res.json()
    assert body["period"] == "week"
    assert body["period_start"] == "2026-05-11"
    assert body["period_end"] == "2026-05-17"
    assert "financials" in body
    assert "jobs_opened" in body

    csv_res = client.get(
        "/v1/reports/export/period-summary",
        headers=headers,
        params={"period": "month", "reference_date": "2026-05-16"},
    )
    assert csv_res.status_code == 200
    assert csv_res.headers["content-type"].startswith("text/csv")
    assert "period_start" in csv_res.text
    assert "2026-05-01" in csv_res.text


def test_period_summary_rejects_invalid_period():
    token, _tenant_id = _bootstrap()
    headers = {"Authorization": f"Bearer {token}"}
    res = client.get("/v1/reports/period-summary", headers=headers, params={"period": "year"})
    assert res.status_code == 400


def test_period_summary_billed_includes_shoe_and_excludes_void():
    # Regression: billed_cents in the period report omitted shoe sales entirely, and
    # counted void/refunded invoices as if they were real billed amounts.
    token, tenant_id = _bootstrap()
    headers = {"Authorization": f"Bearer {token}"}
    tid = UUID(tenant_id)
    in_period = datetime(2026, 5, 16, tzinfo=timezone.utc)

    with Session(engine) as session:
        customer = Customer(tenant_id=tid, full_name="Period Customer")
        session.add(customer)
        session.commit()
        session.refresh(customer)

        watch = Watch(tenant_id=tid, customer_id=customer.id, brand="Seiko")
        session.add(watch)
        session.commit()
        session.refresh(watch)
        job = RepairJob(tenant_id=tid, watch_id=watch.id, job_number="W-PERIOD", title="Service")
        session.add(job)
        session.commit()
        session.refresh(job)
        session.add(Invoice(
            tenant_id=tid, repair_job_id=job.id, invoice_number="INV-PERIOD", status="paid",
            total_cents=10000, created_at=in_period,
        ))
        session.add(Invoice(
            tenant_id=tid, repair_job_id=job.id, invoice_number="INV-PERIOD-VOID", status="void",
            total_cents=50000, created_at=in_period,
        ))

        shoe = Shoe(tenant_id=tid, customer_id=customer.id, shoe_type="boots")
        session.add(shoe)
        session.commit()
        session.refresh(shoe)
        shoe_job = ShoeRepairJob(
            tenant_id=tid, shoe_id=shoe.id, job_number="S-PERIOD", title="Resole",
            status="collected", created_at=in_period,
        )
        session.add(shoe_job)
        session.commit()
        session.refresh(shoe_job)
        session.add(ShoeRepairJobItem(
            tenant_id=tid, shoe_repair_job_id=shoe_job.id, catalogue_key="resole__full",
            catalogue_group="resole", item_name="Full resole", pricing_type="fixed",
            unit_price_cents=6000, quantity=1, created_at=in_period,
        ))

        ak_job = AutoKeyJob(tenant_id=tid, customer_id=customer.id, job_number="AK-PERIOD", title="Key cut")
        session.add(ak_job)
        ak_job_refund = AutoKeyJob(tenant_id=tid, customer_id=customer.id, job_number="AK-PERIOD-REFUND", title="Key cut 2")
        session.add(ak_job_refund)
        session.commit()
        session.refresh(ak_job)
        session.refresh(ak_job_refund)
        session.add(AutoKeyInvoice(
            tenant_id=tid, auto_key_job_id=ak_job.id, invoice_number="AKI-PERIOD", status="paid",
            total_cents=20000, created_at=in_period,
        ))
        session.add(AutoKeyInvoice(
            tenant_id=tid, auto_key_job_id=ak_job_refund.id, invoice_number="AKI-PERIOD-REFUND", status="refunded",
            total_cents=70000, created_at=in_period,
        ))
        session.commit()

    res = client.get(
        "/v1/reports/period-summary",
        headers=headers,
        params={"period": "day", "reference_date": "2026-05-16"},
    )
    assert res.status_code == 200, res.text
    fin = res.json()["financials"]
    # 10000 (watch paid) + 6000 (shoe) + 20000 (mobile paid); void/refunded excluded entirely.
    assert fin["billed_cents"] == 36000
