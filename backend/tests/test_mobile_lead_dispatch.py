import os
from pathlib import Path
from uuid import UUID, uuid4

from sqlmodel import Session, select

_TEST_DB = Path(__file__).with_name(f"test_mobile_lead_dispatch_{uuid4().hex}.db")
os.environ.setdefault("DATABASE_URL", f"sqlite:///{_TEST_DB.as_posix()}")
os.environ.setdefault("JWT_SECRET", "test-secret-not-for-production")
os.environ.setdefault("APP_ENV", "test")

from fastapi.testclient import TestClient

from app.database import create_db_and_tables, engine
from app.main import app
from app.models import AutoKeyJob, ProspectLead, SmsLog, Tenant
from network_link_helpers import link_and_accept, mark_owner_accepted

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


def _setup_network(*, force_hq: bool = False, live: bool = True) -> tuple[str, str, str, str, dict[str, str]]:
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
        link = link_and_accept(client,
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
    if live:
        for _op_id in (op1_id, op2_id):
            mark_owner_accepted(UUID(_op_id))
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


def test_website_lead_skips_operator_who_has_not_accepted_invite():
    ingest_id, op1_id, _op2_id, hq_id, _hq_h = _setup_network(live=False)
    body = _ingest_lead(ingest_id, suburb="Sydney")
    assert body["tenant_id"] == hq_id
    assert body["tenant_id"] != op1_id


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


def test_hq_sets_operator_base_location_and_operator_cannot(monkeypatch):
    _ingest_id, op1_id, _op2_id, _hq_id, hq_h = _setup_network()

    async def _fake_geocode(address: str):
        return (-33.87, 151.21)

    monkeypatch.setattr("app.routes.parent_accounts.geocode_address", _fake_geocode)
    monkeypatch.setattr("app.routes.parent_accounts.postcode_centroid", lambda pc: (-33.87, 151.21))
    monkeypatch.setattr("app.routes.intake_dispatch.geocode_address", _fake_geocode)

    bad = client.put(f"/v1/parent-accounts/me/sites/{op1_id}/base-location", headers=hq_h, json={"postcode": "20"})
    assert bad.status_code == 400
    res = client.put(
        f"/v1/parent-accounts/me/sites/{op1_id}/base-location",
        headers=hq_h,
        json={"postcode": "2000", "ring_radius_km": 25},
    )
    assert res.status_code == 200, res.text
    assert res.json()["ring_radius_km"] == 25
    with Session(engine) as session:
        tenant = session.get(Tenant, UUID(op1_id))
        assert tenant.base_lat == -33.87 and tenant.ring_radius_km == 25

    sites = client.get("/v1/parent-accounts/me/sites?plan_kind=operator&limit=50", headers=hq_h).json()["sites"]
    site = next(s for s in sites if s["tenant_id"] == op1_id)
    assert site["base_lat"] == -33.87 and site["ring_radius_km"] == 25

    with Session(engine) as session:
        slug = session.get(Tenant, UUID(op1_id)).slug
    op_token = _login(slug, next(e for e in [f"op1-{slug.split('-', 1)[1]}@test.local"]))
    blocked = client.post(
        "/v1/settings/dispatch-base-location",
        headers=_headers(op_token),
        json={"address": "1 Somewhere St, Sydney NSW 2000", "ring_radius_km": 5},
    )
    assert blocked.status_code == 403, blocked.text


def test_bare_postcode_works_without_google_key(monkeypatch):
    _ingest_id, op1_id, _op2_id, _hq_id, hq_h = _setup_network()

    async def _no_key(address: str):
        raise ValueError("GOOGLE_MAPS_WEB_SERVICES_KEY is not configured.")

    monkeypatch.setattr("app.routes.parent_accounts.geocode_address", _no_key)
    monkeypatch.setattr("app.routes.parent_accounts.postcode_centroid", lambda pc: (-37.88, 145.08))
    res = client.put(
        f"/v1/parent-accounts/me/sites/{op1_id}/base-location",
        headers=hq_h,
        json={"postcode": "3148", "ring_radius_km": 20},
    )
    assert res.status_code == 200, res.text
    assert res.json()["base_lat"] == -37.88

    full = client.put(
        f"/v1/parent-accounts/me/sites/{op1_id}/base-location",
        headers=hq_h,
        json={"address": "1 Depot St, Chadstone VIC", "ring_radius_km": 20},
    )
    assert full.status_code == 422
    assert "not configured" in full.text
