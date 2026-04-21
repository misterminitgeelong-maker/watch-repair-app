"""
Regression tests for public customer portal endpoints.

Locks in the fix for `RepairJob.customer_id` not existing as a column —
watch jobs are reachable via Watch.customer_id, so the lookup must join
through Watch. See code review finding B-H1.
"""

import os
from pathlib import Path
from uuid import uuid4

from fastapi.testclient import TestClient

_TEST_DB = Path(__file__).with_name(f"test_public_portal_{uuid4().hex}.db")
os.environ["DATABASE_URL"] = f"sqlite:///{_TEST_DB.as_posix()}"
os.environ.setdefault("JWT_SECRET", "test-secret-not-for-production")
os.environ.setdefault("APP_ENV", "test")
# Give portal/customer-lookup a generous limit so rate-limit tests do not bleed in.
os.environ.setdefault("RATE_LIMIT_PUBLIC_CUSTOMER_LOOKUP", "10000/minute")
os.environ.setdefault("RATE_LIMIT_PUBLIC_PORTAL_CREATE", "10000/minute")
os.environ.setdefault("RATE_LIMIT_PUBLIC_PORTAL_SESSION", "10000/minute")

from app.database import create_db_and_tables  # noqa: E402
from app.main import app  # noqa: E402

create_db_and_tables()
client = TestClient(app)


def _bootstrap_and_login(suffix: str) -> tuple[str, str]:
    tenant_slug = f"portal-{suffix}"
    email = f"owner-{suffix}@portal.test"
    password = "pass123456"
    client.post(
        "/v1/auth/bootstrap",
        json={
            "tenant_name": f"Portal {suffix}",
            "tenant_slug": tenant_slug,
            "owner_email": email,
            "owner_full_name": "Owner",
            "owner_password": password,
        },
    )
    login = client.post(
        "/v1/auth/login",
        json={"tenant_slug": tenant_slug, "email": email, "password": password},
    )
    assert login.status_code == 200, login.text
    return login.json()["access_token"], tenant_slug


def _auth_headers(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def test_customer_lookup_returns_watch_job_for_matching_email():
    suffix = uuid4().hex[:8]
    token, _ = _bootstrap_and_login(suffix)
    headers = _auth_headers(token)

    customer_email = f"c-{suffix}@example.com"
    cust_res = client.post(
        "/v1/customers",
        headers=headers,
        json={"full_name": "Public Portal Customer", "email": customer_email},
    )
    assert cust_res.status_code == 201, cust_res.text
    customer_id = cust_res.json()["id"]

    watch_res = client.post(
        "/v1/watches",
        headers=headers,
        json={"customer_id": customer_id, "brand": "Omega", "model": "Speedmaster"},
    )
    assert watch_res.status_code == 201, watch_res.text
    watch_id = watch_res.json()["id"]

    job_res = client.post(
        "/v1/repair-jobs",
        headers=headers,
        json={"watch_id": watch_id, "title": "Full service", "priority": "normal"},
    )
    assert job_res.status_code == 201, job_res.text
    job_number = job_res.json()["job_number"]

    # B-H1 regression: this used to 500 because RepairJob.customer_id does not exist.
    lookup = client.post("/v1/public/customer-lookup", json={"email": customer_email})
    assert lookup.status_code == 200, lookup.text
    payload = lookup.json()
    jobs = payload.get("jobs", [])
    assert any(j["type"] == "watch" and j["job_number"] == job_number for j in jobs), payload


def test_customer_lookup_rejects_invalid_email():
    res = client.post("/v1/public/customer-lookup", json={"email": "not-an-email"})
    assert res.status_code == 422


def test_customer_lookup_returns_empty_for_unknown_email():
    res = client.post(
        "/v1/public/customer-lookup",
        json={"email": f"nobody-{uuid4().hex[:6]}@example.com"},
    )
    assert res.status_code == 200
    assert res.json() == {"jobs": []}
