"""Support-access consent and mobile-job ID capture."""
from datetime import datetime, timedelta, timezone
from uuid import UUID, uuid4

from fastapi.testclient import TestClient
from sqlmodel import Session, select

from app.database import engine
from app.models import (
    AutoKeyIdAccessLog,
    AutoKeyJob,
    Tenant,
    TenantEventLog,
    User,
)
from tests.test_sms_controls import _bootstrap_tenant, _customer, _unique_phone

_WEBHOOK = "/v1/webhook/sms/incoming"


# ── support-access consent ──────────────────────────────────────────────────


def test_owner_grants_and_revokes_support_access(client: TestClient):
    owner, tenant_id, _ = _bootstrap_tenant(client)
    assert client.get("/v1/shop/support-access", headers=owner).json()["enabled"] is False
    on = client.put("/v1/shop/support-access", headers=owner, json={"enabled": True, "hours": 3})
    assert on.status_code == 200 and on.json()["enabled"] is True
    assert client.put("/v1/shop/support-access", headers=owner, json={"enabled": True, "hours": 9999}).status_code == 422
    off = client.put("/v1/shop/support-access", headers=owner, json={"enabled": False})
    assert off.json()["enabled"] is False
    with Session(engine) as session:
        kinds = [e.event_type for e in session.exec(select(TenantEventLog).where(TenantEventLog.tenant_id == tenant_id)).all()]
        assert kinds.count("support_access_changed") == 2


def test_expired_grant_does_not_count(client: TestClient):
    from app.support_access import grant_active

    _, tenant_id, _ = _bootstrap_tenant(client)
    with Session(engine) as session:
        t = session.get(Tenant, tenant_id)
        t.support_access_until = datetime.now(timezone.utc) - timedelta(minutes=1)
        assert grant_active(t) is False
        t.support_access_until = datetime.now(timezone.utc) + timedelta(minutes=1)
        assert grant_active(t) is True


def test_events_written_in_a_support_session_are_tagged_and_support_cannot_self_grant(client: TestClient):
    from app.security import create_access_token

    owner, tenant_id, email = _bootstrap_tenant(client)
    supporter = uuid4()
    with Session(engine) as session:
        owner_user = session.exec(select(User).where(User.email == email)).first()
        token, _ = create_access_token(tenant_id, owner_user.id, owner_user.role, expires_minutes=30, support_actor_user_id=owner_user.id)
    support = {"Authorization": f"Bearer {token}"}
    denied = client.put("/v1/shop/support-access", headers=support, json={"enabled": True, "hours": 1})
    assert denied.status_code == 403

    # an ordinary audit-writing action done in the support session is tagged
    res = client.put("/v1/shop/id-capture-setting", headers=support, json={"require_id_capture": True})
    assert res.status_code == 200
    with Session(engine) as session:
        row = session.exec(
            select(TenantEventLog)
            .where(TenantEventLog.tenant_id == tenant_id)
            .where(TenantEventLog.event_type == "id_capture_requirement_changed")
        ).first()
        assert row.support_actor_user_id == owner_user.id
        assert row.event_summary.endswith("[support session]")


# ── ID capture ──────────────────────────────────────────────────────────────


def _auto_key_job(client: TestClient, headers: dict[str, str]) -> str:
    cid = _customer(client, headers, _unique_phone()[1])
    res = client.post(
        "/v1/auto-key-jobs",
        headers=headers,
        json={"customer_id": cid, "title": "Lockout", "job_type": "Lockout – Car", "status": "booked", "priority": "normal"},
    )
    assert res.status_code == 201, res.text
    return res.json()["id"]


_PAYLOAD = {
    "id_type": "drivers_licence",
    "id_number": "12345678",
    "id_issuer": "VIC",
    "name_on_id": "Jo Citizen",
    "proof_of_ownership_type": "registration",
    "consent_given": True,
    "consent_method": "verbal",
}


def test_id_capture_masks_encrypts_logs_and_requires_consent(client: TestClient):
    h, tenant_id, _ = _bootstrap_tenant(client)
    jid = _auto_key_job(client, h)
    url = f"/v1/auto-key-jobs/{jid}/id-capture"

    assert client.get(url, headers=h).status_code == 404
    assert client.put(url, headers=h, json={**_PAYLOAD, "consent_given": False}).status_code == 422
    saved = client.put(url, headers=h, json=_PAYLOAD)
    assert saved.status_code == 200, saved.text
    body = saved.json()
    assert body["id_number_masked"] == "••••5678" and body["id_number"] is None
    assert "12345678" not in saved.text

    from app.models import AutoKeyIdCapture

    with Session(engine) as session:
        row = session.exec(select(AutoKeyIdCapture).where(AutoKeyIdCapture.auto_key_job_id == UUID(jid))).one()
        assert "12345678" not in row.id_number_encrypted

    assert client.get(url, headers=h).json()["id_number"] is None
    revealed = client.get(url, params={"reveal": "true"}, headers=h).json()
    assert revealed["id_number"] == "12345678"

    log = client.get(f"{url}/access-log", headers=h).json()
    assert sorted(r["action"] for r in log) == ["create", "reveal", "view"]
    # the audit feed never carries the number
    with Session(engine) as session:
        for e in session.exec(select(TenantEventLog).where(TenantEventLog.tenant_id == tenant_id)).all():
            assert "12345678" not in e.event_summary


def test_id_capture_is_tenant_scoped(client: TestClient):
    h1, _, _ = _bootstrap_tenant(client)
    h2, _, _ = _bootstrap_tenant(client)
    jid = _auto_key_job(client, h1)
    assert client.put(f"/v1/auto-key-jobs/{jid}/id-capture", headers=h1, json=_PAYLOAD).status_code == 200
    assert client.get(f"/v1/auto-key-jobs/{jid}/id-capture", headers=h2).status_code == 404
    assert client.put(f"/v1/auto-key-jobs/{jid}/id-capture", headers=h2, json=_PAYLOAD).status_code == 404


def test_job_with_id_record_cannot_be_deleted_and_completion_gate(client: TestClient):
    h, _, _ = _bootstrap_tenant(client)
    jid = _auto_key_job(client, h)
    assert client.put("/v1/shop/id-capture-setting", headers=h, json={"require_id_capture": True}).status_code == 200

    blocked = client.post(f"/v1/auto-key-jobs/{jid}/status", headers=h, json={"status": "work_completed"})
    assert blocked.status_code == 409, blocked.text
    assert client.put(f"/v1/auto-key-jobs/{jid}/id-capture", headers=h, json=_PAYLOAD).status_code == 200
    done = client.post(f"/v1/auto-key-jobs/{jid}/status", headers=h, json={"status": "work_completed"})
    assert done.status_code == 200, done.text

    assert client.delete(f"/v1/auto-key-jobs/{jid}", headers=h).status_code == 409
    with Session(engine) as session:
        assert session.get(AutoKeyJob, UUID(jid)) is not None


def test_completion_not_gated_when_setting_off(client: TestClient):
    h, _, _ = _bootstrap_tenant(client)
    jid = _auto_key_job(client, h)
    done = client.post(f"/v1/auto-key-jobs/{jid}/status", headers=h, json={"status": "work_completed"})
    assert done.status_code == 200, done.text
