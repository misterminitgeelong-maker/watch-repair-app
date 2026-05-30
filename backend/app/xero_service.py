"""Xero accounting integration for Mobile Services (Auto Key) invoices."""

from __future__ import annotations

import base64
import hashlib
import hmac
import logging
from datetime import date, datetime, timedelta, timezone
from typing import Any, Optional
from uuid import UUID

import httpx
from jose import JWTError, jwt
from sqlmodel import Session, select

from .config import settings
from .models import (
    AutoKeyInvoice,
    AutoKeyJob,
    AutoKeyQuote,
    AutoKeyQuoteLineItem,
    Customer,
    CustomerAccount,
    CustomerAccountInvoice,
    CustomerAccountInvoiceLine,
    Tenant,
)

_MONTH_NAMES = [
    "January", "February", "March", "April", "May", "June",
    "July", "August", "September", "October", "November", "December",
]

logger = logging.getLogger(__name__)

XERO_AUTHORIZE_URL = "https://login.xero.com/identity/connect/authorize"
XERO_TOKEN_URL = "https://identity.xero.com/connect/token"
XERO_CONNECTIONS_URL = "https://api.xero.com/connections"
XERO_API_BASE = "https://api.xero.com/api.xro/2.0"

XERO_OAUTH_SCOPES = "offline_access accounting.transactions accounting.contacts"


def xero_configured() -> bool:
    return bool(
        (settings.xero_client_id or "").strip()
        and (settings.xero_client_secret or "").strip()
        and (settings.xero_redirect_uri or "").strip()
    )


def _basic_auth_header() -> str:
    raw = f"{settings.xero_client_id}:{settings.xero_client_secret}".encode()
    return "Basic " + base64.b64encode(raw).decode()


def make_xero_oauth_state(tenant_id: UUID) -> str:
    return jwt.encode(
        {"tid": str(tenant_id), "purpose": "xero_oauth"},
        settings.jwt_secret,
        algorithm=settings.jwt_algorithm,
    )


def parse_xero_oauth_state(state: str) -> UUID:
    try:
        payload = jwt.decode(state, settings.jwt_secret, algorithms=[settings.jwt_algorithm])
    except JWTError as exc:
        raise ValueError("Invalid OAuth state") from exc
    if payload.get("purpose") != "xero_oauth":
        raise ValueError("Invalid OAuth state purpose")
    return UUID(str(payload["tid"]))


def build_xero_authorize_url(tenant_id: UUID) -> str:
    state = make_xero_oauth_state(tenant_id)
    params = {
        "response_type": "code",
        "client_id": settings.xero_client_id.strip(),
        "redirect_uri": settings.xero_redirect_uri.strip(),
        "scope": XERO_OAUTH_SCOPES,
        "state": state,
    }
    query = httpx.QueryParams(params)
    return f"{XERO_AUTHORIZE_URL}?{query}"


def exchange_xero_code(code: str) -> dict[str, Any]:
    with httpx.Client(timeout=30.0) as client:
        res = client.post(
            XERO_TOKEN_URL,
            headers={
                "Authorization": _basic_auth_header(),
                "Content-Type": "application/x-www-form-urlencoded",
            },
            data={
                "grant_type": "authorization_code",
                "code": code,
                "redirect_uri": settings.xero_redirect_uri.strip(),
            },
        )
    res.raise_for_status()
    return res.json()


def refresh_xero_tokens(tenant: Tenant) -> None:
    if not (tenant.xero_refresh_token or "").strip():
        raise ValueError("No Xero refresh token")
    with httpx.Client(timeout=30.0) as client:
        res = client.post(
            XERO_TOKEN_URL,
            headers={
                "Authorization": _basic_auth_header(),
                "Content-Type": "application/x-www-form-urlencoded",
            },
            data={
                "grant_type": "refresh_token",
                "refresh_token": tenant.xero_refresh_token.strip(),
            },
        )
    res.raise_for_status()
    data = res.json()
    tenant.xero_access_token = data.get("access_token")
    if data.get("refresh_token"):
        tenant.xero_refresh_token = data["refresh_token"]
    expires_in = int(data.get("expires_in") or 1800)
    tenant.xero_token_expires_at = datetime.now(timezone.utc) + timedelta(seconds=expires_in)
    tenant.xero_connection_status = "connected"


def _as_utc(dt: Optional[datetime]) -> Optional[datetime]:
    if dt is None:
        return None
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def _ensure_fresh_token(session: Session, tenant: Tenant) -> None:
    if not tenant.xero_access_token:
        raise ValueError("Xero is not connected")
    expires = _as_utc(tenant.xero_token_expires_at)
    if expires and expires > datetime.now(timezone.utc) + timedelta(seconds=60):
        return
    refresh_xero_tokens(tenant)
    session.add(tenant)
    session.commit()
    session.refresh(tenant)


def fetch_xero_connections(access_token: str) -> list[dict[str, Any]]:
    with httpx.Client(timeout=30.0) as client:
        res = client.get(
            XERO_CONNECTIONS_URL,
            headers={"Authorization": f"Bearer {access_token}", "Accept": "application/json"},
        )
    res.raise_for_status()
    return res.json()


def apply_xero_token_response(session: Session, tenant: Tenant, token_data: dict[str, Any]) -> None:
    access_token = token_data.get("access_token")
    if not access_token:
        raise ValueError("Xero token response missing access_token")
    tenant.xero_access_token = access_token
    if token_data.get("refresh_token"):
        tenant.xero_refresh_token = token_data["refresh_token"]
    expires_in = int(token_data.get("expires_in") or 1800)
    tenant.xero_token_expires_at = datetime.now(timezone.utc) + timedelta(seconds=expires_in)

    connections = fetch_xero_connections(access_token)
    if not connections:
        raise ValueError("No Xero organisations found for this account")
    conn = connections[0]
    tenant.xero_tenant_id = conn.get("tenantId") or conn.get("id")
    tenant.xero_connection_status = "connected"
    session.add(tenant)
    session.commit()
    session.refresh(tenant)


def disconnect_xero(session: Session, tenant: Tenant) -> None:
    tenant.xero_tenant_id = None
    tenant.xero_access_token = None
    tenant.xero_refresh_token = None
    tenant.xero_token_expires_at = None
    tenant.xero_connection_status = "disconnected"
    session.add(tenant)
    session.commit()


def verify_xero_webhook_signature(body: bytes, signature: str) -> bool:
    key = (settings.xero_webhook_key or "").strip()
    if not key or not signature:
        return False
    digest = hmac.new(key.encode(), body, hashlib.sha256).digest()
    computed = base64.b64encode(digest).decode()
    return hmac.compare_digest(computed, signature)


def _xero_headers(tenant: Tenant) -> dict[str, str]:
    org_id = (tenant.xero_tenant_id or "").strip()
    if not org_id:
        raise ValueError("Xero organisation id missing")
    return {
        "Authorization": f"Bearer {tenant.xero_access_token}",
        "xero-tenant-id": org_id,
        "Accept": "application/json",
        "Content-Type": "application/json",
    }


def _xero_request(
    session: Session,
    tenant: Tenant,
    method: str,
    path: str,
    *,
    json: Optional[dict] = None,
    params: Optional[dict] = None,
) -> dict[str, Any]:
    _ensure_fresh_token(session, tenant)
    url = f"{XERO_API_BASE}{path}"
    with httpx.Client(timeout=45.0) as client:
        res = client.request(method, url, headers=_xero_headers(tenant), json=json, params=params)
    if res.status_code == 401:
        refresh_xero_tokens(tenant)
        session.add(tenant)
        session.commit()
        session.refresh(tenant)
        with httpx.Client(timeout=45.0) as client:
            res = client.request(method, url, headers=_xero_headers(tenant), json=json, params=params)
    res.raise_for_status()
    if res.content:
        return res.json()
    return {}


def _cents_to_amount(cents: int) -> float:
    return round(int(cents) / 100.0, 2)


def _default_account_code(tenant: Tenant) -> str:
    return (tenant.xero_default_sales_account_code or "200").strip() or "200"


def _default_tax_type(tenant: Tenant, tax_cents: int) -> str:
    if (tenant.xero_default_tax_type or "").strip():
        return tenant.xero_default_tax_type.strip()
    return "OUTPUT" if tax_cents > 0 else "NONE"


def _contact_payload_for_job(session: Session, job: AutoKeyJob) -> dict[str, Any]:
    if job.customer_account_id:
        account = session.get(CustomerAccount, job.customer_account_id)
        if account:
            contact: dict[str, Any] = {"Name": account.name}
            if account.contact_email:
                contact["EmailAddress"] = account.contact_email
            if account.contact_phone:
                contact["Phones"] = [{"PhoneType": "DEFAULT", "PhoneNumber": account.contact_phone}]
            if account.billing_address:
                contact["Addresses"] = [
                    {"AddressType": "POBOX", "AddressLine1": account.billing_address[:500]}
                ]
            return contact
    customer = session.get(Customer, job.customer_id)
    if not customer:
        return {"Name": "Customer"}
    contact = {"Name": customer.full_name or "Customer"}
    if customer.email:
        contact["EmailAddress"] = customer.email
    if customer.phone:
        contact["Phones"] = [{"PhoneType": "DEFAULT", "PhoneNumber": customer.phone}]
    if customer.address:
        contact["Addresses"] = [{"AddressType": "STREET", "AddressLine1": customer.address[:500]}]
    return contact


def _find_or_create_contact(session: Session, tenant: Tenant, contact_payload: dict[str, Any]) -> str:
    name = (contact_payload.get("Name") or "").strip()
    if not name:
        raise ValueError("Contact name required")
    safe_name = name.replace('"', '\\"')
    where = f'Name=="{safe_name}"'
    search = _xero_request(session, tenant, "GET", "/Contacts", params={"where": where})
    contacts = search.get("Contacts") or []
    if contacts:
        contact_id = contacts[0].get("ContactID")
        if contact_id:
            return str(contact_id)
    created = _xero_request(
        session,
        tenant,
        "POST",
        "/Contacts",
        json={"Contacts": [contact_payload]},
    )
    new_contacts = created.get("Contacts") or []
    if not new_contacts or not new_contacts[0].get("ContactID"):
        raise ValueError("Failed to create Xero contact")
    return str(new_contacts[0]["ContactID"])


def _invoice_due_date(session: Session, job: AutoKeyJob) -> date:
    today = date.today()
    if job.customer_account_id:
        account = session.get(CustomerAccount, job.customer_account_id)
        if account and account.payment_terms_days:
            return today + timedelta(days=int(account.payment_terms_days))
    return today + timedelta(days=14)


def _line_items_for_invoice(
    session: Session,
    tenant: Tenant,
    invoice: AutoKeyInvoice,
) -> list[dict[str, Any]]:
    account_code = _default_account_code(tenant)
    tax_type = _default_tax_type(tenant, invoice.tax_cents)
    if invoice.auto_key_quote_id:
        rows = session.exec(
            select(AutoKeyQuoteLineItem)
            .where(AutoKeyQuoteLineItem.auto_key_quote_id == invoice.auto_key_quote_id)
            .order_by(AutoKeyQuoteLineItem.created_at)
        ).all()
        if rows:
            return [
                {
                    "Description": li.description[:4000],
                    "Quantity": float(li.quantity),
                    "UnitAmount": _cents_to_amount(li.unit_price_cents),
                    "AccountCode": account_code,
                    "TaxType": tax_type,
                }
                for li in rows
            ]
    description = f"Mobile Services invoice {invoice.invoice_number}"
    return [
        {
            "Description": description,
            "Quantity": 1.0,
            "UnitAmount": _cents_to_amount(invoice.subtotal_cents or invoice.total_cents),
            "AccountCode": account_code,
            "TaxType": tax_type,
        }
    ]


def sync_auto_key_invoice_to_xero(session: Session, invoice: AutoKeyInvoice, tenant: Tenant) -> None:
    """Push invoice to Xero; never raises — sets sync fields on invoice."""
    if not xero_configured():
        invoice.xero_sync_status = "skipped"
        invoice.xero_sync_error = "Xero is not configured on this server"
        session.add(invoice)
        return
    if (tenant.xero_connection_status or "") != "connected" or not tenant.xero_access_token:
        invoice.xero_sync_status = "pending"
        invoice.xero_sync_error = "Xero is not connected for this workspace"
        session.add(invoice)
        return
    if (invoice.xero_sync_status or "") == "synced" and invoice.xero_invoice_id:
        return

    invoice.xero_sync_status = "pending"
    invoice.xero_sync_error = None
    session.add(invoice)
    session.flush()

    try:
        job = session.get(AutoKeyJob, invoice.auto_key_job_id)
        if not job:
            raise ValueError("Auto key job not found")

        contact_id = _find_or_create_contact(
            session, tenant, _contact_payload_for_job(session, job)
        )
        currency = (invoice.currency or tenant.default_currency or "AUD").strip().upper()
        line_items = _line_items_for_invoice(session, tenant, invoice)
        due = _invoice_due_date(session, job)
        today = date.today()

        payload = {
            "Invoices": [
                {
                    "Type": "ACCREC",
                    "Status": "AUTHORISED",
                    "Contact": {"ContactID": contact_id},
                    "Date": today.isoformat(),
                    "DueDate": due.isoformat(),
                    "CurrencyCode": currency,
                    "InvoiceNumber": invoice.invoice_number[:50],
                    "Reference": f"Mainspring job {job.job_number}"[:255],
                    "LineItems": line_items,
                }
            ]
        }

        result = _xero_request(session, tenant, "POST", "/Invoices", json=payload)
        xero_invoices = result.get("Invoices") or []
        if not xero_invoices:
            raise ValueError("Xero did not return an invoice")
        xero_inv = xero_invoices[0]
        xero_id = xero_inv.get("InvoiceID")
        if not xero_id:
            raise ValueError("Xero invoice missing InvoiceID")

        invoice.xero_invoice_id = str(xero_id)
        invoice.xero_sync_status = "synced"
        invoice.xero_sync_error = None
        invoice.xero_synced_at = datetime.now(timezone.utc)
        tenant.xero_connection_status = "connected"
        session.add(tenant)
        session.add(invoice)
        logger.info(
            "xero_invoice.synced tenant=%s invoice=%s xero_id=%s",
            tenant.id,
            invoice.id,
            xero_id,
        )
    except Exception as exc:
        logger.exception("xero_invoice.sync_failed invoice=%s", invoice.id)
        invoice.xero_sync_status = "failed"
        invoice.xero_sync_error = str(exc)[:2000]
        session.add(invoice)


def _contact_payload_for_account(account: CustomerAccount) -> dict[str, Any]:
    contact: dict[str, Any] = {"Name": account.name or "Customer account"}
    email = (account.contact_email or "").strip()
    if email:
        contact["EmailAddress"] = email
    phone = (account.contact_phone or account.primary_contact_phone or "").strip()
    if phone:
        contact["Phones"] = [{"PhoneType": "DEFAULT", "PhoneNumber": phone}]
    if (account.billing_address or "").strip():
        contact["Addresses"] = [
            {"AddressType": "POBOX", "AddressLine1": account.billing_address[:500]}
        ]
    return contact


def sync_customer_account_invoice_to_xero(
    session: Session, invoice: CustomerAccountInvoice, tenant: Tenant
) -> None:
    """Push ONE aggregated B2B statement invoice to Xero (a line per job).

    Never raises — records sync status on the invoice instead.
    """
    if not xero_configured():
        invoice.xero_sync_status = "skipped"
        invoice.xero_sync_error = "Xero is not configured on this server"
        session.add(invoice)
        return
    if (tenant.xero_connection_status or "") != "connected" or not tenant.xero_access_token:
        invoice.xero_sync_status = "pending"
        invoice.xero_sync_error = "Xero is not connected for this workspace"
        session.add(invoice)
        return
    if (invoice.xero_sync_status or "") == "synced" and invoice.xero_invoice_id:
        return

    invoice.xero_sync_status = "pending"
    invoice.xero_sync_error = None
    session.add(invoice)
    session.flush()

    try:
        account = session.get(CustomerAccount, invoice.customer_account_id)
        if not account:
            raise ValueError("Customer account not found")

        line_rows = session.exec(
            select(CustomerAccountInvoiceLine)
            .where(CustomerAccountInvoiceLine.tenant_id == invoice.tenant_id)
            .where(CustomerAccountInvoiceLine.customer_account_invoice_id == invoice.id)
            .order_by(CustomerAccountInvoiceLine.created_at)
        ).all()
        if not line_rows:
            raise ValueError("Statement invoice has no line items")

        contact_id = _find_or_create_contact(
            session, tenant, _contact_payload_for_account(account)
        )
        account_code = _default_account_code(tenant)
        currency = (invoice.currency or tenant.default_currency or "AUD").strip().upper()

        # One Xero line per job; amounts are taken as-is (tax handled separately below)
        # so the Xero invoice total matches the local statement total exactly.
        line_items: list[dict[str, Any]] = [
            {
                "Description": f"{li.job_number} — {li.description}"[:4000],
                "Quantity": 1.0,
                "UnitAmount": _cents_to_amount(li.amount_cents),
                "AccountCode": account_code,
                "TaxType": "NONE",
            }
            for li in line_rows
        ]
        if invoice.tax_cents > 0:
            line_items.append(
                {
                    "Description": "GST",
                    "Quantity": 1.0,
                    "UnitAmount": _cents_to_amount(invoice.tax_cents),
                    "AccountCode": account_code,
                    "TaxType": "NONE",
                }
            )

        today = date.today()
        terms = int(account.payment_terms_days or 0)
        due = today + timedelta(days=terms if terms > 0 else 14)
        month_name = _MONTH_NAMES[invoice.period_month - 1] if 1 <= invoice.period_month <= 12 else str(invoice.period_month)

        payload = {
            "Invoices": [
                {
                    "Type": "ACCREC",
                    "Status": "AUTHORISED",
                    "Contact": {"ContactID": contact_id},
                    "Date": today.isoformat(),
                    "DueDate": due.isoformat(),
                    "CurrencyCode": currency,
                    "LineAmountTypes": "Exclusive",
                    "InvoiceNumber": invoice.invoice_number[:50],
                    "Reference": f"Statement {month_name} {invoice.period_year}"[:255],
                    "LineItems": line_items,
                }
            ]
        }

        result = _xero_request(session, tenant, "POST", "/Invoices", json=payload)
        xero_invoices = result.get("Invoices") or []
        if not xero_invoices:
            raise ValueError("Xero did not return an invoice")
        xero_id = xero_invoices[0].get("InvoiceID")
        if not xero_id:
            raise ValueError("Xero invoice missing InvoiceID")

        invoice.xero_invoice_id = str(xero_id)
        invoice.xero_sync_status = "synced"
        invoice.xero_sync_error = None
        invoice.xero_synced_at = datetime.now(timezone.utc)
        tenant.xero_connection_status = "connected"
        session.add(tenant)
        session.add(invoice)
        logger.info(
            "xero_b2b_invoice.synced tenant=%s invoice=%s xero_id=%s lines=%s",
            tenant.id,
            invoice.id,
            xero_id,
            len(line_rows),
        )
    except Exception as exc:
        logger.exception("xero_b2b_invoice.sync_failed invoice=%s", invoice.id)
        invoice.xero_sync_status = "failed"
        invoice.xero_sync_error = str(exc)[:2000]
        session.add(invoice)


def fetch_xero_invoice_status(session: Session, tenant: Tenant, xero_invoice_id: str) -> Optional[str]:
    data = _xero_request(session, tenant, "GET", f"/Invoices/{xero_invoice_id}")
    invoices = data.get("Invoices") or []
    if not invoices:
        return None
    return (invoices[0].get("Status") or "").upper()


def mark_auto_key_invoice_paid_from_xero(session: Session, invoice: AutoKeyInvoice) -> bool:
    if invoice.status == "paid":
        return False
    invoice.status = "paid"
    invoice.payment_method = invoice.payment_method or "bank"
    invoice.paid_at = datetime.now(timezone.utc)
    session.add(invoice)
    job = session.get(AutoKeyJob, invoice.auto_key_job_id)
    if job and job.status != "invoice_paid":
        job.status = "invoice_paid"
        session.add(job)
    return True


def sync_auto_key_invoice_after_create(session: Session, invoice: AutoKeyInvoice) -> None:
    """Best-effort Xero push after local invoice create; never raises."""
    tenant = session.get(Tenant, invoice.tenant_id)
    if not tenant:
        return
    try:
        sync_auto_key_invoice_to_xero(session, invoice, tenant)
        session.commit()
        session.refresh(invoice)
    except Exception:
        logger.exception("xero_invoice.post_create_sync_failed invoice=%s", invoice.id)


def mark_auto_key_invoice_voided_from_xero(session: Session, invoice: AutoKeyInvoice) -> bool:
    if invoice.status == "void":
        return False
    if invoice.status == "paid":
        return False
    invoice.status = "void"
    session.add(invoice)
    return True
