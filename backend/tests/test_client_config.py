from fastapi.testclient import TestClient

from app.routes.client_config import public_sentry_dsn
from app.config import settings
from app.limiter import limiter
from app.main import app

client = TestClient(app)


def test_client_config_has_no_legacy_sentry_secret(monkeypatch):
    monkeypatch.setattr(settings, "sentry_dsn", "https://public:secret@o1.ingest.sentry.io/123")
    monkeypatch.setattr(settings, "android_minimum_version_code", 123)
    response = client.get("/v1/client-config/android")
    assert response.status_code == 200
    data = response.json()
    assert data["sentry_dsn"] == "https://public@o1.ingest.sentry.io/123"
    assert data["minimum_version_code"] == 123
    assert data["store_url"] == "https://play.google.com/store/apps/details?id=au.mainspring.app"


def test_invalid_or_insecure_dsn_is_not_published():
    assert public_sentry_dsn("") is None
    assert public_sentry_dsn("not-a-dsn") is None
    assert public_sentry_dsn("http://public@o1.ingest.sentry.io/123") is None
    assert public_sentry_dsn("https://public@o1.ingest.sentry.io:bad/123") is None
    assert public_sentry_dsn("https://public@[broken/123") is None


def test_android_client_config_is_rate_limited_per_client(monkeypatch):
    monkeypatch.setattr(settings, "app_env", "test")
    monkeypatch.setattr(settings, "rate_limit_public_test", "1/minute")
    limiter.reset()
    try:
        headers = {"CF-Connecting-IP": "198.51.100.20"}
        assert client.get("/v1/client-config/android", headers=headers).status_code == 200
        assert client.get("/v1/client-config/android", headers=headers).status_code == 429
        assert client.get("/v1/client-config/android", headers={"CF-Connecting-IP": "198.51.100.21"}).status_code == 200
    finally:
        limiter.reset()
