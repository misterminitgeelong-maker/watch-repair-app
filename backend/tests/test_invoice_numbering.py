import os
from pathlib import Path
from uuid import UUID, uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.exc import IntegrityError
from sqlmodel import Session

_TEST_DB = Path(__file__).with_name(f"test_invoice_numbering_{uuid4().hex}.db")
os.environ["DATABASE_URL"] = f"sqlite:///{_TEST_DB.as_posix()}"
os.environ.setdefault("JWT_SECRET", "test-secret-not-for-production")
os.environ.setdefault("APP_ENV", "test")

from app.database import create_db_and_tables, engine
from app.main import app
from app.models import Invoice

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
    login_res = client.post(
        "/v1/auth/login",
        json={"tenant_slug": tenant_slug, "email": email, "password": password},
    )
    assert login_res.status_code == 200
    return login_res.json()["access_token"]


def _create_watch(headers: dict[str, str]) -> str:
    customer = client.post(
        "/v1/customers",
        headers=headers,
        json={"full_name": "Invoice Customer", "email": "invoice@example.com"},
    )
    assert customer.status_code == 201
    customer_id = customer.json()["id"]
    watch = client.post(
        "/v1/watches",
        headers=headers,
        json={"customer_id": customer_id, "brand": "Omega", "model": "Speedmaster"},
    )
    assert watch.status_code == 201
    return watch.json()["id"]


def _create_approved_quote(headers: dict[str, str], watch_id: str) -> str:
    job = client.post(
        "/v1/repair-jobs",
        headers=headers,
        json={"watch_id": watch_id, "title": "Invoice Numbering Job", "priority": "normal"},
    )
    assert job.status_code == 201
    job_id = job.json()["id"]

    quote = client.post(
        "/v1/quotes",
        headers=headers,
        json={
            "repair_job_id": job_id,
            "tax_cents": 0,
            "line_items": [
                {"item_type": "labor", "description": "Service", "quantity": 1, "unit_price_cents": 10000}
            ],
        },
    )
    assert quote.status_code == 201
    quote_id = quote.json()["id"]

    sent = client.post(f"/v1/quotes/{quote_id}/send", headers=headers)
    assert sent.status_code == 200
    approval_token = sent.json()["approval_token"]

    approved = client.post(
        f"/v1/public/quotes/{approval_token}/decision",
        json={"decision": "approved"},
    )
    assert approved.status_code == 200
    return quote_id


def _create_invoice_from_quote(headers: dict[str, str], quote_id: str) -> dict:
    res = client.post(f"/v1/invoices/from-quote/{quote_id}", headers=headers)
    assert res.status_code == 201
    return res.json()["invoice"]


def test_first_invoice_in_tenant_starts_at_one():
    suffix = uuid4().hex[:8]
    token = _bootstrap_and_login(f"inv-num-first-{suffix}", f"owner-{suffix}@inv.test", "pass123456")
    headers = {"Authorization": f"Bearer {token}"}
    watch_id = _create_watch(headers)
    quote_id = _create_approved_quote(headers, watch_id)

    invoice = _create_invoice_from_quote(headers, quote_id)
    assert invoice["invoice_number"] == "INV-00001"


def test_multiple_invoices_increment_for_same_tenant():
    suffix = uuid4().hex[:8]
    token = _bootstrap_and_login(f"inv-num-multi-{suffix}", f"owner-{suffix}@inv.test", "pass123456")
    headers = {"Authorization": f"Bearer {token}"}
    watch_id = _create_watch(headers)

    inv1 = _create_invoice_from_quote(headers, _create_approved_quote(headers, watch_id))
    inv2 = _create_invoice_from_quote(headers, _create_approved_quote(headers, watch_id))
    inv3 = _create_invoice_from_quote(headers, _create_approved_quote(headers, watch_id))

    assert inv1["invoice_number"] == "INV-00001"
    assert inv2["invoice_number"] == "INV-00002"
    assert inv3["invoice_number"] == "INV-00003"


def test_different_tenants_have_independent_invoice_sequences():
    suffix_a = uuid4().hex[:8]
    suffix_b = uuid4().hex[:8]
    token_a = _bootstrap_and_login(f"inv-num-a-{suffix_a}", f"owner-{suffix_a}@inv.test", "pass123456")
    token_b = _bootstrap_and_login(f"inv-num-b-{suffix_b}", f"owner-{suffix_b}@inv.test", "pass123456")
    headers_a = {"Authorization": f"Bearer {token_a}"}
    headers_b = {"Authorization": f"Bearer {token_b}"}

    quote_a1 = _create_approved_quote(headers_a, _create_watch(headers_a))
    quote_b1 = _create_approved_quote(headers_b, _create_watch(headers_b))
    quote_a2 = _create_approved_quote(headers_a, _create_watch(headers_a))

    inv_a1 = _create_invoice_from_quote(headers_a, quote_a1)
    inv_b1 = _create_invoice_from_quote(headers_b, quote_b1)
    inv_a2 = _create_invoice_from_quote(headers_a, quote_a2)

    assert inv_a1["invoice_number"] == "INV-00001"
    assert inv_b1["invoice_number"] == "INV-00001"
    assert inv_a2["invoice_number"] == "INV-00002"


def test_invoice_number_not_derived_from_row_count_after_delete():
    suffix = uuid4().hex[:8]
    token = _bootstrap_and_login(f"inv-num-gap-{suffix}", f"owner-{suffix}@inv.test", "pass123456")
    headers = {"Authorization": f"Bearer {token}"}
    watch_id = _create_watch(headers)

    inv1 = _create_invoice_from_quote(headers, _create_approved_quote(headers, watch_id))
    inv2 = _create_invoice_from_quote(headers, _create_approved_quote(headers, watch_id))
    assert inv1["invoice_number"] == "INV-00001"
    assert inv2["invoice_number"] == "INV-00002"

    with Session(engine) as session:
        second = session.get(Invoice, UUID(inv2["id"]))
        assert second is not None
        session.delete(second)
        session.commit()

    inv3 = _create_invoice_from_quote(headers, _create_approved_quote(headers, watch_id))
    assert inv3["invoice_number"] == "INV-00003"


def test_invoice_number_uniqueness_protection():
    suffix = uuid4().hex[:8]
    token = _bootstrap_and_login(f"inv-num-uniq-{suffix}", f"owner-{suffix}@inv.test", "pass123456")
    headers = {"Authorization": f"Bearer {token}"}
    watch_id = _create_watch(headers)
    created = _create_invoice_from_quote(headers, _create_approved_quote(headers, watch_id))

    with Session(engine) as session:
        duplicate = Invoice(
            tenant_id=UUID(created["tenant_id"]),
            repair_job_id=UUID(created["repair_job_id"]),
            quote_id=None,
            invoice_number=created["invoice_number"],
            subtotal_cents=100,
            tax_cents=0,
            total_cents=100,
            currency="USD",
        )
        session.add(duplicate)
        with pytest.raises(IntegrityError):
            session.commit()
