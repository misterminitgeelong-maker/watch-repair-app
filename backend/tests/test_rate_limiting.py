import os
from pathlib import Path
from uuid import uuid4

from fastapi.testclient import TestClient

_TEST_DB = Path(__file__).with_name(f"test_rate_limit_{uuid4().hex}.db")
os.environ["DATABASE_URL"] = f"sqlite:///{_TEST_DB.as_posix()}"
os.environ.setdefault("JWT_SECRET", "test-secret-not-for-production")
os.environ.setdefault("APP_ENV", "test")

from app.config import settings
from app.database import create_db_and_tables
from app.limiter import limiter
from app.main import app

create_db_and_tables()
client = TestClient(app)


def _bootstrap_and_login(tenant_slug: str, email: str, password: str) -> str:
    bootstrap = client.post(
        "/v1/auth/bootstrap",
        json={
            "tenant_name": f"Tenant {tenant_slug}",
            "tenant_slug": tenant_slug,
            "owner_email": email,
            "owner_full_name": "Owner",
            "owner_password": password,
        },
    )
    assert bootstrap.status_code == 200
    login = client.post(
        "/v1/auth/login",
        json={"tenant_slug": tenant_slug, "email": email, "password": password},
    )
    assert login.status_code == 200
    return login.json()["access_token"]


def _create_approved_quote(headers: dict[str, str]) -> str:
    customer = client.post(
        "/v1/customers",
        headers=headers,
        json={"full_name": "Rate Limit Customer", "email": "rate@example.com"},
    )
    assert customer.status_code == 201
    watch = client.post(
        "/v1/watches",
        headers=headers,
        json={"customer_id": customer.json()["id"], "brand": "Omega", "model": "Speedmaster"},
    )
    assert watch.status_code == 201
    job = client.post(
        "/v1/repair-jobs",
        headers=headers,
        json={"watch_id": watch.json()["id"], "title": "Rate Limited Quote", "priority": "normal"},
    )
    assert job.status_code == 201
    quote = client.post(
        "/v1/quotes",
        headers=headers,
        json={
            "repair_job_id": job.json()["id"],
            "tax_cents": 0,
            "line_items": [{"item_type": "labor", "description": "Service", "quantity": 1, "unit_price_cents": 10000}],
        },
    )
    assert quote.status_code == 201
    send = client.post(f"/v1/quotes/{quote.json()['id']}/send", headers=headers)
    assert send.status_code == 200
    return send.json()["approval_token"]


def test_login_rate_limit_exceeded_returns_429():
    limiter.reset()
    old = settings.rate_limit_auth_login_test
    settings.rate_limit_auth_login_test = "1/minute"
    try:
        suffix = uuid4().hex[:8]
        client.post(
            "/v1/auth/bootstrap",
            json={
                "tenant_name": f"Tenant rl-{suffix}",
                "tenant_slug": f"rl-{suffix}",
                "owner_email": f"owner-{suffix}@rl.test",
                "owner_full_name": "Owner",
                "owner_password": "pass123456",
            },
        )
        payload = {"tenant_slug": f"rl-{suffix}", "email": f"owner-{suffix}@rl.test", "password": "pass123456"}
        first = client.post("/v1/auth/login", json=payload)
        second = client.post("/v1/auth/login", json=payload)
        assert first.status_code == 200
        assert second.status_code == 429
    finally:
        settings.rate_limit_auth_login_test = old
        limiter.reset()


def test_public_quote_endpoints_rate_limited():
    limiter.reset()
    old_get = settings.rate_limit_public_quote_get
    old_decision = settings.rate_limit_public_quote_decision
    settings.rate_limit_public_quote_get = "1/minute"
    settings.rate_limit_public_quote_decision = "1/minute"
    try:
        suffix = uuid4().hex[:8]
        token = _bootstrap_and_login(f"public-rl-{suffix}", f"owner-{suffix}@publicrl.test", "pass123456")
        headers = {"Authorization": f"Bearer {token}"}
        approval_token = _create_approved_quote(headers)

        first_get = client.get(f"/v1/public/quotes/{approval_token}")
        second_get = client.get(f"/v1/public/quotes/{approval_token}")
        assert first_get.status_code == 200
        assert second_get.status_code == 429

        # Need a fresh quote token for decision endpoint because decision is one-time.
        approval_token_2 = _create_approved_quote(headers)
        first_decision = client.post(
            f"/v1/public/quotes/{approval_token_2}/decision",
            json={"decision": "approved"},
        )
        second_decision = client.post(
            f"/v1/public/quotes/{approval_token_2}/decision",
            json={"decision": "approved"},
        )
        assert first_decision.status_code == 200
        assert second_decision.status_code == 429
    finally:
        settings.rate_limit_public_quote_get = old_get
        settings.rate_limit_public_quote_decision = old_decision
        limiter.reset()


def test_import_csv_rate_limited():
    limiter.reset()
    old = settings.rate_limit_import_csv
    settings.rate_limit_import_csv = "1/minute"
    try:
        suffix = uuid4().hex[:8]
        token = _bootstrap_and_login(f"import-rl-{suffix}", f"owner-{suffix}@importrl.test", "pass123456")
        headers = {"Authorization": f"Bearer {token}"}
        csv_bytes = b"customer_name,brand_case_numbers,quote_price\nAlice,Omega,100\n"
        first = client.post(
            "/v1/import/csv",
            headers=headers,
            files={"file": ("import.csv", csv_bytes, "text/csv")},
        )
        second = client.post(
            "/v1/import/csv",
            headers=headers,
            files={"file": ("import.csv", csv_bytes, "text/csv")},
        )
        assert first.status_code == 200
        assert second.status_code == 429
    finally:
        settings.rate_limit_import_csv = old
        limiter.reset()


def test_public_customer_lookup_rate_limited():
    limiter.reset()
    old = settings.rate_limit_public_customer_lookup
    settings.rate_limit_public_customer_lookup = "1/minute"
    try:
        first = client.post(
            "/v1/public/customer-lookup",
            json={"email": f"nobody-{uuid4().hex[:6]}@example.com"},
        )
        second = client.post(
            "/v1/public/customer-lookup",
            json={"email": f"nobody-{uuid4().hex[:6]}@example.com"},
        )
        assert first.status_code == 200
        assert second.status_code == 429
    finally:
        settings.rate_limit_public_customer_lookup = old
        limiter.reset()


def test_create_portal_session_requires_active_jobs_and_is_rate_limited():
    limiter.reset()
    old = settings.rate_limit_public_portal_create
    settings.rate_limit_public_portal_create = "5/minute"
    try:
        # Unknown email -> 404, never mints a session.
        unknown = client.post(
            "/v1/public/portal/create-session",
            json={"email": f"ghost-{uuid4().hex[:6]}@example.com"},
        )
        assert unknown.status_code == 404

        # Customer exists but has no jobs -> also 404 (blocks email enumeration via portal).
        suffix = uuid4().hex[:8]
        token = _bootstrap_and_login(f"portal-noact-{suffix}", f"owner-{suffix}@portal.test", "pass123456")
        headers = {"Authorization": f"Bearer {token}"}
        email_no_jobs = f"noact-{suffix}@example.com"
        client.post(
            "/v1/customers",
            headers=headers,
            json={"full_name": "No Jobs", "email": email_no_jobs},
        )
        no_jobs = client.post("/v1/public/portal/create-session", json={"email": email_no_jobs})
        assert no_jobs.status_code == 404

        # Rate limit the bare-404 path.
        settings.rate_limit_public_portal_create = "1/minute"
        limiter.reset()
        first = client.post(
            "/v1/public/portal/create-session",
            json={"email": f"rl-{uuid4().hex[:6]}@example.com"},
        )
        second = client.post(
            "/v1/public/portal/create-session",
            json={"email": f"rl-{uuid4().hex[:6]}@example.com"},
        )
        assert first.status_code == 404
        assert second.status_code == 429
    finally:
        settings.rate_limit_public_portal_create = old
        limiter.reset()
