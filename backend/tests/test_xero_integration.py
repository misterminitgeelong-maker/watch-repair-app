"""Xero integration tests with mocked HTTP."""

import base64
import hashlib
import hmac
import json
import os
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import MagicMock, patch
from uuid import UUID, uuid4

import pytest

_TEST_DB = Path(__file__).with_name(f"test_xero_{uuid4().hex}.db")
os.environ["DATABASE_URL"] = f"sqlite:///{_TEST_DB.as_posix()}"

from fastapi.testclient import TestClient
from sqlmodel import Session, select

from app.config import settings
from app.database import create_db_and_tables, engine
from app.main import app
from app.models import AutoKeyInvoice, Tenant

create_db_and_tables()
client = TestClient(app)


def _bootstrap_and_login(tenant_slug: str, email: str, password: str) -> str:
    bootstrap_res = client.post(
        "/v1/auth/bootstrap",
        json={
            "tenant_name": f"Tenant {tenant_slug}",
            "tenant_slug": tenant_slug,
            "owner_email": email,
            "owner_full_name": "Owner",
            "owner_password": password,
            "plan_code": "enterprise",
        },
    )
    assert bootstrap_res.status_code == 200
    login_res = client.post(
        "/v1/auth/login",
        json={"tenant_slug": tenant_slug, "email": email, "password": password},
    )
    assert login_res.status_code == 200
    return login_res.json()["access_token"]


def _xero_signature(body: bytes) -> str:
    digest = hmac.new(settings.xero_webhook_key.encode(), body, hashlib.sha256).digest()
    return base64.b64encode(digest).decode()


@pytest.fixture(autouse=True)
def _xero_env(monkeypatch):
    monkeypatch.setattr(settings, "xero_client_id", "test-client-id")
    monkeypatch.setattr(settings, "xero_client_secret", "test-client-secret")
    monkeypatch.setattr(settings, "xero_redirect_uri", "http://test/v1/billing/xero/callback")
    monkeypatch.setattr(settings, "xero_webhook_key", "test-webhook-key")


def test_sync_auto_key_invoice_to_xero_creates_invoice(monkeypatch):
    suffix = uuid4().hex[:8]
    token = _bootstrap_and_login(f"xero-{suffix}", f"owner-{suffix}@xero.test", "pass123456")
    headers = {"Authorization": f"Bearer {token}"}

    with Session(engine) as session:
        from app.security import decode_access_token

        claims = decode_access_token(token)
        tenant = session.get(Tenant, claims.tenant_id)
        assert tenant
        tenant.xero_connection_status = "connected"
        tenant.xero_tenant_id = "xero-org-123"
        tenant.xero_access_token = "access-token"
        tenant.xero_refresh_token = "refresh-token"
        tenant.xero_token_expires_at = datetime.now(timezone.utc) + timedelta(hours=2)
        session.add(tenant)
        session.commit()

    customer_res = client.post(
        "/v1/customers",
        headers=headers,
        json={"full_name": "Xero Customer", "phone": "0400111222", "email": "xero@test.com"},
    )
    assert customer_res.status_code == 201
    customer_id = customer_res.json()["id"]

    job_res = client.post(
        "/v1/auto-key-jobs",
        headers=headers,
        json={
            "customer_id": customer_id,
            "title": "Spare key",
            "key_quantity": 1,
            "priority": "normal",
            "status": "awaiting_quote",
            "programming_status": "pending",
            "deposit_cents": 0,
            "cost_cents": 0,
        },
    )
    assert job_res.status_code == 201
    job_id = job_res.json()["id"]

    quote_res = client.post(
        f"/v1/auto-key-jobs/{job_id}/quotes",
        headers=headers,
        json={
            "line_items": [{"description": "Key cut", "quantity": 1, "unit_price_cents": 10000}],
            "tax_cents": 1000,
        },
    )
    assert quote_res.status_code == 201
    quote_id = quote_res.json()["id"]

    xero_invoice_id = "11111111-2222-3333-4444-555555555555"

    def _ok_json(data):
        resp = MagicMock()
        resp.status_code = 200
        resp.content = b"{}"
        resp.json = lambda: data
        resp.raise_for_status = MagicMock()
        return resp

    def fake_request(method, url, **kwargs):
        if url.endswith("/Contacts") and method == "GET":
            return _ok_json({"Contacts": []})
        if url.endswith("/Contacts") and method == "POST":
            return _ok_json({"Contacts": [{"ContactID": "contact-abc", "Name": "Xero Customer"}]})
        if url.endswith("/Invoices") and method == "POST":
            return _ok_json(
                {"Invoices": [{"InvoiceID": xero_invoice_id, "InvoiceNumber": "AK-1", "Status": "AUTHORISED"}]}
            )
        return _ok_json({})

    def fake_post(url, **kwargs):
        if "connect/token" in url:
            return _ok_json({"access_token": "access-token", "refresh_token": "refresh-token", "expires_in": 3600})
        return _ok_json({})

    mock_client = MagicMock()
    mock_client.__enter__ = lambda s: mock_client
    mock_client.__exit__ = MagicMock(return_value=False)
    mock_client.request = fake_request
    mock_client.post = fake_post
    mock_client.get = lambda url, **kwargs: _ok_json([])

    with patch("app.xero_service.httpx.Client", return_value=mock_client):
        inv_res = client.post(
            f"/v1/auto-key-jobs/{job_id}/invoices/from-quote/{quote_id}",
            headers=headers,
        )

    assert inv_res.status_code == 201
    body = inv_res.json()
    assert body["xero_sync_status"] == "synced"
    assert body["xero_invoice_id"] == xero_invoice_id

    with Session(engine) as session:
        invoice = session.get(AutoKeyInvoice, UUID(body["id"]))
        assert invoice
        assert invoice.xero_sync_status == "synced"
        assert invoice.xero_invoice_id == xero_invoice_id


def test_sync_customer_account_invoice_aggregates_jobs(monkeypatch):
    suffix = uuid4().hex[:8]
    token = _bootstrap_and_login(f"xero-b2b-{suffix}", f"b2b-{suffix}@xero.test", "pass123456")
    headers = {"Authorization": f"Bearer {token}"}

    with Session(engine) as session:
        from app.security import decode_access_token

        claims = decode_access_token(token)
        tenant = session.get(Tenant, claims.tenant_id)
        assert tenant
        tenant.xero_connection_status = "connected"
        tenant.xero_tenant_id = "xero-org-b2b"
        tenant.xero_access_token = "access-token"
        tenant.xero_refresh_token = "refresh-token"
        tenant.xero_token_expires_at = datetime.now(timezone.utc) + timedelta(hours=2)
        session.add(tenant)
        session.commit()

    customer_res = client.post(
        "/v1/customers",
        headers=headers,
        json={"full_name": "Fleet Customer", "phone": "0400999888"},
    )
    assert customer_res.status_code == 201
    customer_id = customer_res.json()["id"]

    account_res = client.post(
        "/v1/customer-accounts",
        headers=headers,
        json={"name": "Fleet Group", "contact_email": "ap@fleet.test", "payment_terms_days": 30},
    )
    assert account_res.status_code == 201
    account_id = account_res.json()["id"]

    link_res = client.post(
        f"/v1/customer-accounts/{account_id}/customers",
        headers=headers,
        json={"customer_id": customer_id},
    )
    assert link_res.status_code == 200

    created_at = None
    for title, cost in (("Fleet job A", 15000), ("Fleet job B", 22000)):
        job_res = client.post(
            "/v1/auto-key-jobs",
            headers=headers,
            json={
                "customer_id": customer_id,
                "customer_account_id": account_id,
                "title": title,
                "key_quantity": 1,
                "priority": "normal",
                "status": "completed",
                "programming_status": "programmed",
                "deposit_cents": 0,
                "cost_cents": cost,
            },
        )
        assert job_res.status_code == 201, job_res.text
        created_at = job_res.json()["created_at"]

    period_year = int(created_at[0:4])
    period_month = int(created_at[5:7])

    invoice_res = client.post(
        f"/v1/customer-accounts/{account_id}/invoices/monthly",
        headers=headers,
        json={"period_year": period_year, "period_month": period_month, "tax_cents": 3700},
    )
    assert invoice_res.status_code == 201, invoice_res.text
    invoice = invoice_res.json()
    invoice_id = invoice["id"]
    assert invoice["subtotal_cents"] == 37000
    assert len(invoice["lines"]) == 2

    captured: dict = {}

    def _ok_json(data):
        resp = MagicMock()
        resp.status_code = 200
        resp.content = b"{}"
        resp.json = lambda: data
        resp.raise_for_status = MagicMock()
        return resp

    xero_invoice_id = "99999999-8888-7777-6666-555555555555"

    def fake_request(method, url, **kwargs):
        if url.endswith("/Contacts") and method == "GET":
            return _ok_json({"Contacts": []})
        if url.endswith("/Contacts") and method == "POST":
            return _ok_json({"Contacts": [{"ContactID": "contact-fleet", "Name": "Fleet Group"}]})
        if url.endswith("/Invoices") and method == "POST":
            captured["payload"] = kwargs.get("json")
            return _ok_json(
                {"Invoices": [{"InvoiceID": xero_invoice_id, "InvoiceNumber": "B2B-1", "Status": "AUTHORISED"}]}
            )
        return _ok_json({})

    def fake_post(url, **kwargs):
        if "connect/token" in url:
            return _ok_json({"access_token": "access-token", "refresh_token": "refresh-token", "expires_in": 3600})
        return _ok_json({})

    mock_client = MagicMock()
    mock_client.__enter__ = lambda s: mock_client
    mock_client.__exit__ = MagicMock(return_value=False)
    mock_client.request = fake_request
    mock_client.post = fake_post
    mock_client.get = lambda url, **kwargs: _ok_json([])

    with patch("app.xero_service.httpx.Client", return_value=mock_client):
        sync_res = client.post(
            f"/v1/customer-accounts/{account_id}/invoices/{invoice_id}/sync-xero",
            headers=headers,
        )

    assert sync_res.status_code == 200, sync_res.text
    body = sync_res.json()
    assert body["xero_sync_status"] == "synced"
    assert body["xero_invoice_id"] == xero_invoice_id

    # ONE Xero invoice, one line per job + a GST line.
    sent_invoices = captured["payload"]["Invoices"]
    assert len(sent_invoices) == 1
    line_items = sent_invoices[0]["LineItems"]
    assert len(line_items) == 3  # 2 jobs + GST
    amounts = sorted(li["UnitAmount"] for li in line_items)
    assert amounts == [37.0, 150.0, 220.0]


def test_xero_webhook_marks_invoice_paid(monkeypatch):
    suffix = uuid4().hex[:8]
    token = _bootstrap_and_login(f"xero-wh-{suffix}", f"wh-{suffix}@xero.test", "pass123456")
    headers = {"Authorization": f"Bearer {token}"}

    xero_org = "org-webhook-999"
    xero_inv_id = "aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee"

    def _ok_json(data):
        resp = MagicMock()
        resp.status_code = 200
        resp.content = b"{}"
        resp.json = lambda: data
        resp.raise_for_status = MagicMock()
        return resp

    def fake_request(method, url, **kwargs):
        if "/Invoices/" in url and method == "GET":
            return _ok_json({"Invoices": [{"InvoiceID": xero_inv_id, "Status": "PAID"}]})
        if url.endswith("/Contacts") and method == "GET":
            return _ok_json({"Contacts": [{"ContactID": "c1", "Name": "Webhook Customer"}]})
        if url.endswith("/Invoices") and method == "POST":
            return _ok_json({"Invoices": [{"InvoiceID": xero_inv_id, "Status": "AUTHORISED"}]})
        return _ok_json({})

    def fake_post(url, **kwargs):
        if "connect/token" in url:
            return _ok_json({"access_token": "access", "refresh_token": "refresh", "expires_in": 3600})
        if url.endswith("/Contacts"):
            return _ok_json({"Contacts": [{"ContactID": "c1", "Name": "Webhook Customer"}]})
        return _ok_json({})

    mock_client = MagicMock()
    mock_client.__enter__ = lambda s: mock_client
    mock_client.__exit__ = MagicMock(return_value=False)
    mock_client.request = fake_request
    mock_client.post = fake_post

    with patch("app.xero_service.httpx.Client", return_value=mock_client):
        with Session(engine) as session:
            from app.security import decode_access_token

            claims = decode_access_token(token)
            tenant = session.get(Tenant, claims.tenant_id)
            tenant.xero_connection_status = "connected"
            tenant.xero_tenant_id = xero_org
            tenant.xero_access_token = "access"
            tenant.xero_refresh_token = "refresh"
            tenant.xero_token_expires_at = datetime.now(timezone.utc) + timedelta(hours=2)
            session.add(tenant)
            session.commit()

        customer_res = client.post(
            "/v1/customers",
            headers=headers,
            json={"full_name": "Webhook Customer", "phone": "0400333444"},
        )
        assert customer_res.status_code == 201
        job_res = client.post(
            "/v1/auto-key-jobs",
            headers=headers,
            json={
                "customer_id": customer_res.json()["id"],
                "title": "Job",
                "key_quantity": 1,
                "priority": "normal",
                "status": "awaiting_quote",
                "programming_status": "pending",
                "deposit_cents": 0,
                "cost_cents": 11000,
            },
        )
        assert job_res.status_code == 201
        job_id = job_res.json()["id"]

        quote_res = client.post(
            f"/v1/auto-key-jobs/{job_id}/quotes",
            headers=headers,
            json={
                "line_items": [{"description": "Service", "quantity": 1, "unit_price_cents": 10000}],
                "tax_cents": 1000,
            },
        )
        assert quote_res.status_code == 201
        inv_res = client.post(
            f"/v1/auto-key-jobs/{job_id}/invoices/from-quote/{quote_res.json()['id']}",
            headers=headers,
        )
        assert inv_res.status_code == 201
        invoice_id = inv_res.json()["id"]

        with Session(engine) as session:
            invoice = session.get(AutoKeyInvoice, UUID(invoice_id))
            assert invoice
            invoice.xero_invoice_id = xero_inv_id
            invoice.xero_sync_status = "synced"
            invoice.status = "unpaid"
            session.add(invoice)
            session.commit()

        webhook_body = {
            "events": [
                {
                    "eventCategory": "INVOICE",
                    "eventType": "UPDATE",
                    "resourceId": xero_inv_id,
                    "tenantId": xero_org,
                }
            ]
        }
        raw = json.dumps(webhook_body).encode()
        wh_res = client.post(
            "/v1/webhooks/xero",
            content=raw,
            headers={"x-xero-signature": _xero_signature(raw), "Content-Type": "application/json"},
        )
        assert wh_res.status_code == 200

        with Session(engine) as session:
            invoice = session.get(AutoKeyInvoice, UUID(invoice_id))
            assert invoice.status == "paid"
            assert invoice.payment_method == "bank"
            assert invoice.paid_at is not None
