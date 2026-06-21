import logging
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import update
from sqlalchemy.exc import IntegrityError
from sqlmodel import Session, func, select

from ..database import get_session
from ..dependencies import AuthContext, get_auth_context, require_manager_or_above
from ..loyalty_utils import earn_points_for_invoice
from ..config import settings
from ..models import (
    Customer,
    Invoice,
    InvoiceCreateFromQuoteResponse,
    InvoiceNumberCounter,
    InvoiceRead,
    InvoiceSendResponse,
    InvoiceWithPayments,
    Payment,
    PaymentCreate,
    PaymentRead,
    Quote,
    QuoteLineItem,
    RepairJob,
    Tenant,
    TenantEventLog,
    Watch,
)

_logger = logging.getLogger("mainspring.loyalty")

router = APIRouter(prefix="/v1/invoices", tags=["invoices", "payments"])


def _next_invoice_number(session: Session, tenant_id: UUID) -> str:
    for _ in range(20):
        counter = session.exec(
            select(InvoiceNumberCounter).where(InvoiceNumberCounter.tenant_id == tenant_id)
        ).first()
        if not counter:
            counter = InvoiceNumberCounter(tenant_id=tenant_id, next_number=2)
            session.add(counter)
            try:
                session.flush()
                return "INV-00001"
            except IntegrityError:
                session.rollback()
                continue

        current_number = int(counter.next_number)
        result = session.exec(
            update(InvoiceNumberCounter)
            .where(InvoiceNumberCounter.tenant_id == tenant_id)
            .where(InvoiceNumberCounter.next_number == current_number)
            .values(next_number=current_number + 1)
        )
        if result.rowcount != 1:
            continue
        session.flush()
        return f"INV-{current_number:05d}"

    raise HTTPException(status_code=500, detail="Could not allocate invoice number")


@router.get("", response_model=list[InvoiceRead])
def list_invoices(
    auth: AuthContext = Depends(get_auth_context),
    session: Session = Depends(get_session),
):
    invoices = session.exec(
        select(Invoice).where(Invoice.tenant_id == auth.tenant_id)
    ).all()
    return [InvoiceRead.model_validate(inv, from_attributes=True) for inv in invoices]


@router.post("/from-quote/{quote_id}", response_model=InvoiceCreateFromQuoteResponse, status_code=201)
def create_invoice_from_quote(
    quote_id: UUID,
    auth: AuthContext = Depends(require_manager_or_above),
    session: Session = Depends(get_session),
):
    quote = session.get(Quote, quote_id)
    if not quote or quote.tenant_id != auth.tenant_id:
        raise HTTPException(status_code=404, detail="Quote not found")
    if quote.status != "approved":
        raise HTTPException(status_code=409, detail="Quote must be approved before invoicing")
    existing = session.exec(
        select(Invoice)
        .where(Invoice.tenant_id == auth.tenant_id)
        .where(Invoice.quote_id == quote.id)
    ).first()
    if existing:
        raise HTTPException(status_code=409, detail="Invoice already exists for this quote")

    invoice = Invoice(
        tenant_id=auth.tenant_id,
        repair_job_id=quote.repair_job_id,
        quote_id=quote.id,
        invoice_number=_next_invoice_number(session, auth.tenant_id),
        subtotal_cents=quote.subtotal_cents,
        tax_cents=quote.tax_cents,
        total_cents=quote.total_cents,
        currency=quote.currency,
    )
    session.add(invoice)
    session.flush()

    session.add(
        TenantEventLog(
            tenant_id=auth.tenant_id,
            actor_user_id=auth.user_id,
            entity_type="invoice",
            entity_id=invoice.id,
            event_type="invoice_created",
            event_summary=f"Invoice {invoice.invoice_number} created ({invoice.currency} {invoice.total_cents / 100:.2f})",
        )
    )
    session.commit()
    session.refresh(invoice)

    # Best-effort push to Xero (no-op when Xero isn't configured/connected).
    from ..xero_service import sync_repair_invoice_after_create

    sync_repair_invoice_after_create(session, invoice)

    return InvoiceCreateFromQuoteResponse(
        invoice=InvoiceRead.model_validate(invoice, from_attributes=True)
    )


@router.get("/{invoice_id}", response_model=InvoiceWithPayments)
def get_invoice(
    invoice_id: UUID,
    auth: AuthContext = Depends(get_auth_context),
    session: Session = Depends(get_session),
):
    invoice = session.get(Invoice, invoice_id)
    if not invoice or invoice.tenant_id != auth.tenant_id:
        raise HTTPException(status_code=404, detail="Invoice not found")

    payments = session.exec(
        select(Payment).where(Payment.tenant_id == auth.tenant_id).where(Payment.invoice_id == invoice_id)
    ).all()

    return InvoiceWithPayments(
        invoice=InvoiceRead.model_validate(invoice, from_attributes=True),
        payments=[
            PaymentRead(
                id=p.id,
                tenant_id=p.tenant_id,
                invoice_id=p.invoice_id,
                amount_cents=p.amount_cents,
                currency=p.currency,
                status=p.status,
                provider=p.provider,
                provider_reference=p.provider_reference,
            )
            for p in payments
        ],
    )


def _line_items_payload(session: Session, quote_id: UUID | None) -> list[dict]:
    if not quote_id:
        return []
    items = session.exec(
        select(QuoteLineItem).where(QuoteLineItem.quote_id == quote_id).order_by(QuoteLineItem.created_at)
    ).all()
    return [
        {
            "description": li.description,
            "quantity": li.quantity,
            "unit_price_cents": li.unit_price_cents,
            "total_price_cents": li.total_price_cents,
        }
        for li in items
    ]


@router.post("/{invoice_id}/send", response_model=InvoiceSendResponse)
def send_invoice(
    invoice_id: UUID,
    auth: AuthContext = Depends(require_manager_or_above),
    session: Session = Depends(get_session),
):
    invoice = session.get(Invoice, invoice_id)
    if not invoice or invoice.tenant_id != auth.tenant_id:
        raise HTTPException(status_code=404, detail="Invoice not found")

    job = session.get(RepairJob, invoice.repair_job_id)
    if not job or job.tenant_id != auth.tenant_id:
        raise HTTPException(status_code=404, detail="Job not found")

    customer: Customer | None = None
    if job.watch_id:
        watch = session.get(Watch, job.watch_id)
        if watch:
            customer = session.get(Customer, watch.customer_id)

    if not customer or not (customer.email or "").strip():
        raise HTTPException(status_code=400, detail="Customer has no email address on file")

    if not settings.enable_email_notifications:
        return InvoiceSendResponse(
            invoice_id=invoice.id,
            email_sent=False,
            email_skipped_reason="email_disabled",
        )
    if not (settings.sendgrid_api_key or "").strip():
        return InvoiceSendResponse(
            invoice_id=invoice.id,
            email_sent=False,
            email_skipped_reason="sendgrid_not_configured",
        )

    tenant = session.get(Tenant, auth.tenant_id)
    shop_name = (tenant.name if tenant else None) or "Your repair shop"
    from ..email_client import send_invoice_email
    from ..pdf_invoice import build_invoice_pdf

    line_items = _line_items_payload(session, invoice.quote_id)
    try:
        pdf_bytes = build_invoice_pdf(
            invoice_number=invoice.invoice_number,
            job_number=job.job_number,
            customer_name=customer.full_name,
            shop_name=shop_name,
            shop_abn=tenant.abn if tenant else None,
            shop_address=tenant.business_address if tenant else None,
            shop_phone=tenant.shop_phone if tenant else None,
            shop_email=tenant.shop_email if tenant else None,
            payment_instructions=tenant.payment_instructions if tenant else None,
            logo_url=tenant.logo_url if tenant else None,
            brand_color=tenant.brand_color if tenant else None,
            line_items=line_items,
            subtotal_cents=invoice.subtotal_cents,
            tax_cents=invoice.tax_cents,
            total_cents=invoice.total_cents,
            currency=invoice.currency,
        )
    except Exception:
        import logging
        logging.getLogger(__name__).exception("PDF generation failed for invoice %s", invoice.invoice_number)
        pdf_bytes = None

    email_sent, email_error_detail = send_invoice_email(
        to_email=customer.email,
        customer_name=customer.full_name,
        invoice_number=invoice.invoice_number,
        job_number=job.job_number,
        total_cents=invoice.total_cents,
        currency=invoice.currency,
        shop_name=shop_name,
        line_items=line_items,
        shop_logo_url=tenant.logo_url if tenant else None,
        shop_brand_color=tenant.brand_color if tenant else None,
        pdf_bytes=pdf_bytes,
    )
    if email_sent:
        session.add(
            TenantEventLog(
                tenant_id=auth.tenant_id,
                actor_user_id=auth.user_id,
                entity_type="invoice",
                entity_id=invoice.id,
                event_type="invoice_sent_email",
                event_summary=f"Invoice {invoice.invoice_number} emailed to customer",
            )
        )
        session.commit()

    return InvoiceSendResponse(
        invoice_id=invoice.id,
        email_sent=email_sent,
        email_skipped_reason=None if email_sent else "send_failed",
        email_error_detail=None if email_sent else email_error_detail,
    )


@router.get("/{invoice_id}/line-items")
def get_invoice_line_items(
    invoice_id: UUID,
    auth: AuthContext = Depends(get_auth_context),
    session: Session = Depends(get_session),
):
    invoice = session.exec(
        select(Invoice).where(Invoice.id == invoice_id).where(Invoice.tenant_id == auth.tenant_id)
    ).first()
    if not invoice:
        raise HTTPException(status_code=404, detail="Invoice not found")
    if not invoice.quote_id:
        return []
    items = session.exec(
        select(QuoteLineItem).where(QuoteLineItem.quote_id == invoice.quote_id).order_by(QuoteLineItem.created_at)
    ).all()
    return items


@router.post("/{invoice_id}/payments", response_model=PaymentRead, status_code=201)
def create_payment(
    invoice_id: UUID,
    payload: PaymentCreate,
    auth: AuthContext = Depends(require_manager_or_above),
    session: Session = Depends(get_session),
):
    invoice = session.get(Invoice, invoice_id)
    if not invoice or invoice.tenant_id != auth.tenant_id:
        raise HTTPException(status_code=404, detail="Invoice not found")
    if payload.amount_cents <= 0:
        raise HTTPException(status_code=400, detail="Payment amount must be greater than zero")

    already_paid_total = int(
        session.exec(
            select(func.coalesce(func.sum(Payment.amount_cents), 0)).where(Payment.invoice_id == invoice.id)
        ).one()
    )
    remaining = max(0, invoice.total_cents - already_paid_total)
    if remaining == 0:
        raise HTTPException(status_code=409, detail="Invoice is already fully paid")
    if payload.amount_cents > remaining:
        raise HTTPException(
            status_code=400,
            detail=f"Payment exceeds remaining balance ({remaining} cents)",
        )

    payment = Payment(
        tenant_id=auth.tenant_id,
        invoice_id=invoice.id,
        currency=invoice.currency,
        amount_cents=payload.amount_cents,
        provider_reference=payload.provider_reference,
    )
    session.add(payment)
    session.flush()

    paid_total = session.exec(
        select(func.coalesce(func.sum(Payment.amount_cents), 0)).where(Payment.invoice_id == invoice.id)
    ).one()
    newly_paid = int(paid_total) >= invoice.total_cents and invoice.status != "paid"
    invoice.status = "paid" if int(paid_total) >= invoice.total_cents else "unpaid"
    session.add(invoice)

    if newly_paid:
        session.add(
            TenantEventLog(
                tenant_id=auth.tenant_id,
                actor_user_id=auth.user_id,
                entity_type="invoice",
                entity_id=invoice.id,
                event_type="invoice_paid",
                event_summary=f"Invoice {invoice.invoice_number} paid in full ({invoice.currency} {invoice.total_cents / 100:.2f})",
            )
        )
        try:
            pts = earn_points_for_invoice(session, auth.tenant_id, invoice)
            if pts:
                _logger.info("loyalty: awarded %d pts for invoice %s", pts, invoice.invoice_number)
        except Exception:
            _logger.exception("loyalty: earn failed for invoice %s (non-fatal)", invoice.invoice_number)

    session.commit()
    session.refresh(payment)
    return PaymentRead(
        id=payment.id,
        tenant_id=payment.tenant_id,
        invoice_id=payment.invoice_id,
        amount_cents=payment.amount_cents,
        currency=payment.currency,
        status=payment.status,
        provider=payment.provider,
        provider_reference=payment.provider_reference,
    )


@router.post("/{invoice_id}/xero/retry", response_model=InvoiceRead)
def retry_invoice_xero_sync(
    invoice_id: UUID,
    auth: AuthContext = Depends(require_manager_or_above),
    session: Session = Depends(get_session),
):
    invoice = session.get(Invoice, invoice_id)
    if not invoice or invoice.tenant_id != auth.tenant_id:
        raise HTTPException(status_code=404, detail="Invoice not found")
    invoice.xero_sync_status = None
    invoice.xero_sync_error = None
    session.add(invoice)
    session.commit()
    from ..xero_service import sync_repair_invoice_after_create

    sync_repair_invoice_after_create(session, invoice)
    session.refresh(invoice)
    return InvoiceRead.model_validate(invoice, from_attributes=True)
