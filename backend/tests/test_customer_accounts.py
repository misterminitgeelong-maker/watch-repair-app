import os
from pathlib import Path
from uuid import uuid4

_TEST_DB = Path(__file__).with_name(f"test_customer_accounts_{uuid4().hex}.db")
os.environ["DATABASE_URL"] = f"sqlite:///{_TEST_DB.as_posix()}"
os.environ.setdefault("JWT_SECRET", "test-secret-not-for-production")
os.environ.setdefault("APP_ENV", "test")

from fastapi.testclient import TestClient

from app.database import create_db_and_tables
from app.main import app

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


def _create_customer(headers: dict[str, str], full_name: str) -> str:
    res = client.post(
        "/v1/customers",
        headers=headers,
        json={"full_name": full_name, "email": f"{full_name.lower().replace(' ', '.')}@test.local"},
    )
    assert res.status_code == 201
    return res.json()["id"]


def test_create_customer_account_and_link_customers():
    suffix = uuid4().hex[:8]
    token = _bootstrap_and_login(
        tenant_slug=f"b2b-{suffix}",
        email=f"owner-{suffix}@b2b.test",
        password="pass123456",
    )
    headers = {"Authorization": f"Bearer {token}"}

    customer_a = _create_customer(headers, "Store A")
    customer_b = _create_customer(headers, "Store B")

    create_account = client.post(
        "/v1/customer-accounts",
        headers=headers,
        json={
            "name": "Mister Minit Group",
            "account_code": "MM-001",
            "contact_email": "accounts@misterminit.test",
            "payment_terms_days": 30,
        },
    )
    assert create_account.status_code == 201
    account_id = create_account.json()["id"]

    add_a = client.post(
        f"/v1/customer-accounts/{account_id}/customers",
        headers=headers,
        json={"customer_id": customer_a},
    )
    assert add_a.status_code == 200

    add_b = client.post(
        f"/v1/customer-accounts/{account_id}/customers",
        headers=headers,
        json={"customer_id": customer_b},
    )
    assert add_b.status_code == 200

    list_accounts = client.get("/v1/customer-accounts", headers=headers)
    assert list_accounts.status_code == 200
    accounts = list_accounts.json()
    assert len(accounts) == 1
    assert set(accounts[0]["customer_ids"]) == {customer_a, customer_b}

    remove_a = client.delete(f"/v1/customer-accounts/{account_id}/customers/{customer_a}", headers=headers)
    assert remove_a.status_code == 204

    account_after_remove = client.get(f"/v1/customer-accounts/{account_id}", headers=headers)
    assert account_after_remove.status_code == 200
    assert account_after_remove.json()["customer_ids"] == [customer_b]


def test_customer_account_statement_and_monthly_invoice_generation():
    suffix = uuid4().hex[:8]
    token = _bootstrap_and_login(
        tenant_slug=f"b2b-billing-{suffix}",
        email=f"owner-{suffix}@billing.test",
        password="pass123456",
        plan_code="enterprise",
    )
    headers = {"Authorization": f"Bearer {token}"}

    customer_id = _create_customer(headers, "Corporate Client")

    account_res = client.post(
        "/v1/customer-accounts",
        headers=headers,
        json={"name": "Corporate Group", "payment_terms_days": 30},
    )
    assert account_res.status_code == 201
    account_id = account_res.json()["id"]

    link_res = client.post(
        f"/v1/customer-accounts/{account_id}/customers",
        headers=headers,
        json={"customer_id": customer_id},
    )
    assert link_res.status_code == 200

    auto_key_res = client.post(
        "/v1/auto-key-jobs",
        headers=headers,
        json={
            "customer_id": customer_id,
            "customer_account_id": account_id,
            "title": "Fleet key replacement",
            "description": "Replace two transponder keys",
            "key_quantity": 2,
            "programming_status": "programmed",
            "priority": "normal",
            "status": "completed",
            "deposit_cents": 0,
            "cost_cents": 24500,
        },
    )
    assert auto_key_res.status_code == 201

    now = auto_key_res.json()["created_at"]
    period_year = int(now[0:4])
    period_month = int(now[5:7])

    statement_res = client.get(
        f"/v1/customer-accounts/{account_id}/statement",
        headers=headers,
        params={"period_year": period_year, "period_month": period_month},
    )
    assert statement_res.status_code == 200
    statement = statement_res.json()
    assert statement["subtotal_cents"] == 24500
    assert len(statement["lines"]) == 1
    assert statement["lines"][0]["source_type"] == "auto_key"

    invoice_res = client.post(
        f"/v1/customer-accounts/{account_id}/invoices/monthly",
        headers=headers,
        json={"period_year": period_year, "period_month": period_month, "tax_cents": 2450},
    )
    assert invoice_res.status_code == 201
    invoice = invoice_res.json()
    assert invoice["subtotal_cents"] == 24500
    assert invoice["tax_cents"] == 2450
    assert invoice["total_cents"] == 26950
    assert invoice["invoice_number"].startswith("B2B-")
    assert len(invoice["lines"]) == 1

    duplicate_invoice_res = client.post(
        f"/v1/customer-accounts/{account_id}/invoices/monthly",
        headers=headers,
        json={"period_year": period_year, "period_month": period_month, "tax_cents": 2450},
    )
    assert duplicate_invoice_res.status_code == 409

    statement_after_invoice_res = client.get(
        f"/v1/customer-accounts/{account_id}/statement",
        headers=headers,
        params={"period_year": period_year, "period_month": period_month},
    )
    assert statement_after_invoice_res.status_code == 200
    statement_after_invoice = statement_after_invoice_res.json()
    assert statement_after_invoice["subtotal_cents"] == 0
    assert statement_after_invoice["lines"] == []
