"""Shared pytest fixtures for the backend test suite.

Existing test modules predate this file and each set up their own sqlite DB,
``TestClient`` and ``_bootstrap_and_login`` / ``_create_customer`` helpers. This
conftest centralises that boilerplate so new tests can reuse it via fixtures,
while leaving the older modules working unchanged.

Environment variables are set at import time (before ``app`` is imported) so the
SQLModel engine is created against a throwaway sqlite database. pytest loads
conftest before collecting test modules, which makes the test DB deterministic
for any module that relies on these fixtures.
"""
import os
from pathlib import Path
from uuid import uuid4

# Fresh sqlite file per test session; must be set before importing app.database.
_TEST_DB = Path(__file__).with_name(f"conftest_{uuid4().hex}.db")
os.environ.setdefault("DATABASE_URL", f"sqlite:///{_TEST_DB.as_posix()}")
os.environ.setdefault("JWT_SECRET", "test-secret-not-for-production")
os.environ.setdefault("APP_ENV", "test")

import pytest
from fastapi.testclient import TestClient

from app.database import create_db_and_tables
from app.main import app


@pytest.fixture(scope="session", autouse=True)
def _initialise_schema():
    """Ensure tables exist once for the whole session."""
    create_db_and_tables()
    yield


@pytest.fixture(scope="session")
def client() -> TestClient:
    """Shared FastAPI TestClient for the session."""
    return TestClient(app)


@pytest.fixture
def bootstrap_and_login(client: TestClient):
    """Return a helper that bootstraps a tenant and returns its owner access token.

    Slug/email are auto-generated to be unique when not supplied, so tests can be
    called repeatedly within a shared database without collisions.
    """

    def _bootstrap(
        tenant_slug: str | None = None,
        email: str | None = None,
        password: str = "supersecret123",
        owner_full_name: str = "Main Owner",
    ) -> str:
        suffix = uuid4().hex[:8]
        tenant_slug = tenant_slug or f"tenant-{suffix}"
        email = email or f"owner-{suffix}@example.test"

        bootstrap_res = client.post(
            "/v1/auth/bootstrap",
            json={
                "tenant_name": f"Tenant {tenant_slug}",
                "tenant_slug": tenant_slug,
                "owner_email": email,
                "owner_full_name": owner_full_name,
                "owner_password": password,
            },
        )
        assert bootstrap_res.status_code == 200, bootstrap_res.text

        login_res = client.post(
            "/v1/auth/login",
            json={"tenant_slug": tenant_slug, "email": email, "password": password},
        )
        assert login_res.status_code == 200, login_res.text
        return login_res.json()["access_token"]

    return _bootstrap


@pytest.fixture
def auth_headers(bootstrap_and_login) -> dict[str, str]:
    """Authorization headers for a freshly bootstrapped tenant owner."""
    token = bootstrap_and_login()
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
def make_customer(client: TestClient):
    """Return a helper that creates a customer and returns its id."""

    def _make(
        headers: dict[str, str],
        full_name: str = "Alice Watch Owner",
        email: str = "alice@example.com",
        **extra,
    ) -> str:
        res = client.post(
            "/v1/customers",
            headers=headers,
            json={"full_name": full_name, "email": email, **extra},
        )
        assert res.status_code == 201, res.text
        return res.json()["id"]

    return _make


@pytest.fixture
def make_watch(client: TestClient):
    """Return a helper that creates a watch for a customer and returns its id."""

    def _make(
        headers: dict[str, str],
        customer_id: str,
        brand: str = "Omega",
        model: str = "Seamaster",
        **extra,
    ) -> str:
        res = client.post(
            "/v1/watches",
            headers=headers,
            json={"customer_id": customer_id, "brand": brand, "model": model, **extra},
        )
        assert res.status_code == 201, res.text
        return res.json()["id"]

    return _make
