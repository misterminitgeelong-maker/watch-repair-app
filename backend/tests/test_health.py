"""
Regression tests for health + debug endpoints.

Locks in:
- /v1/health stays cheap (no DB work, no tenant-identifying payload).
- /v1/health/deep reports DB + testing/demo status but suppresses demo
  identifiers in production.
- /v1/debug/demo-status is blocked in production. See review B-H3/B-H7.
"""

import os
from pathlib import Path
from uuid import uuid4

from fastapi.testclient import TestClient

_TEST_DB = Path(__file__).with_name(f"test_health_{uuid4().hex}.db")
os.environ["DATABASE_URL"] = f"sqlite:///{_TEST_DB.as_posix()}"
os.environ.setdefault("JWT_SECRET", "test-secret-not-for-production")
os.environ.setdefault("APP_ENV", "test")

from app.config import settings  # noqa: E402
from app.database import create_db_and_tables  # noqa: E402
from app.main import app  # noqa: E402

create_db_and_tables()
client = TestClient(app)


def test_cheap_health_does_not_leak_tenant_info():
    res = client.get("/v1/health")
    assert res.status_code == 200
    payload = res.json()
    assert payload["status"] == "ok"
    assert "startup_seed" in payload
    # Cheap healthcheck must not include the demo payload anymore (B-H3).
    assert "demo" not in payload
    assert "testing_tenant_exists" not in payload


def test_deep_health_includes_status_in_non_production():
    res = client.get("/v1/health/deep")
    assert res.status_code == 200
    payload = res.json()
    assert payload["status"] == "ok"
    assert "startup_seed" in payload
    assert "testing_tenant_configured" in payload
    assert "testing_tenant_exists" in payload
    # In non-production, demo payload may be None or a dict — both are fine.
    assert "demo" in payload


def test_debug_demo_status_blocked_in_production():
    original = settings.app_env
    settings.app_env = "production"
    try:
        res = client.get("/v1/debug/demo-status")
        assert res.status_code == 404
    finally:
        settings.app_env = original


def test_deep_health_suppresses_demo_identifiers_in_production():
    original = settings.app_env
    settings.app_env = "production"
    try:
        res = client.get("/v1/health/deep")
        assert res.status_code == 200
        payload = res.json()
        # In production the demo payload must be suppressed (B-H3).
        assert payload["demo"] is None
    finally:
        settings.app_env = original
