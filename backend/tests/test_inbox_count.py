"""GET /v1/inbox/count — lightweight badge endpoint."""
from uuid import UUID, uuid4

from jose import jwt
from sqlmodel import Session

from app.config import settings
from app.database import engine
from app.models import TenantEventLog


def _tenant_id_from_headers(auth_headers: dict[str, str]) -> UUID:
    token = auth_headers["Authorization"].removeprefix("Bearer ")
    return UUID(jwt.decode(token, settings.jwt_secret, algorithms=[settings.jwt_algorithm])["tenant_id"])


def test_inbox_count_empty(client, auth_headers):
    res = client.get("/v1/inbox/count", headers=auth_headers)
    assert res.status_code == 200, res.text
    assert res.json()["count"] == 0


def test_inbox_count_and_exclude(client, auth_headers):
    tid = _tenant_id_from_headers(auth_headers)
    with Session(engine) as session:
        session.add(
            TenantEventLog(
                tenant_id=tid,
                entity_type="customer",
                entity_id=uuid4(),
                event_type="customer_sms_reply",
                event_summary="test sms",
            )
        )
        session.add(
            TenantEventLog(
                tenant_id=tid,
                entity_type="email",
                entity_id=uuid4(),
                event_type="inbound_email_received",
                event_summary="test email",
            )
        )
        session.commit()

    full = client.get("/v1/inbox/count", headers=auth_headers)
    assert full.status_code == 200
    assert full.json()["count"] == 2

    filtered = client.get(
        "/v1/inbox/count",
        headers=auth_headers,
        params={"exclude": "inbound_email_received"},
    )
    assert filtered.status_code == 200
    assert filtered.json()["count"] == 1


def test_intake_cannot_delete_inbox_alert(client, bootstrap_and_login):
    suffix = uuid4().hex[:8]
    slug = f"inbox-intake-{suffix}"
    email = f"owner-{suffix}@inbox.test"
    token = bootstrap_and_login(tenant_slug=slug, email=email)
    owner_h = {"Authorization": f"Bearer {token}"}

    created = client.post(
        "/v1/users",
        headers=owner_h,
        json={
            "full_name": "Intake Clerk",
            "email": f"intake-{suffix}@inbox.test",
            "password": "pass123456",
            "role": "intake",
        },
    )
    assert created.status_code == 201, created.text

    login = client.post(
        "/v1/auth/login",
        json={"tenant_slug": slug, "email": f"intake-{suffix}@inbox.test", "password": "pass123456"},
    )
    assert login.status_code == 200, login.text
    intake_h = {"Authorization": f"Bearer {login.json()['access_token']}"}

    tid = _tenant_id_from_headers(owner_h)
    event_id = uuid4()
    with Session(engine) as session:
        session.add(
            TenantEventLog(
                id=event_id,
                tenant_id=tid,
                entity_type="quote",
                entity_id=uuid4(),
                event_type="quote_approved",
                event_summary="customer approved",
            )
        )
        session.commit()

    denied = client.delete(f"/v1/inbox/{event_id}", headers=intake_h)
    assert denied.status_code == 403, denied.text

    ok = client.delete(f"/v1/inbox/{event_id}", headers=owner_h)
    assert ok.status_code == 204, ok.text

