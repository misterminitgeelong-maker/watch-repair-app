import os
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
from app.models import AutoKeyJob, ProspectLead, SmsLog, Tenant

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


def _setup_network(*, force_hq: bool = False) -> tuple[str, str, str, str, dict[str, str]]:
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

    if force_hq:
        settings = client.put(
            "/v1/parent-accounts/me/mobile-lead-ingest/dispatch-settings",
            headers=hq_h,
            json={"force_hq_dispatch": True},
        )
        assert settings.status_code == 200, settings.text

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

    return ingest_id, op1_id, op2_id, hq_id, hq_h


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


def test_website_lead_routes_to_mapped_operator_and_alerts_with_no_timer():
    """A website enquiry is just an email — routed to Lead Inbox, no job, no countdown."""
    ingest_id, op1_id, _op2_id, _hq_id, _hq_h = _setup_network()
    op1_jobs_before = 0
    with Session(engine) as session:
        op1_jobs_before = len(
            session.exec(select(AutoKeyJob).where(AutoKeyJob.tenant_id == UUID(op1_id))).all()
        )

    body = _ingest_lead(ingest_id)
    assert body["tenant_id"] == op1_id
    assert "lead_id" in body
    assert "dispatch_id" not in body
    assert "job_id" not in body

    with Session(engine) as session:
        lead = session.get(ProspectLead, UUID(body["lead_id"]))
        assert lead is not None
        assert str(lead.tenant_id) == op1_id
        assert lead.source == "website_lead"
        assert lead.status == "new"
        assert lead.name == "Jane Doe"

        # No live job is created for a website lead — it sits in Lead Inbox until the
        # operator works it.
        op1_jobs_after = session.exec(
            select(AutoKeyJob).where(AutoKeyJob.tenant_id == UUID(op1_id))
        ).all()
        assert len(op1_jobs_after) == op1_jobs_before

        sms_rows = session.exec(
            select(SmsLog).where(SmsLog.event == "website_lead_alert")
        ).all()
        assert len(sms_rows) >= 1
        # No timeout/countdown language — this is a one-time FYI, unlike a live shop booking.
        assert "min" not in sms_rows[0].body.lower()
        assert "Lead Inbox" in sms_rows[0].body


def test_website_lead_routes_by_suburb_map():
    """Different suburbs route to the operator mapped for that suburb."""
    ingest_id, _op1_id, op2_id, _hq_id, _hq_h = _setup_network()
    body = _ingest_lead(ingest_id, suburb="Parramatta")
    assert body["tenant_id"] == op2_id

    with Session(engine) as session:
        lead = session.get(ProspectLead, UUID(body["lead_id"]))
        assert lead is not None
        assert str(lead.tenant_id) == op2_id
        assert lead.suburb_name == "Parramatta"


def test_outside_territory_goes_straight_to_hq():
    ingest_id, _op1_id, _op2_id, hq_id, _hq_h = _setup_network()
    body = _ingest_lead(ingest_id, suburb="Birdsville")
    assert body["tenant_id"] == hq_id

    with Session(engine) as session:
        lead = session.get(ProspectLead, UUID(body["lead_id"]))
        assert lead is not None
        assert str(lead.tenant_id) == hq_id
        assert lead.source == "website_lead"


def test_force_hq_testing_mode_skips_operators():
    ingest_id, op1_id, _op2_id, hq_id, _hq_h = _setup_network(force_hq=True)
    body = _ingest_lead(ingest_id, suburb="Sydney")
    assert body["tenant_id"] == hq_id
    assert body["tenant_id"] != op1_id
