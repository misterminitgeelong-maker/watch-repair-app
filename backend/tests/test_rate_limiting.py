import os
from pathlib import Path
from uuid import uuid4

from fastapi.testclient import TestClient

_TEST_DB = Path(__file__).with_name(f"test_rate_limit_{uuid4().hex}.db")
os.environ.setdefault("DATABASE_URL", f"sqlite:///{_TEST_DB.as_posix()}")
os.environ.setdefault("JWT_SECRET", "test-secret-not-for-production")
os.environ.setdefault("APP_ENV", "test")

from starlette.requests import Request

from app.config import settings
from app.database import create_db_and_tables
from app.limiter import client_ip_key, limiter
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


def test_public_jobs_endpoints_rate_limited():
    """Every unauthenticated /v1/public route carries a per-IP limit (reads and writes)."""
    limiter.reset()
    old = settings.rate_limit_public_test
    settings.rate_limit_public_test = "1/minute"
    try:
        # Read: token-addressed status page. The limiter runs before the handler,
        # so even an unknown token counts against the bucket.
        first = client.get("/v1/public/jobs/not-a-real-token")
        second = client.get("/v1/public/jobs/not-a-real-token")
        assert first.status_code == 404
        assert second.status_code == 429

        limiter.reset()
        # Write: email-keyed lookup with no token at all.
        first = client.post("/v1/public/customer-lookup", json={"email": "nobody@example.test"})
        second = client.post("/v1/public/customer-lookup", json={"email": "nobody@example.test"})
        assert first.status_code == 200
        assert second.status_code == 429

        limiter.reset()
        first = client.post("/v1/public/portal/create-session", json={"email": "nobody@example.test"})
        second = client.post("/v1/public/portal/create-session", json={"email": "nobody@example.test"})
        assert first.status_code == 404
        assert second.status_code == 429
    finally:
        settings.rate_limit_public_test = old
        limiter.reset()


def _ip_request(headers: dict[str, str], client=("127.0.0.1", 123)) -> Request:
    scope = {
        "type": "http",
        "asgi": {"version": "3.0"},
        "http_version": "1.1",
        "method": "GET",
        "scheme": "http",
        "path": "/",
        "raw_path": b"/",
        "query_string": b"",
        "headers": [(k.lower().encode(), v.encode()) for k, v in headers.items()],
        "client": client,
        "server": ("test", 80),
    }
    return Request(scope)


def test_client_ip_key_prefers_valid_cf_connecting_ip():
    assert client_ip_key(_ip_request({"cf-connecting-ip": "203.0.113.10"})) == "203.0.113.10"
    assert client_ip_key(_ip_request({"cf-connecting-ip": "2001:db8::1"})) == "2001:db8::1"


def test_client_ip_key_ignores_malformed_cf_header():
    assert client_ip_key(_ip_request({"cf-connecting-ip": "not-an-ip"})) == "127.0.0.1"


def test_public_rate_limit_is_per_cf_connecting_ip():
    limiter.reset()
    old = settings.rate_limit_public_test
    settings.rate_limit_public_test = "1/minute"
    try:
        first = client.get("/v1/public/jobs/not-a-real-token", headers={"CF-Connecting-IP": "203.0.113.1"})
        second = client.get("/v1/public/jobs/not-a-real-token", headers={"CF-Connecting-IP": "203.0.113.1"})
        other = client.get("/v1/public/jobs/not-a-real-token", headers={"CF-Connecting-IP": "203.0.113.2"})
        assert first.status_code == 404
        assert second.status_code == 429
        assert other.status_code == 404
    finally:
        settings.rate_limit_public_test = old
        limiter.reset()
