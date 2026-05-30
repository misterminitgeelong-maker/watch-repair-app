"""Mobile Services / Auto Key reports — Phase 8 summary fields."""
import os
from datetime import date
from pathlib import Path
from uuid import uuid4

_TEST_DB = Path(__file__).with_name(f"test_akr_{uuid4().hex}.db")
os.environ["DATABASE_URL"] = f"sqlite:///{_TEST_DB.as_posix()}"

from fastapi.testclient import TestClient

from app.database import create_db_and_tables
from app.main import app

create_db_and_tables()
client = TestClient(app)


def _bootstrap(headers_plan: str = "enterprise") -> tuple[str, str]:
    suffix = uuid4().hex[:8]
    slug = f"akr-{suffix}"
    assert client.post(
        "/v1/auth/bootstrap",
        json={
            "tenant_name": "AK Reports",
            "tenant_slug": slug,
            "owner_email": f"owner-{suffix}@test.com",
            "owner_full_name": "Owner",
            "owner_password": "pass123456",
            "plan_code": headers_plan,
        },
    ).status_code == 200
    login = client.post(
        "/v1/auth/login",
        json={"tenant_slug": slug, "email": f"owner-{suffix}@test.com", "password": "pass123456"},
    )
    assert login.status_code == 200
    return login.json()["access_token"], slug


def _customer(headers: dict) -> str:
    r = client.post(
        "/v1/customers",
        headers=headers,
        json={"full_name": "AK Customer", "phone": "0411222333"},
    )
    assert r.status_code == 201
    return r.json()["id"]


def _tech(headers: dict, suffix: str) -> str:
    r = client.post(
        "/v1/users",
        headers=headers,
        json={
            "full_name": f"Tech {suffix}",
            "email": f"tech-{suffix}@test.com",
            "password": "pass123456",
            "role": "tech",
        },
    )
    assert r.status_code == 201, r.text
    return r.json()["id"]


def _job_done(headers: dict, customer_id: str, **kwargs) -> str:
    r = client.post(
        "/v1/auto-key-jobs",
        headers=headers,
        json={
            "customer_id": customer_id,
            "title": kwargs.get("title", "Job"),
            "key_quantity": 1,
            "priority": "normal",
            "status": "awaiting_quote",
            "programming_status": "pending",
            "deposit_cents": 0,
            "cost_cents": 0,
            **{k: v for k, v in kwargs.items() if k != "title"},
        },
    )
    assert r.status_code == 201, r.text
    job_id = r.json()["id"]
    unit = kwargs.get("_unit_cents", 10000)
    tax = kwargs.get("_tax_cents", 1000)
    q = client.post(
        f"/v1/auto-key-jobs/{job_id}/quotes",
        headers=headers,
        json={
            "line_items": [{"description": "Service", "quantity": 1, "unit_price_cents": unit}],
            "tax_cents": tax,
        },
    )
    assert q.status_code == 201, q.text
    comp = client.post(
        f"/v1/auto-key-jobs/{job_id}/status",
        headers=headers,
        json={"status": "work_completed", "note": "ok"},
    )
    assert comp.status_code == 200, comp.text
    return job_id


def _job_intake_only(headers: dict, customer_id: str, **kwargs) -> str:
    """Create a job but DO NOT quote or complete it (a raw lead)."""
    r = client.post(
        "/v1/auto-key-jobs",
        headers=headers,
        json={
            "customer_id": customer_id,
            "title": kwargs.get("title", "Lead"),
            "key_quantity": 1,
            "priority": "normal",
            "status": "awaiting_quote",
            "programming_status": "pending",
            "deposit_cents": 0,
            "cost_cents": 0,
            **{k: v for k, v in kwargs.items() if k != "title"},
        },
    )
    assert r.status_code == 201, r.text
    return r.json()["id"]


def test_auto_key_reports_kpi_cockpit():
    from datetime import datetime, timezone

    token, _slug = _bootstrap()
    headers = {"Authorization": f"Bearer {token}"}
    cust = _customer(headers)

    today = date.today()
    sched = datetime(today.year, today.month, today.day, 9, 0, 0, tzinfo=timezone.utc).isoformat()

    # Two completed+quoted+invoiced jobs (one scheduled for today → on-time).
    _job_done(headers, cust, title="Scheduled job", scheduled_at=sched)
    _job_done(headers, cust, title="Walk-up job")
    # One raw lead with no quote/completion → drags lead→quote conversion below 100%.
    _job_intake_only(headers, cust, title="Cold lead")

    today_iso = today.isoformat()
    rep = client.get(
        "/v1/reports/auto-key",
        headers=headers,
        params={"date_from": today_iso, "date_to": today_iso},
    )
    assert rep.status_code == 200, rep.text
    kpis = rep.json()["kpis"]

    # 2 of 3 jobs were quoted.
    assert kpis["quoted_jobs_count"] == 2
    assert kpis["lead_to_quote_pct"] == round(2 / 3 * 100, 1)

    # Both completed jobs auto-invoiced the same day.
    assert kpis["completed_jobs_count"] == 2
    assert kpis["invoiced_completed_count"] == 2
    assert kpis["same_day_invoiced_count"] == 2
    assert kpis["same_day_invoice_rate_pct"] == 100.0

    # Cycle time is computed (a number, not null) for completed jobs.
    assert kpis["avg_cycle_hours"] is not None

    # One scheduled job, completed on its scheduled civil day → on-time.
    assert kpis["scheduled_completed_count"] == 1
    assert kpis["on_time_count"] == 1
    assert kpis["schedule_adherence_pct"] == 100.0


def test_auto_key_reports_mobile_shop_revenue_and_tech_share():
    token, _slug = _bootstrap()
    headers = {"Authorization": f"Bearer {token}"}
    tid_mobile = _tech(headers, "m")
    tid_shop = _tech(headers, "s")
    cust = _customer(headers)

    _job_done(
        headers,
        cust,
        title="Lockout",
        job_type="Lockout – Car",
        job_address="1 Test St Melbourne VIC",
        assigned_user_id=tid_mobile,
        _unit_cents=20000,
        _tax_cents=2000,
    )
    _job_done(
        headers,
        cust,
        title="In shop",
        job_type="Key Cutting (in-store)",
        assigned_user_id=tid_shop,
        _unit_cents=5000,
        _tax_cents=500,
    )

    today = date.today().isoformat()
    rep = client.get(
        "/v1/reports/auto-key",
        headers=headers,
        params={"date_from": today, "date_to": today},
    )
    assert rep.status_code == 200, rep.text
    data = rep.json()
    s = data["summary"]
    assert s["total_jobs"] >= 2
    assert s["mobile_count"] >= 1
    assert s["shop_count"] >= 1
    assert s["total_revenue_cents"] == 22000 + 5500
    assert s["mobile_revenue_cents"] == 22000
    assert s["shop_revenue_cents"] == 5500
    assert s["mobile_revenue_pct"] + s["shop_revenue_pct"] == 100.0

    by_tech = {row["tech_id"]: row for row in data["jobs_by_tech"]}
    assert tid_mobile in by_tech
    assert tid_shop in by_tech
    assert by_tech[tid_mobile]["revenue_cents"] == 22000
    assert by_tech[tid_shop]["revenue_cents"] == 5500
    assert abs(by_tech[tid_mobile]["revenue_share_pct"] + by_tech[tid_shop]["revenue_share_pct"] - 100.0) < 0.1
