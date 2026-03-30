import json
import re
from datetime import datetime, timedelta, timezone
from typing import Any
from uuid import UUID, uuid4

from fastapi import APIRouter, Depends, HTTPException, Query, Response
from sqlmodel import Session, SQLModel, delete, func, select

from ..auto_key_quote_suggestions import gst_tax_cents, suggest_line_items
from ..config import settings
from ..database import get_session
from ..datetime_utils import local_calendar_day_bounds_utc, naive_utc_from_any
from ..dependencies import AuthContext, enforce_plan_limit, get_auth_context, require_feature, require_tech_or_above
from .. import sms
from ..models import (
    AutoKeyJob,
    AutoKeyJobCreate,
    AutoKeyJobFieldUpdate,
    AutoKeyQuickIntakeCreate,
    AutoKeyInvoice,
    AutoKeyInvoiceRead,
    AutoKeyJobRead,
    AutoKeyJobStatusUpdate,
    AutoKeyQuote,
    AutoKeyQuoteCreate,
    AutoKeyQuoteLineItem,
    AutoKeyQuoteLineItemRead,
    AutoKeyQuoteRead,
    Customer,
    CustomerAccount,
    CustomerAccountMembership,
    Tenant,
    User,
)

router = APIRouter(
    prefix="/v1/auto-key-jobs",
    tags=["auto-key-jobs"],
    dependencies=[Depends(require_feature("auto_key"))],
)


def _normalize_phone(value: str) -> str:
    return re.sub(r"[\s\-\.]", "", (value or "").strip())


def _serialize_additional_services(items: list[Any] | None) -> str | None:
    if not items:
        return None
    cleaned: list[dict[str, str | None]] = []
    for raw in items:
        if not isinstance(raw, dict):
            continue
        preset = (raw.get("preset") or "").strip() or None
        custom = (raw.get("custom") or "").strip() or None
        if preset or custom:
            cleaned.append({"preset": preset, "custom": custom})
    if not cleaned:
        return None
    return json.dumps(cleaned)


def _next_auto_key_job_number(session: Session, tenant_id: UUID) -> str:
    count = session.exec(
        select(func.count()).select_from(AutoKeyJob).where(AutoKeyJob.tenant_id == tenant_id)
    ).one()
    return f"AK-{int(count) + 1:05d}"


def _next_auto_key_invoice_number(session: Session, tenant_id: UUID) -> str:
    count = session.exec(
        select(func.count()).select_from(AutoKeyInvoice).where(AutoKeyInvoice.tenant_id == tenant_id)
    ).one()
    return f"AKI-{int(count) + 1:05d}"


def _ensure_auto_key_invoice_for_completed_job(session: Session, tenant_id: UUID, job: AutoKeyJob) -> AutoKeyInvoice | None:
    """Create an invoice from the latest quote or job cost if the job has none yet."""
    existing = session.exec(
        select(AutoKeyInvoice)
        .where(AutoKeyInvoice.tenant_id == tenant_id)
        .where(AutoKeyInvoice.auto_key_job_id == job.id)
    ).first()
    if existing:
        return existing

    latest_quote = session.exec(
        select(AutoKeyQuote)
        .where(AutoKeyQuote.tenant_id == tenant_id)
        .where(AutoKeyQuote.auto_key_job_id == job.id)
        .order_by(AutoKeyQuote.created_at.desc())
    ).first()
    if latest_quote and latest_quote.status != "declined":
        inv = AutoKeyInvoice(
            tenant_id=tenant_id,
            auto_key_job_id=job.id,
            auto_key_quote_id=latest_quote.id,
            invoice_number=_next_auto_key_invoice_number(session, tenant_id),
            subtotal_cents=latest_quote.subtotal_cents,
            tax_cents=latest_quote.tax_cents,
            total_cents=latest_quote.total_cents,
            currency=latest_quote.currency,
        )
        session.add(inv)
        return inv

    cost = int(job.cost_cents or 0)
    if cost <= 0:
        return None

    tenant = session.get(Tenant, tenant_id)
    currency = (tenant.default_currency if tenant and tenant.default_currency else "AUD").upper()[:3]
    subtotal = int(round(cost / 1.1))
    tax = cost - subtotal
    inv = AutoKeyInvoice(
        tenant_id=tenant_id,
        auto_key_job_id=job.id,
        auto_key_quote_id=None,
        invoice_number=_next_auto_key_invoice_number(session, tenant_id),
        subtotal_cents=subtotal,
        tax_cents=tax,
        total_cents=cost,
        currency=currency,
    )
    session.add(inv)
    return inv


def _to_quote_read(session: Session, quote: AutoKeyQuote) -> AutoKeyQuoteRead:
    items = session.exec(
        select(AutoKeyQuoteLineItem)
        .where(AutoKeyQuoteLineItem.auto_key_quote_id == quote.id)
        .order_by(AutoKeyQuoteLineItem.created_at)
    ).all()
    return AutoKeyQuoteRead(
        id=quote.id,
        tenant_id=quote.tenant_id,
        auto_key_job_id=quote.auto_key_job_id,
        status=quote.status,
        subtotal_cents=quote.subtotal_cents,
        tax_cents=quote.tax_cents,
        total_cents=quote.total_cents,
        currency=quote.currency,
        sent_at=quote.sent_at,
        created_at=quote.created_at,
        line_items=[
            AutoKeyQuoteLineItemRead(
                id=i.id,
                auto_key_quote_id=i.auto_key_quote_id,
                description=i.description,
                quantity=i.quantity,
                unit_price_cents=i.unit_price_cents,
                total_price_cents=i.total_price_cents,
            )
            for i in items
        ],
    )


def _insert_suggested_quote_for_job(
    session: Session,
    *,
    tenant_id: UUID,
    job_id: UUID,
    job_type: str | None,
    key_quantity: int,
    currency: str,
) -> AutoKeyQuote:
    lines = suggest_line_items(job_type, key_quantity)
    subtotal = 0
    quote = AutoKeyQuote(tenant_id=tenant_id, auto_key_job_id=job_id, currency=currency.upper()[:3], tax_cents=0)
    session.add(quote)
    session.flush()
    for desc, qty, unit in lines:
        line_tot = int(round(qty * unit))
        subtotal += line_tot
        session.add(
            AutoKeyQuoteLineItem(
                tenant_id=tenant_id,
                auto_key_quote_id=quote.id,
                description=desc,
                quantity=qty,
                unit_price_cents=unit,
                total_price_cents=line_tot,
            )
        )
    tax = gst_tax_cents(subtotal)
    quote.subtotal_cents = subtotal
    quote.tax_cents = tax
    quote.total_cents = subtotal + tax
    session.add(quote)
    session.flush()
    return quote


@router.get("/quote-suggestions")
def get_auto_key_quote_suggestions(
    job_type: str | None = Query(default=None, max_length=120),
    key_quantity: int = Query(default=1, ge=1, le=99),
    auth: AuthContext = Depends(get_auth_context),
):
    """Retail-style line items + GST for the Mobile Services job type (for quote preview)."""
    lines = suggest_line_items(job_type, key_quantity)
    subtotal = int(round(sum(q * u for _, q, u in lines)))
    tax = gst_tax_cents(subtotal)
    return {
        "line_items": [
            {"description": d, "quantity": q, "unit_price_cents": u}
            for d, q, u in lines
        ],
        "subtotal_cents": subtotal,
        "tax_cents": tax,
        "total_cents": subtotal + tax,
    }


@router.post("", response_model=AutoKeyJobRead, status_code=201)
def create_auto_key_job(
    payload: AutoKeyJobCreate,
    auth: AuthContext = Depends(get_auth_context),
    session: Session = Depends(get_session),
):
    # Plan limit check
    ak_count = int(
        session.exec(
            select(func.count()).select_from(AutoKeyJob).where(AutoKeyJob.tenant_id == auth.tenant_id)
        ).one()
    )
    enforce_plan_limit(auth, "auto_key_job", ak_count)

    customer = session.get(Customer, payload.customer_id)
    if not customer or customer.tenant_id != auth.tenant_id:
        raise HTTPException(status_code=404, detail="Customer not found")

    customer_account_id = payload.customer_account_id
    if customer_account_id:
        account = session.get(CustomerAccount, customer_account_id)
        if not account or account.tenant_id != auth.tenant_id:
            raise HTTPException(status_code=404, detail="Customer account not found")
    else:
        inferred = session.exec(
            select(CustomerAccountMembership)
            .where(CustomerAccountMembership.tenant_id == auth.tenant_id)
            .where(CustomerAccountMembership.customer_id == payload.customer_id)
            .order_by(CustomerAccountMembership.created_at)
        ).first()
        customer_account_id = inferred.customer_account_id if inferred else None

    data = payload.model_dump()
    apply_suggested_quote = bool(data.pop("apply_suggested_quote", False))
    send_booking_sms = bool(data.pop("send_booking_sms", False))
    additional_services = data.pop("additional_services", None) or []
    data["additional_services_json"] = _serialize_additional_services(additional_services)
    data["key_quantity"] = max(1, int(data.get("key_quantity", 1)))
    data["customer_account_id"] = customer_account_id
    if send_booking_sms:
        data["status"] = "pending_booking"

    if data.get("scheduled_at"):
        data["scheduled_at"] = naive_utc_from_any(data["scheduled_at"])

    job = AutoKeyJob(
        tenant_id=auth.tenant_id,
        job_number=_next_auto_key_job_number(session, auth.tenant_id),
        booking_confirmation_token=None,
        **data,
    )
    session.add(job)
    session.flush()

    tenant = session.get(Tenant, auth.tenant_id)
    currency = (tenant.default_currency if tenant and tenant.default_currency else "AUD").upper()[:3]

    need_quote = apply_suggested_quote or send_booking_sms
    if need_quote:
        _insert_suggested_quote_for_job(
            session,
            tenant_id=auth.tenant_id,
            job_id=job.id,
            job_type=job.job_type,
            key_quantity=job.key_quantity,
            currency=currency,
        )

    if send_booking_sms:
        phone = (customer.phone or "").strip()
        if not phone:
            raise HTTPException(
                status_code=400,
                detail="Customer mobile number is required to send a booking confirmation SMS.",
            )
        if not job.scheduled_at:
            raise HTTPException(
                status_code=400,
                detail="Book date & time is required when sending a booking confirmation SMS.",
            )
        latest_quote = session.exec(
            select(AutoKeyQuote)
            .where(AutoKeyQuote.tenant_id == auth.tenant_id)
            .where(AutoKeyQuote.auto_key_job_id == job.id)
            .order_by(AutoKeyQuote.created_at.desc())
        ).first()
        if not latest_quote:
            raise HTTPException(status_code=400, detail="Could not create quote for booking SMS.")
        token = uuid4().hex
        job.booking_confirmation_token = token
        session.add(job)
        session.flush()
        confirm_url = f"{settings.public_base_url.rstrip('/')}/mobile-booking/{token}"
        sms.notify_auto_key_booking_request(
            session,
            tenant_id=auth.tenant_id,
            to_phone=phone,
            customer_name=customer.full_name or "there",
            job_number=job.job_number,
            title=job.title,
            vehicle_make=job.vehicle_make,
            vehicle_model=job.vehicle_model,
            scheduled_at=job.scheduled_at,
            quote_total_cents=latest_quote.total_cents,
            currency=latest_quote.currency,
            shop_name=(tenant.name if tenant else "Mainspring"),
            confirm_url=confirm_url,
        )

    session.commit()
    session.refresh(job)
    return job


@router.post("/quick-intake", response_model=AutoKeyJobRead, status_code=201)
def create_auto_key_job_quick_intake(
    payload: AutoKeyQuickIntakeCreate,
    auth: AuthContext = Depends(get_auth_context),
    session: Session = Depends(get_session),
):
    """Create a minimal job and SMS the customer a link to complete vehicle and job details."""
    name = (payload.full_name or "").strip()
    phone_raw = (payload.phone or "").strip()
    if not name:
        raise HTTPException(status_code=400, detail="Customer name is required.")
    if not phone_raw:
        raise HTTPException(status_code=400, detail="Mobile number is required.")
    norm = _normalize_phone(phone_raw)
    if len(norm) < 8:
        raise HTTPException(status_code=400, detail="Please enter a valid mobile number.")

    ak_count = int(
        session.exec(
            select(func.count()).select_from(AutoKeyJob).where(AutoKeyJob.tenant_id == auth.tenant_id)
        ).one()
    )
    enforce_plan_limit(auth, "auto_key_job", ak_count)

    customer: Customer | None = None
    for row in session.exec(select(Customer).where(Customer.tenant_id == auth.tenant_id)).all():
        if _normalize_phone(row.phone or "") == norm:
            customer = row
            break
    if customer is None:
        customer = Customer(tenant_id=auth.tenant_id, full_name=name, phone=phone_raw)
        session.add(customer)
        session.flush()
    elif name and (not customer.full_name or len(name) > len(customer.full_name or "")):
        customer.full_name = name
        if phone_raw:
            customer.phone = phone_raw
        session.add(customer)
        session.flush()

    inferred = session.exec(
        select(CustomerAccountMembership)
        .where(CustomerAccountMembership.tenant_id == auth.tenant_id)
        .where(CustomerAccountMembership.customer_id == customer.id)
        .order_by(CustomerAccountMembership.created_at)
    ).first()
    customer_account_id = inferred.customer_account_id if inferred else None

    first_token = name.split()[0] if name.split() else "Customer"
    intake_token = uuid4().hex
    job = AutoKeyJob(
        tenant_id=auth.tenant_id,
        customer_id=customer.id,
        customer_account_id=customer_account_id,
        job_number=_next_auto_key_job_number(session, auth.tenant_id),
        status_token=uuid4().hex,
        title=f"Pending — {first_token}",
        status="awaiting_customer_details",
        programming_status="not_required",
        priority="normal",
        key_quantity=1,
        deposit_cents=0,
        cost_cents=0,
        customer_intake_token=intake_token,
    )
    session.add(job)
    session.flush()

    tenant = session.get(Tenant, auth.tenant_id)
    shop_name = (tenant.name if tenant else None) or "Mainspring"
    intake_url = f"{settings.public_base_url.rstrip('/')}/mobile-job-intake/{intake_token}"
    sms.notify_auto_key_customer_intake(
        session,
        tenant_id=auth.tenant_id,
        to_phone=phone_raw,
        customer_name=customer.full_name or first_token,
        shop_name=shop_name,
        job_number=job.job_number,
        intake_url=intake_url,
    )
    session.commit()
    session.refresh(job)
    return job


@router.get("", response_model=list[AutoKeyJobRead])
def list_auto_key_jobs(
    status: str | None = Query(default=None),
    customer_id: UUID | None = Query(default=None, description="Filter by customer"),
    active_only: bool = Query(default=False, description="Exclude completed, collected, no_go"),
    date_from: str | None = Query(default=None, description="Filter scheduled_at >= date (YYYY-MM-DD)"),
    date_to: str | None = Query(default=None, description="Filter scheduled_at <= date (YYYY-MM-DD)"),
    include_unscheduled: bool = Query(default=False, description="With date range, also include jobs with no scheduled_at"),
    assigned_user_id: UUID | None = Query(default=None),
    auth: AuthContext = Depends(get_auth_context),
    session: Session = Depends(get_session),
):
    from sqlalchemy import or_

    cal_tz = settings.schedule_calendar_timezone
    query = select(AutoKeyJob).where(AutoKeyJob.tenant_id == auth.tenant_id)
    if status:
        query = query.where(AutoKeyJob.status == status)
    if customer_id:
        query = query.where(AutoKeyJob.customer_id == customer_id)
    if active_only:
        query = query.where(AutoKeyJob.status.notin_(["completed", "collected", "no_go"]))
    if assigned_user_id:
        query = query.where(AutoKeyJob.assigned_user_id == assigned_user_id)
    if date_from or date_to:
        if date_from and date_to and include_unscheduled:
            try:
                start, end = local_calendar_day_bounds_utc(cal_tz, date_from, date_to)
                if start is None or end is None:
                    raise ValueError("range")
                query = query.where(
                    or_(
                        (AutoKeyJob.scheduled_at >= start) & (AutoKeyJob.scheduled_at <= end),
                        AutoKeyJob.scheduled_at.is_(None),
                    )
                )
            except ValueError:
                raise HTTPException(status_code=400, detail="Invalid date format. Use YYYY-MM-DD for date_from/date_to")
        else:
            if date_from:
                try:
                    start, _ = local_calendar_day_bounds_utc(cal_tz, date_from, date_from)
                    if start is not None:
                        query = query.where(AutoKeyJob.scheduled_at >= start)
                except ValueError:
                    raise HTTPException(status_code=400, detail="Invalid date_from format. Use YYYY-MM-DD")
            if date_to:
                try:
                    _, end = local_calendar_day_bounds_utc(cal_tz, date_to, date_to)
                    if end is not None:
                        query = query.where(AutoKeyJob.scheduled_at <= end)
                except ValueError:
                    raise HTTPException(status_code=400, detail="Invalid date_to format. Use YYYY-MM-DD")
    return session.exec(
        query.order_by(
            AutoKeyJob.scheduled_at.asc(),
            AutoKeyJob.visit_order.asc(),
            AutoKeyJob.created_at.desc(),
        )
    ).all()


@router.get("/{job_id}", response_model=AutoKeyJobRead)
def get_auto_key_job(
    job_id: UUID,
    auth: AuthContext = Depends(get_auth_context),
    session: Session = Depends(get_session),
):
    job = session.get(AutoKeyJob, job_id)
    if not job or job.tenant_id != auth.tenant_id:
        raise HTTPException(status_code=404, detail="Auto key job not found")
    return job


@router.post("/{job_id}/status", response_model=AutoKeyJobRead)
def update_auto_key_job_status(
    job_id: UUID,
    payload: AutoKeyJobStatusUpdate,
    auth: AuthContext = Depends(require_tech_or_above),
    session: Session = Depends(get_session),
):
    job = session.get(AutoKeyJob, job_id)
    if not job or job.tenant_id != auth.tenant_id:
        raise HTTPException(status_code=404, detail="Auto key job not found")

    previous_status = job.status
    job.status = payload.status
    session.add(job)

    moved_to_en_route = previous_status != "en_route" and job.status == "en_route"
    if moved_to_en_route:
        customer = session.get(Customer, job.customer_id)
        phone = (customer.phone or "").strip() if customer else ""
        if customer and phone:
            tenant = session.get(Tenant, auth.tenant_id)
            shop_name = (tenant.name if tenant else None) or "We"
            sms.notify_auto_key_en_route(
                session,
                tenant_id=auth.tenant_id,
                to_phone=phone,
                customer_name=customer.full_name or "there",
                shop_name=shop_name,
                job_number=str(job.job_number),
                job_address=job.job_address,
                scheduled_at=job.scheduled_at,
            )

    moved_to_completed = previous_status != "completed" and job.status == "completed"
    if moved_to_completed:
        invoice = _ensure_auto_key_invoice_for_completed_job(session, auth.tenant_id, job)
        session.flush()
        if invoice:
            if not invoice.customer_view_token:
                invoice.customer_view_token = uuid4().hex
                session.add(invoice)
            session.flush()
            customer = session.get(Customer, job.customer_id)
            phone = (customer.phone or "").strip() if customer else ""
            if customer and phone:
                tenant = session.get(Tenant, auth.tenant_id)
                shop_name = (tenant.name if tenant else None) or "We"
                view_url = f"{settings.public_base_url.rstrip('/')}/mobile-invoice/{invoice.customer_view_token}"
                sms.notify_auto_key_invoice_ready(
                    session,
                    tenant_id=auth.tenant_id,
                    to_phone=phone,
                    customer_name=customer.full_name or "there",
                    shop_name=shop_name,
                    job_number=str(job.job_number),
                    invoice_number=invoice.invoice_number,
                    total_cents=invoice.total_cents,
                    currency=invoice.currency,
                    view_url=view_url,
                )

    session.commit()
    session.refresh(job)
    return job


@router.patch("/{job_id}", response_model=AutoKeyJobRead)
def update_auto_key_job_fields(
    job_id: UUID,
    payload: AutoKeyJobFieldUpdate,
    auth: AuthContext = Depends(require_tech_or_above),
    session: Session = Depends(get_session),
):
    job = session.get(AutoKeyJob, job_id)
    if not job or job.tenant_id != auth.tenant_id:
        raise HTTPException(status_code=404, detail="Auto key job not found")

    schedule_fields = {"scheduled_at", "job_address", "job_type"}
    old_scheduled_at = job.scheduled_at.isoformat() if job.scheduled_at else None
    old_job_address = job.job_address
    old_job_type = job.job_type

    update_data = payload.model_dump(exclude_unset=True)
    if "customer_account_id" in update_data and update_data["customer_account_id"] is not None:
        account = session.get(CustomerAccount, update_data["customer_account_id"])
        if not account or account.tenant_id != auth.tenant_id:
            raise HTTPException(status_code=404, detail="Customer account not found")
    for field, value in update_data.items():
        if field == "scheduled_at" and value is not None:
            value = naive_utc_from_any(value)
        setattr(job, field, value)

    if job.key_quantity < 1:
        job.key_quantity = 1

    schedule_changed = update_data.keys() & schedule_fields and (
        (job.scheduled_at.isoformat() if job.scheduled_at else None) != old_scheduled_at
        or job.job_address != old_job_address
        or job.job_type != old_job_type
    )
    to_notify_phone = None
    if schedule_changed and job.assigned_user_id:
        assigned_user = session.get(User, job.assigned_user_id)
        if assigned_user and assigned_user.phone and assigned_user.phone.strip():
            to_notify_phone = assigned_user.phone.strip()

    session.add(job)
    session.commit()

    if to_notify_phone:
        sms.notify_auto_key_schedule_changed(
            session,
            tenant_id=auth.tenant_id,
            to_phone=to_notify_phone,
            job_number=job.job_number,
            scheduled_at=job.scheduled_at.isoformat() if job.scheduled_at else None,
            job_address=job.job_address,
            job_type=job.job_type,
        )
        session.commit()

    if schedule_changed and job.job_address and job.scheduled_at and job.customer_id:
        customer = session.get(Customer, job.customer_id)
        if customer and customer.phone and customer.phone.strip():
            sms.notify_auto_key_customer_scheduled(
                session,
                tenant_id=auth.tenant_id,
                to_phone=customer.phone.strip(),
                customer_name=customer.full_name or "Customer",
                job_number=job.job_number,
                scheduled_at=job.scheduled_at.isoformat(),
                job_address=job.job_address,
            )
            session.commit()

    session.refresh(job)
    return job


@router.delete("/{job_id}", status_code=204, response_class=Response)
def delete_auto_key_job(
    job_id: UUID,
    auth: AuthContext = Depends(require_tech_or_above),
    session: Session = Depends(get_session),
):
    job = session.get(AutoKeyJob, job_id)
    if not job or job.tenant_id != auth.tenant_id:
        raise HTTPException(status_code=404, detail="Auto key job not found")

    quote_ids = session.exec(
        select(AutoKeyQuote.id)
        .where(AutoKeyQuote.tenant_id == auth.tenant_id)
        .where(AutoKeyQuote.auto_key_job_id == job_id)
    ).all()

    session.exec(
        delete(AutoKeyInvoice)
        .where(AutoKeyInvoice.tenant_id == auth.tenant_id)
        .where(AutoKeyInvoice.auto_key_job_id == job_id)
    )
    if quote_ids:
        session.exec(
            delete(AutoKeyQuoteLineItem)
            .where(AutoKeyQuoteLineItem.tenant_id == auth.tenant_id)
            .where(AutoKeyQuoteLineItem.auto_key_quote_id.in_(quote_ids))
        )
        session.exec(
            delete(AutoKeyQuote)
            .where(AutoKeyQuote.tenant_id == auth.tenant_id)
            .where(AutoKeyQuote.id.in_(quote_ids))
        )

    session.delete(job)
    session.commit()
    return Response(status_code=204)


@router.get("/{job_id}/quotes", response_model=list[AutoKeyQuoteRead])
def list_auto_key_quotes(
    job_id: UUID,
    auth: AuthContext = Depends(get_auth_context),
    session: Session = Depends(get_session),
):
    job = session.get(AutoKeyJob, job_id)
    if not job or job.tenant_id != auth.tenant_id:
        raise HTTPException(status_code=404, detail="Auto key job not found")

    quotes = session.exec(
        select(AutoKeyQuote)
        .where(AutoKeyQuote.tenant_id == auth.tenant_id)
        .where(AutoKeyQuote.auto_key_job_id == job_id)
        .order_by(AutoKeyQuote.created_at.desc())
    ).all()
    return [_to_quote_read(session, q) for q in quotes]


@router.post("/{job_id}/quotes", response_model=AutoKeyQuoteRead, status_code=201)
def create_auto_key_quote(
    job_id: UUID,
    payload: AutoKeyQuoteCreate,
    auth: AuthContext = Depends(require_tech_or_above),
    session: Session = Depends(get_session),
):
    job = session.get(AutoKeyJob, job_id)
    if not job or job.tenant_id != auth.tenant_id:
        raise HTTPException(status_code=404, detail="Auto key job not found")
    if not payload.line_items:
        raise HTTPException(status_code=400, detail="At least one line item is required")

    subtotal = 0
    quote = AutoKeyQuote(
        tenant_id=auth.tenant_id,
        auto_key_job_id=job_id,
        tax_cents=max(0, payload.tax_cents),
    )
    session.add(quote)
    session.flush()

    for item in payload.line_items:
        total_price = int(round(item.quantity * item.unit_price_cents))
        subtotal += total_price
        session.add(
            AutoKeyQuoteLineItem(
                tenant_id=auth.tenant_id,
                auto_key_quote_id=quote.id,
                description=item.description,
                quantity=item.quantity,
                unit_price_cents=item.unit_price_cents,
                total_price_cents=total_price,
            )
        )

    quote.subtotal_cents = subtotal
    quote.total_cents = subtotal + quote.tax_cents
    session.add(quote)
    session.commit()
    session.refresh(quote)
    return _to_quote_read(session, quote)


@router.post("/quotes/{quote_id}/send", response_model=AutoKeyQuoteRead)
def send_auto_key_quote(
    quote_id: UUID,
    auth: AuthContext = Depends(require_tech_or_above),
    session: Session = Depends(get_session),
):
    quote = session.get(AutoKeyQuote, quote_id)
    if not quote or quote.tenant_id != auth.tenant_id:
        raise HTTPException(status_code=404, detail="Auto key quote not found")

    quote.status = "sent"
    quote.sent_at = datetime.now(timezone.utc)
    session.add(quote)
    session.commit()
    session.refresh(quote)
    return _to_quote_read(session, quote)


@router.get("/{job_id}/invoices", response_model=list[AutoKeyInvoiceRead])
def list_auto_key_invoices(
    job_id: UUID,
    auth: AuthContext = Depends(get_auth_context),
    session: Session = Depends(get_session),
):
    job = session.get(AutoKeyJob, job_id)
    if not job or job.tenant_id != auth.tenant_id:
        raise HTTPException(status_code=404, detail="Auto key job not found")

    invoices = session.exec(
        select(AutoKeyInvoice)
        .where(AutoKeyInvoice.tenant_id == auth.tenant_id)
        .where(AutoKeyInvoice.auto_key_job_id == job_id)
        .order_by(AutoKeyInvoice.created_at.desc())
    ).all()
    return [
        AutoKeyInvoiceRead(
            id=i.id,
            tenant_id=i.tenant_id,
            auto_key_job_id=i.auto_key_job_id,
            auto_key_quote_id=i.auto_key_quote_id,
            invoice_number=i.invoice_number,
            status=i.status,
            subtotal_cents=i.subtotal_cents,
            tax_cents=i.tax_cents,
            total_cents=i.total_cents,
            currency=i.currency,
            payment_method=getattr(i, "payment_method", None),
            paid_at=getattr(i, "paid_at", None),
            created_at=i.created_at,
        )
        for i in invoices
    ]


@router.post("/{job_id}/invoices/from-quote/{quote_id}", response_model=AutoKeyInvoiceRead, status_code=201)
def create_auto_key_invoice_from_quote(
    job_id: UUID,
    quote_id: UUID,
    auth: AuthContext = Depends(require_tech_or_above),
    session: Session = Depends(get_session),
):
    job = session.get(AutoKeyJob, job_id)
    if not job or job.tenant_id != auth.tenant_id:
        raise HTTPException(status_code=404, detail="Auto key job not found")

    quote = session.get(AutoKeyQuote, quote_id)
    if not quote or quote.tenant_id != auth.tenant_id or quote.auto_key_job_id != job_id:
        raise HTTPException(status_code=404, detail="Auto key quote not found")

    existing = session.exec(
        select(AutoKeyInvoice)
        .where(AutoKeyInvoice.tenant_id == auth.tenant_id)
        .where(AutoKeyInvoice.auto_key_quote_id == quote_id)
    ).first()
    if existing:
        raise HTTPException(status_code=409, detail="Invoice already exists for this quote")

    invoice = AutoKeyInvoice(
        tenant_id=auth.tenant_id,
        auto_key_job_id=job_id,
        auto_key_quote_id=quote_id,
        invoice_number=_next_auto_key_invoice_number(session, auth.tenant_id),
        subtotal_cents=quote.subtotal_cents,
        tax_cents=quote.tax_cents,
        total_cents=quote.total_cents,
        currency=quote.currency,
    )
    session.add(invoice)
    session.commit()
    session.refresh(invoice)
    return AutoKeyInvoiceRead(
        id=invoice.id,
        tenant_id=invoice.tenant_id,
        auto_key_job_id=invoice.auto_key_job_id,
        auto_key_quote_id=invoice.auto_key_quote_id,
        invoice_number=invoice.invoice_number,
        status=invoice.status,
        subtotal_cents=invoice.subtotal_cents,
        tax_cents=invoice.tax_cents,
        total_cents=invoice.total_cents,
        currency=invoice.currency,
        payment_method=getattr(invoice, "payment_method", None),
        paid_at=getattr(invoice, "paid_at", None),
        created_at=invoice.created_at,
    )


class AutoKeyInvoiceUpdate(SQLModel):
    status: str | None = None
    payment_method: str | None = None  # cash, eftpos, bank, stripe


@router.patch("/{job_id}/invoices/{invoice_id}", response_model=AutoKeyInvoiceRead)
def update_auto_key_invoice(
    job_id: UUID,
    invoice_id: UUID,
    payload: AutoKeyInvoiceUpdate,
    auth: AuthContext = Depends(require_tech_or_above),
    session: Session = Depends(get_session),
):
    """Update auto key invoice (e.g. mark paid for POS completion)."""
    invoice = session.get(AutoKeyInvoice, invoice_id)
    if not invoice or invoice.tenant_id != auth.tenant_id or invoice.auto_key_job_id != job_id:
        raise HTTPException(status_code=404, detail="Auto key invoice not found")
    if payload.status is not None:
        if payload.status not in ("unpaid", "paid", "void"):
            raise HTTPException(status_code=400, detail="Invalid status")
        invoice.status = payload.status
        if payload.status == "paid":
            invoice.paid_at = datetime.now(timezone.utc)
        elif payload.status == "unpaid":
            invoice.paid_at = None
    if payload.payment_method is not None:
        v = (payload.payment_method or "").strip().lower()
        if v and v not in ("cash", "eftpos", "bank", "stripe"):
            raise HTTPException(status_code=400, detail="Invalid payment_method; use cash, eftpos, bank, or stripe")
        invoice.payment_method = v or None
    session.add(invoice)
    session.commit()
    session.refresh(invoice)
    return AutoKeyInvoiceRead(
        id=invoice.id,
        tenant_id=invoice.tenant_id,
        auto_key_job_id=invoice.auto_key_job_id,
        auto_key_quote_id=invoice.auto_key_quote_id,
        invoice_number=invoice.invoice_number,
        status=invoice.status,
        subtotal_cents=invoice.subtotal_cents,
        tax_cents=invoice.tax_cents,
        total_cents=invoice.total_cents,
        currency=invoice.currency,
        payment_method=getattr(invoice, "payment_method", None),
        paid_at=getattr(invoice, "paid_at", None),
        created_at=invoice.created_at,
    )


@router.post("/send-day-before-reminders", summary="Send SMS reminders to techs and customers for tomorrow's jobs")
def send_day_before_reminders(
    auth: AuthContext = Depends(require_tech_or_above),
    session: Session = Depends(get_session),
):
    """Call from a daily cron (e.g. 6pm) to remind assigned techs and customers of tomorrow's scheduled jobs."""
    now = datetime.now(timezone.utc)
    tomorrow_start = (now + timedelta(days=1)).replace(hour=0, minute=0, second=0, microsecond=0)
    tomorrow_end = tomorrow_start + timedelta(days=1)
    jobs = list(session.exec(
        select(AutoKeyJob)
        .where(AutoKeyJob.tenant_id == auth.tenant_id)
        .where(AutoKeyJob.scheduled_at >= tomorrow_start)
        .where(AutoKeyJob.scheduled_at < tomorrow_end)
    ).all())
    techs_notified = 0
    customers_notified = 0

    # Tech reminders (jobs with assigned tech)
    by_tech: dict[UUID, list[AutoKeyJob]] = {}
    for job in jobs:
        uid = job.assigned_user_id
        if uid:
            by_tech.setdefault(uid, []).append(job)
    for uid, job_list in by_tech.items():
        user = session.get(User, uid)
        if not user or not user.phone or not user.phone.strip():
            continue
        summaries = [f"#{j.job_number} {j.title or 'Auto key'}" for j in job_list]
        sms.notify_auto_key_day_before_reminder(
            session,
            tenant_id=auth.tenant_id,
            to_phone=user.phone.strip(),
            job_summaries=summaries,
        )
        session.commit()
        techs_notified += 1

    # Customer reminders (mobile jobs with customer phone)
    seen_customers: set[UUID] = set()
    for job in jobs:
        if not job.job_address or not job.customer_id or job.customer_id in seen_customers:
            continue
        customer = session.get(Customer, job.customer_id)
        if not customer or not customer.phone or not customer.phone.strip():
            continue
        sms.notify_auto_key_customer_day_before(
            session,
            tenant_id=auth.tenant_id,
            to_phone=customer.phone.strip(),
            customer_name=customer.full_name or "Customer",
            job_number=job.job_number,
            scheduled_at=job.scheduled_at.isoformat() if job.scheduled_at else None,
            job_address=job.job_address,
        )
        session.commit()
        seen_customers.add(job.customer_id)
        customers_notified += 1

    return {"techs_notified": techs_notified, "customers_notified": customers_notified}


class SendArrivalSmsPayload(SQLModel):
    time_window: str  # e.g. "9–11am", "2–4pm"


@router.post("/{job_id}/send-arrival-sms", summary="Send arrival window SMS to customer")
def send_arrival_sms(
    job_id: UUID,
    payload: SendArrivalSmsPayload,
    auth: AuthContext = Depends(get_auth_context),
    session: Session = Depends(get_session),
):
    """Send 'Tech arriving between [time_window]' SMS to the job's customer."""
    job = session.get(AutoKeyJob, job_id)
    if not job or job.tenant_id != auth.tenant_id:
        raise HTTPException(status_code=404, detail="Job not found")
    customer = session.get(Customer, job.customer_id) if job.customer_id else None
    if not customer or not customer.phone or not customer.phone.strip():
        raise HTTPException(status_code=400, detail="Customer has no phone number")
    time_window = (payload.time_window or "").strip()
    if not time_window:
        raise HTTPException(status_code=400, detail="Time window is required")
    sms.notify_auto_key_arrival_window(
        session,
        tenant_id=auth.tenant_id,
        to_phone=customer.phone.strip(),
        customer_name=customer.full_name or "Customer",
        job_number=job.job_number,
        time_window=time_window,
    )
    session.commit()
    return {"sent": True}
