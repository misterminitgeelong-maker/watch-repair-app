from app.routes.client_config import android_client_config, public_sentry_dsn
from app.config import settings


def test_client_config_has_no_legacy_sentry_secret(monkeypatch):
    monkeypatch.setattr(settings, "sentry_dsn", "https://public:secret@o1.ingest.sentry.io/123")
    monkeypatch.setattr(settings, "android_minimum_version_code", 123)
    data = android_client_config()
    assert data["sentry_dsn"] == "https://public@o1.ingest.sentry.io/123"
    assert data["minimum_version_code"] == 123
    assert data["store_url"] == "https://play.google.com/store/apps/details?id=au.mainspring.app"


def test_invalid_or_insecure_dsn_is_not_published():
    assert public_sentry_dsn("") is None
    assert public_sentry_dsn("not-a-dsn") is None
    assert public_sentry_dsn("http://public@o1.ingest.sentry.io/123") is None
    assert public_sentry_dsn("https://public@o1.ingest.sentry.io:bad/123") is None
    assert public_sentry_dsn("https://public@[broken/123") is None
