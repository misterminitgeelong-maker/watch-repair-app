"""Mobile Services operations cockpit: focus filters, comparisons, capacity."""
import os
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from uuid import UUID, uuid4
from zoneinfo import ZoneInfo

_TEST_DB = Path(__file__).with_name(f"test_mobile_cockpit_{uuid4().hex}.db")
os.environ["DATABASE_URL"] = f"sqlite:///{_TEST_DB.as_posix()}"

import pytest
from fastapi.testclient import TestClient
from sqlmodel import Session, select

from app.database import create_db_and_tables, engine
from app.main import app
from app.mobile_cockpit import (
    ASSUMED_JOB_MINUTES,
    FOCUS_KEYS,
    TECH_DAY_MINUTES,
    WeeklySeries,
    compare_metric,
    invoice_age_bucket,
    pct_change,
    technician_rows,
    tone_for,
)
from app.models import AutoKeyInvoice, AutoKeyJob, Tenant, User

create_db_and_tables()
client = TestClient(app)

TZ = ZoneInfo("Australia/Melbourne")


# ── Pure arithmetic ──────────────────────────────────────────────────────────
def test_pct_change_handles_zero_baseline():
    assert pct_change(100, 0) is None
    assert pct_change(0, 0) is None
    assert pct_change(150, 100) == 50.0
    assert pct_change(50, 100) == -50.0
    assert pct_change(50, -100) == 150.0  # baseline magnitude, not sign


def test_tone_respects_direction():
    assert tone_for("higher_is_better", 10) == "good"
    assert tone_for("higher_is_better", -10) == "bad"
    assert tone_for("lower_is_better", -10) == "good"
    assert tone_for("lower_is_better", 10) == "bad"
    assert tone_for("neutral", 10) == "neutral"
    assert tone_for("higher_is_better", 0) == "neutral"
    assert tone_for("higher_is_better", None) == "neutral"


def _series(values_by_offset: dict[int, float], anchor: date) -> WeeklySeries:
    s = WeeklySeries()
    for offset, value in values_by_offset.items():
        s.add(anchor + timedelta(days=offset), value)
    return s


def test_compare_metric_paces_an_incomplete_week_against_the_same_days():
    monday = date(2026, 9, 14)
    # Last week: 100/day. Four weeks before that: 50/day. This week so far (Mon-Wed): 120/day.
    values: dict[int, float] = {}
    for week_back in range(1, 6):
        for d in range(7):
            values[-7 * week_back + d] = 100 if week_back == 1 else 50
    for d in range(3):
        values[d] = 120
    metric = compare_metric(
        key="collected", label="Cash", unit="cents", series=_series(values, monday), this_week=monday,
        days_elapsed=3, direction="higher_is_better", target=700, definition="",
    )
    assert metric["partial"] is True
    assert metric["current"] == 360
    assert metric["previous"] == 700  # full last week, for the record
    assert metric["previous_to_date"] == 300  # Mon-Wed last week
    assert metric["vs_previous"] == {"abs": 60, "pct": 20.0}
    assert metric["vs_previous_tone"] == "good"
    # Four-week average uses the four weeks before this one: (100 + 50 + 50 + 50) / 4 per day.
    assert metric["four_week_avg"] == pytest.approx(7 * 62.5)
    assert metric["four_week_avg_to_date"] == pytest.approx(3 * 62.5)
    assert metric["vs_four_week"]["abs"] == pytest.approx(360 - 187.5)
    assert metric["target"] == 700
    assert metric["target_to_date"] == 300
    assert metric["vs_target"] == {"abs": 60, "pct": 20.0}


def test_compare_metric_with_no_history_reports_no_percentage():
    monday = date(2026, 9, 14)
    metric = compare_metric(
        key="jobs_completed", label="Jobs", unit="count", series=_series({0: 4}, monday), this_week=monday,
        days_elapsed=7, direction="higher_is_better", definition="",
    )
    assert metric["partial"] is False
    assert metric["vs_previous"] == {"abs": 4, "pct": None}
    assert metric["vs_previous_tone"] == "good"
    assert metric["vs_target"] is None
    assert metric["vs_target_tone"] == "neutral"


def test_lower_is_better_metric_marks_a_rise_as_bad():
    monday = date(2026, 9, 14)
    metric = compare_metric(
        key="x", label="x", unit="count", series=_series({-7: 2, 0: 5}, monday), this_week=monday,
        days_elapsed=7, direction="lower_is_better", definition="",
    )
    assert metric["vs_previous"]["abs"] == 3
    assert metric["vs_previous_tone"] == "bad"


def test_invoice_age_buckets():
    now = datetime(2026, 9, 18, tzinfo=timezone.utc)
    assert invoice_age_bucket(now - timedelta(days=3), now) == "current"
    assert invoice_age_bucket(now - timedelta(days=7), now) == "current"
    assert invoice_age_bucket(now - timedelta(days=8), now) == "d8_30"
    assert invoice_age_bucket(now - timedelta(days=30), now) == "d8_30"
    assert invoice_age_bucket(now - timedelta(days=31), now) == "d31_plus"
    assert invoice_age_bucket(None, now) == "current"


def test_technician_rows_capacity_and_conflicts():
    tenant_id = uuid4()
    tech = User(id=uuid4(), tenant_id=tenant_id, email="t@x", full_name="Tech One", role="tech", password_hash="x")
    owner = User(id=uuid4(), tenant_id=tenant_id, email="o@x", full_name="Owner", role="owner", password_hash="x")
    idle = User(id=uuid4(), tenant_id=tenant_id, email="i@x", full_name="Idle Tech", role="tech", password_hash="x")
    now = datetime(2026, 9, 18, 2, 0, tzinfo=timezone.utc)  # 12:00 Melbourne
    customer = uuid4()

    def job(num: str, when: datetime, user: User | None, status: str = "booking_confirmed") -> AutoKeyJob:
        return AutoKeyJob(
            tenant_id=tenant_id, customer_id=customer, job_number=num, title=num, status=status,
            scheduled_at=when.replace(tzinfo=None), assigned_user_id=user.id if user else None,
        )

    a = job("A", now - timedelta(hours=2), tech, status="on_site")
    b = job("B", now + timedelta(hours=1), tech)
    c = job("C", now + timedelta(hours=1, minutes=30), tech)  # 30 min after B -> conflict
    d = job("D", now + timedelta(hours=3), owner)
    rows = technician_rows(
        users=[tech, owner, idle], active_jobs=[a, b, c, d], today_jobs=[a, b, c, d], late_today_ids=set(),
        week_collected_by_user={tech.id: 12345}, week_completed_by_user={tech.id: 2}, now=now,
    )
    by_name = {r["name"]: r for r in rows}
    assert list(by_name) == ["Tech One", "Owner", "Idle Tech"]  # busiest first, then name
    t = by_name["Tech One"]
    assert t["scheduled_today"] == 3
    assert t["booked_minutes_today"] == 3 * ASSUMED_JOB_MINUTES
    assert t["available_minutes"] == TECH_DAY_MINUTES - 3 * ASSUMED_JOB_MINUTES
    assert t["in_field_now"] is True and t["current_job_number"] == "A"
    assert t["next_job"]["job_number"] == "B"
    assert t["conflicts"] == [{"job_id": str(b.id), "job_number": "B", "next_job_id": str(c.id), "next_job_number": "C", "gap_minutes": 30}]
    assert t["collected_week_cents"] == 12345 and t["completed_week"] == 2
    # An owner with a booking counts as capacity; a tech with nothing still appears as available.
    assert by_name["Owner"]["scheduled_today"] == 1
    assert by_name["Idle Tech"]["available_minutes"] == TECH_DAY_MINUTES


# ── End-to-end through the API ───────────────────────────────────────────────
def _tenant() -> tuple[dict[str, str], UUID, str]:
    suffix = uuid4().hex[:8]
    slug = f"cockpit-{suffix}"
    email = f"owner-{suffix}@test.com"
    r = client.post(
        "/v1/auth/bootstrap",
        json={
            "tenant_name": "Cockpit Mobile",
            "tenant_slug": slug,
            "owner_email": email,
            "owner_full_name": "Owner",
            "owner_password": "pass123456",
            "plan_code": "enterprise",
        },
    )
    assert r.status_code == 200, r.text
    login = client.post("/v1/auth/login", json={"tenant_slug": slug, "email": email, "password": "pass123456"})
    headers = {"Authorization": f"Bearer {login.json()['access_token']}"}
    with Session(engine) as s:
        tenant = s.exec(select(Tenant).where(Tenant.slug == slug)).one()
        tenant.timezone = "Australia/Melbourne"
        s.add(tenant)
        s.commit()
        tenant_id = tenant.id
    return headers, tenant_id, slug


def _user(headers: dict[str, str], name: str, role: str = "tech") -> str:
    r = client.post("/v1/users", headers=headers, json={"email": f"{uuid4().hex[:6]}@test.com", "full_name": name, "password": "pass123456", "role": role})
    assert r.status_code in (200, 201), r.text
    return r.json()["id"]


def _customer(headers: dict[str, str]) -> str:
    r = client.post("/v1/customers", headers=headers, json={"full_name": f"Cust {uuid4().hex[:4]}", "phone": "0400000000"})
    assert r.status_code == 201, r.text
    return r.json()["id"]


def _job(headers, customer_id, title, *, status="awaiting_quote", scheduled_at=None, assigned_user_id=None, cost_cents=0, job_address="1 Test St") -> str:
    payload = {
        "customer_id": customer_id, "title": title, "key_quantity": 1, "priority": "normal", "status": status,
        "programming_status": "pending", "deposit_cents": 0, "cost_cents": cost_cents, "job_address": job_address,
    }
    if scheduled_at:
        payload["scheduled_at"] = scheduled_at.isoformat()
    if assigned_user_id:
        payload["assigned_user_id"] = assigned_user_id
    r = client.post("/v1/auto-key-jobs", headers=headers, json=payload)
    assert r.status_code == 201, r.text
    return r.json()["id"]


def _set(job_id: str, **fields) -> None:
    with Session(engine) as s:
        job = s.get(AutoKeyJob, UUID(job_id))
        for k, v in fields.items():
            setattr(job, k, v)
        s.add(job)
        s.commit()


def _invoice(tenant_id: UUID, job_id: str, total: int, *, status: str, created_at: datetime, paid_at: datetime | None = None) -> None:
    with Session(engine) as s:
        s.add(
            AutoKeyInvoice(
                tenant_id=tenant_id, auto_key_job_id=UUID(job_id), invoice_number=f"INV-{uuid4().hex[:6]}", status=status,
                subtotal_cents=total, total_cents=total, created_at=created_at.replace(tzinfo=None),
                paid_at=paid_at.replace(tzinfo=None) if paid_at else None,
            )
        )
        s.commit()


def _seed(headers, tenant_id):
    now = datetime.now(timezone.utc)
    local_now = now.astimezone(TZ)
    today = local_now.date()
    monday = today - timedelta(days=today.weekday())
    tech = _user(headers, "Tech Alpha")
    customer = _customer(headers)
    def local(day: date, hour: int, minute: int = 0) -> datetime:
        return datetime(day.year, day.month, day.day, hour, minute, tzinfo=TZ).astimezone(timezone.utc)

    # Booked yesterday evening and never started -> late, and not part of today.
    late = _job(headers, customer, "Late one", status="booking_confirmed", scheduled_at=local(today - timedelta(days=1), 23, 0), assigned_user_id=tech, cost_cents=20000)
    # Two bookings 30 minutes apart late tonight -> today + conflict, not late.
    b1 = _job(headers, customer, "Tonight A", status="booking_confirmed", scheduled_at=local(today, 23, 0), assigned_user_id=tech, cost_cents=15000)
    b2 = _job(headers, customer, "Tonight B", status="booking_confirmed", scheduled_at=local(today, 23, 30), assigned_user_id=tech, cost_cents=0)
    unscheduled = _job(headers, customer, "No time yet", status="awaiting_quote")  # also unassigned + needs quote
    on_hold = _job(headers, customer, "Parts", status="booking_on_hold", scheduled_at=now - timedelta(days=1), assigned_user_id=tech)
    stale_quote = _job(headers, customer, "Quoted ages ago", status="quote_sent")
    _set(stale_quote, updated_at=(now - timedelta(days=3)).replace(tzinfo=None))
    fresh_quote = _job(headers, customer, "Quoted today", status="quote_sent")
    unconfirmed = _job(headers, customer, "Sent booking", status="awaiting_booking_confirmation")
    _set(unconfirmed, updated_at=(now - timedelta(hours=30)).replace(tzinfo=None))
    legacy_pending = _job(headers, customer, "Legacy pending", status="awaiting_quote")
    _set(legacy_pending, status="pending_booking", updated_at=(now - timedelta(hours=30)).replace(tzinfo=None))
    done_unpaid = _job(headers, customer, "Done unpaid", status="work_completed", assigned_user_id=tech)
    _set(done_unpaid, work_completed_at=local(monday, 8).replace(tzinfo=None))  # this week, whatever today is
    _invoice(tenant_id, done_unpaid, 30000, status="unpaid", created_at=now - timedelta(days=10))  # overdue
    paid_this_week = _job(headers, customer, "Paid this week", status="invoice_paid", assigned_user_id=tech)
    _set(paid_this_week, work_completed_at=local(monday, 9).replace(tzinfo=None))
    _invoice(tenant_id, paid_this_week, 25000, status="paid", created_at=local(monday, 9), paid_at=local(monday, 10))
    paid_last_week = _job(headers, customer, "Paid last week", status="invoice_paid", assigned_user_id=tech)
    _set(paid_last_week, work_completed_at=local(monday - timedelta(days=7), 9).replace(tzinfo=None))
    _invoice(tenant_id, paid_last_week, 50000, status="paid", created_at=local(monday - timedelta(days=7), 9), paid_at=local(monday - timedelta(days=7), 10))
    return {
        "tech": tech, "late": late, "b1": b1, "b2": b2, "unscheduled": unscheduled, "on_hold": on_hold,
        "stale_quote": stale_quote, "fresh_quote": fresh_quote, "unconfirmed": unconfirmed, "legacy_pending": legacy_pending,
        "done_unpaid": done_unpaid, "paid_this_week": paid_this_week, "paid_last_week": paid_last_week, "monday": monday, "today": today,
    }


def test_cockpit_counts_match_the_list_drill_down_for_every_focus():
    headers, tenant_id, _ = _tenant()
    ids = _seed(headers, tenant_id)
    res = client.get("/v1/reports/auto-key/cockpit", headers=headers)
    assert res.status_code == 200, res.text
    body = res.json()
    assert body["timezone"] == "Australia/Melbourne"
    assert body["as_of"] == ids["today"].isoformat()
    assert body["week"]["start"] == ids["monday"].isoformat()

    queues = {q["key"]: q for q in body["attention"]}
    queues.update({v["key"]: v for v in body["follow_ups"].values()})
    expected = {
        "late": {ids["late"]},
        "today": {ids["b1"], ids["b2"]},
        "in_field": set(),
        "unscheduled": {ids["unscheduled"], ids["stale_quote"], ids["fresh_quote"], ids["unconfirmed"], ids["legacy_pending"]},
        "unassigned": {ids["unscheduled"], ids["stale_quote"], ids["fresh_quote"], ids["unconfirmed"], ids["legacy_pending"]},
        "on_hold": {ids["on_hold"]},
        "needs_quote": {ids["unscheduled"]},
        "quote_follow_up": {ids["stale_quote"]},
        "confirmation_follow_up": {ids["unconfirmed"], ids["legacy_pending"]},
        "completed_unpaid": {ids["done_unpaid"]},
        "overdue_invoices": {ids["done_unpaid"]},
        "unpaid_invoices": {ids["done_unpaid"]},
        "this_week": {ids["b1"], ids["b2"]} | ({ids["late"], ids["on_hold"]} if ids["today"].weekday() > 0 else set()),  # yesterday is in this week unless today is Monday
        "completed_this_week": {ids["done_unpaid"], ids["paid_this_week"]},
        "invoiced_this_week": {ids["paid_this_week"]},
        "collected_this_week": {ids["paid_this_week"]},
    }
    assert set(FOCUS_KEYS) == set(expected)
    for key, job_ids in expected.items():
        if key in queues:
            assert queues[key]["count"] == len(job_ids), key
            assert {item["id"] for item in queues[key]["items"]} == job_ids, key
        else:
            assert body["period_drill"][key]["count"] == len(job_ids), key
        page = client.get("/v1/auto-key-jobs/page", headers=headers, params={"focus": key, "limit": 50})
        assert page.status_code == 200, page.text
        assert page.json()["total"] == len(job_ids), key
        assert {item["id"] for item in page.json()["items"]} == job_ids, key

    # Items are labelled with the canonical vocabulary, even for a legacy stored value.
    legacy = next(i for i in queues["confirmation_follow_up"]["items"] if i["id"] == ids["legacy_pending"])
    assert legacy["status"] == "pending_booking"
    assert legacy["canonical_status"] == "awaiting_booking_confirmation"
    assert legacy["category"] == "booking"


def test_cockpit_money_ladder_and_capacity():
    headers, tenant_id, _ = _tenant()
    ids = _seed(headers, tenant_id)
    body = client.get("/v1/reports/auto-key/cockpit", headers=headers).json()
    metrics = {m["key"]: m for m in body["metrics"]}
    collected = metrics["collected"]
    assert collected["current"] == 25000
    assert collected["previous"] == 50000
    # Monday counts in both weeks whatever today is, so like-for-like pacing sees last Monday's $500.
    assert collected["previous_to_date"] == 50000
    assert collected["vs_previous"] == {"abs": -25000, "pct": -50.0}
    assert collected["vs_previous_tone"] == "bad"
    assert collected["target"] is None and collected["vs_target"] is None
    assert collected["partial"] == (body["week"]["days_elapsed"] < 7)
    assert metrics["jobs_completed"]["current"] == 2
    assert metrics["completed"]["current"] == 55000  # $250 paid + $300 invoiced-unpaid, both completed this week
    assert metrics["booked"]["current"] >= 15000  # tonight's priced booking; the late one may fall in this week too

    outstanding = body["outstanding"]
    assert outstanding["current"] == 30000
    assert outstanding["count"] == 1
    assert outstanding["aging_cents"] == {"current": 0, "d8_30": 30000, "d31_plus": 0}
    assert outstanding["overdue_cents"] == 30000
    assert body["follow_ups"]["overdue_invoices"]["value_cents"] == 30000
    assert body["follow_ups"]["overdue_invoices"]["items"][0]["invoice_age_days"] == 10
    assert body["follow_ups"]["completed_unpaid"]["value_cents"] == 30000

    techs = {t["user_id"]: t for t in body["technicians"]}
    alpha = techs[ids["tech"]]
    # Two tonight (the late one was yesterday); the tonight pair conflicts.
    assert alpha["scheduled_today"] == 2
    assert alpha["late_today"] == 0
    assert alpha["active_jobs"] == 4  # late, tonight x2, on hold
    assert len(alpha["conflicts"]) == 1
    assert alpha["conflicts"][0]["gap_minutes"] == 30
    assert alpha["collected_week_cents"] == 25000
    assert alpha["completed_week"] == 2  # paid this week + done unpaid, both completed on Monday
    assert body["capacity"]["conflicts"] == 1
    assert body["capacity"]["capacity_minutes"] == TECH_DAY_MINUTES * len(body["technicians"])

    categories = {c["category"]: c["count"] for c in body["active_by_category"]}
    assert categories["pipeline"] == 3  # needs quote + two quote_sent
    assert categories["booking"] == 6  # late, tonight x2, on hold, unconfirmed x2
    codes = {d["code"] for d in body["data_quality"]}
    assert {"assumed_duration", "no_target", "unpriced_bookings", "no_geocoding"} <= codes


def test_owner_sets_weekly_target_and_pacing_appears():
    headers, tenant_id, slug = _tenant()
    _seed(headers, tenant_id)
    res = client.patch("/v1/reports/auto-key/cockpit/target", headers=headers, json={"weekly_target_cents": 70000})
    assert res.status_code == 200, res.text
    body = client.get("/v1/reports/auto-key/cockpit", headers=headers).json()
    collected = next(m for m in body["metrics"] if m["key"] == "collected")
    assert collected["target"] == 70000
    assert collected["target_to_date"] == pytest.approx(70000 * body["week"]["days_elapsed"] / 7)
    assert collected["vs_target"]["abs"] == pytest.approx(25000 - collected["target_to_date"])
    assert body["weekly_target_cents"] == 70000
    assert "no_target" not in {d["code"] for d in body["data_quality"]}
    # Technicians cannot set it.
    tech_id = _user(headers, "Target Tech")
    with Session(engine) as s:
        tech = s.get(User, UUID(tech_id))
        email = tech.email
    login = client.post("/v1/auth/login", json={"tenant_slug": slug, "email": email, "password": "pass123456"})
    tech_headers = {"Authorization": f"Bearer {login.json()['access_token']}"}
    assert client.patch("/v1/reports/auto-key/cockpit/target", headers=tech_headers, json={"weekly_target_cents": 1}).status_code == 403
    # Clearing works.
    assert client.patch("/v1/reports/auto-key/cockpit/target", headers=headers, json={"weekly_target_cents": None}).json()["weekly_target_cents"] is None


def test_cockpit_is_tenant_isolated_and_empty_state_is_clean():
    headers, _tenant_id, _ = _tenant()
    other, other_id, _ = _tenant()
    _seed(other, other_id)
    body = client.get("/v1/reports/auto-key/cockpit", headers=headers).json()
    assert all(q["count"] == 0 and q["items"] == [] for q in body["attention"])
    assert all(v["count"] == 0 for v in body["follow_ups"].values())
    assert body["outstanding"]["current"] == 0
    for metric in body["metrics"]:
        assert metric["current"] == 0
        assert metric["vs_previous"] == {"abs": 0, "pct": None}
        assert metric["vs_previous_tone"] == "neutral"
    assert body["technicians"] == []
    assert "no_technicians" in {d["code"] for d in body["data_quality"]}
    assert client.get("/v1/auto-key-jobs/page", headers=headers, params={"focus": "late"}).json()["total"] == 0
    assert client.get("/v1/auto-key-jobs/page", headers=headers, params={"focus": "nope"}).status_code == 422
    assert client.get("/v1/auto-key-jobs/page", headers=headers, params={"category": "nope"}).status_code == 422


def test_category_filter_on_the_list_uses_the_vocabulary():
    headers, tenant_id, _ = _tenant()
    ids = _seed(headers, tenant_id)
    page = client.get("/v1/auto-key-jobs/page", headers=headers, params={"category": "pipeline", "limit": 50}).json()
    assert {i["id"] for i in page["items"]} == {ids["unscheduled"], ids["stale_quote"], ids["fresh_quote"]}
    page = client.get("/v1/auto-key-jobs/page", headers=headers, params={"directory": "all", "category": "paid", "limit": 50}).json()
    assert {i["id"] for i in page["items"]} == {ids["paid_this_week"], ids["paid_last_week"]}


def test_as_of_rejects_bad_dates():
    headers, _, _ = _tenant()
    assert client.get("/v1/reports/auto-key/cockpit", headers=headers, params={"as_of": "yesterday"}).status_code == 400
    assert client.get("/v1/reports/auto-key/cockpit", headers=headers, params={"as_of": "2026-09-01"}).status_code == 200
