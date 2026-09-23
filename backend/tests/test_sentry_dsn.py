from app.config import sentry_dsn_looks_valid


def test_empty_sentry_dsn_is_valid_disabled():
    assert sentry_dsn_looks_valid("") is True
    assert sentry_dsn_looks_valid("   ") is True


def test_typical_sentry_dsn_is_accepted():
    assert sentry_dsn_looks_valid("https://abc123@o1.ingest.sentry.io/99") is True


def test_malformed_sentry_dsn_is_rejected():
    assert sentry_dsn_looks_valid("not-a-dsn") is False
    assert sentry_dsn_looks_valid("https://ingest.sentry.io/99") is False
    assert sentry_dsn_looks_valid("https://abc123@o1.ingest.sentry.io/") is False


def test_sentry_release_prefers_explicit_then_railway_sha(monkeypatch):
    from app.config import sentry_release, settings

    monkeypatch.setattr(settings, "sentry_release", "")
    monkeypatch.delenv("RAILWAY_GIT_COMMIT_SHA", raising=False)
    monkeypatch.delenv("APP_BUILD_ID", raising=False)
    assert sentry_release() is None

    monkeypatch.setenv("APP_BUILD_ID", "build123")
    assert sentry_release() == "build123"
    monkeypatch.setenv("RAILWAY_GIT_COMMIT_SHA", "abc123")
    assert sentry_release() == "abc123"
    monkeypatch.setattr(settings, "sentry_release", "v1.2.3")
    assert sentry_release() == "v1.2.3"
