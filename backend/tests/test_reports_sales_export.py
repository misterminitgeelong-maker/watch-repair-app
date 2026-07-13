"""Category-scoped sales export and by_category summary breakdown (watch / shoe / mobile)."""
import os
from datetime import datetime, timezone
from pathlib import Path
from uuid import UUID, uuid4

_TEST_DB = Path(__file__).with_name(f"test_sales_export_{uuid4().hex}.db")
os.environ["DATABASE_URL"] = f"sqlite:///{_TEST_DB.as_posix()}"

import csv
import io

from fastapi.testclient import TestClient
from sqlmodel import Session

from app.database import create_db_and_tables, engine
from app.main import app
from app.models import (
    AutoKeyInvoice,
    AutoKeyJob,
    Customer,
    Invoice,
    RepairJob,
    Shoe,
    ShoeRepairJob,
    ShoeRepairJobItem,
    Watch,
)

create_db_and_tables()
client = TestClient(app)


def _bootstrap() -> tuple[str, str]:
    suffix = uuid4().hex[:8]
    slug = f"sales-{suffix}"
    bootstrap = client.post(
        "/v1/auth/bootstrap",
        json={
            "tenant_name": "Sales Export Co",
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


def _seed_all_categories(tenant_id: str) -> None:
    tid = UUID(tenant_id)
    with Session(engine) as session:
        customer = Customer(tenant_id=tid, full_name="Jane Sales")
        session.add(customer)
        session.commit()
        session.refresh(customer)

        # Watch repair sale
        watch = Watch(tenant_id=tid, customer_id=customer.id, brand="Seiko")
        session.add(watch)
        session.commit()
        session.refresh(watch)

        job = RepairJob(tenant_id=tid, watch_id=watch.id, job_number="W-0001", title="Movement service")
        session.add(job)
        session.commit()
        session.refresh(job)

        invoice = Invoice(
            tenant_id=tid,
            repair_job_id=job.id,
            invoice_number="INV-0001",
            status="paid",
            total_cents=15000,
        )
        session.add(invoice)

        # Shoe repair sale
        shoe = Shoe(tenant_id=tid, customer_id=customer.id, shoe_type="boots")
        session.add(shoe)
        session.commit()
        session.refresh(shoe)

        shoe_job = ShoeRepairJob(tenant_id=tid, shoe_id=shoe.id, job_number="S-0001", title="Resole", status="collected")
        session.add(shoe_job)
        session.commit()
        session.refresh(shoe_job)

        shoe_item = ShoeRepairJobItem(
            tenant_id=tid,
            shoe_repair_job_id=shoe_job.id,
            catalogue_key="resole__full",
            catalogue_group="resole",
            item_name="Full resole",
            pricing_type="fixed",
            unit_price_cents=8000,
            quantity=1,
        )
        session.add(shoe_item)

        # Mobile services (auto-key) sale
        ak_job = AutoKeyJob(tenant_id=tid, customer_id=customer.id, job_number="AK-0001", title="Car key cut")
        session.add(ak_job)
        session.commit()
        session.refresh(ak_job)

        ak_invoice = AutoKeyInvoice(
            tenant_id=tid,
            auto_key_job_id=ak_job.id,
            invoice_number="AKI-0001",
            status="paid",
            total_cents=22000,
        )
        session.add(ak_invoice)
        session.commit()


def test_by_category_summary_breakdown():
    token, tenant_id = _bootstrap()
    headers = {"Authorization": f"Bearer {token}"}
    _seed_all_categories(tenant_id)

    res = client.get("/v1/reports/summary", headers=headers)
    assert res.status_code == 200, res.text
    by_category = res.json()["by_category"]

    assert by_category["watch"]["jobs"] == 1
    assert by_category["watch"]["revenue_cents"] == 15000
    assert by_category["shoe"]["jobs"] == 1
    assert by_category["shoe"]["revenue_cents"] == 8000
    assert by_category["mobile"]["jobs"] == 1
    assert by_category["mobile"]["revenue_cents"] == 22000


def _csv_rows(text: str) -> list[dict]:
    return list(csv.DictReader(io.StringIO(text)))


def test_export_sales_scoped_by_category():
    token, tenant_id = _bootstrap()
    headers = {"Authorization": f"Bearer {token}"}
    _seed_all_categories(tenant_id)

    watch_res = client.get("/v1/reports/export/sales", headers=headers, params={"category": "watch"})
    assert watch_res.status_code == 200
    watch_rows = _csv_rows(watch_res.text)
    assert len(watch_rows) == 1
    assert watch_rows[0]["category"] == "Watch Repair"
    assert watch_rows[0]["amount_cents"] == "15000"
    assert watch_rows[0]["customer_name"] == "Jane Sales"

    shoe_res = client.get("/v1/reports/export/sales", headers=headers, params={"category": "shoe"})
    shoe_rows = _csv_rows(shoe_res.text)
    assert len(shoe_rows) == 1
    assert shoe_rows[0]["category"] == "Shoe Repair"
    assert shoe_rows[0]["amount_cents"] == "8000"

    mobile_res = client.get("/v1/reports/export/sales", headers=headers, params={"category": "mobile"})
    mobile_rows = _csv_rows(mobile_res.text)
    assert len(mobile_rows) == 1
    assert mobile_rows[0]["category"] == "Mobile Services"
    assert mobile_rows[0]["amount_cents"] == "22000"


def test_export_sales_all_combines_every_category():
    token, tenant_id = _bootstrap()
    headers = {"Authorization": f"Bearer {token}"}
    _seed_all_categories(tenant_id)

    res = client.get("/v1/reports/export/sales", headers=headers, params={"category": "all"})
    assert res.status_code == 200
    rows = _csv_rows(res.text)
    assert len(rows) == 3
    categories = {r["category"] for r in rows}
    assert categories == {"Watch Repair", "Shoe Repair", "Mobile Services"}


def test_export_sales_rejects_invalid_category():
    token, _tenant_id = _bootstrap()
    headers = {"Authorization": f"Bearer {token}"}
    res = client.get("/v1/reports/export/sales", headers=headers, params={"category": "bogus"})
    assert res.status_code == 400


def _seed_watch_invoice(tenant_id: str, *, invoice_number: str, created_at: datetime, amount_cents: int) -> None:
    tid = UUID(tenant_id)
    with Session(engine) as session:
        customer = Customer(tenant_id=tid, full_name="Dated Customer")
        session.add(customer)
        session.commit()
        session.refresh(customer)

        watch = Watch(tenant_id=tid, customer_id=customer.id, brand="Citizen")
        session.add(watch)
        session.commit()
        session.refresh(watch)

        job = RepairJob(tenant_id=tid, watch_id=watch.id, job_number=f"W-{invoice_number}", title="Battery")
        session.add(job)
        session.commit()
        session.refresh(job)

        session.add(Invoice(
            tenant_id=tid,
            repair_job_id=job.id,
            invoice_number=invoice_number,
            status="paid",
            total_cents=amount_cents,
            created_at=created_at,
        ))
        session.commit()


def test_export_sales_filters_by_explicit_date_range():
    token, tenant_id = _bootstrap()
    headers = {"Authorization": f"Bearer {token}"}
    _seed_watch_invoice(
        tenant_id, invoice_number="OLD-0001",
        created_at=datetime(2026, 1, 5, tzinfo=timezone.utc), amount_cents=5000,
    )
    _seed_watch_invoice(
        tenant_id, invoice_number="MID-0001",
        created_at=datetime(2026, 6, 15, tzinfo=timezone.utc), amount_cents=7000,
    )
    _seed_watch_invoice(
        tenant_id, invoice_number="NEW-0001",
        created_at=datetime(2026, 12, 20, tzinfo=timezone.utc), amount_cents=9000,
    )

    res = client.get(
        "/v1/reports/export/sales",
        headers=headers,
        params={"category": "watch", "date_from": "2026-06-01", "date_to": "2026-06-30"},
    )
    assert res.status_code == 200
    rows = _csv_rows(res.text)
    assert len(rows) == 1
    assert rows[0]["reference"] == "MID-0001"
    assert "2026-06-01_2026-06-30" in res.headers["content-disposition"]


def test_export_sales_filters_by_period_shortcut():
    token, tenant_id = _bootstrap()
    headers = {"Authorization": f"Bearer {token}"}
    _seed_watch_invoice(
        tenant_id, invoice_number="APR-0001",
        created_at=datetime(2026, 4, 10, tzinfo=timezone.utc), amount_cents=5000,
    )
    _seed_watch_invoice(
        tenant_id, invoice_number="MAY-0001",
        created_at=datetime(2026, 5, 16, tzinfo=timezone.utc), amount_cents=7000,
    )

    res = client.get(
        "/v1/reports/export/sales",
        headers=headers,
        params={"category": "watch", "period": "month", "reference_date": "2026-05-16"},
    )
    assert res.status_code == 200
    rows = _csv_rows(res.text)
    assert len(rows) == 1
    assert rows[0]["reference"] == "MAY-0001"


def test_export_sales_rejects_invalid_period():
    token, _tenant_id = _bootstrap()
    headers = {"Authorization": f"Bearer {token}"}
    res = client.get("/v1/reports/export/sales", headers=headers, params={"category": "watch", "period": "year"})
    assert res.status_code == 400


def test_export_sales_rejects_invalid_date():
    token, _tenant_id = _bootstrap()
    headers = {"Authorization": f"Bearer {token}"}
    res = client.get(
        "/v1/reports/export/sales", headers=headers, params={"category": "watch", "date_from": "not-a-date"}
    )
    assert res.status_code == 400
