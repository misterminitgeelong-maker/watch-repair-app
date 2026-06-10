"""Reminder SMS for quotes with no customer decision after QUOTE_REMINDER_DAYS."""
from datetime import datetime, timedelta, timezone
from uuid import UUID, uuid4

from fastapi.testclient import TestClient
from sqlmodel import Session, select

from app.database import engine
from app.models import AutoKeyQuote, Quote, RepairJob, SmsLog

_REMINDERS = "/v1/quotes/send-reminders"


def _bootstrap_tenant(client: TestClient) -> dict[str, str]:
    suffix = uuid4().hex[:8]
    slug = f"quote-rem-{suffix}"
    email = f"owner-{suffix}@reminders.test"
    boot = client.post(
        "/v1/auth/bootstrap",
        json={
            "tenant_name": f"Reminders {suffix}",
            "tenant_slug": slug,
            "owner_email": email,
            "owner_full_name": "Owner",
            "owner_password": "pass123456",
            "plan_code": "enterprise",
        },
    )
    assert boot.status_code == 200, boot.text
    login = client.post(
        "/v1/auth/login",
        json={"tenant_slug": slug, "email": email, "password": "pass123456"},
    )
    assert login.status_code == 200, login.text
    return {"Authorization": f"Bearer {login.json()['access_token']}"}


def _customer(client: TestClient, headers: dict[str, str], phone: str | None = "0400123456") -> str:
    res = client.post(
        "/v1/customers",
        headers=headers,
        json={"full_name": "Reminder Customer", "phone": phone},
    )
    assert res.status_code == 201, res.text
    return res.json()["id"]


def _sent_watch_quote(client: TestClient, headers: dict[str, str], customer_id: str) -> tuple[str, str]:
    """Create watch + job + quote, send it, return (quote_id, job_id)."""
    watch = client.post(
        "/v1/watches",
        headers=headers,
        json={"customer_id": customer_id, "brand": "Omega", "model": "Seamaster"},
    )
    assert watch.status_code == 201, watch.text
    job = client.post(
        "/v1/repair-jobs",
        headers=headers,
        json={"watch_id": watch.json()["id"], "title": "Reminder test", "priority": "normal"},
    )
    assert job.status_code == 201, job.text
    quote = client.post(
        "/v1/quotes",
        headers=headers,
        json={
            "repair_job_id": job.json()["id"],
            "tax_cents": 0,
            "line_items": [
                {"item_type": "labor", "description": "Full service", "quantity": 1, "unit_price_cents": 30000}
            ],
        },
    )
    assert quote.status_code == 201, quote.text
    sent = client.post(f"/v1/quotes/{quote.json()['id']}/send", headers=headers)
    assert sent.status_code == 200, sent.text
    return quote.json()["id"], job.json()["id"]


def _backdate_quote(quote_id: str, days: int, *, expire: bool = False) -> None:
    with Session(engine) as session:
        quote = session.get(Quote, UUID(quote_id))
        quote.sent_at = datetime.now(timezone.utc) - timedelta(days=days)
        if expire:
            quote.status = "expired"
            quote.approval_token_expires_at = datetime.now(timezone.utc) - timedelta(days=1)
        session.add(quote)
        session.commit()


def test_watch_quote_reminder_sent_once_and_link_refreshed(client: TestClient):
    headers = _bootstrap_tenant(client)
    customer_id = _customer(client, headers)
    quote_id, job_id = _sent_watch_quote(client, headers, customer_id)
    _backdate_quote(quote_id, days=8)

    res = client.post(_REMINDERS, headers=headers)
    assert res.status_code == 200, res.text
    assert res.json()["watch_sent"] == 1

    with Session(engine) as session:
        quote = session.get(Quote, UUID(quote_id))
        assert quote.reminder_sent_at is not None
        # Link refreshed for another full TTL window.
        expires = quote.approval_token_expires_at
        if expires.tzinfo is None:
            expires = expires.replace(tzinfo=timezone.utc)
        assert expires > datetime.now(timezone.utc) + timedelta(days=6)

        log = session.exec(
            select(SmsLog)
            .where(SmsLog.repair_job_id == UUID(job_id))
            .where(SmsLog.event == "quote_reminder")
        ).first()
        assert log is not None
        assert "/approve/" in log.body

    # One reminder per quote — second run is a no-op.
    res2 = client.post(_REMINDERS, headers=headers)
    assert res2.status_code == 200
    assert res2.json()["watch_sent"] == 0


def test_expired_watch_quote_is_reactivated_by_reminder(client: TestClient):
    headers = _bootstrap_tenant(client)
    customer_id = _customer(client, headers)
    quote_id, _job_id = _sent_watch_quote(client, headers, customer_id)
    _backdate_quote(quote_id, days=9, expire=True)

    res = client.post(_REMINDERS, headers=headers)
    assert res.status_code == 200
    assert res.json()["watch_sent"] == 1

    with Session(engine) as session:
        quote = session.get(Quote, UUID(quote_id))
        assert quote.status == "sent"
        expires = quote.approval_token_expires_at
        if expires.tzinfo is None:
            expires = expires.replace(tzinfo=timezone.utc)
        assert expires > datetime.now(timezone.utc)


def test_no_reminder_when_job_already_decided(client: TestClient):
    headers = _bootstrap_tenant(client)
    customer_id = _customer(client, headers)
    quote_id, job_id = _sent_watch_quote(client, headers, customer_id)
    _backdate_quote(quote_id, days=8)

    with Session(engine) as session:
        job = session.get(RepairJob, UUID(job_id))
        job.status = "go_ahead"
        session.add(job)
        session.commit()

    res = client.post(_REMINDERS, headers=headers)
    assert res.status_code == 200
    assert res.json()["watch_sent"] == 0
    assert res.json()["skipped"] >= 1


def test_recent_quote_not_reminded_yet(client: TestClient):
    headers = _bootstrap_tenant(client)
    customer_id = _customer(client, headers)
    quote_id, _job_id = _sent_watch_quote(client, headers, customer_id)
    _backdate_quote(quote_id, days=2)

    res = client.post(_REMINDERS, headers=headers)
    assert res.status_code == 200
    assert res.json()["watch_sent"] == 0

    with Session(engine) as session:
        quote = session.get(Quote, UUID(quote_id))
        assert quote.reminder_sent_at is None


def test_mobile_services_quote_reminder(client: TestClient):
    headers = _bootstrap_tenant(client)
    customer_id = _customer(client, headers, phone="0400765432")

    job = client.post(
        "/v1/auto-key-jobs",
        headers=headers,
        json={
            "customer_id": customer_id,
            "title": "Add key",
            "vehicle_make": "Toyota",
            "vehicle_model": "Corolla",
        },
    )
    assert job.status_code == 201, job.text
    job_id = job.json()["id"]

    quote = client.post(
        f"/v1/auto-key-jobs/{job_id}/quotes",
        headers=headers,
        json={
            "tax_cents": 0,
            "line_items": [{"description": "Add key incl programming", "quantity": 1, "unit_price_cents": 38000}],
        },
    )
    assert quote.status_code == 201, quote.text
    quote_id = quote.json()["id"]
    sent = client.post(f"/v1/auto-key-jobs/quotes/{quote_id}/send", headers=headers)
    assert sent.status_code == 200, sent.text

    with Session(engine) as session:
        ak_quote = session.get(AutoKeyQuote, UUID(quote_id))
        ak_quote.sent_at = datetime.now(timezone.utc) - timedelta(days=8)
        session.add(ak_quote)
        session.commit()

    res = client.post(_REMINDERS, headers=headers)
    assert res.status_code == 200, res.text
    assert res.json()["mobile_sent"] == 1

    with Session(engine) as session:
        ak_quote = session.get(AutoKeyQuote, UUID(quote_id))
        assert ak_quote.reminder_sent_at is not None
        log = session.exec(
            select(SmsLog)
            .where(SmsLog.auto_key_job_id == UUID(job_id))
            .where(SmsLog.event == "auto_key_quote_reminder")
        ).first()
        assert log is not None
        assert "/mobile-quote/" in log.body

    res2 = client.post(_REMINDERS, headers=headers)
    assert res2.json()["mobile_sent"] == 0
