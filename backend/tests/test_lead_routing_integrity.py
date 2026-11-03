"""Lead routing integrity: idempotent public creators, invited-only dispatch, atomic accept,
network-scoped + redacted Dispatch Pool, and HQ lead-volume counting website leads."""
from datetime import datetime, timedelta, timezone
from uuid import UUID, uuid4

import pytest
from sqlmodel import Session, select

from app.database import engine
from app.models import (
    AutoKeyJob,
    IntakeJob,
    ParentAccount,
    ProspectLead,
    ShopMobileBookingRequest,
    SmsLog,
    Tenant,
    User,
)
from app.security import decode_access_token
from network_link_helpers import link_and_accept, mark_owner_accepted, put_operators_in_new_network

SECRET = "test-webhook-secret-16chars"


def _tid(token: str) -> UUID:
    return decode_access_token(token).tenant_id


def _h(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
def lead_network(client, bootstrap_and_login):
    """HQ + one live operator routed for Sydney NSW, with the website lead feed enabled."""
    sfx = uuid4().hex[:8]
    hq_email, op_email = f"hq-{sfx}@test.local", f"op-{sfx}@test.local"
    hq_tok = bootstrap_and_login(tenant_slug=f"hq-{sfx}", email=hq_email, plan_code="enterprise")
    op_slug = f"op-{sfx}"
    op_tok = bootstrap_and_login(tenant_slug=op_slug, email=op_email, plan_code="basic_auto_key")
    op_id, hq_id = _tid(op_tok), _tid(hq_tok)
    with Session(engine) as s:
        op = s.get(Tenant, op_id)
        op.mobile_dispatch_phone = "+61400000001"
        s.add(op)
        s.commit()
    hq_h = _h(hq_tok)
    r = link_and_accept(client, "/v1/parent-accounts/me/link-tenant", headers=hq_h,
                        json={"tenant_slug": op_slug, "owner_email": op_email})
    assert r.status_code == 200, r.text
    enable = client.post("/v1/parent-accounts/me/mobile-lead-ingest/enable", headers=hq_h)
    assert enable.status_code == 200, enable.text
    ingest_id = enable.json()["mobile_lead_ingest_public_id"]
    assert client.put("/v1/parent-accounts/me/mobile-lead-ingest/secret", headers=hq_h,
                      json={"webhook_secret": SECRET}).status_code == 200
    assert client.put("/v1/parent-accounts/me/mobile-lead-ingest/escalation-tenant", headers=hq_h,
                      json={"tenant_id": str(hq_id)}).status_code == 200
    assert client.post("/v1/parent-accounts/me/mobile-lead-routes", headers=hq_h,
                       json={"suburb": "Sydney", "state_code": "NSW", "target_tenant_id": str(op_id)}).status_code == 200
    mark_owner_accepted(op_id)
    return {"ingest_id": ingest_id, "op_id": op_id, "hq_id": hq_id, "hq_h": hq_h, "op_tok": op_tok}


def _lead_body(**over):
    body = {"suburb": "Sydney", "state_code": "NSW", "customer_name": "Jane Doe",
            "phone": "0412 345 678", "vehicle_make": "Toyota", "vehicle_model": "Corolla"}
    body.update(over)
    return body


def _post_lead(client, ingest_id, body, **headers):
    return client.post(f"/v1/public/mobile-key-leads/{ingest_id}",
                       headers={"X-Mobile-Lead-Secret": SECRET, **headers}, json=body)


def _lead_count(tenant_id) -> int:
    with Session(engine) as s:
        return len(s.exec(select(ProspectLead).where(ProspectLead.tenant_id == tenant_id)
                          .where(ProspectLead.source == "website_lead")).all())


def _alert_count(tenant_id) -> int:
    with Session(engine) as s:
        return len(s.exec(select(SmsLog).where(SmsLog.tenant_id == tenant_id)
                          .where(SmsLog.event == "website_lead_alert")).all())


# ── 1. idempotency ───────────────────────────────────────────────────────────

def test_double_post_mobile_key_lead_creates_one_lead_and_one_alert(client, lead_network):
    n = lead_network
    first = _post_lead(client, n["ingest_id"], _lead_body())
    # Same customer, phone typed differently (normalised) -> still the same submission.
    second = _post_lead(client, n["ingest_id"], _lead_body(phone="+61412345678"))
    assert first.status_code == second.status_code == 200
    assert first.json() == second.json()
    assert second.headers.get("X-Idempotent-Replay") == "true"
    assert _lead_count(n["op_id"]) == 1
    assert _alert_count(n["op_id"]) == 1


def test_different_submission_is_not_deduped(client, lead_network):
    n = lead_network
    a = _post_lead(client, n["ingest_id"], _lead_body())
    b = _post_lead(client, n["ingest_id"], _lead_body(phone="0499999999", customer_name="John Roe"))
    assert a.json()["lead_id"] != b.json()["lead_id"]
    assert _lead_count(n["op_id"]) == 2


def test_idempotency_key_header_returns_original_lead(client, lead_network):
    n = lead_network
    first = _post_lead(client, n["ingest_id"], _lead_body(), **{"Idempotency-Key": "form-abc"})
    # Same key, even if the payload was edited, is the same submission.
    retry = _post_lead(client, n["ingest_id"], _lead_body(customer_name="Jane D."), **{"Idempotency-Key": "form-abc"})
    other = _post_lead(client, n["ingest_id"], _lead_body(), **{"Idempotency-Key": "form-xyz"})
    assert retry.json() == first.json()
    assert other.json()["lead_id"] != first.json()["lead_id"]
    assert _lead_count(n["op_id"]) == 2


def test_repeat_outside_window_is_a_new_lead(client, lead_network):
    n = lead_network
    first = _post_lead(client, n["ingest_id"], _lead_body())
    with Session(engine) as s:
        lead = s.get(ProspectLead, UUID(first.json()["lead_id"]))
        lead.created_at = datetime.now(timezone.utc) - timedelta(minutes=30)
        lead.external_ref = lead.external_ref.rsplit(":", 1)[0] + ":1"  # an older window bucket
        s.add(lead)
        s.commit()
    again = _post_lead(client, n["ingest_id"], _lead_body())
    assert again.json()["lead_id"] != first.json()["lead_id"]


def test_double_post_key_enquiry_creates_one_lead(client, lead_network):
    n = lead_network
    body = {"customer_name": "Sam Buyer", "phone": "0422 111 222", "suburb": "Sydney", "state_code": "NSW",
            "service": "spare_key", "vehicle_make": "Mazda"}
    r1 = client.post(f"/v1/public/key-enquiry/{n['ingest_id']}", json=body)
    r2 = client.post(f"/v1/public/key-enquiry/{n['ingest_id']}", json={**body, "phone": "+61422111222"})
    assert r1.status_code == r2.status_code == 200
    assert _lead_count(n["op_id"]) == 1
    assert _alert_count(n["op_id"]) == 1


def test_double_post_public_intake_creates_one_pool_job(client, lead_network, monkeypatch):
    async def fake_geocode(_a):
        return (-37.8136, 144.9631)

    monkeypatch.setattr("app.routes.intake_dispatch.geocode_address", fake_geocode)
    body = {"customer_name": "Pat Q", "customer_phone": "0433 000 111", "job_address": "5 High St, Richmond VIC 3121",
            "ingest_public_id": lead_network["ingest_id"]}
    r1 = client.post("/v1/public/intake", json=body)
    r2 = client.post("/v1/public/intake", json={**body, "customer_phone": "+61433000111"})
    r3 = client.post("/v1/public/intake", json=body, headers={"Idempotency-Key": "k1"})
    r4 = client.post("/v1/public/intake", json=body, headers={"Idempotency-Key": "k1"})
    assert r1.status_code == r2.status_code == 200
    assert r1.json()["id"] == r2.json()["id"]
    assert r3.json()["id"] == r4.json()["id"] != r1.json()["id"]
    with Session(engine) as s:
        assert len(s.exec(select(IntakeJob).where(IntakeJob.customer_name == "Pat Q")).all()) == 2


# ── 2. invited-operators-only ────────────────────────────────────────────────

def test_non_invited_operator_is_excluded_from_shop_booking_and_pool(client, bootstrap_and_login):
    from app.routes.shop_mobile_bookings import _tenant_is_bookable_operator

    live_tok = bootstrap_and_login(plan_code="pro")
    shell_tok = bootstrap_and_login(plan_code="pro")
    live_id, shell_id = _tid(live_tok), _tid(shell_tok)
    parent_id = put_operators_in_new_network(live_id)
    put_operators_in_new_network(shell_id, live=False)  # operator role, invite never accepted
    with Session(engine) as s:
        assert _tenant_is_bookable_operator(s, live_id)
        assert not _tenant_is_bookable_operator(s, shell_id)
    # Pool: 409 on list and claim for the shell operator.
    with Session(engine) as s:
        job = IntakeJob(customer_name="X", job_address="1 A St, Richmond VIC 3121", job_lat=-37.8, job_lng=145.0,
                        parent_account_id=parent_id)
        s.add(job)
        s.commit()
        job_id = job.id
    assert client.get("/v1/pool", headers=_h(shell_tok)).status_code == 409
    assert client.post(f"/v1/pool/{job_id}/claim", headers=_h(shell_tok)).status_code == 409
    assert client.get("/v1/pool", headers=_h(live_tok)).status_code == 200


def test_website_lead_skips_unaccepted_operator_unchanged(client, bootstrap_and_login):
    """Regression guard: the existing website-lead rule is the one now shared."""
    from app.parent_network import tenant_is_live

    tok = bootstrap_and_login(plan_code="pro")
    tid = _tid(tok)
    put_operators_in_new_network(tid, live=False)
    with Session(engine) as s:
        assert not tenant_is_live(s, tid)
    mark_owner_accepted(tid)
    with Session(engine) as s:
        assert tenant_is_live(s, tid)


# ── 3. atomic accept ─────────────────────────────────────────────────────────

def _make_pending_booking(op_tok, *, scheduled_at=None):
    op_id = _tid(op_tok)
    with Session(engine) as s:
        owner = s.exec(select(User).where(User.tenant_id == op_id)).first()
        row = ShopMobileBookingRequest(
            parent_account_id=put_operators_in_new_network(op_id),
            requesting_tenant_id=op_id, target_operator_tenant_id=op_id, created_by_user_id=owner.id,
            customer_name="Race Customer", job_address="9 Low St, Richmond VIC 3121",
            preferred_scheduled_at=scheduled_at,
            offer_expires_at=datetime.now(timezone.utc) + timedelta(minutes=30),
        )
        s.add(row)
        s.commit()
        return row.id


def test_concurrent_booking_accept_loser_gets_409(client, bootstrap_and_login, monkeypatch):
    from app.routes import shop_mobile_bookings as mod

    tok = bootstrap_and_login(plan_code="pro")
    booking_id = _make_pending_booking(tok)

    real = mod._schedule_conflict_warning

    def other_request_wins_first(session, op, when):
        # A second request commits its accept after this one read status='pending'.
        with Session(engine) as other:
            row = other.get(ShopMobileBookingRequest, booking_id)
            row.status = "accepted"
            other.add(row)
            other.commit()
        return real(session, op, when)

    monkeypatch.setattr(mod, "_schedule_conflict_warning", other_request_wins_first)
    res = client.post(f"/v1/shop-mobile-bookings/{booking_id}/accept", headers=_h(tok))
    assert res.status_code == 409, res.text
    with Session(engine) as s:
        assert s.exec(select(AutoKeyJob).where(AutoKeyJob.shop_mobile_booking_request_id == booking_id)).first() is None


def test_booking_accept_once_then_409_and_double_booking_is_only_a_warning(client, bootstrap_and_login):
    tok = bootstrap_and_login(plan_code="pro")
    op_id = _tid(tok)
    when = datetime.now(timezone.utc).replace(hour=3, minute=0, second=0, microsecond=0) + timedelta(days=1)
    booking_id = _make_pending_booking(tok, scheduled_at=when)
    with Session(engine) as s:
        cust_owner = s.exec(select(User).where(User.tenant_id == op_id)).first()
        from app.models import Customer
        c = Customer(tenant_id=op_id, full_name="Existing")
        s.add(c)
        s.flush()
        s.add(AutoKeyJob(tenant_id=op_id, customer_id=c.id, job_number="AK-X1", title="busy", scheduled_at=when,
                         job_type="Mobile Key", status="scheduled", priority="normal", key_quantity=1,
                         programming_status="pending", deposit_cents=0, cost_cents=0))
        s.commit()
    first = client.post(f"/v1/shop-mobile-bookings/{booking_id}/accept", headers=_h(tok))
    assert first.status_code == 200, first.text
    assert first.json().get("schedule_conflict_warning")
    second = client.post(f"/v1/shop-mobile-bookings/{booking_id}/accept", headers=_h(tok))
    assert second.status_code in (400, 409)
    with Session(engine) as s:
        assert len(s.exec(select(AutoKeyJob).where(AutoKeyJob.shop_mobile_booking_request_id == booking_id)).all()) == 1


def test_pool_claim_loser_gets_409_not_500(client, bootstrap_and_login, monkeypatch):
    tok_a, tok_b = bootstrap_and_login(plan_code="pro"), bootstrap_and_login(plan_code="pro")
    parent_id = put_operators_in_new_network(_tid(tok_a), _tid(tok_b))
    with Session(engine) as s:
        job = IntakeJob(customer_name="C", job_address="1 A St, Richmond VIC 3121", job_lat=-37.8, job_lng=145.0,
                        parent_account_id=parent_id)
        s.add(job)
        s.commit()
        job_id = job.id
    # B read the job as unclaimed, then A's claim committed before B's conditional UPDATE.
    from app.routes import intake_dispatch as mod
    real = mod.enforce_plan_limit

    def a_wins_in_between(*a, **k):
        with Session(engine) as other:
            j = other.get(IntakeJob, job_id)
            j.status, j.claimed_by_tenant_id = "claimed", _tid(tok_a)
            other.add(j)
            other.commit()
        return real(*a, **k)

    monkeypatch.setattr(mod, "enforce_plan_limit", a_wins_in_between)
    res = client.post(f"/v1/pool/{job_id}/claim", headers=_h(tok_b))
    assert res.status_code == 409, res.text


# ── 4. pool network scope + PII redaction ────────────────────────────────────

def test_pool_is_isolated_between_hq_networks(client, bootstrap_and_login):
    tok_a, tok_b = bootstrap_and_login(plan_code="pro"), bootstrap_and_login(plan_code="pro")
    parent_a = put_operators_in_new_network(_tid(tok_a))
    parent_b = put_operators_in_new_network(_tid(tok_b))  # same location, different HQ
    with Session(engine) as s:
        ja = IntakeJob(customer_name="A job", job_address="1 A St, Richmond VIC 3121", job_lat=-37.8136,
                       job_lng=144.9631, parent_account_id=parent_a)
        jb = IntakeJob(customer_name="B job", job_address="2 B St, Richmond VIC 3121", job_lat=-37.8136,
                       job_lng=144.9631, parent_account_id=parent_b)
        s.add(ja)
        s.add(jb)
        s.commit()
        ja_id, jb_id = str(ja.id), str(jb.id)
    ids_a = {j["id"] for j in client.get("/v1/pool", headers=_h(tok_a)).json()}
    ids_b = {j["id"] for j in client.get("/v1/pool", headers=_h(tok_b)).json()}
    assert ja_id in ids_a and jb_id not in ids_a
    assert jb_id in ids_b and ja_id not in ids_b
    # Cross-HQ claim looks like a missing job and does not claim it.
    assert client.post(f"/v1/pool/{jb_id}/claim", headers=_h(tok_a)).status_code == 404
    with Session(engine) as s:
        assert s.get(IntakeJob, UUID(jb_id)).status == "unclaimed"


def test_pool_redacts_pii_until_claimed(client, bootstrap_and_login):
    tok = bootstrap_and_login(plan_code="pro")
    parent_id = put_operators_in_new_network(_tid(tok))
    with Session(engine) as s:
        job = IntakeJob(customer_name="Secret Name", customer_phone="0412999888", customer_email="s@x.test",
                        job_address="12 Smith Street, Richmond VIC 3121", job_lat=-37.8136, job_lng=144.9631,
                        vehicle_make="Honda", vehicle_model="Civic", registration_plate="ABC123",
                        description="Gate code 4321", parent_account_id=parent_id)
        s.add(job)
        s.commit()
        job_id = str(job.id)
    listing = client.get("/v1/pool", headers=_h(tok))
    assert listing.status_code == 200, listing.text
    item = next(j for j in listing.json() if j["id"] == job_id)
    assert (item["suburb"], item["postcode"], item["job_type"]) == ("Richmond", "3121", "Mobile Key")
    assert (item["vehicle_make"], item["vehicle_model"]) == ("Honda", "Civic")
    blob = listing.text
    for secret in ("Secret Name", "0412999888", "s@x.test", "Smith", "ABC123", "4321"):
        assert secret not in blob
    claim = client.post(f"/v1/pool/{job_id}/claim", headers=_h(tok))
    assert claim.status_code == 200, claim.text
    assert claim.json()["customer_name"] == "Secret Name"
    assert claim.json()["job_address"].startswith("12 Smith Street")


def test_redact_job_address_variants():
    from app.routes.intake_dispatch import redact_job_address

    assert redact_job_address("Unit 2, 5 Foo Rd, Mount Waverley VIC 3149") == {
        "suburb": "Mount Waverley", "state": "VIC", "postcode": "3149"}
    assert redact_job_address("9 Bar St, Parramatta 2150")["postcode"] == "2150"
    assert redact_job_address("somewhere")["postcode"] is None


# ── 5. HQ lead-volume report ─────────────────────────────────────────────────

def test_lead_volume_counts_website_prospect_leads(client):
    from app.minit_provision import ensure_minit_pilot_account

    email, pw = "hq-owner@test.mainspring.au", "MinitPilot2026!"
    with Session(engine) as s:
        ensure_minit_pilot_account(s, parent_name="Mister Minit", hq_tenant_slug="mmsupport",
                                   hq_tenant_name="Mister Minit HQ", hq_owner_email=email, hq_owner_password=pw)
    tok = client.post("/v1/auth/login", json={"tenant_slug": "mmsupport", "email": email, "password": pw}).json()["access_token"]
    url = "/v1/parent-accounts/me/operations/lead-volume"
    before = client.get(url, headers=_h(tok)).json()
    hq_id = _tid(tok)
    with Session(engine) as s:
        s.add(ProspectLead(tenant_id=hq_id, name="W", source="website_lead", status="new"))
        s.add(ProspectLead(tenant_id=hq_id, name="P", source="prospected", status="new"))  # not a website lead
        s.commit()
    after = client.get(url, headers=_h(tok)).json()
    for key in ("daily", "weekly", "monthly"):
        assert after[key][-1]["website_leads"] - before[key][-1]["website_leads"] == 1
        assert after[key][-1]["total"] - before[key][-1]["total"] == 1
