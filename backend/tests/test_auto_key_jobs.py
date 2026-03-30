import os
from pathlib import Path
from uuid import UUID, uuid4

_TEST_DB = Path(__file__).with_name(f"test_auto_key_{uuid4().hex}.db")
os.environ["DATABASE_URL"] = f"sqlite:///{_TEST_DB.as_posix()}"

from fastapi.testclient import TestClient
from sqlmodel import Session, select

from app.config import settings
from app.database import create_db_and_tables, engine
from app.main import app
from app.models import AutoKeyInvoice

create_db_and_tables()
client = TestClient(app)


def _bootstrap_and_login(tenant_slug: str, email: str, password: str, plan_code: str = "enterprise") -> str:
    bootstrap_payload = {
        "tenant_name": f"Tenant {tenant_slug}",
        "tenant_slug": tenant_slug,
        "owner_email": email,
        "owner_full_name": "Owner",
        "owner_password": password,
        "plan_code": plan_code,
    }
    bootstrap_res = client.post("/v1/auth/bootstrap", json=bootstrap_payload)
    assert bootstrap_res.status_code == 200

    login_payload = {
        "tenant_slug": tenant_slug,
        "email": email,
        "password": password,
    }
    login_res = client.post("/v1/auth/login", json=login_payload)
    assert login_res.status_code == 200
    return login_res.json()["access_token"]


def _create_customer(headers: dict[str, str]) -> str:
    res = client.post(
        "/v1/customers",
        headers=headers,
        json={"full_name": "Auto Key Customer", "phone": "0400000000"},
    )
    assert res.status_code == 201
    return res.json()["id"]


def test_auto_invoice_created_once_when_job_completed():
    suffix = uuid4().hex[:8]
    token = _bootstrap_and_login(
        tenant_slug=f"autokey-{suffix}",
        email=f"owner-{suffix}@autokey.test",
        password="pass123456",
    )
    headers = {"Authorization": f"Bearer {token}"}

    customer_id = _create_customer(headers)

    create_job_res = client.post(
        "/v1/auto-key-jobs",
        headers=headers,
        json={
            "customer_id": customer_id,
            "title": "Duplicate transponder",
            "key_quantity": 1,
            "priority": "normal",
            "status": "awaiting_quote",
            "programming_status": "pending",
            "deposit_cents": 0,
            "cost_cents": 0,
        },
    )
    assert create_job_res.status_code == 201
    job_id = create_job_res.json()["id"]

    create_quote_res = client.post(
        f"/v1/auto-key-jobs/{job_id}/quotes",
        headers=headers,
        json={
            "line_items": [
                {"description": "Program key", "quantity": 1, "unit_price_cents": 18000},
            ],
            "tax_cents": 1800,
        },
    )
    assert create_quote_res.status_code == 201
    quote_id = create_quote_res.json()["id"]

    complete_res = client.post(
        f"/v1/auto-key-jobs/{job_id}/status",
        headers=headers,
        json={"status": "completed", "note": "Done"},
    )
    assert complete_res.status_code == 200
    assert complete_res.json()["status"] == "completed"

    invoices_after_first = client.get(f"/v1/auto-key-jobs/{job_id}/invoices", headers=headers)
    assert invoices_after_first.status_code == 200
    first_list = invoices_after_first.json()
    assert len(first_list) == 1
    assert first_list[0]["auto_key_quote_id"] == quote_id
    assert first_list[0]["total_cents"] == 19800

    # Repeating the completed status should not create duplicate invoices.
    complete_again_res = client.post(
        f"/v1/auto-key-jobs/{job_id}/status",
        headers=headers,
        json={"status": "completed", "note": "Still done"},
    )
    assert complete_again_res.status_code == 200

    invoices_after_second = client.get(f"/v1/auto-key-jobs/{job_id}/invoices", headers=headers)
    assert invoices_after_second.status_code == 200
    assert len(invoices_after_second.json()) == 1


def test_auto_invoice_from_job_cost_when_no_quote():
    suffix = uuid4().hex[:8]
    token = _bootstrap_and_login(
        tenant_slug=f"autokey-cost-{suffix}",
        email=f"owner-{suffix}@autokey.test",
        password="pass123456",
    )
    headers = {"Authorization": f"Bearer {token}"}
    customer_id = _create_customer(headers)

    create_job_res = client.post(
        "/v1/auto-key-jobs",
        headers=headers,
        json={
            "customer_id": customer_id,
            "title": "Roadside spare",
            "key_quantity": 1,
            "priority": "normal",
            "status": "booked",
            "programming_status": "pending",
            "deposit_cents": 0,
            "cost_cents": 11000,
        },
    )
    assert create_job_res.status_code == 201
    job_id = create_job_res.json()["id"]

    complete_res = client.post(
        f"/v1/auto-key-jobs/{job_id}/status",
        headers=headers,
        json={"status": "completed", "note": "Done"},
    )
    assert complete_res.status_code == 200

    invoices_res = client.get(f"/v1/auto-key-jobs/{job_id}/invoices", headers=headers)
    assert invoices_res.status_code == 200
    inv_list = invoices_res.json()
    assert len(inv_list) == 1
    assert inv_list[0]["total_cents"] == 11000
    assert inv_list[0]["subtotal_cents"] == 10000
    assert inv_list[0]["tax_cents"] == 1000
    assert inv_list[0]["auto_key_quote_id"] is None


def test_public_invoice_view_uses_customer_token_after_complete(monkeypatch):
    monkeypatch.setattr(settings, "stripe_secret_key", "")
    suffix = uuid4().hex[:8]
    token = _bootstrap_and_login(
        tenant_slug=f"autokey-pubinv-{suffix}",
        email=f"owner-{suffix}@autokey.test",
        password="pass123456",
    )
    headers = {"Authorization": f"Bearer {token}"}
    customer_id = _create_customer(headers)

    create_job_res = client.post(
        "/v1/auto-key-jobs",
        headers=headers,
        json={
            "customer_id": customer_id,
            "title": "Public invoice job",
            "key_quantity": 1,
            "priority": "normal",
            "status": "on_site",
            "programming_status": "pending",
            "deposit_cents": 0,
            "cost_cents": 5000,
        },
    )
    assert create_job_res.status_code == 201
    job_id = create_job_res.json()["id"]

    r = client.post(
        f"/v1/auto-key-jobs/{job_id}/status",
        headers=headers,
        json={"status": "completed", "note": "Done"},
    )
    assert r.status_code == 200

    with Session(engine) as s:
        row = s.exec(
            select(AutoKeyInvoice).where(AutoKeyInvoice.auto_key_job_id == UUID(job_id))
        ).first()
        assert row is not None
        assert row.customer_view_token
        view_token = row.customer_view_token

    pub = client.get(f"/v1/public/auto-key-invoice/{view_token}")
    assert pub.status_code == 200
    data = pub.json()
    assert data["invoice_number"]
    assert data["total_cents"] == 5000
    assert data["job_title"] == "Public invoice job"
    assert len(data["line_items"]) >= 1
    assert data.get("can_pay_online") is False

    co = client.post(f"/v1/public/auto-key-invoice/{view_token}/checkout")
    assert co.status_code == 503

    bad = client.get("/v1/public/auto-key-invoice/not-a-real-token")
    assert bad.status_code == 404


def test_en_route_transition_succeeds():
    suffix = uuid4().hex[:8]
    token = _bootstrap_and_login(
        tenant_slug=f"autokey-route-{suffix}",
        email=f"owner-{suffix}@autokey.test",
        password="pass123456",
    )
    headers = {"Authorization": f"Bearer {token}"}
    customer_id = _create_customer(headers)

    create_job_res = client.post(
        "/v1/auto-key-jobs",
        headers=headers,
        json={
            "customer_id": customer_id,
            "title": "En route test",
            "key_quantity": 1,
            "priority": "normal",
            "status": "booked",
            "programming_status": "pending",
            "deposit_cents": 0,
            "cost_cents": 0,
            "job_address": "1 Test St",
        },
    )
    assert create_job_res.status_code == 201
    job_id = create_job_res.json()["id"]

    route_res = client.post(
        f"/v1/auto-key-jobs/{job_id}/status",
        headers=headers,
        json={"status": "en_route", "note": "Driving"},
    )
    assert route_res.status_code == 200
    assert route_res.json()["status"] == "en_route"
