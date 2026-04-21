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
from app.models import AutoKeyInvoice, Tenant

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
        json={"status": "work_completed", "note": "Done"},
    )
    assert complete_res.status_code == 200
    assert complete_res.json()["status"] == "work_completed"

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
        json={"status": "work_completed", "note": "Still done"},
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
        json={"status": "work_completed", "note": "Done"},
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
        json={"status": "work_completed", "note": "Done"},
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


def test_public_invoice_pay_online_requires_stripe_connect(monkeypatch):
    monkeypatch.setattr(settings, "stripe_secret_key", "sk_test_fake")
    monkeypatch.setattr(settings, "enable_stripe_invoice_checkout", True)
    suffix = uuid4().hex[:8]
    token = _bootstrap_and_login(
        tenant_slug=f"autokey-connect-{suffix}",
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
            "title": "Connect gate job",
            "key_quantity": 1,
            "priority": "normal",
            "status": "on_site",
            "programming_status": "pending",
            "deposit_cents": 0,
            "cost_cents": 6000,
        },
    )
    assert create_job_res.status_code == 201
    job_id = create_job_res.json()["id"]

    r = client.post(
        f"/v1/auto-key-jobs/{job_id}/status",
        headers=headers,
        json={"status": "work_completed", "note": "Done"},
    )
    assert r.status_code == 200

    with Session(engine) as s:
        row = s.exec(
            select(AutoKeyInvoice).where(AutoKeyInvoice.auto_key_job_id == UUID(job_id))
        ).first()
        assert row is not None
        tenant_id = row.tenant_id
        view_token = row.customer_view_token

    pub = client.get(f"/v1/public/auto-key-invoice/{view_token}")
    assert pub.status_code == 200
    assert pub.json().get("can_pay_online") is False

    co = client.post(f"/v1/public/auto-key-invoice/{view_token}/checkout")
    assert co.status_code == 503

    with Session(engine) as s:
        tenant = s.get(Tenant, tenant_id)
        assert tenant is not None
        tenant.stripe_connect_account_id = "acct_test_fake"
        tenant.stripe_connect_charges_enabled = True
        tenant.stripe_connect_payouts_enabled = True
        tenant.stripe_connect_details_submitted = True
        s.add(tenant)
        s.commit()

    pub2 = client.get(f"/v1/public/auto-key-invoice/{view_token}")
    assert pub2.status_code == 200
    assert pub2.json().get("can_pay_online") is True


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


def test_quote_suggestions_pricing_tier_applies_discount():
    suffix = uuid4().hex[:8]
    token = _bootstrap_and_login(
        tenant_slug=f"autokey-tier-{suffix}",
        email=f"owner-{suffix}@autokey.test",
        password="pass123456",
    )
    headers = {"Authorization": f"Bearer {token}"}

    retail = client.get(
        "/v1/auto-key-jobs/quote-suggestions",
        headers=headers,
        params={"job_type": "Diagnostic", "key_quantity": 1, "pricing_tier": "retail"},
    )
    assert retail.status_code == 200
    retail_json = retail.json()
    assert retail_json["pricing_tier"] == "retail"
    assert retail_json["subtotal_cents"] == 15900
    assert retail_json["tax_cents"] == 1590
    assert retail_json["total_cents"] == 17490

    b2b = client.get(
        "/v1/auto-key-jobs/quote-suggestions",
        headers=headers,
        params={"job_type": "Diagnostic", "key_quantity": 1, "pricing_tier": "b2b"},
    )
    assert b2b.status_code == 200
    b2b_json = b2b.json()
    assert b2b_json["pricing_tier"] == "b2b"
    assert b2b_json["subtotal_cents"] == 12720
    assert b2b_json["tax_cents"] == 1272
    assert b2b_json["total_cents"] == 13992


def test_quote_suggestions_rejects_unknown_pricing_tier():
    suffix = uuid4().hex[:8]
    token = _bootstrap_and_login(
        tenant_slug=f"autokey-tier-bad-{suffix}",
        email=f"owner-{suffix}@autokey.test",
        password="pass123456",
    )
    headers = {"Authorization": f"Bearer {token}"}
    bad = client.get(
        "/v1/auto-key-jobs/quote-suggestions",
        headers=headers,
        params={"job_type": "Diagnostic", "pricing_tier": "vip"},
    )
    assert bad.status_code == 422


def test_list_auto_key_jobs_active_only_filters_final_statuses():
    suffix = uuid4().hex[:8]
    token = _bootstrap_and_login(
        tenant_slug=f"autokey-active-{suffix}",
        email=f"owner-{suffix}@autokey.test",
        password="pass123456",
    )
    headers = {"Authorization": f"Bearer {token}"}
    customer_id = _create_customer(headers)

    active_res = client.post(
        "/v1/auto-key-jobs",
        headers=headers,
        json={
            "customer_id": customer_id,
            "title": "Active job",
            "key_quantity": 1,
            "priority": "normal",
            "status": "booked",
            "programming_status": "pending",
            "deposit_cents": 0,
            "cost_cents": 0,
        },
    )
    assert active_res.status_code == 201

    final_res = client.post(
        "/v1/auto-key-jobs",
        headers=headers,
        json={
            "customer_id": customer_id,
            "title": "Done job",
            "key_quantity": 1,
            "priority": "normal",
            "status": "work_completed",
            "programming_status": "pending",
            "deposit_cents": 0,
            "cost_cents": 0,
        },
    )
    assert final_res.status_code == 201

    all_jobs = client.get("/v1/auto-key-jobs", headers=headers)
    assert all_jobs.status_code == 200
    assert len(all_jobs.json()) == 2

    active_only = client.get("/v1/auto-key-jobs", headers=headers, params={"active_only": True})
    assert active_only.status_code == 200
    active_payload = active_only.json()
    assert len(active_payload) == 1
    assert active_payload[0]["title"] == "Active job"


def test_update_auto_key_invoice_can_mark_paid():
    suffix = uuid4().hex[:8]
    token = _bootstrap_and_login(
        tenant_slug=f"autokey-invupd-{suffix}",
        email=f"owner-{suffix}@autokey.test",
        password="pass123456",
    )
    headers = {"Authorization": f"Bearer {token}"}
    customer_id = _create_customer(headers)

    job_res = client.post(
        "/v1/auto-key-jobs",
        headers=headers,
        json={
            "customer_id": customer_id,
            "title": "Invoice update job",
            "key_quantity": 1,
            "priority": "normal",
            "status": "booked",
            "programming_status": "pending",
            "deposit_cents": 0,
            "cost_cents": 11000,
        },
    )
    assert job_res.status_code == 201
    job_id = job_res.json()["id"]

    complete = client.post(
        f"/v1/auto-key-jobs/{job_id}/status",
        headers=headers,
        json={"status": "work_completed", "note": "Done"},
    )
    assert complete.status_code == 200

    invoices = client.get(f"/v1/auto-key-jobs/{job_id}/invoices", headers=headers)
    assert invoices.status_code == 200
    invoice_id = invoices.json()[0]["id"]

    update = client.patch(
        f"/v1/auto-key-jobs/invoices/{invoice_id}",
        headers=headers,
        json={"status": "paid", "payment_method": "eftpos"},
    )
    assert update.status_code == 200
    data = update.json()
    assert data["status"] == "paid"
    assert data["payment_method"] == "eftpos"
    assert data["paid_at"] is not None
