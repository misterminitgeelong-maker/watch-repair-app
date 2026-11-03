"""SMS safety controls: STOP/START suppression, MessageSid dedupe, ambiguous-sender
attribution and soft fair-use metering."""
from datetime import datetime, timedelta, timezone
from uuid import UUID, uuid4

import pytest
from fastapi.testclient import TestClient
from sqlmodel import Session, select

from app import sms
from app.config import settings
from app.database import engine
from app.models import (
    NETWORK_ROLE_HQ,
    NETWORK_ROLE_RETAIL,
    InboundSmsReceipt,
    JobMessage,
    ParentAccount,
    ParentAccountSite,
    Quote,
    RepairJob,
    SmsLog,
    SmsSuppression,
    Tenant,
    TenantEventLog,
    User,
)
from app.sms_controls import month_bounds_utc

_WEBHOOK = "/v1/webhook/sms/incoming"


def _unique_phone() -> tuple[str, str]:
    """(Twilio E.164 From, stored local phone), unique per call."""
    local = "04" + f"{uuid4().int % 10**8:08d}"
    return f"+61{local[1:]}", local


def _bootstrap_tenant(client: TestClient, label: str = "ctl") -> tuple[dict[str, str], UUID, str]:
    suffix = uuid4().hex[:8]
    slug = f"{label}-{suffix}"
    email = f"owner-{suffix}@{label}.test"
    boot = client.post(
        "/v1/auth/bootstrap",
        json={
            "tenant_name": f"SMS Ctl {suffix}",
            "tenant_slug": slug,
            "owner_email": email,
            "owner_full_name": "Owner",
            "owner_password": "pass123456",
            "plan_code": "enterprise",
        },
    )
    assert boot.status_code == 200, boot.text
    login = client.post("/v1/auth/login", json={"tenant_slug": slug, "email": email, "password": "pass123456"})
    assert login.status_code == 200, login.text
    return {"Authorization": f"Bearer {login.json()['access_token']}"}, UUID(boot.json()["tenant_id"]), email


def _customer(client: TestClient, headers: dict[str, str], phone: str) -> str:
    res = client.post("/v1/customers", headers=headers, json={"full_name": "Ctl Customer", "phone": phone})
    assert res.status_code == 201, res.text
    return res.json()["id"]


def _job_with_sent_quote(client: TestClient, headers: dict[str, str], customer_id: str) -> tuple[UUID, str]:
    watch = client.post(
        "/v1/watches", headers=headers, json={"customer_id": customer_id, "brand": "Omega", "model": "Seamaster"}
    )
    assert watch.status_code == 201, watch.text
    job = client.post(
        "/v1/repair-jobs",
        headers=headers,
        json={"watch_id": watch.json()["id"], "title": "Ctl job", "priority": "normal"},
    )
    assert job.status_code == 201, job.text
    quote = client.post(
        "/v1/quotes",
        headers=headers,
        json={
            "repair_job_id": job.json()["id"],
            "tax_cents": 0,
            "line_items": [{"item_type": "labor", "description": "Service", "quantity": 1, "unit_price_cents": 1000}],
        },
    )
    assert quote.status_code == 201, quote.text
    assert client.post(f"/v1/quotes/{quote.json()['id']}/send", headers=headers).status_code == 200
    return UUID(job.json()["id"]), quote.json()["id"]


def _add_sent_log(tenant_id: UUID, to_phone: str, created_at: datetime | None = None) -> None:
    with Session(engine) as session:
        session.add(SmsLog(
            tenant_id=tenant_id, to_phone=to_phone, body="Outbound", event="quote_sent",
            status="sent", created_at=created_at or datetime.now(timezone.utc),
        ))
        session.commit()


def _suppression(phone: str) -> SmsSuppression | None:
    from app.phone_utils import normalize_phone

    with Session(engine) as session:
        return session.exec(
            select(SmsSuppression).where(SmsSuppression.phone_normalized == normalize_phone(phone))
        ).first()


def _send(tenant_id: UUID, phone: str, event: str = "test") -> tuple[str | None, str]:
    with Session(engine) as session:
        result = sms._logged_send(session, tenant_id=tenant_id, repair_job_id=None, to_phone=phone, body="hi", event=event)
        session.commit()
        return result


# ── Suppression ──────────────────────────────────────────────────────────────

@pytest.mark.parametrize("word", ["STOP", "stopall", "Unsubscribe", "CANCEL", "end", " Quit "])
def test_stop_keywords_suppress_and_block_sends(client: TestClient, word: str):
    from_phone, stored = _unique_phone()
    headers, tenant_id, _ = _bootstrap_tenant(client)
    _customer(client, headers, stored)

    res = client.post(_WEBHOOK, data={"From": from_phone, "Body": word, "MessageSid": f"SM{uuid4().hex}"})
    assert res.status_code == 200
    assert "<Message>" not in res.text  # no auto-reply to an opted-out number
    row = _suppression(from_phone)
    assert row is not None and row.active

    _sid, status = _send(tenant_id, stored)
    assert status == "suppressed"
    with Session(engine) as session:
        log = session.exec(
            select(SmsLog).where(SmsLog.tenant_id == tenant_id).where(SmsLog.status == "suppressed")
        ).first()
        assert log is not None and log.provider_sid is None and log.attempt_count == 0


def test_suppression_is_global_across_tenants(client: TestClient):
    from_phone, stored = _unique_phone()
    headers_a, tenant_a, _ = _bootstrap_tenant(client)
    _, tenant_b, _ = _bootstrap_tenant(client)
    _customer(client, headers_a, stored)
    client.post(_WEBHOOK, data={"From": from_phone, "Body": "STOP"})
    assert _send(tenant_b, stored)[1] == "suppressed"


def test_start_and_unstop_resubscribe(client: TestClient):
    from_phone, stored = _unique_phone()
    headers, tenant_id, _ = _bootstrap_tenant(client)
    _customer(client, headers, stored)
    for word in ("START", "UNSTOP"):
        client.post(_WEBHOOK, data={"From": from_phone, "Body": "STOP"})
        assert _send(tenant_id, stored)[1] == "suppressed"
        client.post(_WEBHOOK, data={"From": from_phone, "Body": word})
        assert not _suppression(from_phone).active
        assert _send(tenant_id, stored)[1] in ("dry_run", "sent")


def test_yes_resubscribes_only_when_suppressed_and_quote_reply_still_works(client: TestClient):
    from_phone, stored = _unique_phone()
    headers, tenant_id, _ = _bootstrap_tenant(client)
    customer_id = _customer(client, headers, stored)
    job_id, quote_id = _job_with_sent_quote(client, headers, customer_id)

    # Not suppressed: YES is a plain quote approval and creates no suppression row.
    res = client.post(_WEBHOOK, data={"From": from_phone, "Body": "YES"})
    assert "approved" in res.text.lower()
    assert _suppression(from_phone) is None
    with Session(engine) as session:
        assert session.get(Quote, UUID(quote_id)).status == "approved"

    # Suppressed: YES lifts the suppression.
    client.post(_WEBHOOK, data={"From": from_phone, "Body": "STOP"})
    assert _suppression(from_phone).active
    client.post(_WEBHOOK, data={"From": from_phone, "Body": "YES"})
    assert not _suppression(from_phone).active


def test_stop_does_not_decline_or_approve_quote(client: TestClient):
    from_phone, stored = _unique_phone()
    headers, _tenant, _ = _bootstrap_tenant(client)
    customer_id = _customer(client, headers, stored)
    _job_id, quote_id = _job_with_sent_quote(client, headers, customer_id)
    client.post(_WEBHOOK, data={"From": from_phone, "Body": "CANCEL"})
    with Session(engine) as session:
        assert session.get(Quote, UUID(quote_id)).status == "sent"


def test_free_text_message_endpoint_respects_suppression(client: TestClient):
    from_phone, stored = _unique_phone()
    headers, tenant_id, _ = _bootstrap_tenant(client)
    customer_id = _customer(client, headers, stored)
    job_id, _q = _job_with_sent_quote(client, headers, customer_id)

    ok = client.post(f"/v1/repair-jobs/{job_id}/messages", headers=headers, json={"body": "Hello there"})
    assert ok.status_code == 201, ok.text

    client.post(_WEBHOOK, data={"From": from_phone, "Body": "STOP"})
    blocked = client.post(f"/v1/repair-jobs/{job_id}/messages", headers=headers, json={"body": "Hello again"})
    assert blocked.status_code == 409
    with Session(engine) as session:
        outbound = session.exec(
            select(JobMessage).where(JobMessage.repair_job_id == job_id).where(JobMessage.direction == "outbound")
        ).all()
        assert [m.body for m in outbound] == ["Hello there"]
        assert session.exec(
            select(SmsLog).where(SmsLog.repair_job_id == job_id).where(SmsLog.status == "suppressed")
        ).first() is not None


# ── MessageSid dedupe ────────────────────────────────────────────────────────

def test_replayed_message_sid_is_a_noop(client: TestClient):
    from_phone, stored = _unique_phone()
    headers, tenant_id, _ = _bootstrap_tenant(client)
    customer_id = _customer(client, headers, stored)
    job_id, quote_id = _job_with_sent_quote(client, headers, customer_id)
    sid = f"SM{uuid4().hex}"

    first = client.post(_WEBHOOK, data={"From": from_phone, "Body": "Where is my watch?", "MessageSid": sid})
    second = client.post(_WEBHOOK, data={"From": from_phone, "Body": "Where is my watch?", "MessageSid": sid})
    assert first.status_code == second.status_code == 200
    with Session(engine) as session:
        msgs = session.exec(
            select(JobMessage).where(JobMessage.direction == "inbound").where(JobMessage.from_phone == from_phone)
        ).all()
        assert len(msgs) == 1
        assert len(session.exec(select(InboundSmsReceipt).where(InboundSmsReceipt.message_sid == sid)).all()) == 1
        events = session.exec(
            select(TenantEventLog)
            .where(TenantEventLog.tenant_id == tenant_id)
            .where(TenantEventLog.event_type == "customer_sms_reply")
        ).all()
        assert len(events) == 1


def test_replayed_yes_does_not_reapply_decision(client: TestClient):
    from_phone, stored = _unique_phone()
    headers, _tenant, _ = _bootstrap_tenant(client)
    customer_id = _customer(client, headers, stored)
    _job_id, _quote_id = _job_with_sent_quote(client, headers, customer_id)
    sid = f"SM{uuid4().hex}"
    first = client.post(_WEBHOOK, data={"From": from_phone, "Body": "YES", "MessageSid": sid})
    assert "approved" in first.text.lower()
    second = client.post(_WEBHOOK, data={"From": from_phone, "Body": "YES", "MessageSid": sid})
    assert "<Message>" not in second.text


# ── Ambiguous attribution ────────────────────────────────────────────────────

def _two_shops_same_phone(client: TestClient):
    from_phone, stored = _unique_phone()
    headers_a, tenant_a, _ = _bootstrap_tenant(client)
    headers_b, tenant_b, _ = _bootstrap_tenant(client)
    cust_a = _customer(client, headers_a, stored)
    cust_b = _customer(client, headers_b, stored)
    job_a, quote_a = _job_with_sent_quote(client, headers_a, cust_a)
    job_b, quote_b = _job_with_sent_quote(client, headers_b, cust_b)
    return from_phone, (tenant_a, job_a, quote_a), (tenant_b, job_b, quote_b)


def _quote_status(quote_id: str) -> str:
    with Session(engine) as session:
        return session.get(Quote, UUID(quote_id)).status


def _inbound_count(from_phone: str) -> int:
    with Session(engine) as session:
        return len(session.exec(
            select(JobMessage).where(JobMessage.direction == "inbound").where(JobMessage.from_phone == from_phone)
        ).all())


def test_ambiguous_phone_without_recent_outbound_is_not_acted_on(client: TestClient):
    from_phone, a, b = _two_shops_same_phone(client)
    res = client.post(_WEBHOOK, data={"From": from_phone, "Body": "YES"})
    assert res.status_code == 200
    assert "approved" not in res.text.lower()
    assert _quote_status(a[2]) == "sent"
    assert _quote_status(b[2]) == "sent"
    assert _inbound_count(from_phone) == 0


def test_ambiguous_phone_with_only_stale_outbound_is_not_acted_on(client: TestClient):
    from_phone, a, b = _two_shops_same_phone(client)
    stale = datetime.now(timezone.utc) - timedelta(days=settings.sms_attribution_window_days + 5)
    _add_sent_log(a[0], from_phone, stale)
    res = client.post(_WEBHOOK, data={"From": from_phone, "Body": "YES"})
    assert "approved" not in res.text.lower()
    assert _quote_status(a[2]) == "sent" and _quote_status(b[2]) == "sent"


def test_ambiguous_phone_recent_outbound_picks_that_tenant_only(client: TestClient):
    from_phone, a, b = _two_shops_same_phone(client)
    now = datetime.now(timezone.utc)
    _add_sent_log(a[0], from_phone, now - timedelta(days=3))
    _add_sent_log(b[0], from_phone, now - timedelta(hours=1))
    res = client.post(_WEBHOOK, data={"From": from_phone, "Body": "YES"})
    assert "approved" in res.text.lower()
    assert _quote_status(b[2]) == "approved"
    assert _quote_status(a[2]) == "sent"


def test_stop_from_ambiguous_phone_still_suppresses(client: TestClient):
    from_phone, a, b = _two_shops_same_phone(client)
    client.post(_WEBHOOK, data={"From": from_phone, "Body": "STOP"})
    row = _suppression(from_phone)
    assert row is not None and row.active
    assert _send(a[0], from_phone)[1] == "suppressed"
    assert _send(b[0], from_phone)[1] == "suppressed"


# ── Fair-use metering ────────────────────────────────────────────────────────

def _events(tenant_id: UUID, event_type: str) -> list[TenantEventLog]:
    with Session(engine) as session:
        return list(session.exec(
            select(TenantEventLog)
            .where(TenantEventLog.tenant_id == tenant_id)
            .where(TenantEventLog.event_type == event_type)
        ).all())


def test_fair_use_events_fire_once_at_80_and_100_and_never_block(client: TestClient, monkeypatch):
    monkeypatch.setattr(settings, "sms_monthly_fair_use_limit", 5)
    _headers, tenant_id, _ = _bootstrap_tenant(client)
    phone = _unique_phone()[1]
    statuses = []
    for _ in range(3):
        statuses.append(_send(tenant_id, phone)[1])
    assert _events(tenant_id, "sms_fair_use_80") == []
    statuses.append(_send(tenant_id, phone)[1])  # 4 of 5 = 80%
    assert len(_events(tenant_id, "sms_fair_use_80")) == 1
    assert _events(tenant_id, "sms_fair_use_100") == []
    statuses.append(_send(tenant_id, phone)[1])  # 5 of 5 = 100%
    assert len(_events(tenant_id, "sms_fair_use_100")) == 1
    for _ in range(3):  # over the limit: still sends, no duplicate events
        statuses.append(_send(tenant_id, phone)[1])
    assert all(s in ("dry_run", "sent") for s in statuses)
    assert len(_events(tenant_id, "sms_fair_use_80")) == 1
    assert len(_events(tenant_id, "sms_fair_use_100")) == 1


def test_fair_use_disabled_when_limit_zero(client: TestClient, monkeypatch):
    monkeypatch.setattr(settings, "sms_monthly_fair_use_limit", 0)
    _headers, tenant_id, _ = _bootstrap_tenant(client)
    for _ in range(3):
        _send(tenant_id, _unique_phone()[1])
    assert _events(tenant_id, "sms_fair_use_80") == [] and _events(tenant_id, "sms_fair_use_100") == []


def test_suppressed_sends_do_not_count(client: TestClient, monkeypatch):
    monkeypatch.setattr(settings, "sms_monthly_fair_use_limit", 2)
    from_phone, stored = _unique_phone()
    _headers, tenant_id, _ = _bootstrap_tenant(client)
    client.post(_WEBHOOK, data={"From": from_phone, "Body": "STOP"})
    for _ in range(4):
        assert _send(tenant_id, stored)[1] == "suppressed"
    assert _events(tenant_id, "sms_fair_use_100") == []


def test_month_bounds_use_melbourne_calendar():
    # 2026-06-30 14:30 UTC is 2026-07-01 00:30 in Melbourne (AEST, UTC+10).
    start, end = month_bounds_utc(datetime(2026, 6, 30, 14, 30, tzinfo=timezone.utc))
    assert start == datetime(2026, 6, 30, 14, 0, tzinfo=timezone.utc)
    assert end == datetime(2026, 7, 31, 14, 0, tzinfo=timezone.utc)
    start, end = month_bounds_utc(datetime(2026, 12, 15, tzinfo=timezone.utc))
    assert end > start and end.astimezone(timezone.utc).month in (12, 1)


def test_usage_endpoint_owner_self_and_cross_tenant_denied(client: TestClient, monkeypatch):
    monkeypatch.setattr(settings, "sms_monthly_fair_use_limit", 10)
    headers, tenant_id, _ = _bootstrap_tenant(client)
    other_headers, other_tenant, _ = _bootstrap_tenant(client)
    for _ in range(4):
        _send(tenant_id, _unique_phone()[1])

    res = client.get("/v1/sms/usage", headers=headers)
    assert res.status_code == 200, res.text
    body = res.json()
    assert body["sent"] == 4 and body["limit"] == 10 and body["remaining"] == 6
    assert body["warn_threshold_reached"] is False and body["limit_reached"] is False
    assert body["enforced"] is False

    # Another shop's owner cannot look at this tenant.
    assert client.get("/v1/sms/usage", params={"tenant_id": str(tenant_id)}, headers=other_headers).status_code == 404
    assert client.get("/v1/sms/usage", params={"tenant_id": str(uuid4())}, headers=headers).status_code == 404
    assert client.get("/v1/sms/usage").status_code in (401, 403)


def test_usage_endpoint_hq_owner_sees_linked_operators_only(client: TestClient):
    hq_headers, hq_tenant, _ = _bootstrap_tenant(client, "hq")
    _, linked, _ = _bootstrap_tenant(client, "linked")
    _, unlinked, _ = _bootstrap_tenant(client, "unlinked")
    _send(linked, _unique_phone()[1])
    with Session(engine) as session:
        parent = ParentAccount(name="Ctl HQ", owner_email=f"{uuid4().hex[:8]}@example.test")
        session.add(parent)
        session.flush()
        session.add(ParentAccountSite(parent_account_id=parent.id, tenant_id=hq_tenant, network_role=NETWORK_ROLE_HQ))
        session.add(ParentAccountSite(parent_account_id=parent.id, tenant_id=linked, network_role=NETWORK_ROLE_RETAIL))
        session.commit()

    ok = client.get("/v1/sms/usage", params={"tenant_id": str(linked)}, headers=hq_headers)
    assert ok.status_code == 200, ok.text
    assert ok.json()["tenant_id"] == str(linked) and ok.json()["sent"] == 1
    assert client.get("/v1/sms/usage", params={"tenant_id": str(unlinked)}, headers=hq_headers).status_code == 404


def test_usage_endpoint_platform_admin_sees_any_tenant(client: TestClient):
    _, target, _ = _bootstrap_tenant(client)
    _h, admin_tenant, admin_email = _bootstrap_tenant(client, "padmin")
    with Session(engine) as session:
        user = session.exec(select(User).where(User.email == admin_email)).first()
        user.role = "platform_admin"
        session.add(user)
        session.commit()
        slug = session.get(Tenant, admin_tenant).slug
    login = client.post("/v1/auth/login", json={"tenant_slug": slug, "email": admin_email, "password": "pass123456"})
    assert login.status_code == 200, login.text
    headers = {"Authorization": f"Bearer {login.json()['access_token']}"}
    res = client.get("/v1/sms/usage", params={"tenant_id": str(target)}, headers=headers)
    assert res.status_code == 200, res.text
