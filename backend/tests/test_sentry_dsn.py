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
