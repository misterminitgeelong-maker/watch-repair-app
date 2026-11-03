"""Bundled monthly Minit-style HQ invoice: preview, issue, Stripe collection.

Platform admins name the network with ``parent_account_id``; an HQ owner/admin
always gets their own network (read only). Routing / Prospecting add-ons come
from the HQ's saved billing settings; the preview endpoints can override them
with query flags. Only a platform admin can issue or void an invoice. Issuing
freezes the numbers in ``HqInvoice`` and asks Stripe to email a pay-by-link
invoice (card or bank), so nothing is charged without the HQ paying it.
"""
from __future__ import annotations

import json
import logging
from datetime import datetime, timedelta, timezone
from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import Response
from pydantic import BaseModel, Field
from sqlmodel import Session, select

from ..config import settings
from ..database import unscoped_session
from ..dependencies import AuthContext, get_auth_context, require_platform_admin
from ..hq_invoice_pdf import build_hq_invoice_pdf
from ..minit_billing import (
    InvoiceSummary,
    SiteForBilling,
    compute_invoice,
    parse_month,
    summary_to_csv,
    summary_to_dict,
)
from ..models import HqInvoice, HqSettings, ParentAccount, ParentAccountSite, Tenant, User
from ..parent_network import parents_for_user, require_parent_role
from ..regions import is_nz_minit_placement

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/v1/hq-billing", tags=["hq-billing"])

PAYMENT_TERMS_DAYS = 14


def _resolve_parent(session: Session, auth: AuthContext, parent_account_id: UUID | None) -> ParentAccount:
    if auth.role == "platform_admin":
        if parent_account_id is None:
            raise HTTPException(status_code=422, detail="parent_account_id is required for platform admins")
        parent = session.get(ParentAccount, parent_account_id)
        if not parent:
            raise HTTPException(status_code=404, detail="Parent account not found")
        return parent
    if auth.role != "owner" or auth.support_actor_user_id is not None:
        raise HTTPException(status_code=403, detail="Owner access required")
    user = session.get(User, auth.user_id)
    if not user or not user.is_active:
        raise HTTPException(status_code=401, detail="Invalid token")
    parents = parents_for_user(session, user)
    if not parents:
        raise HTTPException(status_code=403, detail="No access to a parent account")
    parent = parents[0]
    if parent_account_id is not None and parent_account_id != parent.id:
        raise HTTPException(status_code=403, detail="No access to this parent account")
    require_parent_role(session, parent, user, write=True)  # HQ admin only
    return parent


def build_summary(
    session: Session, parent: ParentAccount, month: str | None, routing: bool | None, prospecting: bool | None
) -> InvoiceSummary:
    """``routing`` / ``prospecting`` of None mean "use the HQ's saved setting"."""
    if routing is None:
        routing = bool(parent.billing_routing_addon)
    if prospecting is None:
        prospecting = bool(parent.billing_prospecting_addon)
    try:
        billing_month = parse_month(month) if month else datetime.now(timezone.utc).date().replace(day=1)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc))
    rows = session.exec(
        select(ParentAccountSite, Tenant)
        .join(Tenant, Tenant.id == ParentAccountSite.tenant_id)
        .where(ParentAccountSite.parent_account_id == parent.id)
    ).all()
    sites = [
        SiteForBilling(
            tenant_id=str(t.id),
            name=t.name,
            network_role=s.network_role,
            is_active=bool(t.is_active),
            billing_exempt=bool(t.billing_exempt),
            shop_number=t.shop_number,
            is_nz=is_nz_minit_placement(t.minit_region, t.minit_area)
            or (t.default_currency or "").strip().upper() == "NZD",
        )
        for s, t in rows
    ]
    return compute_invoice(sites, billing_month, routing=routing, prospecting=prospecting)


@router.get("/monthly-summary")
def monthly_summary(
    month: str | None = Query(default=None, description="YYYY-MM, default current month"),
    routing: Optional[bool] = None,
    prospecting: Optional[bool] = None,
    parent_account_id: UUID | None = None,
    auth: AuthContext = Depends(get_auth_context),
    session: Session = Depends(unscoped_session),
):
    parent = _resolve_parent(session, auth, parent_account_id)
    data = summary_to_dict(build_summary(session, parent, month, routing, prospecting))
    data["parent_account_id"] = str(parent.id)
    return data


@router.get("/monthly-summary.csv")
def monthly_summary_csv(
    month: str | None = None,
    routing: Optional[bool] = None,
    prospecting: Optional[bool] = None,
    parent_account_id: UUID | None = None,
    auth: AuthContext = Depends(get_auth_context),
    session: Session = Depends(unscoped_session),
):
    parent = _resolve_parent(session, auth, parent_account_id)
    inv = build_summary(session, parent, month, routing, prospecting)
    return Response(
        summary_to_csv(inv),
        media_type="text/csv",
        headers={"Content-Disposition": f'attachment; filename="hq-billing-{inv.billing_month:%Y-%m}.csv"'},
    )


# ── billing settings ─────────────────────────────────────────────────────────
class BillingSettingsIn(BaseModel):
    routing_addon: bool
    prospecting_addon: bool
    billing_email: Optional[str] = Field(default=None, max_length=320)


def _settings_out(parent: ParentAccount) -> dict:
    return {
        "parent_account_id": str(parent.id),
        "routing_addon": bool(parent.billing_routing_addon),
        "prospecting_addon": bool(parent.billing_prospecting_addon),
        "billing_email": parent.billing_email or parent.owner_email,
        "billing_email_is_default": not parent.billing_email,
    }


@router.get("/settings")
def get_billing_settings(
    parent_account_id: UUID | None = None,
    auth: AuthContext = Depends(get_auth_context),
    session: Session = Depends(unscoped_session),
):
    return _settings_out(_resolve_parent(session, auth, parent_account_id))


@router.put("/settings")
def put_billing_settings(
    payload: BillingSettingsIn,
    parent_account_id: UUID,
    auth: AuthContext = Depends(require_platform_admin),
    session: Session = Depends(unscoped_session),
):
    parent = session.get(ParentAccount, parent_account_id)
    if not parent:
        raise HTTPException(status_code=404, detail="Parent account not found")
    email = (payload.billing_email or "").strip() or None
    if email and ("@" not in email or " " in email):
        raise HTTPException(status_code=422, detail="Enter a valid billing email")
    parent.billing_routing_addon = payload.routing_addon
    parent.billing_prospecting_addon = payload.prospecting_addon
    parent.billing_email = email
    session.add(parent)
    session.commit()
    return _settings_out(parent)


# ── issued invoices ──────────────────────────────────────────────────────────
class CreateInvoiceIn(BaseModel):
    parent_account_id: UUID
    month: str = Field(description="YYYY-MM")


def _invoice_number(parent: ParentAccount, billing_month) -> str:
    return f"MS-{billing_month:%Y%m}-{parent.id.hex[:4].upper()}"


def _invoice_out(inv: HqInvoice, *, full: bool = False) -> dict:
    out = {
        "id": str(inv.id),
        "parent_account_id": str(inv.parent_account_id),
        "billing_month": inv.billing_month.strftime("%Y-%m"),
        "invoice_number": inv.invoice_number,
        "status": inv.status,
        "operator_count": inv.operator_count,
        "subtotal_ex_gst_cents": inv.subtotal_cents,
        "gst_cents": inv.gst_cents,
        "total_inc_gst_cents": inv.total_cents,
        "currency": inv.currency,
        "stripe_hosted_url": inv.stripe_hosted_url,
        "issued_at": inv.issued_at,
        "due_at": inv.due_at,
        "paid_at": inv.paid_at,
        "created_at": inv.created_at,
    }
    if full:
        out["snapshot"] = json.loads(inv.snapshot_json or "{}")
    return out


def _load_invoice(session: Session, auth: AuthContext, invoice_id: UUID) -> tuple[HqInvoice, ParentAccount]:
    inv = session.get(HqInvoice, invoice_id)
    if not inv:
        raise HTTPException(status_code=404, detail="Invoice not found")
    # Same access rule as the preview: platform admin, or the HQ's own admin.
    parent = _resolve_parent(session, auth, inv.parent_account_id if auth.role == "platform_admin" else None)
    if parent.id != inv.parent_account_id:
        raise HTTPException(status_code=404, detail="Invoice not found")
    return inv, parent


@router.post("/invoices", status_code=201)
def create_invoice(
    payload: CreateInvoiceIn,
    auth: AuthContext = Depends(require_platform_admin),
    session: Session = Depends(unscoped_session),
):
    """Freeze this month's numbers as a draft. Re-running replaces an unissued draft."""
    parent = session.get(ParentAccount, payload.parent_account_id)
    if not parent:
        raise HTTPException(status_code=404, detail="Parent account not found")
    summary = build_summary(session, parent, payload.month, None, None)
    if summary.operator_count == 0:
        raise HTTPException(status_code=422, detail="No billable operators in this network for that month")
    data = summary_to_dict(summary)
    inv = session.exec(
        select(HqInvoice).where(
            HqInvoice.parent_account_id == parent.id, HqInvoice.billing_month == summary.billing_month
        )
    ).first()
    if inv and inv.status != "draft":
        raise HTTPException(status_code=409, detail=f"That month is already {inv.status}")
    if not inv:
        inv = HqInvoice(
            parent_account_id=parent.id,
            billing_month=summary.billing_month,
            invoice_number=_invoice_number(parent, summary.billing_month),
        )
    inv.snapshot_json = json.dumps(data)
    inv.operator_count = summary.operator_count
    inv.subtotal_cents = summary.subtotal_cents
    inv.gst_cents = summary.gst_total_cents
    inv.total_cents = summary.total_cents
    session.add(inv)
    session.commit()
    return _invoice_out(inv, full=True)


@router.get("/invoices")
def list_invoices(
    parent_account_id: UUID | None = None,
    auth: AuthContext = Depends(get_auth_context),
    session: Session = Depends(unscoped_session),
):
    parent = _resolve_parent(session, auth, parent_account_id)
    rows = session.exec(
        select(HqInvoice).where(HqInvoice.parent_account_id == parent.id).order_by(HqInvoice.billing_month.desc())
    ).all()
    return {"invoices": [_invoice_out(r) for r in rows]}


@router.get("/invoices/{invoice_id}")
def get_invoice(invoice_id: UUID, auth: AuthContext = Depends(get_auth_context), session: Session = Depends(unscoped_session)):
    inv, _ = _load_invoice(session, auth, invoice_id)
    return _invoice_out(inv, full=True)


@router.get("/invoices/{invoice_id}/pdf")
def invoice_pdf(invoice_id: UUID, auth: AuthContext = Depends(get_auth_context), session: Session = Depends(unscoped_session)):
    inv, parent = _load_invoice(session, auth, invoice_id)
    hq = session.exec(select(HqSettings).where(HqSettings.parent_account_id == parent.id)).first()
    pdf = build_hq_invoice_pdf(
        invoice_number=inv.invoice_number,
        status=inv.status,
        bill_to=(hq.display_name if hq else parent.name),
        snapshot=json.loads(inv.snapshot_json or "{}"),
        issued_on=inv.issued_at.strftime("%d %b %Y") if inv.issued_at else None,
        due_on=inv.due_at.strftime("%d %b %Y") if inv.due_at else None,
    )
    return Response(pdf, media_type="application/pdf",
                    headers={"Content-Disposition": f'attachment; filename="{inv.invoice_number}.pdf"'})


def _stripe():
    if not settings.stripe_secret_key:
        raise HTTPException(status_code=503, detail="Stripe is not configured on this server")
    import stripe as _s

    _s.api_key = settings.stripe_secret_key
    return _s


def _stripe_lines(snapshot: dict) -> list[tuple[str, int]]:
    """Aggregate the snapshot into a few readable Stripe line items (ex-GST, then GST)."""
    month = snapshot["billing_month"]
    lines = snapshot["lines"]
    n = len(lines)
    out: list[tuple[str, int]] = [(f"Mainspring core platform, {n} operator{'s' if n != 1 else ''} ({month})",
                                   sum(l["core_cents"] for l in lines))]
    for key, label in (("routing_cents", "Lead routing add-on"), ("prospecting_cents", "Prospecting add-on")):
        total = sum(l[key] for l in lines)
        if total:
            out.append((f"{label}, {sum(1 for l in lines if l[key])} operators ({month})", total))
    for g in snapshot["gst"]:
        out.append((f"{g['label']} {g['rate_percent']:g}%", g["amount_cents"]))
    return out


@router.post("/invoices/{invoice_id}/issue")
def issue_invoice(
    invoice_id: UUID,
    auth: AuthContext = Depends(require_platform_admin),
    session: Session = Depends(unscoped_session),
):
    """Create the Stripe invoice and email it to the HQ's billing contact."""
    inv, parent = _load_invoice(session, auth, invoice_id)
    if inv.status != "draft":
        raise HTTPException(status_code=409, detail=f"Invoice is already {inv.status}")
    email = parent.billing_email or parent.owner_email
    if not email:
        raise HTTPException(status_code=422, detail="Set a billing email for this HQ first")
    st = _stripe()
    snapshot = json.loads(inv.snapshot_json)
    hq = session.exec(select(HqSettings).where(HqSettings.parent_account_id == parent.id)).first()
    name = hq.display_name if hq else parent.name
    key = f"hqinv-{inv.id}"
    stripe_invoice_id: str | None = None
    try:
        if not parent.stripe_customer_id:
            cust = st.Customer.create(name=name, email=email, metadata={"parent_account_id": str(parent.id)},
                                      idempotency_key=f"hqcust-{parent.id}")
            parent.stripe_customer_id = cust["id"]
            session.add(parent)
            session.commit()
        si = st.Invoice.create(
            customer=parent.stripe_customer_id,
            collection_method="send_invoice",
            days_until_due=PAYMENT_TERMS_DAYS,
            currency=inv.currency.lower(),
            auto_advance=True,
            pending_invoice_items_behavior="exclude",
            description=f"Mainspring {snapshot['billing_month']} · {inv.invoice_number}",
            metadata={"hq_invoice_id": str(inv.id), "parent_account_id": str(parent.id)},
            idempotency_key=f"{key}-inv",
        )
        stripe_invoice_id = si["id"]
        for i, (desc, cents) in enumerate(_stripe_lines(snapshot)):
            st.InvoiceItem.create(customer=parent.stripe_customer_id, invoice=stripe_invoice_id, amount=cents,
                                  currency=inv.currency.lower(), description=desc, idempotency_key=f"{key}-item{i}")
        st.Invoice.finalize_invoice(stripe_invoice_id)
        sent = st.Invoice.send_invoice(stripe_invoice_id)
    except HTTPException:
        raise
    except Exception:
        logger.exception("Stripe issue failed for HQ invoice %s", inv.id)
        if stripe_invoice_id:
            try:
                st.Invoice.void_invoice(stripe_invoice_id)
            except Exception:
                try:
                    st.Invoice.delete(stripe_invoice_id)
                except Exception:
                    logger.exception("Could not clean up Stripe invoice %s", stripe_invoice_id)
        raise HTTPException(status_code=502, detail="Stripe could not create the invoice. Nothing was sent; try again.")
    now = datetime.now(timezone.utc)
    inv.status = "issued"
    inv.stripe_invoice_id = stripe_invoice_id
    inv.stripe_hosted_url = sent.get("hosted_invoice_url")
    inv.stripe_pdf_url = sent.get("invoice_pdf")
    inv.issued_at = now
    inv.due_at = now + timedelta(days=PAYMENT_TERMS_DAYS)
    session.add(inv)
    session.commit()
    return _invoice_out(inv)


@router.post("/invoices/{invoice_id}/void")
def void_invoice(
    invoice_id: UUID,
    auth: AuthContext = Depends(require_platform_admin),
    session: Session = Depends(unscoped_session),
):
    inv, _ = _load_invoice(session, auth, invoice_id)
    if inv.status == "paid":
        raise HTTPException(status_code=409, detail="A paid invoice cannot be voided; refund it in Stripe")
    if inv.status == "void":
        return _invoice_out(inv)
    if inv.status == "issued" and inv.stripe_invoice_id:
        st = _stripe()
        try:
            st.Invoice.void_invoice(inv.stripe_invoice_id)
        except Exception:
            logger.exception("Stripe void failed for %s", inv.stripe_invoice_id)
            raise HTTPException(status_code=502, detail="Stripe could not void the invoice. Try again.")
    inv.status = "void"
    session.add(inv)
    session.commit()
    return _invoice_out(inv)
