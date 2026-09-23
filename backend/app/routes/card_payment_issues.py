"""Resolve card payments that couldn't be applied to an invoice.

The Stripe webhook records a ``CardPaymentIssue`` (and an inbox alert) when a
customer is charged for a mobile invoice that was already paid, voided, or had
a different total. Staff resolve it here: refund the charge, apply it to the
invoice, or dismiss it (e.g. already handled in the Stripe dashboard).
"""
from __future__ import annotations

import logging
from datetime import datetime, timezone
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import Session, select

from ..config import settings
from ..database import get_session
from ..dependencies import AuthContext, get_auth_context, require_manager_or_above
from ..models import (
    AutoKeyInvoice,
    AutoKeyJob,
    CardPaymentIssue,
    CardPaymentIssueRead,
    TenantEventLog,
    User,
)
from ..money import format_cents

router = APIRouter(prefix="/v1/card-payment-issues", tags=["card-payment-issues"])
logger = logging.getLogger(__name__)


def _load(session: Session, issue_id: UUID, tenant_id: UUID) -> CardPaymentIssue:
    issue = session.get(CardPaymentIssue, issue_id)
    if not issue or issue.tenant_id != tenant_id:
        raise HTTPException(status_code=404, detail="Payment issue not found")
    return issue


def _to_read(session: Session, issue: CardPaymentIssue) -> CardPaymentIssueRead:
    invoice = session.get(AutoKeyInvoice, issue.auto_key_invoice_id) if issue.auto_key_invoice_id else None
    is_open = issue.status == "open"
    return CardPaymentIssueRead(
        id=issue.id,
        auto_key_invoice_id=issue.auto_key_invoice_id,
        invoice_number=invoice.invoice_number if invoice else None,
        invoice_status=invoice.status if invoice else None,
        invoice_total_cents=invoice.total_cents if invoice else None,
        amount_cents=issue.amount_cents,
        currency=issue.currency,
        problem=issue.problem,
        status=issue.status,
        can_refund=is_open and bool(issue.payment_intent_id),
        can_apply=is_open and invoice is not None and invoice.status == "unpaid",
        resolved_at=issue.resolved_at,
        created_at=issue.created_at,
    )


def _resolve(session: Session, issue: CardPaymentIssue, auth: AuthContext, status: str, summary: str) -> None:
    now = datetime.now(timezone.utc)
    issue.status = status
    issue.resolved_at = now
    issue.resolved_by_user_id = auth.user_id
    session.add(issue)
    # The inbox alert has done its job; the audit trail keeps the outcome.
    for alert in session.exec(
        select(TenantEventLog)
        .where(TenantEventLog.tenant_id == issue.tenant_id)
        .where(TenantEventLog.event_type == "card_payment_needs_attention")
        .where(TenantEventLog.entity_id == issue.id)
    ).all():
        session.delete(alert)
    actor = session.get(User, auth.user_id)
    session.add(
        TenantEventLog(
            tenant_id=issue.tenant_id,
            actor_user_id=auth.user_id,
            actor_email=actor.email if actor else None,
            entity_type="card_payment_issue",
            entity_id=issue.id,
            event_type=f"card_payment_{status}",
            event_summary=summary,
        )
    )
    session.commit()


def _require_open(issue: CardPaymentIssue) -> None:
    if issue.status != "open":
        raise HTTPException(status_code=409, detail=f"This payment was already {issue.status}.")


@router.get("/{issue_id}", response_model=CardPaymentIssueRead)
def get_card_payment_issue(
    issue_id: UUID,
    auth: AuthContext = Depends(get_auth_context),
    session: Session = Depends(get_session),
):
    return _to_read(session, _load(session, issue_id, auth.tenant_id))


@router.post("/{issue_id}/refund", response_model=CardPaymentIssueRead)
def refund_card_payment_issue(
    issue_id: UUID,
    auth: AuthContext = Depends(require_manager_or_above),
    session: Session = Depends(get_session),
):
    """Refund the whole charge to the customer's card through Stripe."""
    issue = _load(session, issue_id, auth.tenant_id)
    _require_open(issue)
    if not issue.payment_intent_id:
        raise HTTPException(status_code=400, detail="No Stripe payment is recorded for this charge. Refund it in Stripe, then dismiss.")
    if not (settings.stripe_secret_key or "").strip():
        raise HTTPException(status_code=503, detail="Stripe is not configured on this server")
    try:
        import stripe as stripe_mod

        stripe_mod.api_key = settings.stripe_secret_key.strip()
        kwargs: dict = {"payment_intent": issue.payment_intent_id}
        if issue.stripe_account_id:
            # Direct charge on the shop's own Stripe account.
            kwargs["stripe_account"] = issue.stripe_account_id
        else:
            # Legacy destination charge on the platform: pull the shop's share back too.
            kwargs["reverse_transfer"] = True
        refund = stripe_mod.Refund.create(**kwargs, idempotency_key=f"card-issue-refund-{issue.id}")
    except HTTPException:
        raise
    except Exception as exc:  # stripe.error.StripeError and friends
        logger.warning("card payment refund failed issue=%s: %s", issue.id, exc)
        raise HTTPException(status_code=502, detail=f"Stripe refused the refund: {getattr(exc, 'user_message', None) or exc}")
    _resolve(
        session, issue, auth, "refunded",
        f"Refunded card payment of {format_cents(issue.amount_cents, issue.currency)} "
        f"(Stripe refund {getattr(refund, 'id', None) or refund.get('id')}).",
    )
    return _to_read(session, issue)


@router.post("/{issue_id}/apply", response_model=CardPaymentIssueRead)
def apply_card_payment_issue(
    issue_id: UUID,
    auth: AuthContext = Depends(require_manager_or_above),
    session: Session = Depends(get_session),
):
    """Accept the charge as payment of its invoice (e.g. the total changed after the link was sent)."""
    issue = _load(session, issue_id, auth.tenant_id)
    _require_open(issue)
    invoice = session.get(AutoKeyInvoice, issue.auto_key_invoice_id) if issue.auto_key_invoice_id else None
    if invoice is None or invoice.tenant_id != auth.tenant_id:
        raise HTTPException(status_code=404, detail="Invoice not found")
    if invoice.status != "unpaid":
        raise HTTPException(
            status_code=409,
            detail=f"Invoice {invoice.invoice_number} is already {invoice.status}; refund the charge instead.",
        )
    invoice.status = "paid"
    invoice.payment_method = "stripe"
    invoice.paid_at = datetime.now(timezone.utc)
    session.add(invoice)
    job = session.get(AutoKeyJob, invoice.auto_key_job_id)
    if job and job.status != "invoice_paid":
        job.status = "invoice_paid"
        session.add(job)
    note = ""
    if issue.amount_cents != invoice.total_cents:
        note = f" (charged {format_cents(issue.amount_cents, issue.currency)} against a total of {format_cents(invoice.total_cents, invoice.currency)})"
    _resolve(
        session, issue, auth, "applied",
        f"Applied card payment to invoice {invoice.invoice_number}{note}.",
    )
    return _to_read(session, issue)


@router.post("/{issue_id}/dismiss", response_model=CardPaymentIssueRead)
def dismiss_card_payment_issue(
    issue_id: UUID,
    auth: AuthContext = Depends(require_manager_or_above),
    session: Session = Depends(get_session),
):
    """Close the alert without acting here (handled directly in Stripe)."""
    issue = _load(session, issue_id, auth.tenant_id)
    _require_open(issue)
    _resolve(
        session, issue, auth, "dismissed",
        f"Dismissed card payment alert for {format_cents(issue.amount_cents, issue.currency)} (handled outside the app).",
    )
    return _to_read(session, issue)
