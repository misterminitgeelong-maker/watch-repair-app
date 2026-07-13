"""Scheduled weekly/monthly sales report emails: due-detection and period bounds."""
import os
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from uuid import UUID, uuid4

_TEST_DB = Path(__file__).with_name(f"test_sales_report_email_{uuid4().hex}.db")
os.environ["DATABASE_URL"] = f"sqlite:///{_TEST_DB.as_posix()}"

from fastapi.testclient import TestClient
from sqlmodel import Session

from app.database import create_db_and_tables, engine
from app.main import app
from app.models import Customer, Invoice, RepairJob, User, UserNotificationPreference, Watch
from app.services import sales_report_email as sre

create_db_and_tables()
client = TestClient(app)


def _bootstrap() -> tuple[str, str, str]:
    """Returns (access_token, tenant_id, owner_user_id)."""
    suffix = uuid4().hex[:8]
    slug = f"srpt-{suffix}"
    bootstrap = client.post(
        "/v1/auth/bootstrap",
        json={
            "tenant_name": "Sales Report Co",
            "tenant_slug": slug,
            "owner_email": f"owner-{suffix}@test.com",
            "owner_full_name": "Owner",
            "owner_password": "pass123456",
            "plan_code": "enterprise",
        },
    )
    assert bootstrap.status_code == 200
    body = bootstrap.json()
    tenant_id = body["tenant_id"]
    owner_user_id = body["owner_user"]["id"]
    login = client.post(
        "/v1/auth/login",
        json={"tenant_slug": slug, "email": f"owner-{suffix}@test.com", "password": "pass123456"},
    )
    assert login.status_code == 200
    return login.json()["access_token"], tenant_id, owner_user_id


def _enable_weekly_report(tenant_id: str, user_id: str) -> None:
    tid, uid = UUID(tenant_id), UUID(user_id)
    with Session(engine) as session:
        session.add(UserNotificationPreference(tenant_id=tid, user_id=uid, email_weekly_sales_report=True))
        session.commit()


def _seed_watch_invoice(tenant_id: str, *, invoice_number: str, created_at: datetime, amount_cents: int) -> None:
    tid = UUID(tenant_id)
    with Session(engine) as session:
        customer = Customer(tenant_id=tid, full_name="Report Customer")
        session.add(customer)
        session.commit()
        session.refresh(customer)
        watch = Watch(tenant_id=tid, customer_id=customer.id, brand="Bulova")
        session.add(watch)
        session.commit()
        session.refresh(watch)
        job = RepairJob(tenant_id=tid, watch_id=watch.id, job_number=f"W-{invoice_number}", title="Service")
        session.add(job)
        session.commit()
        session.refresh(job)
        session.add(Invoice(
            tenant_id=tid, repair_job_id=job.id, invoice_number=invoice_number, status="paid",
            total_cents=amount_cents, created_at=created_at,
        ))
        session.commit()


def test_is_due_none_last_sent_is_always_due():
    assert sre._is_due(None, "week", date(2026, 7, 13)) is True
    assert sre._is_due(None, "month", date(2026, 7, 13)) is True


def test_is_due_same_iso_week_is_not_due():
    last_sent = datetime(2026, 7, 13, 9, 0, tzinfo=timezone.utc)  # Monday
    still_this_week = date(2026, 7, 16)  # Thursday, same ISO week
    assert sre._is_due(last_sent, "week", still_this_week) is False


def test_is_due_next_iso_week_is_due():
    last_sent = datetime(2026, 7, 13, 9, 0, tzinfo=timezone.utc)  # Monday
    next_week = date(2026, 7, 20)  # following Monday
    assert sre._is_due(last_sent, "week", next_week) is True


def test_is_due_same_month_is_not_due_next_month_is_due():
    last_sent = datetime(2026, 7, 5, tzinfo=timezone.utc)
    assert sre._is_due(last_sent, "month", date(2026, 7, 28)) is False
    assert sre._is_due(last_sent, "month", date(2026, 8, 1)) is True


def test_previous_period_bounds_week_covers_prior_monday_to_sunday():
    # Today = Sunday 2026-07-19 -> previous completed week is Mon 07-06 to Sun 07-12.
    _start_dt, _end_dt, start_ymd, end_ymd = sre._previous_period_bounds("week", date(2026, 7, 19))
    assert start_ymd == "2026-07-06"
    assert end_ymd == "2026-07-12"


def test_previous_period_bounds_month_covers_prior_calendar_month():
    _start_dt, _end_dt, start_ymd, end_ymd = sre._previous_period_bounds("month", date(2026, 7, 13))
    assert start_ymd == "2026-06-01"
    assert end_ymd == "2026-06-30"


def test_send_due_sales_report_emails_marks_sent_and_is_idempotent_within_period():
    _token, tenant_id, owner_user_id = _bootstrap()
    _enable_weekly_report(tenant_id, owner_user_id)

    with Session(engine) as session:
        summary1 = sre.send_due_sales_report_emails(session, tenant_id=UUID(tenant_id))
    assert summary1["weekly_sent"] + summary1["skipped"] == 1  # dry-run in tests -> counted as skipped, not an error

    with Session(engine) as session:
        pref = session.exec(
            select_pref(tenant_id, owner_user_id)
        ).first()
        assert pref is not None
        first_sent_at = pref.last_weekly_sales_report_sent_at
        assert first_sent_at is not None

    # Running again immediately (same ISO week) must not re-send or touch the timestamp.
    with Session(engine) as session:
        summary2 = sre.send_due_sales_report_emails(session, tenant_id=UUID(tenant_id))
    assert summary2["weekly_sent"] == 0
    assert summary2["skipped"] == 0

    with Session(engine) as session:
        pref = session.exec(select_pref(tenant_id, owner_user_id)).first()
        assert pref.last_weekly_sales_report_sent_at == first_sent_at


def select_pref(tenant_id: str, user_id: str):
    from sqlmodel import select
    return (
        select(UserNotificationPreference)
        .where(UserNotificationPreference.tenant_id == UUID(tenant_id))
        .where(UserNotificationPreference.user_id == UUID(user_id))
    )


def test_send_due_sales_report_emails_covers_only_the_completed_week(monkeypatch):
    _token, tenant_id, owner_user_id = _bootstrap()
    _enable_weekly_report(tenant_id, owner_user_id)

    today = datetime.now(timezone.utc).date()
    _start_dt, _end_dt, start_ymd, end_ymd = sre._previous_period_bounds("week", today)
    in_range = datetime.strptime(start_ymd, "%Y-%m-%d").replace(tzinfo=timezone.utc) + timedelta(days=1)
    out_of_range = datetime.now(timezone.utc) + timedelta(days=0)  # today, i.e. current (incomplete) week

    _seed_watch_invoice(tenant_id, invoice_number="INRANGE", created_at=in_range, amount_cents=15000)
    _seed_watch_invoice(tenant_id, invoice_number="TODAY", created_at=out_of_range, amount_cents=99999)

    captured = {}

    def fake_send(**kwargs):
        captured.update(kwargs)
        return True, None

    monkeypatch.setattr(sre.email_client, "send_sales_report_email", fake_send)

    with Session(engine) as session:
        sre.send_due_sales_report_emails(session, tenant_id=UUID(tenant_id))

    assert captured, "expected the report email function to have been invoked"
    assert captured["period_start"] == start_ymd
    assert captured["period_end"] == end_ymd
    assert captured["category_summary"]["watch"]["revenue_cents"] == 15000
    assert b"INRANGE" in captured["csv_bytes"]
    assert b"TODAY" not in captured["csv_bytes"]


def test_notification_preferences_endpoint_exposes_sales_report_flags():
    token, _tenant_id, _owner_user_id = _bootstrap()
    headers = {"Authorization": f"Bearer {token}"}

    res = client.get("/v1/me/notification-preferences", headers=headers)
    assert res.status_code == 200, res.text
    body = res.json()
    assert body["email_weekly_sales_report"] is False
    assert body["email_monthly_sales_report"] is False
    assert body["last_weekly_sales_report_sent_at"] is None

    patched = client.patch(
        "/v1/me/notification-preferences",
        headers=headers,
        json={"email_weekly_sales_report": True, "email_monthly_sales_report": True},
    )
    assert patched.status_code == 200, patched.text
    assert patched.json()["email_weekly_sales_report"] is True
    assert patched.json()["email_monthly_sales_report"] is True
