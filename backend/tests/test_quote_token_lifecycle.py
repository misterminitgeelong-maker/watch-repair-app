import os
from datetime import datetime, timedelta, timezone
from pathlib import Path
from uuid import uuid4

from fastapi.testclient import TestClient
from sqlmodel import Session, select

_TEST_DB = Path(__file__).with_name(f"test_quote_tokens_{uuid4().hex}.db")
os.environ["DATABASE_URL"] = f"sqlite:///{_TEST_DB.as_posix()}"
os.environ.setdefault("JWT_SECRET", "test-secret-not-for-production")
os.environ.setdefault("APP_ENV", "test")

from app.database import create_db_and_tables, engine
from app.main import app
from app.models import Quote

create_db_and_tables()
client = TestClient(app)


def _bootstrap_and_login(tenant_slug: str, email: str, password: str) -> str:
    bootstrap = client.post(
        "/v1/auth/bootstrap",
        json={
            "tenant_name": f"Tenant {tenant_slug}",
            "tenant_slug": tenant_slug,
            "owner_email": email,
            "owner_full_name": "Owner",
            "owner_password": password,
        },
    )
    assert bootstrap.status_code == 200
    login = client.post(
        "/v1/auth/login",
        json={"tenant_slug": tenant_slug, "email": email, "password": password},
    )
    assert login.status_code == 200
    return login.json()["access_token"]


def _create_and_send_quote(headers: dict[str, str]) -> str:
    customer = client.post(
        "/v1/customers",
        headers=headers,
        json={"full_name": "Quote Token Customer", "email": "quote-token@example.com"},
    )
    assert customer.status_code == 201
    watch = client.post(
        "/v1/watches",
        headers=headers,
        json={"customer_id": customer.json()["id"], "brand": "Omega", "model": "Seamaster"},
    )
    assert watch.status_code == 201
    job = client.post(
        "/v1/repair-jobs",
        headers=headers,
        json={"watch_id": watch.json()["id"], "title": "Token lifecycle", "priority": "normal"},
    )
    assert job.status_code == 201
    quote = client.post(
        "/v1/quotes",
        headers=headers,
        json={
            "repair_job_id": job.json()["id"],
            "tax_cents": 0,
            "line_items": [
                {
                    "item_type": "labor",
                    "description": "Service",
                    "quantity": 1,
                    "unit_price_cents": 10000,
                }
            ],
        },
    )
    assert quote.status_code == 201
    sent = client.post(f"/v1/quotes/{quote.json()['id']}/send", headers=headers)
    assert sent.status_code == 200
    return sent.json()["approval_token"]


def test_public_quote_token_valid():
    token = _bootstrap_and_login("quotetok1", "owner1@example.com", "Admin123!")
    headers = {"Authorization": f"Bearer {token}"}
    approval_token = _create_and_send_quote(headers)
    res = client.get(f"/v1/public/quotes/{approval_token}")
    assert res.status_code == 200
    assert res.json()["status"] == "sent"


def test_public_quote_token_expired_rejected():
    token = _bootstrap_and_login("quotetok2", "owner2@example.com", "Admin123!")
    headers = {"Authorization": f"Bearer {token}"}
    approval_token = _create_and_send_quote(headers)

    with Session(engine) as session:
        quote = session.exec(select(Quote).where(Quote.approval_token == approval_token)).first()
        assert quote is not None
        quote.approval_token_expires_at = datetime.now(timezone.utc) - timedelta(minutes=1)
        session.add(quote)
        session.commit()

    fetch_res = client.get(f"/v1/public/quotes/{approval_token}")
    assert fetch_res.status_code == 410
    assert fetch_res.json()["detail"] == "Quote approval link has expired"

    decision_res = client.post(
        f"/v1/public/quotes/{approval_token}/decision",
        json={"decision": "approved"},
    )
    assert decision_res.status_code == 410
    assert decision_res.json()["detail"] == "Quote approval link has expired"


def test_public_quote_token_invalid_rejected():
    res = client.get("/v1/public/quotes/not-a-real-token")
    assert res.status_code == 404
    assert res.json()["detail"] == "Invalid token"


def test_public_quote_token_already_decided_rejected():
    token = _bootstrap_and_login("quotetok3", "owner3@example.com", "Admin123!")
    headers = {"Authorization": f"Bearer {token}"}
    approval_token = _create_and_send_quote(headers)

    first = client.post(
        f"/v1/public/quotes/{approval_token}/decision",
        json={"decision": "approved"},
    )
    assert first.status_code == 200
    second = client.post(
        f"/v1/public/quotes/{approval_token}/decision",
        json={"decision": "declined"},
    )
    assert second.status_code == 409
    assert second.json()["detail"] == "Decision already recorded"
