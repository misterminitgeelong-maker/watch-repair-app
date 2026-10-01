"""Phone push: device token registration and inbox-alert fan-out."""
from uuid import uuid4

from sqlmodel import Session, select

from app import push
from app.database import engine
from app.models import DeviceToken, TenantEventLog

TOKEN = "t" * 40


def test_register_is_idempotent_and_moves_between_users(client, auth_headers, bootstrap_and_login):
    assert client.post("/v1/me/devices", headers=auth_headers, json={"token": TOKEN}).status_code == 204
    assert client.post("/v1/me/devices", headers=auth_headers, json={"token": TOKEN, "platform": "ios"}).status_code == 204
    with Session(engine) as db:
        rows = db.exec(select(DeviceToken).where(DeviceToken.token == TOKEN)).all()
        assert len(rows) == 1 and rows[0].platform == "ios"
    assert client.post("/v1/me/devices", headers=auth_headers, json={"token": "short"}).status_code == 422
    assert client.delete("/v1/me/devices", headers=auth_headers, params={"token": TOKEN}).status_code == 204
    with Session(engine) as db:
        assert db.exec(select(DeviceToken).where(DeviceToken.token == TOKEN)).first() is None


def test_register_requires_auth(client):
    assert client.post("/v1/me/devices", json={"token": TOKEN}).status_code in (401, 403)


def test_inbox_alert_pushes_after_commit(client, auth_headers, bootstrap_and_login, monkeypatch):
    client.post("/v1/me/devices", headers=auth_headers, json={"token": TOKEN})
    with Session(engine) as db:
        tenant_id = db.exec(select(DeviceToken).where(DeviceToken.token == TOKEN)).one().tenant_id

    sent: list[tuple] = []
    monkeypatch.setattr(push, "fcm_enabled", lambda: True)
    monkeypatch.setattr(push, "_service_account", lambda: {"project_id": "p", "client_email": "e", "private_key": "k"})
    monkeypatch.setattr(push, "send_to_tokens", lambda tokens, title, body: sent.append((tuple(tokens), title, body)) or [])
    monkeypatch.setattr(push, "_dispatch", lambda items: [push.notify_tenant(*i) for i in items])

    with Session(engine) as db:
        db.add(TenantEventLog(tenant_id=tenant_id, entity_type="quote", entity_id=uuid4(), event_type="quote_approved", event_summary="Quote approved"))
        db.add(TenantEventLog(tenant_id=tenant_id, entity_type="session", event_type="login", event_summary="Signed in"))
        db.commit()
    assert sent == [((TOKEN,), "Mainspring", "Quote approved")]

    sent.clear()
    with Session(engine) as db:
        db.add(TenantEventLog(tenant_id=tenant_id, entity_type="quote", entity_id=uuid4(), event_type="invoice_paid", event_summary="Paid"))
        db.rollback()
    assert sent == []


def test_dead_tokens_are_pruned(client, auth_headers, bootstrap_and_login, monkeypatch):
    client.post("/v1/me/devices", headers=auth_headers, json={"token": TOKEN})
    with Session(engine) as db:
        tenant_id = db.exec(select(DeviceToken).where(DeviceToken.token == TOKEN)).one().tenant_id
    monkeypatch.setattr(push, "fcm_enabled", lambda: True)
    monkeypatch.setattr(push, "send_to_tokens", lambda tokens, title, body: list(tokens))
    push.notify_tenant(tenant_id, "Mainspring", "x")
    with Session(engine) as db:
        assert db.exec(select(DeviceToken).where(DeviceToken.token == TOKEN)).first() is None
