"""Dispatch Pool digest alerts: one SMS+email per nearby operator, once per stale job."""
import os
from datetime import datetime, timedelta, timezone
from pathlib import Path
from uuid import UUID, uuid4

from sqlmodel import Session, select

_TEST_DB = Path(__file__).with_name(f"test_pool_alerts_{uuid4().hex}.db")
os.environ["DATABASE_URL"] = f"sqlite:///{_TEST_DB.as_posix()}"
os.environ.setdefault("JWT_SECRET", "test-secret-not-for-production")
os.environ.setdefault("APP_ENV", "test")

from fastapi.testclient import TestClient

from app.database import create_db_and_tables, engine
from app.main import app
from app.models import EmailLog, IntakeJob, SmsLog, Tenant
from app.services.pool_alerts import process_stale_pool_jobs

create_db_and_tables()
client = TestClient(app)

SYDNEY = (-33.8688, 151.2093)
PERTH = (-31.9523, 115.8613)


def _bootstrap_operator(slug: str, *, lat: float, lng: float, phone: str = "+61400000099") -> UUID:
    suffix = uuid4().hex[:6]
    email = f"owner-{slug}-{suffix}@test.local"
    res = client.post(
        "/v1/auth/bootstrap",
        json={
            "tenant_name": f"Operator {slug}",
            "tenant_slug": slug,
            "owner_email": email,
            "owner_full_name": "Owner",
            "owner_password": "pass123456",
            "plan_code": "basic_auto_key",
        },
    )
    assert res.status_code == 200, res.text
    tenant_id = UUID(res.json()["tenant_id"])
    with Session(engine) as session:
        tenant = session.get(Tenant, tenant_id)
        tenant.base_lat = lat
        tenant.base_lng = lng
        tenant.mobile_dispatch_phone = phone
        tenant.shop_email = email
        session.add(tenant)
        session.commit()
    return tenant_id


def _make_intake_job(*, lat: float, lng: float, age_minutes: int) -> UUID:
    with Session(engine) as session:
        job = IntakeJob(
            customer_name="Jane Doe",
            job_address="1 Test St",
            job_lat=lat,
            job_lng=lng,
            status="unclaimed",
            created_at=datetime.now(timezone.utc) - timedelta(minutes=age_minutes),
        )
        session.add(job)
        session.commit()
        session.refresh(job)
        return job.id


def test_stale_job_alerts_nearby_operator_once():
    suffix = uuid4().hex[:6]
    op_id = _bootstrap_operator(f"pa-near-{suffix}", lat=SYDNEY[0], lng=SYDNEY[1])
    job_id = _make_intake_job(lat=SYDNEY[0], lng=SYDNEY[1], age_minutes=15)

    with Session(engine) as session:
        summary = process_stale_pool_jobs(session)
    assert summary["stale_jobs"] >= 1
    assert summary["operators_alerted"] >= 1

    with Session(engine) as session:
        job = session.get(IntakeJob, job_id)
        assert job.alerted_at is not None

        sms_rows = session.exec(
            select(SmsLog).where(SmsLog.event == "pool_jobs_waiting").where(SmsLog.tenant_id == op_id)
        ).all()
        assert len(sms_rows) == 1
        assert "1 job" in sms_rows[0].body

        email_rows = session.exec(
            select(EmailLog).where(EmailLog.event == "pool_jobs_waiting").where(EmailLog.tenant_id == op_id)
        ).all()
        assert len(email_rows) == 1

    # Second sweep must not re-alert the same job/operator.
    with Session(engine) as session:
        summary2 = process_stale_pool_jobs(session)
    assert summary2["stale_jobs"] == 0
    with Session(engine) as session:
        sms_rows_after = session.exec(
            select(SmsLog).where(SmsLog.event == "pool_jobs_waiting").where(SmsLog.tenant_id == op_id)
        ).all()
        assert len(sms_rows_after) == 1


def test_distant_operator_not_alerted():
    suffix = uuid4().hex[:6]
    op_id = _bootstrap_operator(f"pa-far-{suffix}", lat=PERTH[0], lng=PERTH[1])
    _make_intake_job(lat=SYDNEY[0], lng=SYDNEY[1], age_minutes=15)

    with Session(engine) as session:
        process_stale_pool_jobs(session)

    with Session(engine) as session:
        sms_rows = session.exec(
            select(SmsLog).where(SmsLog.event == "pool_jobs_waiting").where(SmsLog.tenant_id == op_id)
        ).all()
        assert len(sms_rows) == 0


def test_fresh_job_not_yet_alerted():
    suffix = uuid4().hex[:6]
    _bootstrap_operator(f"pa-fresh-{suffix}", lat=SYDNEY[0], lng=SYDNEY[1])
    job_id = _make_intake_job(lat=SYDNEY[0], lng=SYDNEY[1], age_minutes=2)

    with Session(engine) as session:
        process_stale_pool_jobs(session)

    with Session(engine) as session:
        job = session.get(IntakeJob, job_id)
        assert job.alerted_at is None
