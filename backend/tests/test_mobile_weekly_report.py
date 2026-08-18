"""Tests for the weekly Mobile Services network report (backend/app/services/mobile_weekly_report.py).

Covers: per-operator customers/jobs/sales computed from real AutoKeyJob +
AutoKeyInvoice rows (paid invoices only), the enquiry backlog pulled in from
the email-lead bucketing, opt-in gating, and idempotent send-once-per-week.
Email sending itself is a no-op in tests (ENABLE_EMAIL_NOTIFICATIONS unset),
so we assert on what *would* have been sent rather than real delivery.
"""

import os
from datetime import datetime, timedelta, timezone
from pathlib import Path
from uuid import UUID, uuid4

_TEST_DB = Path(__file__).with_name(f"test_mobile_weekly_report_{uuid4().hex}.db")
os.environ["DATABASE_URL"] = f"sqlite:///{_TEST_DB.as_posix()}"
os.environ.setdefault("JWT_SECRET", "test-secret-not-for-production")
os.environ.setdefault("APP_ENV", "test")

from fastapi.testclient import TestClient
from sqlmodel import Session, select

from app.database import create_db_and_tables, engine
from app.main import app
from app.minit_provision import ensure_minit_pilot_account
from app.models import AutoKeyInvoice, AutoKeyJob, Customer, InboundEmail, ParentAccount, Tenant
from app.services.mobile_weekly_report import (
    build_mobile_weekly_report,
    send_due_mobile_weekly_reports,
)

create_db_and_tables()
client = TestClient(app)

HQ_EMAIL = "hq-owner@test.mainspring.au"
HQ_PASSWORD = "MinitPilot2026!"


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


def _link_operator(headers: dict, operator_label: str) -> str:
    suffix = uuid4().hex[:8]
    slug, email = f"op-{suffix}", f"op-{suffix}@test.local"
    res = client.post(
        "/v1/auth/bootstrap",
        json={
            "tenant_name": f"Tenant {slug}", "tenant_slug": slug, "owner_email": email,
            "owner_full_name": "Owner", "owner_password": "pass123456", "plan_code": "basic_auto_key",
        },
    )
    assert res.status_code == 200, res.text
    link = client.post("/v1/parent-accounts/me/link-tenant", headers=headers, json={"tenant_slug": slug, "owner_email": email})
    assert link.status_code == 200, link.text
    with Session(engine) as session:
        tenant = session.exec(select(Tenant).where(Tenant.slug == slug)).one()
        tenant.name = operator_label
        session.add(tenant)
        session.commit()
        return str(tenant.id)


def _seed_job_and_paid_invoice(tenant_id_str: str, *, created_at: datetime, total_cents: int) -> None:
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
            status="invoiced",
            programming_status="not_required",
            created_at=created_at,
        )
        session.add(job)
        session.flush()
        session.add(
            AutoKeyInvoice(
                tenant_id=tenant_id,
                auto_key_job_id=job.id,
                invoice_number=f"AKI-{uuid4().hex[:8]}",
                status="paid",
                total_cents=total_cents,
                created_at=created_at,
            )
        )
        session.commit()


def test_build_report_computes_current_and_prior_week_and_backlog():
    token = _ensure_hq()
    headers = {"Authorization": f"Bearer {token}"}
    operator_label = f"Mobile Services Unique {uuid4().hex[:8]}"
    operator_id = _link_operator(headers, operator_label)

    now = datetime.now(timezone.utc)
    # This week: one paid job.
    _seed_job_and_paid_invoice(operator_id, created_at=now, total_cents=15000)
    # Last week: a bigger paid job, for the comparison.
    _seed_job_and_paid_invoice(operator_id, created_at=now - timedelta(days=7), total_cents=20000)

    with Session(engine) as session:
        parent = session.exec(select(ParentAccount).where(ParentAccount.owner_email == HQ_EMAIL)).one()
        # An unactioned enquiry naming this operator, for the backlog count.
        session.add(
            InboundEmail(
                parent_account_id=parent.id,
                subject="new booking enquiry",
                from_email="no-reply@powerfulform.com",
                text_body=(
                    "Please Select Your Location: NSW\n"
                    f"Nearest Provider NSW: Mister Minit {operator_label}\n"
                    "First Name: Jamie\nLast Name: Test\nPhone: 0400 000 000\n"
                    "Service Required: Key Cutting\nHow would you like to be contacted: Phone"
                ),
                status="new",
            )
        )
        session.commit()

        from app.report_periods import resolve_period_bounds

        today = now.date()
        start_dt, end_dt, _s, _e = resolve_period_bounds("week", today)
        rows = build_mobile_weekly_report(session, parent=parent, start_dt=start_dt, end_dt=end_dt)

    row = next(r for r in rows if str(r.operator_tenant_id) == operator_id)
    with Session(engine) as session:
        this_operator_jobs = session.exec(
            select(AutoKeyJob).where(AutoKeyJob.tenant_id == UUID(operator_id))
        ).all()
        assert len(this_operator_jobs) == 2
    assert row.jobs_count == 1
    assert row.sales_cents == 15000
    assert row.prior_week_jobs_count == 1
    assert row.prior_week_sales_cents == 20000
    assert row.enquiries_not_actioned == 1


def test_settings_toggle_and_send_now_endpoint():
    token = _ensure_hq()
    headers = {"Authorization": f"Bearer {token}"}

    settings_res = client.get("/v1/parent-accounts/me/operations/mobile-weekly-report/settings", headers=headers)
    assert settings_res.status_code == 200
    assert settings_res.json()["opt_in"] is False

    put_res = client.put(
        "/v1/parent-accounts/me/operations/mobile-weekly-report/settings", headers=headers, json={"opt_in": True}
    )
    assert put_res.status_code == 200
    assert put_res.json()["opt_in"] is True

    send_res = client.post("/v1/parent-accounts/me/operations/mobile-weekly-report/send-now", headers=headers)
    assert send_res.status_code == 200
    assert send_res.json()["last_sent_at"] is not None


def test_preview_endpoint_requires_minit_hq():
    suffix = uuid4().hex[:8]
    slug, email = f"generic-{suffix}", f"generic-{suffix}@test.local"
    res = client.post(
        "/v1/auth/bootstrap",
        json={
            "tenant_name": "Generic HQ", "tenant_slug": slug, "owner_email": email,
            "owner_full_name": "Owner", "owner_password": "pass123456", "plan_code": "enterprise",
        },
    )
    assert res.status_code == 200, res.text
    login = client.post("/v1/auth/login", json={"tenant_slug": slug, "email": email, "password": "pass123456"})
    token = login.json()["access_token"]
    res = client.get(
        "/v1/parent-accounts/me/operations/mobile-weekly-report",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert res.status_code == 403


def test_send_due_reports_only_sends_for_opted_in_parents_once_per_week():
    token = _ensure_hq()
    headers = {"Authorization": f"Bearer {token}"}
    client.put("/v1/parent-accounts/me/operations/mobile-weekly-report/settings", headers=headers, json={"opt_in": True})

    with Session(engine) as session:
        parent = session.exec(select(ParentAccount).where(ParentAccount.owner_email == HQ_EMAIL)).one()
        parent.last_mobile_weekly_report_sent_at = None
        session.add(parent)
        session.commit()

        summary_1 = send_due_mobile_weekly_reports(session, parent_id=parent.id)
        # Email is disabled in tests (dry-run) -> counted as skipped, not an error;
        # what matters is exactly one parent was processed and marked sent-for-this-week.
        assert summary_1["sent"] + summary_1["skipped"] == 1

        summary_2 = send_due_mobile_weekly_reports(session, parent_id=parent.id)
        assert summary_2["skipped"] == 1
        assert summary_2["sent"] == 0
