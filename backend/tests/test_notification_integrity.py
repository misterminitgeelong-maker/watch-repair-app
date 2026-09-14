"""Data integrity for outbound notifications: record, retry, redeliver.

These tests pin the batch-3 contract: every customer-facing send writes an
EmailLog/SmsLog row *before* the provider is called, 5xx/timeouts are retried,
4xx is not, and a sweep redelivers failed rows under the attempt cap.
"""
from __future__ import annotations

from uuid import uuid4
from unittest.mock import MagicMock

import httpx
import pytest
from sqlmodel import Session, select

from app.database import engine
from app.models import EmailLog, SmsLog, Tenant


def _tenant(session: Session) -> Tenant:
    tenant = Tenant(name="Notify Shop", slug=f"notify-{uuid4().hex[:8]}")
    session.add(tenant)
    session.commit()
    session.refresh(tenant)
    return tenant


class _FakeResponse:
    def __init__(self, status_code: int, text: str = "") -> None:
        self.status_code = status_code
        self.text = text


def _patch_sendgrid(monkeypatch, handler) -> list:
    posts: list = []

    class _FakeClient:
        def __init__(self, *args, **kwargs) -> None:
            pass

        def __enter__(self):
            return self

        def __exit__(self, *args) -> bool:
            return False

        def post(self, url, json=None, headers=None):
            posts.append({"url": url, "json": json})
            return handler(len(posts), url, json)

    monkeypatch.setattr("app.email_client.httpx.Client", _FakeClient)
    return posts


@pytest.fixture
def live_email(monkeypatch):
    monkeypatch.setattr("app.email_client.settings.enable_email_notifications", True)
    monkeypatch.setattr("app.email_client.settings.sendgrid_api_key", "sg-test-key")
    monkeypatch.setattr("app.email_client.settings.email_from_address", "noreply@example.test")
    monkeypatch.setattr("app.email_client.time.sleep", lambda _s: None)


@pytest.fixture
def live_sms(monkeypatch):
    monkeypatch.setattr("app.sms.settings.twilio_account_sid", "ACtest")
    monkeypatch.setattr("app.sms.settings.twilio_auth_token", "token")
    monkeypatch.setattr("app.sms.settings.twilio_from_number", "+61400000000")
    monkeypatch.setattr("app.sms.time.sleep", lambda _s: None)
    from app import sms as sms_mod

    sms_mod.reset_twilio_client()
    yield
    sms_mod.reset_twilio_client()


def test_quote_email_writes_log_when_session_passed(live_email, monkeypatch):
    """Customer-facing sends used to persist nothing; they must write EmailLog."""
    posts = _patch_sendgrid(monkeypatch, lambda *_a, **_k: _FakeResponse(202))
    from app.email_client import send_quote_sent_email

    with Session(engine) as session:
        tenant = _tenant(session)
        ok, err = send_quote_sent_email(
            to_email="cust@example.test",
            customer_name="Alex",
            total_cents=9900,
            approval_token="tok",
            job_number="W-1",
            shop_name="Notify Shop",
            session=session,
            tenant_id=tenant.id,
        )
        session.commit()
        assert ok is True
        assert err is None
        row = session.exec(
            select(EmailLog).where(EmailLog.tenant_id == tenant.id).where(EmailLog.event == "quote_sent")
        ).one()
        assert row.status == "sent"
        assert row.to_email == "cust@example.test"
        assert row.attempt_count >= 1
        assert row.payload_json
        assert row.last_attempt_at is not None
    assert len(posts) == 1


def test_sendgrid_retries_5xx_then_succeeds(live_email, monkeypatch):
    def handler(n, *_a, **_k):
        if n == 1:
            return _FakeResponse(503, "unavailable")
        return _FakeResponse(202)

    posts = _patch_sendgrid(monkeypatch, handler)
    from app.email_client import send_invoice_email

    with Session(engine) as session:
        tenant = _tenant(session)
        ok, err = send_invoice_email(
            to_email="cust@example.test",
            customer_name="Alex",
            invoice_number="INV-1",
            job_number="W-1",
            total_cents=1200,
            session=session,
            tenant_id=tenant.id,
        )
        session.commit()
        assert ok is True
        assert err is None
        row = session.exec(select(EmailLog).where(EmailLog.tenant_id == tenant.id)).one()
        assert row.status == "sent"
        assert row.attempt_count == 2
    assert len(posts) == 2


def test_sendgrid_does_not_retry_4xx(live_email, monkeypatch):
    posts = _patch_sendgrid(monkeypatch, lambda *_a, **_k: _FakeResponse(400, "bad request"))
    from app.email_client import send_job_ready_email
    from app.config import settings as app_settings

    with Session(engine) as session:
        tenant = _tenant(session)
        ok, err = send_job_ready_email(
            to_email="cust@example.test",
            customer_name="Alex",
            job_number="W-1",
            status_token="st",
            session=session,
            tenant_id=tenant.id,
        )
        session.commit()
        assert ok is False
        assert err
        row = session.exec(select(EmailLog).where(EmailLog.tenant_id == tenant.id)).one()
        assert row.status == "failed"
        assert row.attempt_count >= app_settings.notification_redelivery_max_attempts
    assert len(posts) == 1


def test_sendgrid_retries_timeouts(live_email, monkeypatch):
    calls = {"n": 0}

    def handler(n, *_a, **_k):
        calls["n"] = n
        if n == 1:
            raise httpx.TimeoutException("timed out")
        return _FakeResponse(202)

    _patch_sendgrid(monkeypatch, handler)
    from app.email_client import send_portal_bookmark_email

    with Session(engine) as session:
        tenant = _tenant(session)
        ok, _err = send_portal_bookmark_email(
            to_email="cust@example.test",
            portal_url="https://example.test/p",
            session=session,
            tenant_id=tenant.id,
        )
        session.commit()
        assert ok is True
        row = session.exec(select(EmailLog).where(EmailLog.tenant_id == tenant.id)).one()
        assert row.status == "sent"
        assert row.attempt_count == 2
    assert calls["n"] == 2


def test_sms_log_exists_before_twilio_send(live_sms, monkeypatch):
    from app import sms as sms_mod

    order: list[str] = []
    orig_begin = sms_mod._begin_sms_log

    def tracking_begin(session, **kwargs):
        order.append("log")
        return orig_begin(session, **kwargs)

    class _FakeMessage:
        sid = "SM-before"

    def fake_create(**_kwargs):
        order.append("send")
        return _FakeMessage()

    fake_client = MagicMock()
    fake_client.messages.create.side_effect = fake_create
    monkeypatch.setattr(sms_mod, "_begin_sms_log", tracking_begin)
    monkeypatch.setattr(sms_mod, "_get_twilio_client", lambda: fake_client)

    with Session(engine) as session:
        tenant = _tenant(session)
        sid, status = sms_mod._logged_send(
            session,
            tenant_id=tenant.id,
            repair_job_id=None,
            to_phone="+61411111111",
            body="hello",
            event="job_live",
        )
        session.commit()
        assert sid == "SM-before"
        assert status == "sent"
        assert order == ["log", "send"]
        row = session.exec(select(SmsLog).where(SmsLog.tenant_id == tenant.id)).one()
        assert row.status == "sent"
        assert row.attempt_count >= 1
        assert row.last_attempt_at is not None


def test_sms_does_not_retry_4xx(live_sms, monkeypatch):
    from app import sms as sms_mod

    class _Fake4xx(Exception):
        status = 400

    fake_client = MagicMock()
    fake_client.messages.create.side_effect = _Fake4xx("invalid number")
    monkeypatch.setattr(sms_mod, "_get_twilio_client", lambda: fake_client)

    with Session(engine) as session:
        tenant = _tenant(session)
        sid, status = sms_mod._logged_send(
            session,
            tenant_id=tenant.id,
            repair_job_id=None,
            to_phone="+61411111111",
            body="hello",
            event="quote_sent",
        )
        assert sid is None
        assert status == "failed"
        row = session.exec(select(SmsLog).where(SmsLog.tenant_id == tenant.id)).one()
        assert row.attempt_count >= 1
        assert fake_client.messages.create.call_count == 1


def test_sms_retries_5xx_then_succeeds(live_sms, monkeypatch):
    from app import sms as sms_mod

    class _Fake5xx(Exception):
        status = 503

    class _FakeMessage:
        sid = "SM-ok"

    fake_client = MagicMock()
    fake_client.messages.create.side_effect = [_Fake5xx("twilio down"), _FakeMessage()]
    monkeypatch.setattr(sms_mod, "_get_twilio_client", lambda: fake_client)

    with Session(engine) as session:
        tenant = _tenant(session)
        sid, status = sms_mod._logged_send(
            session,
            tenant_id=tenant.id,
            repair_job_id=None,
            to_phone="+61411111111",
            body="hello",
            event="quote_sent",
        )
        assert sid == "SM-ok"
        assert status == "sent"
        row = session.exec(select(SmsLog).where(SmsLog.tenant_id == tenant.id)).one()
        assert row.attempt_count == 2
        assert fake_client.messages.create.call_count == 2


def test_redelivery_sweep_resends_failed_email_under_cap(live_email, monkeypatch):
    posts = _patch_sendgrid(monkeypatch, lambda *_a, **_k: _FakeResponse(202))
    from app.services.notification_redelivery import redeliver_failed_notifications
    import json
    from datetime import datetime, timezone

    with Session(engine) as session:
        tenant = _tenant(session)
        session.add(
            EmailLog(
                tenant_id=tenant.id,
                to_email="lost@example.test",
                event="quote_sent",
                status="failed",
                error="SendGrid HTTP 503",
                attempt_count=1,
                last_attempt_at=datetime.now(timezone.utc),
                payload_json=json.dumps(
                    {
                        "subject": "Your watch repair quote – Job #W-9",
                        "body_plain": "Hi",
                        "body_html": "<p>Hi</p>",
                        "shop_name": "Notify Shop",
                        "reply_to": None,
                    }
                ),
            )
        )
        session.commit()
        summary = redeliver_failed_notifications(session)
        assert summary["email_sent"] == 1
        row = session.exec(select(EmailLog).where(EmailLog.tenant_id == tenant.id)).one()
        assert row.status == "sent"
    assert len(posts) == 1


def test_redelivery_sweep_skips_exhausted_rows(live_email, monkeypatch):
    posts = _patch_sendgrid(monkeypatch, lambda *_a, **_k: _FakeResponse(202))
    from app.services.notification_redelivery import redeliver_failed_notifications
    from app.config import settings as app_settings
    from datetime import datetime, timezone

    with Session(engine) as session:
        tenant = _tenant(session)
        session.add(
            EmailLog(
                tenant_id=tenant.id,
                to_email="done@example.test",
                event="quote_sent",
                status="failed",
                error="SendGrid HTTP 503",
                attempt_count=app_settings.notification_redelivery_max_attempts,
                last_attempt_at=datetime.now(timezone.utc),
                payload_json='{"subject":"x","body_plain":"y","shop_name":"S"}',
            )
        )
        session.commit()
        summary = redeliver_failed_notifications(session)
        assert summary["email_sent"] == 0
        assert summary["skipped"] >= 1
    assert posts == []


def test_redelivery_sweep_resends_failed_sms(live_sms, monkeypatch):
    from app import sms as sms_mod
    from app.services.notification_redelivery import redeliver_failed_notifications
    from datetime import datetime, timezone

    class _FakeMessage:
        sid = "SM-retry"

    fake_client = MagicMock()
    fake_client.messages.create.return_value = _FakeMessage()
    monkeypatch.setattr(sms_mod, "_get_twilio_client", lambda: fake_client)

    with Session(engine) as session:
        tenant = _tenant(session)
        session.add(
            SmsLog(
                tenant_id=tenant.id,
                to_phone="+61411111111",
                body="please retry",
                event="quote_sent",
                status="failed",
                attempt_count=1,
                last_attempt_at=datetime.now(timezone.utc),
            )
        )
        session.commit()
        summary = redeliver_failed_notifications(session)
        assert summary["sms_sent"] == 1
        row = session.exec(select(SmsLog).where(SmsLog.tenant_id == tenant.id)).one()
        assert row.status == "sent"
        assert row.provider_sid == "SM-retry"
    assert fake_client.messages.create.call_count == 1
