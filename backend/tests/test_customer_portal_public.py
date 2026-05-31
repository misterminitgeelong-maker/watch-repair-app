"""Tests for the slug/phone mobile-key customer self-service portal.

Covers the portal that was wired up in the hardening roadmap (model
``CustomerPortalSession`` + router mount). Also exercises the shared conftest
fixtures (``client``, ``bootstrap_and_login``).
"""
from uuid import uuid4

import app.routes.customer_portal_public as portal_routes


def _create_shop(client, bootstrap_and_login) -> str:
    """Bootstrap a tenant and return its slug (the portal keys off tenant slug)."""
    slug = f"portal-shop-{uuid4().hex[:8]}"
    bootstrap_and_login(tenant_slug=slug)
    return slug


def test_portal_lookup_creates_session_and_customer(client, bootstrap_and_login):
    slug = _create_shop(client, bootstrap_and_login)

    res = client.post(
        f"/v1/public/portal/{slug}/lookup",
        json={"name": "Jane Driver", "phone": "0400111222"},
    )
    assert res.status_code == 200, res.text
    body = res.json()
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


def test_portal_profile_returns_customer(client, bootstrap_and_login):
    slug = _create_shop(client, bootstrap_and_login)
    lookup = client.post(
        f"/v1/public/portal/{slug}/lookup",
        json={"name": "Sam Key", "phone": "0411222333"},
    )
    token = lookup.json()["token"]

    res = client.get(f"/v1/public/portal/{slug}/profile", params={"token": token})
    assert res.status_code == 200, res.text
    body = res.json()
    assert body["name"] == "Sam Key"
    assert body["intake_jobs"] == []
    assert body["loyalty"] is None


def test_portal_book_creates_intake_job(client, bootstrap_and_login, monkeypatch):
    slug = _create_shop(client, bootstrap_and_login)
    lookup = client.post(
        f"/v1/public/portal/{slug}/lookup",
        json={"name": "Booking Customer", "phone": "0422333444"},
    )
    token = lookup.json()["token"]

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
