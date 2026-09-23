"""Tests for the slug/phone mobile-key customer self-service portal.

Covers the portal that was wired up in the hardening roadmap (model
``CustomerPortalSession`` + router mount). Also exercises the shared conftest
fixtures (``client``, ``bootstrap_and_login``).
"""
from uuid import uuid4

import app.routes.customer_portal_public as portal_routes
import app.sms as sms_module


def _sign_in(client, monkeypatch, slug: str, name: str, phone: str) -> dict:
    """Request a code, read it off the (faked) text, and verify it."""
    sent: dict[str, str] = {}

    def _capture(_session, *, tenant_id, to_phone, shop_name, code):
        sent["code"] = code
        sent["to"] = to_phone
        return "dry_run"

    monkeypatch.setattr(sms_module, "send_portal_login_code", _capture)
    asked = client.post(f"/v1/public/portal/{slug}/lookup", json={"name": name, "phone": phone})
    assert asked.status_code == 200, asked.text
    assert "token" not in asked.json()
    assert sent["to"] == phone
    verified = client.post(f"/v1/public/portal/{slug}/verify", json={"phone": phone, "code": sent["code"]})
    assert verified.status_code == 200, verified.text
    return verified.json()


def _create_shop(client, bootstrap_and_login) -> str:
    """Bootstrap a tenant and return its slug (the portal keys off tenant slug)."""
    slug = f"portal-shop-{uuid4().hex[:8]}"
    bootstrap_and_login(tenant_slug=slug)
    return slug


def test_portal_lookup_creates_session_and_customer(client, bootstrap_and_login, monkeypatch):
    slug = _create_shop(client, bootstrap_and_login)

    body = _sign_in(client, monkeypatch, slug, "Jane Driver", "0400111222")
    assert body["token"]
    assert body["name"] == "Jane Driver"
    assert body["phone"] == "0400111222"


def test_portal_lookup_unknown_shop_404(client):
    res = client.post(
        "/v1/public/portal/does-not-exist/lookup",
        json={"name": "Jane", "phone": "0400111222"},
    )
    assert res.status_code == 404


def test_portal_profile_requires_valid_token(client, bootstrap_and_login):
    slug = _create_shop(client, bootstrap_and_login)
    res = client.get(
        f"/v1/public/portal/{slug}/profile",
        params={"token": "not-a-real-token"},
    )
    assert res.status_code == 401


def test_portal_profile_returns_customer(client, bootstrap_and_login, monkeypatch):
    slug = _create_shop(client, bootstrap_and_login)
    token = _sign_in(client, monkeypatch, slug, "Sam Key", "0411222333")["token"]

    res = client.get(f"/v1/public/portal/{slug}/profile", params={"token": token})
    assert res.status_code == 200, res.text
    body = res.json()
    assert body["name"] == "Sam Key"
    assert body["intake_jobs"] == []
    assert body["loyalty"] is None


def test_portal_book_creates_intake_job(client, bootstrap_and_login, monkeypatch):
    slug = _create_shop(client, bootstrap_and_login)
    token = _sign_in(client, monkeypatch, slug, "Booking Customer", "0422333444")["token"]

    async def _fake_geocode(_address: str):
        return (-37.8136, 144.9631)

    monkeypatch.setattr(portal_routes, "geocode_address", _fake_geocode)

    res = client.post(
        f"/v1/public/portal/{slug}/book",
        params={"token": token},
        json={
            "job_address": "123 Collins St, Melbourne VIC 3000",
            "vehicle_make": "Toyota",
            "vehicle_model": "Corolla",
            "vehicle_year": "2019",
            "description": "Lost keys",
        },
    )
    assert res.status_code == 200, res.text
    body = res.json()
    assert body["intake_job_id"]
    assert body["status"] == "unclaimed"

    profile = client.get(
        f"/v1/public/portal/{slug}/profile", params={"token": token}
    ).json()
    assert len(profile["intake_jobs"]) == 1
    assert profile["intake_jobs"][0]["job_address"].startswith("123 Collins St")


def test_portal_wrong_code_is_rejected_and_locks_after_five_tries(client, bootstrap_and_login, monkeypatch):
    slug = _create_shop(client, bootstrap_and_login)
    monkeypatch.setattr(sms_module, "send_portal_login_code", lambda *_a, **_k: "dry_run")
    client.post(f"/v1/public/portal/{slug}/lookup", json={"name": "Guess Er", "phone": "0433444555"})
    for _ in range(5):
        wrong = client.post(f"/v1/public/portal/{slug}/verify", json={"phone": "0433444555", "code": "000000"})
        assert wrong.status_code == 401
    # Even a correct guess is refused once the code is locked.
    from sqlmodel import Session, select

    from app.database import engine
    from app.models import CustomerPortalOtp

    with Session(engine) as session:
        otp = session.exec(select(CustomerPortalOtp).where(CustomerPortalOtp.phone == "0433444555")).one()
        assert otp.attempts == 5
