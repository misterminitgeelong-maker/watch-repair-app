from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import Session, func, select

from ..database import get_session
from ..dependencies import AuthContext, get_auth_context, require_manager_or_above
from ..models import (
    Invoice,
    InvoiceCreateFromQuoteResponse,
    InvoiceRead,
    InvoiceWithPayments,
    Payment,
    PaymentCreate,
    PaymentRead,
    Quote,
    TenantEventLog,
)

router = APIRouter(prefix="/v1/invoices", tags=["invoices", "payments"])


def _next_invoice_number(session: Session, tenant_id: UUID) -> str:
    count = session.exec(select(func.count()).select_from(Invoice).where(Invoice.tenant_id == tenant_id)).one()
    return f"INV-{int(count) + 1:05d}"


@router.get("", response_model=list[InvoiceRead])
def list_invoices(
    auth: AuthContext = Depends(get_auth_context),
    session: Session = Depends(get_session),
):
    invoices = session.exec(
        select(Invoice).where(Invoice.tenant_id == auth.tenant_id)
    ).all()
    return [
        InvoiceRead(
            id=inv.id,
            tenant_id=inv.tenant_id,
            repair_job_id=inv.repair_job_id,
            quote_id=inv.quote_id,
            invoice_number=inv.invoice_number,
            status=inv.status,
            subtotal_cents=inv.subtotal_cents,
            tax_cents=inv.tax_cents,
            total_cents=inv.total_cents,
            currency=inv.currency,
            created_at=inv.created_at,
        )
        for inv in invoices
    ]


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
    return InvoiceCreateFromQuoteResponse(invoice=InvoiceRead(
        id=invoice.id,
        tenant_id=invoice.tenant_id,
        repair_job_id=invoice.repair_job_id,
        quote_id=invoice.quote_id,
        invoice_number=invoice.invoice_number,
        status=invoice.status,
        subtotal_cents=invoice.subtotal_cents,
        tax_cents=invoice.tax_cents,
        total_cents=invoice.total_cents,
        currency=invoice.currency,
        created_at=invoice.created_at,
    ))


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
        invoice=InvoiceRead(
            id=invoice.id,
            tenant_id=invoice.tenant_id,
            repair_job_id=invoice.repair_job_id,
            quote_id=invoice.quote_id,
            invoice_number=invoice.invoice_number,
            status=invoice.status,
            subtotal_cents=invoice.subtotal_cents,
            tax_cents=invoice.tax_cents,
            total_cents=invoice.total_cents,
            currency=invoice.currency,
            created_at=invoice.created_at,
        ),
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
        amount_cents=payload.amount_cents,
        provider_reference=payload.provider_reference,
    )
    session.add(payment)
    session.flush()

    paid_total = session.exec(
        select(func.coalesce(func.sum(Payment.amount_cents), 0)).where(Payment.invoice_id == invoice.id)
    ).one()
    invoice.status = "paid" if int(paid_total) >= invoice.total_cents else "unpaid"
    session.add(invoice)

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
