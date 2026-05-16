"""Period report summary and CSV export (day / week / month / quarter)."""
import os
from datetime import date
from pathlib import Path
from uuid import uuid4

_TEST_DB = Path(__file__).with_name(f"test_period_rpt_{uuid4().hex}.db")
os.environ["DATABASE_URL"] = f"sqlite:///{_TEST_DB.as_posix()}"

from fastapi.testclient import TestClient

from app.database import create_db_and_tables
from app.main import app
from app.report_periods import resolve_period_bounds

create_db_and_tables()
client = TestClient(app)


def _bootstrap() -> str:
    suffix = uuid4().hex[:8]
    slug = f"prpt-{suffix}"
    assert client.post(
        "/v1/auth/bootstrap",
        json={
            "tenant_name": "Period Reports",
            "tenant_slug": slug,
            "owner_email": f"owner-{suffix}@test.com",
            "owner_full_name": "Owner",
            "owner_password": "pass123456",
        },
    ).status_code == 200
    login = client.post(
        "/v1/auth/login",
        json={"tenant_slug": slug, "email": f"owner-{suffix}@test.com", "password": "pass123456"},
    )
    assert login.status_code == 200
    return login.json()["access_token"]


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
    token = _bootstrap()
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
    token = _bootstrap()
    headers = {"Authorization": f"Bearer {token}"}
    res = client.get("/v1/reports/period-summary", headers=headers, params={"period": "year"})
    assert res.status_code == 400
