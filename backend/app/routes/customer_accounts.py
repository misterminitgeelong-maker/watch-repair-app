from uuid import UUID
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Query, Response
from sqlmodel import Session, func, select

from ..database import get_session
from ..dependencies import AuthContext, get_auth_context, require_feature, require_manager_or_above
from ..models import (
    Customer,
    CustomerAccount,
    CustomerAccountCreate,
    CustomerAccountInvoice,
    CustomerAccountInvoiceLine,
    CustomerAccountInvoiceRead,
    CustomerAccountMemberAdd,
    CustomerAccountMembership,
    CustomerAccountMonthlyInvoiceCreate,
    CustomerAccountRead,
    CustomerAccountStatementLine,
    CustomerAccountStatementResponse,
    CustomerAccountUpdate,
    AutoKeyJob,
    RepairJob,
    ShoeRepairJob,
)

router = APIRouter(
    prefix="/v1/customer-accounts",
    tags=["customer-accounts"],
    dependencies=[Depends(require_feature("customer_accounts"))],
)


def _to_read(session: Session, account: CustomerAccount) -> CustomerAccountRead:
    membership_rows = session.exec(
        select(CustomerAccountMembership)
        .where(CustomerAccountMembership.tenant_id == account.tenant_id)
        .where(CustomerAccountMembership.customer_account_id == account.id)
        .order_by(CustomerAccountMembership.created_at)
    ).all()
    customer_ids = [m.customer_id for m in membership_rows]
    return CustomerAccountRead(
        id=account.id,
        tenant_id=account.tenant_id,
        name=account.name,
        account_code=account.account_code,
        contact_name=account.contact_name,
        contact_email=account.contact_email,
        contact_phone=account.contact_phone,
        billing_address=account.billing_address,
        payment_terms_days=account.payment_terms_days,
        notes=account.notes,
        is_active=account.is_active,
        created_at=account.created_at,
        customer_ids=customer_ids,
        # Fleet/Dealer fields
        account_type=account.account_type,
        fleet_size=account.fleet_size,
        primary_contact_name=account.primary_contact_name,
        primary_contact_phone=account.primary_contact_phone,
        billing_cycle=account.billing_cycle,
        credit_limit=account.credit_limit,
        account_notes=account.account_notes,
    )


def _next_customer_account_invoice_number(session: Session, tenant_id: UUID) -> str:
    count = session.exec(
        select(func.count())
        .select_from(CustomerAccountInvoice)
        .where(CustomerAccountInvoice.tenant_id == tenant_id)
    ).one()
    return f"B2B-{int(count) + 1:05d}"


def _period_window(period_year: int, period_month: int) -> tuple[datetime, datetime]:
    if period_month < 1 or period_month > 12:
        raise HTTPException(status_code=400, detail="period_month must be between 1 and 12")
    if period_year < 2000 or period_year > 2100:
        raise HTTPException(status_code=400, detail="period_year is out of range")

    start = datetime(period_year, period_month, 1, tzinfo=timezone.utc)
    if period_month == 12:
        end = datetime(period_year + 1, 1, 1, tzinfo=timezone.utc)
    else:
        end = datetime(period_year, period_month + 1, 1, tzinfo=timezone.utc)
    return start, end


def _build_statement(
    session: Session,
    tenant_id: UUID,
    account_id: UUID,
    period_year: int,
    period_month: int,
) -> CustomerAccountStatementResponse:
    start, end = _period_window(period_year, period_month)

    lines: list[CustomerAccountStatementLine] = []

    invoice_ids = session.exec(
        select(CustomerAccountInvoice.id)
        .where(CustomerAccountInvoice.tenant_id == tenant_id)
        .where(CustomerAccountInvoice.customer_account_id == account_id)
    ).all()

    invoiced_watch_job_ids: set[UUID] = set()
    invoiced_shoe_job_ids: set[UUID] = set()
    invoiced_auto_key_job_ids: set[UUID] = set()
    if invoice_ids:
        invoiced_watch_job_ids = set(
            session.exec(
                select(CustomerAccountInvoiceLine.source_job_id)
                .where(CustomerAccountInvoiceLine.tenant_id == tenant_id)
                .where(CustomerAccountInvoiceLine.customer_account_invoice_id.in_(invoice_ids))
                .where(CustomerAccountInvoiceLine.source_type == "watch")
            ).all()
        )
        invoiced_shoe_job_ids = set(
            session.exec(
                select(CustomerAccountInvoiceLine.source_job_id)
                .where(CustomerAccountInvoiceLine.tenant_id == tenant_id)
                .where(CustomerAccountInvoiceLine.customer_account_invoice_id.in_(invoice_ids))
                .where(CustomerAccountInvoiceLine.source_type == "shoe")
            ).all()
        )
        invoiced_auto_key_job_ids = set(
            session.exec(
                select(CustomerAccountInvoiceLine.source_job_id)
                .where(CustomerAccountInvoiceLine.tenant_id == tenant_id)
                .where(CustomerAccountInvoiceLine.customer_account_invoice_id.in_(invoice_ids))
                .where(CustomerAccountInvoiceLine.source_type == "auto_key")
            ).all()
        )

    watch_jobs = session.exec(
        select(RepairJob)
        .where(RepairJob.tenant_id == tenant_id)
        .where(RepairJob.customer_account_id == account_id)
        .where(RepairJob.status.in_(["completed", "awaiting_collection", "collected"]))
        .where(RepairJob.created_at >= start)
        .where(RepairJob.created_at < end)
        .order_by(RepairJob.created_at)
    ).all()
    for job in watch_jobs:
        if job.cost_cents <= 0:
            continue
        if job.id in invoiced_watch_job_ids:
            continue
        lines.append(
            CustomerAccountStatementLine(
                source_type="watch",
                source_job_id=job.id,
                job_number=job.job_number,
                description=job.title,
                amount_cents=job.cost_cents,
            )
        )

    shoe_jobs = session.exec(
        select(ShoeRepairJob)
        .where(ShoeRepairJob.tenant_id == tenant_id)
        .where(ShoeRepairJob.customer_account_id == account_id)
        .where(ShoeRepairJob.status.in_(["completed", "awaiting_collection", "collected"]))
        .where(ShoeRepairJob.created_at >= start)
        .where(ShoeRepairJob.created_at < end)
        .order_by(ShoeRepairJob.created_at)
    ).all()
    for job in shoe_jobs:
        if job.cost_cents <= 0:
            continue
        if job.id in invoiced_shoe_job_ids:
            continue
        lines.append(
            CustomerAccountStatementLine(
                source_type="shoe",
                source_job_id=job.id,
                job_number=job.job_number,
                description=job.title,
                amount_cents=job.cost_cents,
            )
        )

    auto_key_jobs = session.exec(
        select(AutoKeyJob)
        .where(AutoKeyJob.tenant_id == tenant_id)
        .where(AutoKeyJob.customer_account_id == account_id)
        .where(AutoKeyJob.status.in_(["completed", "awaiting_collection", "collected"]))
        .where(AutoKeyJob.created_at >= start)
        .where(AutoKeyJob.created_at < end)
        .order_by(AutoKeyJob.created_at)
    ).all()
    for job in auto_key_jobs:
        if job.cost_cents <= 0:
            continue
        if job.id in invoiced_auto_key_job_ids:
            continue
        lines.append(
            CustomerAccountStatementLine(
                source_type="auto_key",
                source_job_id=job.id,
                job_number=job.job_number,
                description=job.title,
                amount_cents=job.cost_cents,
            )
        )

    subtotal_cents = sum(line.amount_cents for line in lines)
    return CustomerAccountStatementResponse(
        customer_account_id=account_id,
        period_year=period_year,
        period_month=period_month,
        lines=lines,
        subtotal_cents=subtotal_cents,
    )


def _invoice_to_read(session: Session, invoice: CustomerAccountInvoice) -> CustomerAccountInvoiceRead:
    line_rows = session.exec(
        select(CustomerAccountInvoiceLine)
        .where(CustomerAccountInvoiceLine.tenant_id == invoice.tenant_id)
        .where(CustomerAccountInvoiceLine.customer_account_invoice_id == invoice.id)
        .order_by(CustomerAccountInvoiceLine.created_at)
    ).all()
    return CustomerAccountInvoiceRead(
        id=invoice.id,
        tenant_id=invoice.tenant_id,
        customer_account_id=invoice.customer_account_id,
        invoice_number=invoice.invoice_number,
        period_year=invoice.period_year,
        period_month=invoice.period_month,
        status=invoice.status,
        subtotal_cents=invoice.subtotal_cents,
        tax_cents=invoice.tax_cents,
        total_cents=invoice.total_cents,
        currency=invoice.currency,
        created_at=invoice.created_at,
        lines=[
            CustomerAccountStatementLine(
                source_type=line.source_type,
                source_job_id=line.source_job_id,
                job_number=line.job_number,
                description=line.description,
                amount_cents=line.amount_cents,
            )
            for line in line_rows
        ],
    )


@router.get("", response_model=list[CustomerAccountRead])
def list_customer_accounts(
    auth: AuthContext = Depends(get_auth_context),
    session: Session = Depends(get_session),
):
    accounts = session.exec(
        select(CustomerAccount)
        .where(CustomerAccount.tenant_id == auth.tenant_id)
        .order_by(CustomerAccount.created_at.desc())
    ).all()
    return [_to_read(session, a) for a in accounts]


@router.post("", response_model=CustomerAccountRead, status_code=201)
def create_customer_account(
    payload: CustomerAccountCreate,
    auth: AuthContext = Depends(require_manager_or_above),
    session: Session = Depends(get_session),
):
    name = payload.name.strip()
    if not name:
        raise HTTPException(status_code=400, detail="Account name is required")

    account = CustomerAccount(
        tenant_id=auth.tenant_id,
        name=name,
        account_code=(payload.account_code or '').strip() or None,
        contact_name=(payload.contact_name or '').strip() or None,
        contact_email=(payload.contact_email or '').strip() or None,
        contact_phone=(payload.contact_phone or '').strip() or None,
        billing_address=(payload.billing_address or '').strip() or None,
        payment_terms_days=max(0, payload.payment_terms_days),
        notes=(payload.notes or '').strip() or None,
        # Fleet/Dealer fields
        account_type=(payload.account_type or '').strip() or None,
        fleet_size=payload.fleet_size,
        primary_contact_name=(payload.primary_contact_name or '').strip() or None,
        primary_contact_phone=(payload.primary_contact_phone or '').strip() or None,
        billing_cycle=(payload.billing_cycle or '').strip() or None,
        credit_limit=payload.credit_limit,
        account_notes=(payload.account_notes or '').strip() or None,
    )
    session.add(account)
    session.commit()
    session.refresh(account)
    return _to_read(session, account)


@router.get("/{account_id}", response_model=CustomerAccountRead)
def get_customer_account(
    account_id: UUID,
    auth: AuthContext = Depends(get_auth_context),
    session: Session = Depends(get_session),
):
    account = session.get(CustomerAccount, account_id)
    if not account or account.tenant_id != auth.tenant_id:
        raise HTTPException(status_code=404, detail="Customer account not found")
    return _to_read(session, account)


@router.patch("/{account_id}", response_model=CustomerAccountRead)
def update_customer_account(
    account_id: UUID,
    payload: CustomerAccountUpdate,
    auth: AuthContext = Depends(require_manager_or_above),
    session: Session = Depends(get_session),
):
    account = session.get(CustomerAccount, account_id)
    if not account or account.tenant_id != auth.tenant_id:
        raise HTTPException(status_code=404, detail="Customer account not found")

    updates = payload.model_dump(exclude_unset=True)
    for field, value in updates.items():
        setattr(account, field, value)

    if account.name is not None:
        account.name = account.name.strip()
    if not account.name:
        raise HTTPException(status_code=400, detail="Account name is required")

    account.payment_terms_days = max(0, account.payment_terms_days)

    session.add(account)
    session.commit()
    session.refresh(account)
    return _to_read(session, account)


@router.post("/{account_id}/customers", response_model=CustomerAccountRead)
def add_customer_to_account(
    account_id: UUID,
    payload: CustomerAccountMemberAdd,
    auth: AuthContext = Depends(require_manager_or_above),
    session: Session = Depends(get_session),
):
    account = session.get(CustomerAccount, account_id)
    if not account or account.tenant_id != auth.tenant_id:
        raise HTTPException(status_code=404, detail="Customer account not found")

    customer = session.get(Customer, payload.customer_id)
    if not customer or customer.tenant_id != auth.tenant_id:
        raise HTTPException(status_code=404, detail="Customer not found")

    existing = session.exec(
        select(CustomerAccountMembership)
        .where(CustomerAccountMembership.tenant_id == auth.tenant_id)
        .where(CustomerAccountMembership.customer_account_id == account_id)
        .where(CustomerAccountMembership.customer_id == payload.customer_id)
    ).first()
    if not existing:
        session.add(
            CustomerAccountMembership(
                tenant_id=auth.tenant_id,
                customer_account_id=account_id,
                customer_id=payload.customer_id,
            )
        )
        session.commit()

    session.refresh(account)
    return _to_read(session, account)


@router.delete("/{account_id}/customers/{customer_id}", status_code=204, response_class=Response)
def remove_customer_from_account(
    account_id: UUID,
    customer_id: UUID,
    auth: AuthContext = Depends(require_manager_or_above),
    session: Session = Depends(get_session),
):
    account = session.get(CustomerAccount, account_id)
    if not account or account.tenant_id != auth.tenant_id:
        raise HTTPException(status_code=404, detail="Customer account not found")

    membership = session.exec(
        select(CustomerAccountMembership)
        .where(CustomerAccountMembership.tenant_id == auth.tenant_id)
        .where(CustomerAccountMembership.customer_account_id == account_id)
        .where(CustomerAccountMembership.customer_id == customer_id)
    ).first()
    if membership:
        session.delete(membership)
        session.commit()

    return Response(status_code=204)


@router.get("/{account_id}/statement", response_model=CustomerAccountStatementResponse)
def preview_customer_account_statement(
    account_id: UUID,
    period_year: int = Query(..., ge=2000, le=2100),
    period_month: int = Query(..., ge=1, le=12),
    auth: AuthContext = Depends(get_auth_context),
    session: Session = Depends(get_session),
):
    account = session.get(CustomerAccount, account_id)
    if not account or account.tenant_id != auth.tenant_id:
        raise HTTPException(status_code=404, detail="Customer account not found")

    return _build_statement(session, auth.tenant_id, account_id, period_year, period_month)


@router.get("/{account_id}/invoices", response_model=list[CustomerAccountInvoiceRead])
def list_customer_account_invoices(
    account_id: UUID,
    auth: AuthContext = Depends(get_auth_context),
    session: Session = Depends(get_session),
):
    account = session.get(CustomerAccount, account_id)
    if not account or account.tenant_id != auth.tenant_id:
        raise HTTPException(status_code=404, detail="Customer account not found")

    invoices = session.exec(
        select(CustomerAccountInvoice)
        .where(CustomerAccountInvoice.tenant_id == auth.tenant_id)
        .where(CustomerAccountInvoice.customer_account_id == account_id)
        .order_by(CustomerAccountInvoice.created_at.desc())
    ).all()
    return [_invoice_to_read(session, inv) for inv in invoices]


@router.post("/{account_id}/invoices/monthly", response_model=CustomerAccountInvoiceRead, status_code=201)
def generate_customer_account_monthly_invoice(
    account_id: UUID,
    payload: CustomerAccountMonthlyInvoiceCreate,
    auth: AuthContext = Depends(require_manager_or_above),
    session: Session = Depends(get_session),
):
    account = session.get(CustomerAccount, account_id)
    if not account or account.tenant_id != auth.tenant_id:
        raise HTTPException(status_code=404, detail="Customer account not found")

    existing = session.exec(
        select(CustomerAccountInvoice)
        .where(CustomerAccountInvoice.tenant_id == auth.tenant_id)
        .where(CustomerAccountInvoice.customer_account_id == account_id)
        .where(CustomerAccountInvoice.period_year == payload.period_year)
        .where(CustomerAccountInvoice.period_month == payload.period_month)
    ).first()
    if existing:
        raise HTTPException(status_code=409, detail="Monthly invoice already exists for this period")

    statement = _build_statement(
        session,
        auth.tenant_id,
        account_id,
        payload.period_year,
        payload.period_month,
    )
    if not statement.lines:
        raise HTTPException(status_code=400, detail="No billable jobs found for this period")

    tax_cents = max(0, int(payload.tax_cents or 0))
    invoice = CustomerAccountInvoice(
        tenant_id=auth.tenant_id,
        customer_account_id=account_id,
        invoice_number=_next_customer_account_invoice_number(session, auth.tenant_id),
        period_year=payload.period_year,
        period_month=payload.period_month,
        subtotal_cents=statement.subtotal_cents,
        tax_cents=tax_cents,
        total_cents=statement.subtotal_cents + tax_cents,
        currency="AUD",
    )
    session.add(invoice)
    session.flush()

    for line in statement.lines:
        session.add(
            CustomerAccountInvoiceLine(
                tenant_id=auth.tenant_id,
                customer_account_invoice_id=invoice.id,
                source_type=line.source_type,
                source_job_id=line.source_job_id,
                job_number=line.job_number,
                description=line.description,
                amount_cents=line.amount_cents,
            )
        )

    session.commit()
    session.refresh(invoice)
    return _invoice_to_read(session, invoice)
