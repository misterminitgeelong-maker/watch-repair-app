"""Mobile network KPI engine: trade-day / operating-week windows, snapshots, CSV, live jobs."""

from __future__ import annotations

import os
from datetime import datetime, timedelta, timezone
from pathlib import Path
from uuid import UUID, uuid4
from zoneinfo import ZoneInfo

_TEST_DB = Path(__file__).with_name(f"test_mobile_network_kpis_{uuid4().hex}.db")
os.environ.setdefault("DATABASE_URL", f"sqlite:///{_TEST_DB.as_posix()}")
os.environ.setdefault("JWT_SECRET", "test-secret-not-for-production")
os.environ.setdefault("APP_ENV", "test")

from fastapi.testclient import TestClient
from sqlmodel import Session, select

from app.database import create_db_and_tables, engine
from app.main import app
from app.minit_provision import ensure_minit_pilot_account
from app.mobile_network_kpis import (
    NETWORK_TZ,
    classify_job_type,
    classify_lead_source,
    csv_bytes_for_report,
    daily_trade_dates_due,
    last_completed_operating_week,
    operating_week_window,
    weekly_compile_due,
)
from app.models import AutoKeyInvoice, AutoKeyJob, Customer, ParentAccount, Tenant
from app.services.mobile_kpi_close import compile_daily_snapshot, compile_weekly_snapshot, email_weekly_snapshot
from network_link_helpers import link_and_accept

create_db_and_tables()
client = TestClient(app)

HQ_EMAIL = "hq-owner@test.mainspring.au"
HQ_PASSWORD = "MinitPilot2026!"
SYDNEY = ZoneInfo("Australia/Sydney")


def _ensure_hq() -> str:
    with Session(engine) as session:
        ensure_minit_pilot_account(
            session,
            parent_name="Mister Minit",
            hq_tenant_slug="mmsupport",
            hq_tenant_name="Mister Minit HQ",
            hq_owner_email=HQ_EMAIL,
            hq_owner_password=HQ_PASSWORD,
        )
    login = client.post(
        "/v1/auth/login",
        json={"tenant_slug": "mmsupport", "email": HQ_EMAIL, "password": HQ_PASSWORD},
    )
    assert login.status_code == 200, login.text
    return login.json()["access_token"]


def _link_operator(headers: dict, operator_label: str, shop_number: str | None = None) -> str:
    suffix = uuid4().hex[:8]
    slug, email = f"op-{suffix}", f"op-{suffix}@test.local"
    res = client.post(
        "/v1/auth/bootstrap",
        json={
            "tenant_name": f"Tenant {slug}",
            "tenant_slug": slug,
            "owner_email": email,
            "owner_full_name": "Owner",
            "owner_password": "pass123456",
            "plan_code": "basic_auto_key",
        },
    )
    assert res.status_code == 200, res.text
    link = link_and_accept(client,
        "/v1/parent-accounts/me/link-tenant",
        headers=headers,
        json={"tenant_slug": slug, "owner_email": email},
    )
    assert link.status_code == 200, link.text
    with Session(engine) as session:
        tenant = session.exec(select(Tenant).where(Tenant.slug == slug)).one()
        tenant.name = operator_label
        if shop_number:
            tenant.shop_number = shop_number
        session.add(tenant)
        session.commit()
        return str(tenant.id)


def _seed_job(
    tenant_id_str: str,
    *,
    created_at: datetime,
    total_cents: int | None,
    job_type: str | None = None,
    lead_source: str = "shop_referred",
    work_completed_at: datetime | None = None,
    paid: bool = True,
) -> None:
    tenant_id = UUID(tenant_id_str)
    with Session(engine) as session:
        customer = Customer(tenant_id=tenant_id, full_name="Test Customer", phone="0400000000")
        session.add(customer)
        session.flush()
        job = AutoKeyJob(
            tenant_id=tenant_id,
            customer_id=customer.id,
            job_number=f"AK-{uuid4().hex[:8]}",
            title="Test job",
            status="invoice_paid" if paid else "en_route",
            programming_status="not_required",
            created_at=created_at,
            job_type=job_type,
            commission_lead_source=lead_source,
            work_completed_at=work_completed_at,
        )
        session.add(job)
        session.flush()
        if total_cents is not None:
            session.add(
                AutoKeyInvoice(
                    tenant_id=tenant_id,
                    auto_key_job_id=job.id,
                    invoice_number=f"AKI-{uuid4().hex[:8]}",
                    status="paid" if paid else "unpaid",
                    total_cents=total_cents,
                    created_at=created_at,
                    paid_at=created_at if paid else None,
                )
            )
        session.commit()


def test_classify_job_type_and_lead_source():
    assert classify_job_type("Lockout – Car") == "lockout"
    assert classify_job_type("All Keys Lost") == "all_keys_lost"
    assert classify_job_type("Duplicate Key") == "key_cutting"
    assert classify_job_type("Key Cutting (in-store)") == "key_cutting"
    assert classify_job_type("Remote / Fob Sync") == "remote_fob"
    assert classify_job_type("Ignition Replace") == "ignition"
    assert classify_job_type("Transponder Programming") == "transponder"
    assert classify_job_type("Diagnostic") == "diagnostic"
    assert classify_job_type("Add Key") == "key_cutting"
    assert classify_job_type("AKL") == "all_keys_lost"
    assert classify_job_type("Broken Key Extraction") == "lockout"
    assert classify_job_type("Door Lock Change") == "lockout"
    assert classify_job_type("Mobile Key") == "other"
    assert classify_job_type("Something else") == "other"
    assert classify_lead_source("tech_sourced") == "tech_sourced"
    assert classify_lead_source("mystery") == "other"
    assert classify_lead_source("") == "other"
    assert classify_lead_source(None) == "other"


def test_operating_week_window_edges():
    # Saturday 22:59 Sydney is still in the week that ends 23:00.
    before = datetime(2026, 9, 19, 22, 59, tzinfo=SYDNEY)
    start, end, start_ymd, end_ymd = operating_week_window(before)
    assert start_ymd == "2026-09-13"
    assert end_ymd == "2026-09-19"
    assert not weekly_compile_due(before)
    completed = last_completed_operating_week(before)
    assert completed[2] == "2026-09-06"

    after = datetime(2026, 9, 19, 23, 6, tzinfo=SYDNEY)
    assert weekly_compile_due(after)
    start2, end2, start_ymd2, end_ymd2 = last_completed_operating_week(after)
    assert start_ymd2 == "2026-09-13"
    assert end_ymd2 == "2026-09-19"
    assert as_utc_iso(end2).startswith("2026-09-19") or end2.astimezone(SYDNEY).hour == 23

    # Sunday 00:30 is the gap after Saturday 23:00, before Sunday 01:00 — previous week.
    gap = datetime(2026, 9, 20, 0, 30, tzinfo=SYDNEY)
    gap_start, _gap_end, gap_start_ymd, _gap_end_ymd = operating_week_window(gap)
    assert gap_start_ymd == "2026-09-13"
    assert not weekly_compile_due(gap)

    sunday_open = datetime(2026, 9, 20, 1, 0, tzinfo=SYDNEY)
    _s, _e, open_ymd, _ey = operating_week_window(sunday_open)
    assert open_ymd == "2026-09-20"


def as_utc_iso(dt: datetime) -> str:
    return dt.astimezone(timezone.utc).isoformat()


def test_daily_trade_dates_due():
    morning = datetime(2026, 9, 21, 10, 0, tzinfo=SYDNEY)
    due = daily_trade_dates_due(morning)
    assert due[0] == datetime(2026, 9, 20).date()
    assert len(due) == 14
    assert datetime(2026, 9, 7).date() in due
    evening = datetime(2026, 9, 21, 21, 0, tzinfo=SYDNEY)
    due_evening = daily_trade_dates_due(evening)
    assert due_evening[0] == datetime(2026, 9, 21).date()
    assert datetime(2026, 9, 20).date() in due_evening


def test_csv_has_bom_headers_and_network_total():
    token = _ensure_hq()
    headers = {"Authorization": f"Bearer {token}"}
    operator_id = _link_operator(headers, "CSV Van", "3904")
    now = datetime.now(timezone.utc)
    _seed_job(operator_id, created_at=now, total_cents=18900, job_type="Lockout – Car", lead_source="tech_sourced")

    with Session(engine) as session:
        parent = session.exec(select(ParentAccount).where(ParentAccount.owner_email == HQ_EMAIL)).one()
        from app.mobile_network_kpis import build_network_kpis

        report = build_network_kpis(session, parent, now - timedelta(hours=1), now + timedelta(hours=1))
        raw = csv_bytes_for_report(report)
    text = raw.decode("utf-8")
    assert text.startswith("\ufeff")
    assert "Operator" in text.splitlines()[0]
    assert "Sales $" in text
    assert "Lockout jobs" in text
    assert "Tech sourced jobs" in text
    assert "CSV Van" in text
    assert "Network total" in text
    assert "189.00" in text


def test_daily_snapshot_is_idempotent():
    token = _ensure_hq()
    headers = {"Authorization": f"Bearer {token}"}
    operator_id = _link_operator(headers, "Daily Van")
    now = datetime.now(timezone.utc)
    _seed_job(operator_id, created_at=now, total_cents=5000, job_type="Diagnostic")
    trade_date = now.astimezone(NETWORK_TZ).date()

    with Session(engine) as session:
        parent = session.exec(select(ParentAccount).where(ParentAccount.owner_email == HQ_EMAIL)).one()
        first = compile_daily_snapshot(session, parent, trade_date, now=now)
        second = compile_daily_snapshot(session, parent, trade_date, now=now)
    assert len(first) >= 1
    assert second == []


def test_daily_snapshot_duplicate_insert_is_ignored():
    token = _ensure_hq()
    headers = {"Authorization": f"Bearer {token}"}
    operator_id = _link_operator(headers, "Race Van")
    now = datetime.now(timezone.utc)
    _seed_job(operator_id, created_at=now, total_cents=2500, job_type="Diagnostic")
    trade_date = now.astimezone(NETWORK_TZ).date()

    from app.models import MobileKpiDailySnapshot
    from app.services.mobile_kpi_close import _persist_ignoring_conflict

    with Session(engine) as session:
        parent = session.exec(select(ParentAccount).where(ParentAccount.owner_email == HQ_EMAIL)).one()
        written = compile_daily_snapshot(session, parent, trade_date, now=now)
        assert written
        duplicate = MobileKpiDailySnapshot(
            parent_account_id=parent.id,
            operator_tenant_id=UUID(operator_id),
            trade_date=trade_date,
            payload_json="{}",
            compiled_at=now,
        )
        assert _persist_ignoring_conflict(session, duplicate) is False
        session.commit()


def test_live_kpis_include_tech_sourced_jobs():
    token = _ensure_hq()
    headers = {"Authorization": f"Bearer {token}"}
    operator_id = _link_operator(headers, "Tech Sourced Van")
    now = datetime.now(timezone.utc)
    _seed_job(
        operator_id,
        created_at=now,
        total_cents=44900,
        job_type="All Keys Lost",
        lead_source="tech_sourced",
        work_completed_at=now,
    )

    live = client.get("/v1/parent-accounts/me/operations/mobile-kpis/live", headers=headers)
    assert live.status_code == 200, live.text
    body = live.json()
    row = next(r for r in body["week"]["operators"] if r["operator_tenant_id"] == operator_id)
    assert row["jobs_created"] >= 1
    assert row["lead_jobs"]["tech_sourced"] >= 1
    assert row["sales_cents"] >= 44900
    assert row["jobs_completed"] >= 1

    jobs = client.get("/v1/parent-accounts/me/operations/mobile-jobs", headers=headers)
    assert jobs.status_code == 200, jobs.text
    numbers = {j["job_number"] for j in jobs.json()["jobs"]}
    assert any(n.startswith("AK-") for n in numbers)


def test_recipients_toggle_and_weekly_email_stamp(monkeypatch):
    token = _ensure_hq()
    headers = {"Authorization": f"Bearer {token}"}

    listed = client.get("/v1/parent-accounts/me/operations/mobile-kpis/recipients", headers=headers)
    assert listed.status_code == 200, listed.text
    people = listed.json()["recipients"]
    assert people
    target = next(p for p in people if p["email"].lower() == HQ_EMAIL)
    put = client.put(
        "/v1/parent-accounts/me/operations/mobile-kpis/recipients",
        headers=headers,
        json={"user_id": target["user_id"], "email_mobile_kpi_report": True},
    )
    assert put.status_code == 200, put.text
    flagged = next(p for p in put.json()["recipients"] if p["user_id"] == target["user_id"])
    assert flagged["email_mobile_kpi_report"] is True
    client.put(
        "/v1/parent-accounts/me/operations/mobile-kpis/settings",
        headers=headers,
        json={"opt_in": True},
    )

    sends: list[str] = []

    def _fake_send(**kwargs):
        sends.append(kwargs["to_email"])
        return True, None

    monkeypatch.setattr("app.email_client.send_mobile_weekly_report_email", _fake_send)

    with Session(engine) as session:
        parent = session.exec(select(ParentAccount).where(ParentAccount.owner_email == HQ_EMAIL)).one()
        saturday = datetime(2026, 9, 19, 23, 10, tzinfo=SYDNEY)
        snap = compile_weekly_snapshot(session, parent, at=saturday, force=True)
        sent = email_weekly_snapshot(session, parent, snap)
        session.refresh(snap)
    assert sent is True
    assert HQ_EMAIL in sends
    assert snap.emailed_at is not None
    csv_text = client.get(
        f"/v1/parent-accounts/me/operations/mobile-kpis/weeks/{snap.week_start_ymd}/csv",
        headers=headers,
    )
    assert csv_text.status_code == 200, csv_text.text
    assert csv_text.headers["content-type"].startswith("text/csv")
    assert csv_text.content.startswith(b"\xef\xbb\xbf") or csv_text.content.decode("utf-8-sig").startswith("Operator")


def test_weekly_email_not_stamped_when_sendgrid_rejects(monkeypatch):
    token = _ensure_hq()
    headers = {"Authorization": f"Bearer {token}"}
    listed = client.get("/v1/parent-accounts/me/operations/mobile-kpis/recipients", headers=headers)
    target = listed.json()["recipients"][0]
    client.put(
        "/v1/parent-accounts/me/operations/mobile-kpis/recipients",
        headers=headers,
        json={"user_id": target["user_id"], "email_mobile_kpi_report": True},
    )

    monkeypatch.setattr("app.email_client.send_mobile_weekly_report_email", lambda **_k: (False, "dry_run"))

    with Session(engine) as session:
        parent = session.exec(select(ParentAccount).where(ParentAccount.owner_email == HQ_EMAIL)).one()
        saturday = datetime(2026, 9, 19, 23, 10, tzinfo=SYDNEY)
        snap = compile_weekly_snapshot(session, parent, at=saturday, force=True)
        sent = email_weekly_snapshot(session, parent, snap)
        session.refresh(snap)
    assert sent is False
    assert snap.emailed_at is None


def test_opt_in_gates_allocated_recipients(monkeypatch):
    token = _ensure_hq()
    headers = {"Authorization": f"Bearer {token}"}
    listed = client.get("/v1/parent-accounts/me/operations/mobile-kpis/recipients", headers=headers)
    target = listed.json()["recipients"][0]
    client.put(
        "/v1/parent-accounts/me/operations/mobile-kpis/recipients",
        headers=headers,
        json={"user_id": target["user_id"], "email_mobile_kpi_report": True},
    )
    client.put(
        "/v1/parent-accounts/me/operations/mobile-kpis/settings",
        headers=headers,
        json={"opt_in": False},
    )
    sends: list[str] = []
    monkeypatch.setattr(
        "app.email_client.send_mobile_weekly_report_email",
        lambda **kwargs: sends.append(kwargs["to_email"]) or (True, None),
    )
    with Session(engine) as session:
        parent = session.exec(select(ParentAccount).where(ParentAccount.owner_email == HQ_EMAIL)).one()
        saturday = datetime(2026, 9, 19, 23, 10, tzinfo=SYDNEY)
        snap = compile_weekly_snapshot(session, parent, at=saturday, force=True)
        sent = email_weekly_snapshot(session, parent, snap)
    assert sent is False
    assert sends == []


def test_avg_sale_uses_paid_customers_not_created_jobs():
    token = _ensure_hq()
    headers = {"Authorization": f"Bearer {token}"}
    operator_id = _link_operator(headers, "Avg Sale Van")
    now = datetime.now(timezone.utc)
    _seed_job(operator_id, created_at=now, total_cents=None, job_type="Diagnostic", paid=False)
    _seed_job(operator_id, created_at=now, total_cents=10000, job_type="Diagnostic", paid=True)
    live = client.get("/v1/parent-accounts/me/operations/mobile-kpis/live", headers=headers, params={"scope": "week"})
    assert live.status_code == 200, live.text
    row = next(r for r in live.json()["week"]["operators"] if r["operator_tenant_id"] == operator_id)
    assert row["jobs_created"] >= 2
    assert row["customers_count"] >= 2
    assert row["paid_customers_count"] == 1
    assert row["avg_sale_cents"] == 10000


def test_daily_snapshot_force_recompiles():
    token = _ensure_hq()
    headers = {"Authorization": f"Bearer {token}"}
    operator_id = _link_operator(headers, "Rebuild Van")
    now = datetime.now(timezone.utc)
    _seed_job(operator_id, created_at=now, total_cents=3000, job_type="Diagnostic")
    trade_date = now.astimezone(NETWORK_TZ).date()
    with Session(engine) as session:
        parent = session.exec(select(ParentAccount).where(ParentAccount.owner_email == HQ_EMAIL)).one()
        first = compile_daily_snapshot(session, parent, trade_date, now=now)
        again = compile_daily_snapshot(session, parent, trade_date, now=now, force=True)
    assert len(first) >= 1
    assert len(again) >= 1
    rebuilt = client.post(
        f"/v1/parent-accounts/me/operations/mobile-kpis/days/{trade_date.isoformat()}/rebuild",
        headers=headers,
    )
    assert rebuilt.status_code == 200, rebuilt.text
    csv_res = client.get(
        f"/v1/parent-accounts/me/operations/mobile-kpis/days/{trade_date.isoformat()}/csv",
        headers=headers,
    )
    assert csv_res.status_code == 200, csv_res.text
    assert csv_res.headers["content-type"].startswith("text/csv")


def test_jobs_report_total_count_is_not_the_page_size():
    token = _ensure_hq()
    headers = {"Authorization": f"Bearer {token}"}
    operator_id = _link_operator(headers, "Count Van")
    now = datetime.now(timezone.utc)
    for _ in range(3):
        _seed_job(operator_id, created_at=now, total_cents=1000, job_type="Diagnostic")
    res = client.get(
        "/v1/parent-accounts/me/operations/mobile-jobs",
        headers=headers,
        params={"operator_tenant_id": operator_id, "limit": 1},
    )
    assert res.status_code == 200, res.text
    body = res.json()
    assert body["total_count"] >= 3
    assert len(body["jobs"]) == 1
    assert body["has_more"] is True
    assert body["jobs"][0]["job_type"] == "Diagnostic"
    assert "commission_lead_source" in body["jobs"][0]

