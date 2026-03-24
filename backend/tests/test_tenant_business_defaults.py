import os
from pathlib import Path
from uuid import UUID, uuid4

from fastapi.testclient import TestClient
from sqlmodel import Session, select

_TEST_DB = Path(__file__).with_name(f"test_tenant_defaults_{uuid4().hex}.db")
os.environ["DATABASE_URL"] = f"sqlite:///{_TEST_DB.as_posix()}"
os.environ.setdefault("JWT_SECRET", "test-secret-not-for-production")
os.environ.setdefault("APP_ENV", "test")

from app.database import create_db_and_tables, engine
from app.main import app
from app.models import Tenant

create_db_and_tables()
client = TestClient(app)


def _bootstrap_and_login(tenant_slug: str, email: str, password: str) -> tuple[str, str]:
    bootstrap_payload = {
        "tenant_name": f"Tenant {tenant_slug}",
        "tenant_slug": tenant_slug,
        "owner_email": email,
        "owner_full_name": "Owner",
        "owner_password": password,
    }
    bootstrap_res = client.post("/v1/auth/bootstrap", json=bootstrap_payload)
    assert bootstrap_res.status_code == 200
    tenant_id = bootstrap_res.json()["tenant_id"]

    login_res = client.post(
        "/v1/auth/login",
        json={"tenant_slug": tenant_slug, "email": email, "password": password},
    )
    assert login_res.status_code == 200
    return tenant_id, login_res.json()["access_token"]


def _create_watch(headers: dict[str, str]) -> str:
    customer = client.post(
        "/v1/customers",
        headers=headers,
        json={"full_name": "Currency Customer", "email": "currency@example.com"},
    )
    assert customer.status_code == 201
    customer_id = customer.json()["id"]
    watch = client.post(
        "/v1/watches",
        headers=headers,
        json={"customer_id": customer_id, "brand": "Seiko", "model": "SKX"},
    )
    assert watch.status_code == 201
    return watch.json()["id"]


def _create_approved_quote(headers: dict[str, str], watch_id: str) -> str:
    job = client.post(
        "/v1/repair-jobs",
        headers=headers,
        json={"watch_id": watch_id, "title": "Tenant Currency Job", "priority": "normal"},
    )
    assert job.status_code == 201
    job_id = job.json()["id"]

    quote = client.post(
        "/v1/quotes",
        headers=headers,
        json={
            "repair_job_id": job_id,
            "tax_cents": 200,
            "line_items": [{"item_type": "labor", "description": "Service", "quantity": 1, "unit_price_cents": 10000}],
        },
    )
    assert quote.status_code == 201
    quote_id = quote.json()["id"]

    sent = client.post(f"/v1/quotes/{quote_id}/send", headers=headers)
    assert sent.status_code == 200
    approved = client.post(
        f"/v1/public/quotes/{sent.json()['approval_token']}/decision",
        json={"decision": "approved"},
    )
    assert approved.status_code == 200
    return quote_id


def test_new_tenant_defaults_are_set():
    suffix = uuid4().hex[:8]
    tenant_id, _ = _bootstrap_and_login(f"defaults-{suffix}", f"owner-{suffix}@defaults.test", "pass123456")
    with Session(engine) as session:
        tenant = session.get(Tenant, UUID(tenant_id))
        assert tenant is not None
        assert tenant.default_currency == "AUD"
        assert tenant.timezone == "Australia/Melbourne"


def test_quote_currency_uses_tenant_default():
    suffix = uuid4().hex[:8]
    tenant_id, token = _bootstrap_and_login(f"quote-cur-{suffix}", f"owner-{suffix}@quotecur.test", "pass123456")
    headers = {"Authorization": f"Bearer {token}"}
    with Session(engine) as session:
        tenant = session.get(Tenant, UUID(tenant_id))
        tenant.default_currency = "USD"
        session.add(tenant)
        session.commit()

    quote = client.post(
        "/v1/quotes",
        headers=headers,
        json={
            "repair_job_id": client.post(
                "/v1/repair-jobs",
                headers=headers,
                json={"watch_id": _create_watch(headers), "title": "USD quote", "priority": "normal"},
            ).json()["id"],
            "tax_cents": 0,
            "line_items": [{"item_type": "labor", "description": "Service", "quantity": 1, "unit_price_cents": 10000}],
        },
    )
    assert quote.status_code == 201
    assert quote.json()["currency"] == "USD"


def test_invoice_and_payment_currency_follow_quote_and_invoice():
    suffix = uuid4().hex[:8]
    tenant_id, token = _bootstrap_and_login(f"inv-pay-cur-{suffix}", f"owner-{suffix}@invpay.test", "pass123456")
    headers = {"Authorization": f"Bearer {token}"}
    with Session(engine) as session:
        tenant = session.get(Tenant, UUID(tenant_id))
        tenant.default_currency = "NZD"
        session.add(tenant)
        session.commit()

    quote_id = _create_approved_quote(headers, _create_watch(headers))
    quote_res = client.get("/v1/quotes", headers=headers)
    assert quote_res.status_code == 200
    created_quote = next(q for q in quote_res.json() if q["id"] == quote_id)
    assert created_quote["currency"] == "NZD"

    inv_res = client.post(f"/v1/invoices/from-quote/{quote_id}", headers=headers)
    assert inv_res.status_code == 201
    invoice = inv_res.json()["invoice"]
    assert invoice["currency"] == "NZD"

    pay_res = client.post(
        f"/v1/invoices/{invoice['id']}/payments",
        headers=headers,
        json={"amount_cents": 10200, "provider_reference": "tenant-currency-test"},
    )
    assert pay_res.status_code == 201
    assert pay_res.json()["currency"] == "NZD"
