import os
from datetime import datetime, timedelta, timezone
from pathlib import Path
from uuid import UUID, uuid4

from sqlmodel import Session, select

_TEST_DB = Path(__file__).with_name(f"test_mobile_lead_dispatch_{uuid4().hex}.db")
os.environ["DATABASE_URL"] = f"sqlite:///{_TEST_DB.as_posix()}"
os.environ.setdefault("JWT_SECRET", "test-secret-not-for-production")
os.environ.setdefault("APP_ENV", "test")

from fastapi.testclient import TestClient

from app.database import create_db_and_tables, engine
from app.main import app
from app.models import AutoKeyJob, MobileLeadDispatch, SmsLog, Tenant
from app.services.mobile_lead_dispatch import (
    DISPATCH_STATUS_ESCALATED_HQ,
    DISPATCH_STATUS_OFFERING,
    DISPATCH_STATUS_QUOTED,
    advance_expired_dispatch,
    complete_dispatch_if_quoted,
)

create_db_and_tables()
client = TestClient(app)

WEBHOOK_SECRET = "test-webhook-secret-16chars"


def _bootstrap(slug: str, email: str, plan_code: str, *, dispatch_phone: str | None = None) -> dict:
    res = client.post(
        "/v1/auth/bootstrap",
        json={
            "tenant_name": f"Tenant {slug}",
            "tenant_slug": slug,
            "owner_email": email,
            "owner_full_name": "Owner",
            "owner_password": "pass123456",
            "plan_code": plan_code,
        },
    )
    assert res.status_code == 200, res.text
    if dispatch_phone:
        with Session(engine) as session:
            tenant = session.exec(select(Tenant).where(Tenant.slug == slug)).one()
            tenant.mobile_dispatch_phone = dispatch_phone
            session.add(tenant)
            session.commit()
    return res.json()


def _login(slug: str, email: str) -> str:
    res = client.post(
        "/v1/auth/login",
        json={"tenant_slug": slug, "email": email, "password": "pass123456"},
    )
    assert res.status_code == 200, res.text
    return res.json()["access_token"]


def _headers(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def _setup_network() -> tuple[str, str, str]:
    suffix = uuid4().hex[:8]
    hq_slug = f"hq-{suffix}"
    op1_slug = f"op1-{suffix}"
    op2_slug = f"op2-{suffix}"
    hq_email = f"hq-{suffix}@test.local"
    op1_email = f"op1-{suffix}@test.local"
    op2_email = f"op2-{suffix}@test.local"

    _bootstrap(hq_slug, hq_email, "enterprise")
    _bootstrap(op1_slug, op1_email, "basic_auto_key", dispatch_phone="+61400000001")
    _bootstrap(op2_slug, op2_email, "basic_auto_key", dispatch_phone="+61400000002")

    hq_token = _login(hq_slug, hq_email)
    hq_h = _headers(hq_token)

    for op_slug, op_email in ((op1_slug, op1_email), (op2_slug, op2_email)):
        link = client.post(
            "/v1/parent-accounts/me/link-tenant",
            headers=hq_h,
            json={"tenant_slug": op_slug, "owner_email": op_email},
        )
        assert link.status_code == 200, link.text

    enable = client.post("/v1/parent-accounts/me/mobile-lead-ingest/enable", headers=hq_h)
    assert enable.status_code == 200, enable.text
    ingest_id = enable.json()["mobile_lead_ingest_public_id"]

    secret = client.put(
        "/v1/parent-accounts/me/mobile-lead-ingest/secret",
        headers=hq_h,
        json={"webhook_secret": WEBHOOK_SECRET},
    )
    assert secret.status_code == 200, secret.text

    sites = client.get("/v1/parent-accounts/me/sites?plan_kind=operator&limit=50", headers=hq_h)
    assert sites.status_code == 200, sites.text
    op_sites = sites.json()["sites"]
    op1_id = next(s["tenant_id"] for s in op_sites if s["tenant_slug"] == op1_slug)
    op2_id = next(s["tenant_id"] for s in op_sites if s["tenant_slug"] == op2_slug)
    hq_site = client.get("/v1/parent-accounts/me/sites?limit=10", headers=hq_h).json()["sites"]
    hq_id = next(s["tenant_id"] for s in hq_site if s["tenant_slug"] == hq_slug)

    esc = client.put(
        "/v1/parent-accounts/me/mobile-lead-ingest/escalation-tenant",
        headers=hq_h,
        json={"tenant_id": hq_id},
    )
    assert esc.status_code == 200, esc.text

    dispatch_settings = client.put(
        "/v1/parent-accounts/me/mobile-lead-ingest/dispatch-settings",
        headers=hq_h,
        json={"offer_timeout_minutes": 30, "max_operator_offers": 2},
    )
    assert dispatch_settings.status_code == 200, dispatch_settings.text

    route1 = client.post(
        "/v1/parent-accounts/me/mobile-lead-routes",
        headers=hq_h,
        json={"suburb": "Sydney", "state_code": "NSW", "target_tenant_id": op1_id},
    )
    assert route1.status_code == 200, route1.text

    route2 = client.post(
        "/v1/parent-accounts/me/mobile-lead-routes",
        headers=hq_h,
        json={"suburb": "Parramatta", "state_code": "NSW", "target_tenant_id": op2_id},
    )
    assert route2.status_code == 200, route2.text

    return ingest_id, op1_id, op2_id, hq_h


def _ingest_lead(ingest_id: str, *, suburb: str = "Sydney") -> dict:
    res = client.post(
        f"/v1/public/mobile-key-leads/{ingest_id}",
        headers={"X-Mobile-Lead-Secret": WEBHOOK_SECRET},
        json={
            "suburb": suburb,
            "state_code": "NSW",
            "customer_name": "Jane Doe",
            "phone": "0412345678",
            "vehicle_make": "Toyota",
            "vehicle_model": "Corolla",
        },
    )
    assert res.status_code == 200, res.text
    return res.json()


def test_website_lead_creates_dispatch_and_sms():
    ingest_id, op1_id, _op2_id = _setup_network()
    body = _ingest_lead(ingest_id)

    assert body["dispatch_status"] == DISPATCH_STATUS_OFFERING
    assert body["tenant_id"] == op1_id
    assert body["job_id"] is not None
    assert body["offer_expires_at"] is not None

    with Session(engine) as session:
        dispatch = session.get(MobileLeadDispatch, UUID(body["dispatch_id"]))
        assert dispatch is not None
        assert dispatch.status == DISPATCH_STATUS_OFFERING
        assert str(dispatch.current_operator_tenant_id) == op1_id

        sms_rows = session.exec(
            select(SmsLog).where(SmsLog.event == "mobile_lead_offer")
        ).all()
        assert len(sms_rows) >= 1
        assert "30 min" in sms_rows[0].body


def test_dispatch_escalates_to_next_operator_then_hq():
    ingest_id, op1_id, op2_id = _setup_network()
    body = _ingest_lead(ingest_id)
    dispatch_id = UUID(body["dispatch_id"])
    first_job_id = body["job_id"]

    with Session(engine) as session:
        dispatch = session.get(MobileLeadDispatch, dispatch_id)
        assert dispatch is not None
        dispatch.offer_expires_at = datetime.now(timezone.utc) - timedelta(minutes=1)
        session.add(dispatch)
        session.commit()

        action = advance_expired_dispatch(session, dispatch)
        session.commit()
        session.refresh(dispatch)
        assert action == "next_operator"
        assert str(dispatch.current_operator_tenant_id) == op2_id
        assert str(dispatch.auto_key_job_id) != first_job_id

        first_job = session.get(AutoKeyJob, UUID(first_job_id))
        assert first_job is not None
        assert first_job.status == "failed_job"

        dispatch.offer_expires_at = datetime.now(timezone.utc) - timedelta(minutes=1)
        session.add(dispatch)
        session.commit()

        action2 = advance_expired_dispatch(session, dispatch)
        session.commit()
        session.refresh(dispatch)
        assert action2 == "escalated_hq"
        assert dispatch.status == DISPATCH_STATUS_ESCALATED_HQ


def test_outside_territory_goes_straight_to_hq():
    ingest_id, _op1_id, _op2_id = _setup_network()
    body = _ingest_lead(ingest_id, suburb="Birdsville")

    assert body["dispatch_status"] == DISPATCH_STATUS_ESCALATED_HQ
    assert body["offer_expires_at"] is None

    with Session(engine) as session:
        dispatch = session.get(MobileLeadDispatch, UUID(body["dispatch_id"]))
        assert dispatch is not None
        assert dispatch.status == DISPATCH_STATUS_ESCALATED_HQ

        sms_rows = session.exec(
            select(SmsLog)
            .where(SmsLog.event == "mobile_lead_offer")
            .where(SmsLog.auto_key_job_id == UUID(body["job_id"]))
        ).all()
        assert len(sms_rows) == 0


def test_force_hq_testing_mode_skips_operators():
    ingest_id, _op1_id, _op2_id, hq_h = _setup_network()
    settings = client.put(
        "/v1/parent-accounts/me/mobile-lead-ingest/dispatch-settings",
        headers=hq_h,
        json={"force_hq_dispatch": True},
    )
    assert settings.status_code == 200, settings.text

    body = _ingest_lead(ingest_id, suburb="Sydney")
    assert body["dispatch_status"] == DISPATCH_STATUS_ESCALATED_HQ
    assert body["offer_expires_at"] is None

    with Session(engine) as session:
        dispatch = session.get(MobileLeadDispatch, UUID(body["dispatch_id"]))
        assert dispatch is not None
        sms_rows = session.exec(
            select(SmsLog)
            .where(SmsLog.event == "mobile_lead_offer")
            .where(SmsLog.auto_key_job_id == UUID(body["job_id"]))
        ).all()
        assert len(sms_rows) == 0


def test_quote_completes_dispatch():
    ingest_id, _op1_id, _op2_id = _setup_network()
    body = _ingest_lead(ingest_id)
    job_id = body["job_id"]

    with Session(engine) as session:
        dispatch = session.get(MobileLeadDispatch, UUID(body["dispatch_id"]))
        assert dispatch is not None
        job = session.get(AutoKeyJob, UUID(job_id))
        assert job is not None
        job.status = "quote_sent"
        session.add(job)
        complete_dispatch_if_quoted(session, job.id)
        session.commit()
        session.refresh(dispatch)
        assert dispatch.status == DISPATCH_STATUS_QUOTED
