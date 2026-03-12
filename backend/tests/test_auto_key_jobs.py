import os
from pathlib import Path
from uuid import uuid4

_TEST_DB = Path(__file__).with_name(f"test_auto_key_{uuid4().hex}.db")
os.environ["DATABASE_URL"] = f"sqlite:///{_TEST_DB.as_posix()}"

from fastapi.testclient import TestClient

from app.database import create_db_and_tables
from app.main import app

create_db_and_tables()
client = TestClient(app)


def _bootstrap_and_login(tenant_slug: str, email: str, password: str) -> str:
    bootstrap_payload = {
        "tenant_name": f"Tenant {tenant_slug}",
        "tenant_slug": tenant_slug,
        "owner_email": email,
        "owner_full_name": "Owner",
        "owner_password": password,
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
