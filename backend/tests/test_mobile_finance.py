"""Mobile Services finance report: periods, money, conversion, ageing, trends, durations, CSV."""
import csv
import io
import os
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from uuid import UUID, uuid4
from zoneinfo import ZoneInfo

_TEST_DB = Path(__file__).with_name(f"test_mobile_finance_{uuid4().hex}.db")
os.environ["DATABASE_URL"] = f"sqlite:///{_TEST_DB.as_posix()}"

import pytest
from fastapi.testclient import TestClient
from sqlmodel import Session, select

from app.database import create_db_and_tables, engine
from app.main import app
from app.mobile_finance import (
    AR_BUCKETS,
    Period,
    ar_ageing,
    duration_stats,
    job_durations,
    outstanding_as_of,
    pct,
    resolve_period,
    timelines_from_events,
    trend_averages,
    working_days,
)
from app.models import AutoKeyInvoice, AutoKeyJob, AutoKeyQuote, Tenant, TenantEventLog, User

create_db_and_tables()
client = TestClient(app)
TZ = ZoneInfo("Australia/Melbourne")


# ── Periods ──────────────────────────────────────────────────────────────────
def test_period_presets_are_shop_civil_dates():
    today = date(2026, 9, 17)  # Thursday
    assert (resolve_period("week", today).start, resolve_period("week", today).end) == (date(2026, 9, 14), date(2026, 9, 20))
    assert (resolve_period("last_week", today).start, resolve_period("last_week", today).end) == (date(2026, 9, 7), date(2026, 9, 13))
    assert (resolve_period("month", today).start, resolve_period("month", today).end) == (date(2026, 9, 1), date(2026, 9, 30))
    assert (resolve_period("last_month", today).start, resolve_period("last_month", today).end) == (date(2026, 8, 1), date(2026, 8, 31))
    assert (resolve_period("quarter", today).start, resolve_period("quarter", today).end) == (date(2026, 7, 1), date(2026, 9, 30))
    assert (resolve_period("last_4_weeks", today).start, resolve_period("last_4_weeks", today).end) == (date(2026, 8, 17), date(2026, 9, 13))
    p13 = resolve_period("last_13_weeks", today)
    assert p13.end == date(2026, 9, 13) and p13.days == 91
    # Year and quarter edges.
    assert resolve_period("last_month", date(2026, 1, 10)).start == date(2025, 12, 1)
    assert resolve_period("quarter", date(2026, 12, 31)).end == date(2026, 12, 31)
    custom = resolve_period("custom", today, "2026-08-01", "2026-08-15")
    assert custom.days == 15 and custom.previous() == Period(date(2026, 7, 17), date(2026, 7, 31), "previous period")
    with pytest.raises(ValueError):
        resolve_period("custom", today, "2026-08-15", "2026-08-01")
    with pytest.raises(ValueError):
        resolve_period("custom", today, None, None)
    with pytest.raises(ValueError):
        resolve_period("fortnight", today)


def test_working_days_are_mon_to_sat_to_date():
    week = Period(date(2026, 9, 14), date(2026, 9, 20), "w")
    assert working_days(week, date(2026, 9, 30)) == 6  # full week, Sunday excluded
    assert working_days(week, date(2026, 9, 17)) == 4  # Thursday, in progress
    assert working_days(week, date(2026, 9, 10)) == 0  # not started


def test_pct_never_divides_by_zero():
    assert pct(1, 0) is None
    assert pct(0, 0) is None
    assert pct(1, 4) == 25.0


def _inv(created: datetime, total: int, status: str = "unpaid", paid: datetime | None = None) -> AutoKeyInvoice:
    return AutoKeyInvoice(tenant_id=uuid4(), auto_key_job_id=uuid4(), invoice_number="x", status=status, total_cents=total, created_at=created.replace(tzinfo=None), paid_at=paid.replace(tzinfo=None) if paid else None)


def test_outstanding_as_of_looks_back_in_time():
    t0 = datetime(2026, 9, 1, tzinfo=timezone.utc)
    invoices = [
        _inv(t0, 100, "paid", t0 + timedelta(days=10)),  # unpaid on day 5, paid by day 15
        _inv(t0 + timedelta(days=3), 200),  # still unpaid
        _inv(t0 + timedelta(days=20), 400),  # not yet raised on day 15
        _inv(t0, 800, "void"),
    ]
    assert outstanding_as_of(invoices, t0 + timedelta(days=5)) == (300, 2)
    assert outstanding_as_of(invoices, t0 + timedelta(days=15)) == (200, 1)
    assert outstanding_as_of(invoices, t0 + timedelta(days=25)) == (600, 2)


def test_ar_ageing_buckets_and_overdue_share():
    now = datetime(2026, 9, 17, tzinfo=timezone.utc)
    invoices = [
        _inv(now - timedelta(days=2), 100),
        _inv(now - timedelta(days=7), 100),
        _inv(now - timedelta(days=8), 200),
        _inv(now - timedelta(days=45), 300),
        _inv(now - timedelta(days=90), 400),
        _inv(now - timedelta(days=90), 999, "paid", now),
    ]
    ageing = ar_ageing(invoices, now)
    assert ageing["total_cents"] == 1100
    assert ageing["overdue_cents"] == 900
    assert ageing["overdue_pct"] == pytest.approx(81.8)
    assert [(b["key"], b["cents"], b["count"]) for b in ageing["buckets"]] == [
        ("current", 200, 2), ("d8_30", 200, 1), ("d31_60", 300, 1), ("d61_plus", 400, 1),
    ]
    assert [b[0] for b in AR_BUCKETS] == ["current", "d8_30", "d31_60", "d61_plus"]


def test_trend_averages_need_a_full_window():
    rows = [{"v": i} for i in range(1, 14)]
    assert trend_averages(rows, "v") == {"last_4_avg": 11.5, "last_13_avg": 7.0, "latest": 13}
    assert trend_averages(rows[:5], "v")["last_13_avg"] is None


# ── Durations from the event log ─────────────────────────────────────────────
def _event(job_id: UUID, when: datetime, summary: str) -> TenantEventLog:
    return TenantEventLog(tenant_id=uuid4(), entity_type="auto_key_job", entity_id=job_id, event_type="auto_key_status_changed", event_summary=summary, created_at=when.replace(tzinfo=None))


def test_timelines_take_the_earliest_transition_and_ignore_notes():
    job = uuid4()
    t0 = datetime(2026, 9, 17, 0, 0, tzinfo=timezone.utc)
    events = [
        _event(job, t0 + timedelta(minutes=40), "Status changed from En Route to On Site — parked out front"),
        _event(job, t0 + timedelta(minutes=10), "Status changed from Booking Confirmed to En Route"),
        _event(job, t0 + timedelta(minutes=45), "Status changed from En Route to On Site"),  # later duplicate ignored
        _event(job, t0 + timedelta(minutes=99), "Status changed from On Site to Work Completed"),
        TenantEventLog(tenant_id=uuid4(), entity_type="auto_key_job", entity_id=job, event_type="auto_key_job_updated", event_summary="Updated to On Site notes", created_at=t0.replace(tzinfo=None)),
    ]
    tl = timelines_from_events(events)[job]
    assert tl.en_route_at == t0 + timedelta(minutes=10)
    assert tl.on_site_at == t0 + timedelta(minutes=40)


def test_job_durations_report_sample_sizes_and_skip_forgotten_statuses():
    t0 = datetime(2026, 9, 17, 0, 0, tzinfo=timezone.utc)
    tech = uuid4()
    a = AutoKeyJob(tenant_id=uuid4(), customer_id=uuid4(), job_number="A", title="A", job_type="AKL", assigned_user_id=tech, work_completed_at=(t0 + timedelta(minutes=100)).replace(tzinfo=None))
    b = AutoKeyJob(tenant_id=uuid4(), customer_id=uuid4(), job_number="B", title="B", job_type="AKL", assigned_user_id=tech, work_completed_at=(t0 + timedelta(minutes=70)).replace(tzinfo=None))
    forgotten = AutoKeyJob(tenant_id=uuid4(), customer_id=uuid4(), job_number="F", title="F", job_type="Lockout", work_completed_at=(t0 + timedelta(days=3)).replace(tzinfo=None))
    no_events = AutoKeyJob(tenant_id=uuid4(), customer_id=uuid4(), job_number="N", title="N", work_completed_at=t0.replace(tzinfo=None))
    events = [
        _event(a.id, t0 + timedelta(minutes=10), "Status changed from Booking Confirmed to En Route"),
        _event(a.id, t0 + timedelta(minutes=40), "Status changed from En Route to On Site"),
        _event(b.id, t0 + timedelta(minutes=30), "Status changed from Booking Confirmed to On Site"),
        _event(forgotten.id, t0, "Status changed from Booking Confirmed to On Site"),
    ]
    d = job_durations([a, b, forgotten, no_events], timelines_from_events(events))
    assert d["estimated_minutes"] == 60 and d["estimate_source"] == "assumed"
    assert d["on_site"] == {"count": 2, "avg_minutes": 50.0, "median_minutes": 50.0, "p90_minutes": 60.0}
    assert d["travel"] == {"count": 1, "avg_minutes": 30.0, "median_minutes": 30.0, "p90_minutes": 30.0}
    assert d["by_job_type"][0] == {"job_type": "AKL", "count": 2, "avg_minutes": 50.0, "median_minutes": 50.0, "p90_minutes": 60.0}
    assert d["_by_tech"][tech]["count"] == 2
    assert duration_stats([]) == {"count": 0, "avg_minutes": None, "median_minutes": None, "p90_minutes": None}


# ── End to end ───────────────────────────────────────────────────────────────
def _tenant():
    suffix = uuid4().hex[:8]
    slug = f"fin-{suffix}"
    email = f"owner-{suffix}@test.com"
    r = client.post("/v1/auth/bootstrap", json={"tenant_name": "Finance Mobile", "tenant_slug": slug, "owner_email": email, "owner_full_name": "Owner", "owner_password": "pass123456", "plan_code": "enterprise"})
    assert r.status_code == 200, r.text
    login = client.post("/v1/auth/login", json={"tenant_slug": slug, "email": email, "password": "pass123456"})
    headers = {"Authorization": f"Bearer {login.json()['access_token']}"}
    with Session(engine) as s:
        tenant = s.exec(select(Tenant).where(Tenant.slug == slug)).one()
        tenant.timezone = "Australia/Melbourne"
        tenant.mobile_weekly_target_cents = 70000
        s.add(tenant)
        s.commit()
        tenant_id = tenant.id
    return headers, tenant_id, slug


def _local(day: date, hour: int) -> datetime:
    return datetime(day.year, day.month, day.day, hour, tzinfo=TZ).astimezone(timezone.utc)


def _seed(headers, tenant_id) -> dict:
    now = datetime.now(timezone.utc)
    today = now.astimezone(TZ).date()
    month_start = today.replace(day=1)
    prev_month_end = month_start - timedelta(days=1)
    tech = client.post("/v1/users", headers=headers, json={"email": f"t-{uuid4().hex[:6]}@test.com", "full_name": "Fin Tech", "password": "pass123456", "role": "tech"}).json()["id"]
    customer = client.post("/v1/customers", headers=headers, json={"full_name": "Fin Customer", "phone": "0400000001"}).json()["id"]

    def job(title, status, cost, scheduled=None, assigned=tech):
        payload = {"customer_id": customer, "title": title, "key_quantity": 1, "priority": "normal", "status": status, "programming_status": "pending", "deposit_cents": 0, "cost_cents": cost, "job_type": "AKL"}
        if scheduled:
            payload["scheduled_at"] = scheduled.isoformat()
        if assigned:
            payload["assigned_user_id"] = assigned
        r = client.post("/v1/auto-key-jobs", headers=headers, json=payload)
        assert r.status_code == 201, r.text
        return UUID(r.json()["id"])

    d1 = month_start  # first day of this month (always in the period, always <= today)
    paid_now = job("Paid this month", "invoice_paid", 30000, _local(d1, 9))
    unpaid_now = job("Done unpaid", "work_completed", 20000, _local(d1, 11))
    booked_only = job("Booked, not done", "booking_confirmed", 15000, _local(d1, 14))
    paid_prev = job("Paid last month", "invoice_paid", 50000, _local(prev_month_end, 9))
    lost = job("No go", "no_go", 99999, _local(d1, 16))
    with Session(engine) as s:
        for jid, when in ((paid_now, _local(d1, 12)), (unpaid_now, _local(d1, 13)), (paid_prev, _local(prev_month_end, 12))):
            j = s.get(AutoKeyJob, jid)
            j.work_completed_at = when.replace(tzinfo=None)
            s.add(j)
        s.add(AutoKeyInvoice(tenant_id=tenant_id, auto_key_job_id=paid_now, invoice_number="F-1", status="paid", total_cents=30000, created_at=_local(d1, 12).replace(tzinfo=None), paid_at=_local(d1, 15).replace(tzinfo=None), payment_method="eftpos"))
        s.add(AutoKeyInvoice(tenant_id=tenant_id, auto_key_job_id=unpaid_now, invoice_number="F-2", status="unpaid", total_cents=20000, created_at=_local(d1, 13).replace(tzinfo=None)))
        s.add(AutoKeyInvoice(tenant_id=tenant_id, auto_key_job_id=paid_prev, invoice_number="F-0", status="paid", total_cents=50000, created_at=_local(prev_month_end, 12).replace(tzinfo=None), paid_at=_local(prev_month_end, 13).replace(tzinfo=None)))
        # Quotes: two sent this month, one approved.
        s.add(AutoKeyQuote(tenant_id=tenant_id, auto_key_job_id=paid_now, status="approved", total_cents=30000, sent_at=_local(d1, 8).replace(tzinfo=None), created_at=_local(d1, 8).replace(tzinfo=None)))
        s.add(AutoKeyQuote(tenant_id=tenant_id, auto_key_job_id=booked_only, status="sent", total_cents=15000, sent_at=_local(d1, 8).replace(tzinfo=None), created_at=_local(d1, 8).replace(tzinfo=None)))
        # Real transition events for the paid job: en route 09:00, on site 09:30, completed 12:00 -> 150 min on site, 30 min travel.
        s.add(TenantEventLog(tenant_id=tenant_id, entity_type="auto_key_job", entity_id=paid_now, event_type="auto_key_status_changed", event_summary="Status changed from Booking Confirmed to En Route", created_at=_local(d1, 9).replace(tzinfo=None)))
        s.add(TenantEventLog(tenant_id=tenant_id, entity_type="auto_key_job", entity_id=paid_now, event_type="auto_key_status_changed", event_summary="Status changed from En Route to On Site", created_at=(_local(d1, 9) + timedelta(minutes=30)).replace(tzinfo=None)))
        # Commission rules for the tech: 20% on everything.
        u = s.get(User, UUID(tech))
        u.mobile_commission_rules_json = '{"enabled": true, "retainer_cents_per_period": 0, "rates_bp": {"shop_referred": 2000, "tech_sourced": 2000, "minit_sourced": 2000}, "eligible_job_statuses": ["invoice_paid", "work_completed"]}'
        s.add(u)
        s.commit()
    return {"tech": tech, "paid_now": paid_now, "unpaid_now": unpaid_now, "booked_only": booked_only, "paid_prev": paid_prev, "lost": lost, "today": today, "month_start": month_start}


def test_finance_report_this_month():
    headers, tenant_id, _ = _tenant()
    ids = _seed(headers, tenant_id)
    res = client.get("/v1/reports/auto-key/finance", headers=headers, params={"period": "month"})
    assert res.status_code == 200, res.text
    body = res.json()
    assert body["period"]["start"] == ids["month_start"].isoformat()
    assert body["timezone"] == "Australia/Melbourne"
    m = {x["key"]: x for x in body["metrics"]}
    assert m["booked"]["current"] == 65000  # 300 + 200 + 150; the no-go job is excluded
    assert m["booked"]["sample"] == 3
    assert m["completed"]["current"] == 50000  # invoice totals of the two completed jobs
    assert m["invoiced"]["current"] == 50000
    assert m["collected"]["current"] == 30000
    assert m["collected"]["previous"] == 50000
    assert m["collected"]["vs_previous"] == {"abs": -20000, "pct": -40.0}
    assert m["collected"]["vs_previous_tone"] == "bad"
    assert m["collected"]["drill"] == {"date_field": "paid", "date_from": body["period"]["start"], "date_to": body["period"]["end"], "directory": "all"}
    assert m["outstanding"]["current"] == 20000 and m["outstanding"]["sample"] == 1
    assert m["outstanding"]["direction"] == "lower_is_better"
    assert m["commission"]["current"] == 6000  # 20% of $300 collected
    assert m["contribution"]["current"] == 24000
    assert m["aov"]["current"] == 30000
    assert m["jobs_completed"]["current"] == 2
    assert m["jobs_per_working_day"]["sample"] == body["period"]["working_days"] > 0
    assert m["jobs_per_working_day"]["current"] == pytest.approx(round(2 / body["period"]["working_days"], 2))
    assert m["quotes_sent"]["current"] == 2
    # Definitions travel with the numbers.
    assert "gross margin" in m["contribution"]["definition"].lower()
    assert all(x["definition"] for x in body["metrics"])

    conv = {c["key"]: c for c in body["conversion"]}
    assert conv["quote_to_approved"]["pct"] == 50.0
    assert conv["booking_to_completion"] == {**conv["booking_to_completion"], "numerator": 2, "denominator": 3}
    assert conv["lead_to_booking"]["denominator"] >= 5

    assert body["target"]["weekly_cents"] == 70000
    assert body["target"]["to_date_cents"] == round(70000 * body["period"]["elapsed_days"] / 7)
    assert body["target"]["variance_cents"] == 30000 - body["target"]["to_date_cents"]

    ageing = body["ar_ageing"]
    assert ageing["total_cents"] == 20000
    assert ageing["open_invoices"][0]["invoice_number"] == "F-2"

    assert len(body["trend"]["weeks"]) == 13
    assert body["trend"]["averages"]["collected_cents"]["last_13_avg"] is not None
    assert sum(w["collected_cents"] for w in body["trend"]["weeks"]) >= 30000

    tech = next(t for t in body["technicians"] if t["user_id"] == ids["tech"])
    assert tech["jobs_completed"] == 2 and tech["collected_cents"] == 30000 and tech["commission_cents"] == 6000
    assert tech["on_site"]["count"] == 1 and tech["on_site"]["avg_minutes"] == 150.0
    assert tech["utilisation_pct"] is not None

    d = body["durations"]
    assert d["on_site"] == {"count": 1, "avg_minutes": 150.0, "median_minutes": 150.0, "p90_minutes": 150.0}
    assert d["travel"]["count"] == 1 and d["travel"]["avg_minutes"] == 30.0
    codes = {q["code"] for q in body["data_quality"]}
    assert "no_cost_data" in codes and "duration_sample" in codes and "no_geocoding" in codes
    assert "no_commission_rules" not in codes


def test_finance_drill_downs_match_the_list():
    headers, tenant_id, _ = _tenant()
    ids = _seed(headers, tenant_id)
    body = client.get("/v1/reports/auto-key/finance", headers=headers, params={"period": "month"}).json()
    for key, expected in (
        ("collected", {ids["paid_now"]}),
        ("invoiced", {ids["paid_now"], ids["unpaid_now"]}),
        ("completed", {ids["paid_now"], ids["unpaid_now"]}),
        ("booked", {ids["paid_now"], ids["unpaid_now"], ids["booked_only"], ids["lost"]}),
    ):
        drill = next(x for x in body["metrics"] if x["key"] == key)["drill"]
        page = client.get("/v1/auto-key-jobs/page", headers=headers, params={**drill, "limit": 50})
        assert page.status_code == 200, page.text
        assert {UUID(i["id"]) for i in page["items"]} if False else {UUID(i["id"]) for i in page.json()["items"]} == expected, key
    # Validation.
    assert client.get("/v1/auto-key-jobs/page", headers=headers, params={"date_field": "paid"}).status_code == 422
    assert client.get("/v1/auto-key-jobs/page", headers=headers, params={"date_field": "nope", "date_from": "2026-01-01", "date_to": "2026-01-02"}).status_code == 422
    assert client.get("/v1/auto-key-jobs/page", headers=headers, params={"date_field": "paid", "date_from": "2026-01-02", "date_to": "2026-01-01"}).status_code == 400


def test_finance_periods_validate_and_tenants_are_isolated():
    headers, tenant_id, _ = _tenant()
    _seed(headers, tenant_id)
    other, _, _ = _tenant()
    assert client.get("/v1/reports/auto-key/finance", headers=headers, params={"period": "fortnight"}).status_code == 422
    assert client.get("/v1/reports/auto-key/finance", headers=headers, params={"period": "custom"}).status_code == 400
    assert client.get("/v1/reports/auto-key/finance", headers=headers, params={"period": "custom", "date_from": "2026-01-01", "date_to": "2026-01-31"}).status_code == 200
    for preset in ("week", "last_week", "last_month", "quarter", "last_4_weeks", "last_13_weeks"):
        assert client.get("/v1/reports/auto-key/finance", headers=headers, params={"period": preset}).status_code == 200, preset
    empty = client.get("/v1/reports/auto-key/finance", headers=other, params={"period": "month"}).json()
    assert all(x["current"] in (0, None) for x in empty["metrics"])
    assert empty["ar_ageing"]["total_cents"] == 0
    assert empty["technicians"] == []
    assert empty["target"]["collected_cents"] == 0 and empty["target"]["attainment_pct"] in (0.0, None)
    assert "no_commission_rules" in {q["code"] for q in empty["data_quality"]}


def test_finance_csv_exports_match_the_period():
    headers, tenant_id, _ = _tenant()
    ids = _seed(headers, tenant_id)
    res = client.get("/v1/reports/auto-key/finance/export", headers=headers, params={"period": "month", "kind": "summary"})
    assert res.status_code == 200, res.text
    assert res.headers["content-type"].startswith("text/csv")
    rows = list(csv.reader(io.StringIO(res.content.decode("utf-8-sig"))))
    assert rows[0][0] == "Mobile Services finance summary"
    collected = next(r for r in rows if r and r[0] == "Cash collected")
    assert collected[1] == "300.00" and collected[2] == "500.00" and collected[4] == "-40.0"
    assert any(r and r[0] == "Fin Tech" for r in rows)

    res = client.get("/v1/reports/auto-key/finance/export", headers=headers, params={"period": "month", "kind": "invoices"})
    assert res.status_code == 200
    rows = list(csv.DictReader(io.StringIO(res.content.decode("utf-8-sig"))))
    assert {r["invoice_number"] for r in rows} == {"F-1", "F-2"}  # last month's F-0 is outside the period
    paid = next(r for r in rows if r["invoice_number"] == "F-1")
    assert paid["total"] == "300.00" and paid["technician"] == "Fin Tech" and paid["payment_method"] == "eftpos"
    assert client.get("/v1/reports/auto-key/finance/export", headers=headers, params={"kind": "everything"}).status_code == 422
    # Technicians cannot export.
    tech_login = client.post("/v1/auth/login", json={"tenant_slug": client.get("/v1/auth/session", headers=headers).json()["tenant_slug"], "email": _tech_email(ids["tech"]), "password": "pass123456"})
    tech_headers = {"Authorization": f"Bearer {tech_login.json()['access_token']}"}
    assert client.get("/v1/reports/auto-key/finance/export", headers=tech_headers, params={"period": "month"}).status_code == 403
    assert client.get("/v1/reports/auto-key/finance", headers=tech_headers, params={"period": "month"}).status_code == 200


def _tech_email(user_id: str) -> str:
    with Session(engine) as s:
        return s.get(User, UUID(user_id)).email
