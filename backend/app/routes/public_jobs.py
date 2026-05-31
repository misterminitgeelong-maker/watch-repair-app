import base64
import io
import importlib
import json
import logging
import re
from datetime import datetime, timedelta, timezone
from typing import Any, Optional
from uuid import UUID, uuid4

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import RedirectResponse, Response
from sqlmodel import Field, Session, SQLModel, select

from ..config import settings
from ..database import get_session

logger = logging.getLogger(__name__)
from ..datetime_utils import isoformat_z_utc, naive_utc_from_any
from ..models import (
    AutoKeyInvoice,
    AutoKeyJob,
    AutoKeyQuote,
    AutoKeyQuoteLineItem,
    Customer,
    JobStatusHistory,
    PortalSession,
    Quote,
    RepairJob,
    Shoe,
    ShoeJobStatusHistory,
    ShoeRepairJob,
    ShoeRepairJobItem,
    Tenant,
    TenantEventLog,
    Watch,
)

router = APIRouter(prefix="/v1/public", tags=["public-jobs"])

from .attachments import attachment_storage  # noqa: E402


def _next_aki_invoice_number(session: Session, tenant_id) -> str:
    from uuid import UUID as _UUID
    rows = session.exec(
        select(AutoKeyInvoice.invoice_number)
        .where(AutoKeyInvoice.tenant_id == tenant_id)
        .where(AutoKeyInvoice.invoice_number.like("AKI-%"))
    ).all()
    max_seq = 0
    pat = re.compile(r"^AKI-(\d+)$")
    for raw in rows:
        m = pat.match(str(raw or ""))
        if m:
            max_seq = max(max_seq, int(m.group(1)))
    candidate = max_seq + 1
    while True:
        number = f"AKI-{candidate:05d}"
        if not session.exec(
            select(AutoKeyInvoice.id)
            .where(AutoKeyInvoice.tenant_id == tenant_id)
            .where(AutoKeyInvoice.invoice_number == number)
        ).first():
            return number
        candidate += 1


class PublicAutoKeyIntakeSubmit(SQLModel):
    full_name: Optional[str] = Field(default=None, max_length=500)
    vehicle_make: Optional[str] = Field(default=None, max_length=120)
    vehicle_model: Optional[str] = Field(default=None, max_length=120)
    vehicle_year: Optional[int] = Field(default=None, ge=1900, le=2100)
    registration_plate: Optional[str] = Field(default=None, max_length=32)
    vin: Optional[str] = Field(default=None, max_length=64)
    job_address: Optional[str] = Field(default=None, max_length=500)
    job_type: Optional[str] = Field(default=None, max_length=200)
    additional_services: list[dict[str, Any]] = Field(default_factory=list)
    scheduled_at: Optional[datetime] = None
    description: Optional[str] = Field(default=None, max_length=4000)
    key_quantity: int = Field(default=1, ge=1, le=99)
    key_type: Optional[str] = Field(default=None, max_length=200)
    blade_code: Optional[str] = Field(default=None, max_length=120)
    chip_type: Optional[str] = Field(default=None, max_length=200)
    tech_notes: Optional[str] = Field(default=None, max_length=4000)


def _serialize_intake_services(items: list[Any] | None) -> str | None:
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
    return json.dumps(cleaned) if cleaned else None


def _customer_intake_title(customer_full_name: str, make: str | None, year: int | None, model: str | None) -> str:
    parts = (customer_full_name or "").strip().split()
    first = parts[0] if parts else "Customer"
    bits: list[str] = []
    if make and str(make).strip():
        bits.append(str(make).strip())
    if year is not None:
        bits.append(str(year))
    if model and str(model).strip():
        bits.append(str(model).strip())
    car = " ".join(bits)
    return f"{first} - {car}" if car else f"{first} - Job"


@router.get("/jobs/{status_token}")
def get_public_job_status(status_token: str, session: Session = Depends(get_session)):
    job = session.exec(select(RepairJob).where(RepairJob.status_token == status_token)).first()
    if not job:
        raise HTTPException(status_code=404, detail="Invalid or expired link")

    watch = session.get(Watch, job.watch_id)
    history = session.exec(
        select(JobStatusHistory)
        .where(JobStatusHistory.repair_job_id == job.id)
        .order_by(JobStatusHistory.created_at)
    ).all()

    return {
        "job_number": job.job_number,
        "status": job.status,
        "title": job.title,
        "description": job.description,
        "priority": job.priority,
        "pre_quote_cents": job.pre_quote_cents,
        "created_at": job.created_at,
        "collection_date": job.collection_date.isoformat() if job.collection_date else None,
        "watch": {
            "brand": watch.brand if watch else None,
            "model": watch.model if watch else None,
            "serial_number": watch.serial_number if watch else None,
        },
        "history": [
            {
                "old_status": entry.old_status,
                "new_status": entry.new_status,
                "change_note": entry.change_note,
                "created_at": entry.created_at,
            }
            for entry in history
        ],
    }


@router.get("/jobs/{status_token}/qr")
def get_public_job_qr(status_token: str, session: Session = Depends(get_session)):
    job = session.exec(select(RepairJob).where(RepairJob.status_token == status_token)).first()
    if not job:
        raise HTTPException(status_code=404, detail="Invalid or expired link")

    target_url = f"{settings.public_base_url}/status/{status_token}"
    qrcode = importlib.import_module("qrcode")
    image = qrcode.make(target_url)
    buffer = io.BytesIO()
    image.save(buffer, format="PNG")
    return Response(content=buffer.getvalue(), media_type="image/png")


@router.get("/shoe-jobs/{status_token}")
def get_public_shoe_job_status(status_token: str, session: Session = Depends(get_session)):
    job = session.exec(select(ShoeRepairJob).where(ShoeRepairJob.status_token == status_token)).first()
    if not job:
        raise HTTPException(status_code=404, detail="Invalid or expired link")

    shoe = session.get(Shoe, job.shoe_id)
    items = session.exec(
        select(ShoeRepairJobItem)
        .where(ShoeRepairJobItem.shoe_repair_job_id == job.id)
        .order_by(ShoeRepairJobItem.created_at)
    ).all()
    history = session.exec(
        select(ShoeJobStatusHistory)
        .where(ShoeJobStatusHistory.shoe_repair_job_id == job.id)
        .order_by(ShoeJobStatusHistory.created_at.asc())
    ).all()
    estimated_total_cents = int(
        sum((item.unit_price_cents or 0) * item.quantity for item in items if item.unit_price_cents is not None)
    )

    return {
        "job_number": job.job_number,
        "status": job.status,
        "title": job.title,
        "description": job.description,
        "priority": job.priority,
        "deposit_cents": job.deposit_cents,
        "estimated_total_cents": estimated_total_cents,
        "created_at": job.created_at,
        "shoe": {
            "shoe_type": shoe.shoe_type if shoe else None,
            "brand": shoe.brand if shoe else None,
            "color": shoe.color if shoe else None,
        },
        "items": [
            {
                "item_name": item.item_name,
                "quantity": item.quantity,
                "unit_price_cents": item.unit_price_cents,
                "notes": item.notes,
            }
            for item in items
        ],
        "history": [
            {
                "old_status": h.old_status,
                "new_status": h.new_status,
                "change_note": h.change_note,
                "created_at": isoformat_z_utc(naive_utc_from_any(h.created_at)),
            }
            for h in history
            if h.new_status != (h.old_status or "")
        ],
    }


@router.get("/shoe-jobs/{status_token}/qr")
def get_public_shoe_job_qr(status_token: str, session: Session = Depends(get_session)):
    job = session.exec(select(ShoeRepairJob).where(ShoeRepairJob.status_token == status_token)).first()
    if not job:
        raise HTTPException(status_code=404, detail="Invalid or expired link")

    target_url = f"{settings.public_base_url}/shoe-status/{status_token}"
    qrcode = importlib.import_module("qrcode")
    image = qrcode.make(target_url)
    buffer = io.BytesIO()
    image.save(buffer, format="PNG")
    return Response(content=buffer.getvalue(), media_type="image/png")


# ── Shoe quote approval (public) ────────────────────────────────────────────

def _shoe_quote_token_is_expired(job: ShoeRepairJob) -> bool:
    if not job.quote_approval_token_expires_at:
        return False
    exp = job.quote_approval_token_expires_at
    if exp.tzinfo is None:
        exp = exp.replace(tzinfo=timezone.utc)
    return datetime.now(timezone.utc) > exp


@router.get("/shoe-quotes/{token}")
def get_public_shoe_quote(token: str, session: Session = Depends(get_session)):
    job = session.exec(select(ShoeRepairJob).where(ShoeRepairJob.quote_approval_token == token)).first()
    if not job:
        raise HTTPException(status_code=404, detail="Invalid or expired link")
    if _shoe_quote_token_is_expired(job):
        raise HTTPException(status_code=410, detail="This quote link has expired. Please contact the shop for a new one.")

    items = session.exec(
        select(ShoeRepairJobItem).where(ShoeRepairJobItem.shoe_repair_job_id == job.id).order_by(ShoeRepairJobItem.created_at)
    ).all()
    shoe = session.get(Shoe, job.shoe_id)

    subtotal_cents = int(sum((i.unit_price_cents or 0) * i.quantity for i in items if i.unit_price_cents is not None))

    # Get shop name from tenant
    tenant = session.get(Tenant, job.tenant_id)
    shop_name = (tenant.name if tenant else None) or "Shoe Repair Shop"

    return {
        "job_number": job.job_number,
        "title": job.title,
        "description": job.description,
        "quote_status": job.quote_status,
        "quote_approval_token_expires_at": isoformat_z_utc(naive_utc_from_any(job.quote_approval_token_expires_at)) if job.quote_approval_token_expires_at else None,
        "shop_name": shop_name,
        "shoe": {
            "shoe_type": shoe.shoe_type if shoe else None,
            "brand": shoe.brand if shoe else None,
            "color": shoe.color if shoe else None,
        },
        "items": [
            {
                "item_name": i.item_name,
                "quantity": i.quantity,
                "unit_price_cents": i.unit_price_cents,
                "notes": i.notes,
            }
            for i in items
        ],
        "subtotal_cents": subtotal_cents,
    }


class ShoeQuoteDecisionRequest(SQLModel):
    decision: str  # "approved" | "declined"
    customer_signature_data_url: Optional[str] = None


@router.post("/shoe-quotes/{token}/decision")
def decide_shoe_quote(
    token: str,
    payload: ShoeQuoteDecisionRequest,
    session: Session = Depends(get_session),
):
    job = session.exec(select(ShoeRepairJob).where(ShoeRepairJob.quote_approval_token == token)).first()
    if not job:
        raise HTTPException(status_code=404, detail="Invalid or expired link")
    if _shoe_quote_token_is_expired(job):
        raise HTTPException(status_code=410, detail="This quote link has expired.")
    if job.quote_status in ("approved", "declined"):
        raise HTTPException(status_code=409, detail=f"This quote has already been {job.quote_status}.")

    decision = payload.decision.lower()
    if decision not in ("approved", "declined"):
        raise HTTPException(status_code=422, detail="decision must be 'approved' or 'declined'")

    job.quote_status = decision
    if decision == "approved":
        job.status = "go_ahead"
    else:
        job.status = "no_go"
    session.add(job)

    # Status history
    session.add(ShoeJobStatusHistory(
        tenant_id=job.tenant_id,
        shoe_repair_job_id=job.id,
        old_status="awaiting_go_ahead",
        new_status=job.status,
        change_note=f"Customer {decision} quote via online link",
    ))

    # Inbox event
    event_type = "quote_approved" if decision == "approved" else "quote_declined"
    summary = (
        f"Customer approved shoe repair quote for job #{job.job_number}"
        if decision == "approved"
        else f"Customer declined shoe repair quote for job #{job.job_number}"
    )
    session.add(TenantEventLog(
        tenant_id=job.tenant_id,
        entity_type="shoe_repair_job",
        entity_id=job.id,
        event_type=event_type,
        event_summary=summary,
    ))

    session.commit()
    return {"decision": decision, "job_number": job.job_number}


@router.get("/auto-key-booking/{token}")
def get_public_auto_key_booking(token: str, session: Session = Depends(get_session)):
    job = session.exec(select(AutoKeyJob).where(AutoKeyJob.booking_confirmation_token == token)).first()
    if not job:
        raise HTTPException(status_code=404, detail="Invalid or expired link")

    quote = session.exec(
        select(AutoKeyQuote)
        .where(AutoKeyQuote.auto_key_job_id == job.id)
        .order_by(AutoKeyQuote.created_at.desc())
    ).first()
    line_payload: list[dict] = []
    if quote:
        items = session.exec(
            select(AutoKeyQuoteLineItem)
            .where(AutoKeyQuoteLineItem.auto_key_quote_id == quote.id)
            .order_by(AutoKeyQuoteLineItem.created_at)
        ).all()
        line_payload = [
            {
                "description": i.description,
                "quantity": i.quantity,
                "unit_price_cents": i.unit_price_cents,
                "total_price_cents": i.total_price_cents,
            }
            for i in items
        ]

    return {
        "job_id": str(job.id),
        "status_token": job.status_token,
        "job_number": job.job_number,
        "title": job.title,
        "status": job.status,
        "vehicle_make": job.vehicle_make,
        "vehicle_model": job.vehicle_model,
        "scheduled_at": isoformat_z_utc(job.scheduled_at),
        "job_address": job.job_address,
        "quote_total_cents": quote.total_cents if quote else 0,
        "subtotal_cents": quote.subtotal_cents if quote else 0,
        "tax_cents": quote.tax_cents if quote else 0,
        "currency": quote.currency if quote else "AUD",
        "line_items": line_payload,
        "already_confirmed": job.status == "booked",
    }


class AutoKeyBookingConfirmBody(SQLModel):
    signature_data: Optional[str] = None  # base64 PNG (no data: prefix)
    signer_name: Optional[str] = None


@router.post("/auto-key-booking/{token}/confirm")
def confirm_public_auto_key_booking(
    token: str,
    body: AutoKeyBookingConfirmBody = AutoKeyBookingConfirmBody(),
    session: Session = Depends(get_session),
):
    job = session.exec(select(AutoKeyJob).where(AutoKeyJob.booking_confirmation_token == token)).first()
    if not job:
        raise HTTPException(status_code=404, detail="Invalid or expired link")
    if job.status == "booked":
        return {"ok": True, "status": "booked", "message": "Booking was already confirmed."}
    if job.status != "pending_booking":
        raise HTTPException(
            status_code=400,
            detail="This job is not awaiting booking confirmation.",
        )
    job.status = "booked"
    session.add(job)

    quote = session.exec(
        select(AutoKeyQuote)
        .where(AutoKeyQuote.auto_key_job_id == job.id)
        .order_by(AutoKeyQuote.created_at.desc())
    ).first()
    if quote and quote.status == "draft":
        quote.status = "approved"
        session.add(quote)

    if quote and body.signature_data:
        try:
            raw_b64 = body.signature_data
            if "," in raw_b64:
                raw_b64 = raw_b64.split(",", 1)[1]
            png_bytes = base64.b64decode(raw_b64)
            storage_key = f"quote-signatures/{quote.id}/{uuid4().hex}_booking_signature.png"
            attachment_storage.save_bytes(storage_key, png_bytes, content_type="image/png")
            quote.signature_storage_key = storage_key
            quote.signed_at = datetime.now(timezone.utc)
            quote.signer_name = (body.signer_name or "").strip() or None
            session.add(quote)
        except Exception:
            logger.exception("booking_signature_upload_failed job=%s", job.id)

    session.commit()
    session.refresh(job)
    return {"ok": True, "status": "booked", "message": "Thanks — your booking is confirmed."}


@router.get("/auto-key-intake/{token}")
def get_public_auto_key_intake(token: str, session: Session = Depends(get_session)):
    job = session.exec(
        select(AutoKeyJob).where(AutoKeyJob.customer_intake_token == token)
    ).first()
    if not job or job.status != "awaiting_customer_details":
        raise HTTPException(status_code=404, detail="Invalid or expired link")

    tenant = session.get(Tenant, job.tenant_id)
    customer = session.get(Customer, job.customer_id)
    shop_name = (tenant.name if tenant else "") or "Shop"
    hint = (customer.full_name or "").strip().split()[0] if customer and customer.full_name else None

    return {
        "job_id": str(job.id),
        "status_token": job.status_token,
        "shop_name": shop_name,
        "job_number": job.job_number,
        "customer_first_name_hint": hint,
        "vehicle_make": job.vehicle_make,
        "vehicle_model": job.vehicle_model,
        "vehicle_year": job.vehicle_year,
        "registration_plate": job.registration_plate,
        "job_address": job.job_address,
        "job_type": job.job_type,
    }


@router.post("/auto-key-intake/{token}/submit")
def submit_public_auto_key_intake(
    token: str,
    payload: PublicAutoKeyIntakeSubmit,
    session: Session = Depends(get_session),
):
    job = session.exec(
        select(AutoKeyJob).where(AutoKeyJob.customer_intake_token == token)
    ).first()
    if not job or job.status != "awaiting_customer_details":
        raise HTTPException(status_code=404, detail="Invalid or expired link")

    if not any(
        [
            (payload.job_type or "").strip(),
            (payload.vehicle_make or "").strip(),
            (payload.description or "").strip(),
        ]
    ):
        raise HTTPException(
            status_code=400,
            detail="Please add at least a vehicle or describe what you need.",
        )

    customer = session.get(Customer, job.customer_id)
    if not customer:
        raise HTTPException(status_code=404, detail="Customer not found")

    if (payload.full_name or "").strip():
        customer.full_name = (payload.full_name or "").strip()
        session.add(customer)

    job.vehicle_make = (payload.vehicle_make or "").strip() or None
    job.vehicle_model = (payload.vehicle_model or "").strip() or None
    job.vehicle_year = payload.vehicle_year
    job.registration_plate = (payload.registration_plate or "").strip() or None
    job.vin = (payload.vin or "").strip() or None
    job.job_address = (payload.job_address or "").strip() or None
    job.job_type = (payload.job_type or "").strip() or None
    job.description = (payload.description or "").strip() or None
    job.key_quantity = max(1, int(payload.key_quantity))
    job.key_type = (payload.key_type or "").strip() or None
    job.blade_code = (payload.blade_code or "").strip() or None
    job.chip_type = (payload.chip_type or "").strip() or None
    job.tech_notes = (payload.tech_notes or "").strip() or None
    job.additional_services_json = _serialize_intake_services(payload.additional_services)

    if payload.scheduled_at:
        job.scheduled_at = naive_utc_from_any(payload.scheduled_at)
    session.flush()

    job.title = _customer_intake_title(
        customer.full_name,
        job.vehicle_make,
        job.vehicle_year,
        job.vehicle_model,
    )
    job.status = "awaiting_quote"
    job.customer_intake_token = None
    session.add(job)
    session.commit()
    session.refresh(job)
    return {"ok": True, "message": "Thanks — we have your details and will be in touch."}


@router.get("/auto-key-invoice/{token}")
def get_public_auto_key_invoice(token: str, session: Session = Depends(get_session)):
    invoice = session.exec(
        select(AutoKeyInvoice).where(AutoKeyInvoice.customer_view_token == token)
    ).first()
    if not invoice:
        raise HTTPException(status_code=404, detail="Invalid or expired link")

    job = session.get(AutoKeyJob, invoice.auto_key_job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Invalid or expired link")

    tenant = session.get(Tenant, invoice.tenant_id)
    shop_name = tenant.name if tenant else ""

    line_payload: list[dict] = []
    if invoice.auto_key_quote_id:
        items = session.exec(
            select(AutoKeyQuoteLineItem)
            .where(AutoKeyQuoteLineItem.auto_key_quote_id == invoice.auto_key_quote_id)
            .order_by(AutoKeyQuoteLineItem.created_at)
        ).all()
        line_payload = [
            {
                "description": i.description,
                "quantity": i.quantity,
                "unit_price_cents": i.unit_price_cents,
                "total_price_cents": i.total_price_cents,
            }
            for i in items
        ]
    else:
        line_payload = [
            {
                "description": job.title or "Mobile service",
                "quantity": 1,
                "unit_price_cents": invoice.subtotal_cents,
                "total_price_cents": invoice.subtotal_cents,
            }
        ]

    connect_ready = bool(
        tenant
        and (tenant.stripe_connect_account_id or "").strip()
        and tenant.stripe_connect_charges_enabled
    )
    pay_online = (
        settings.enable_stripe_invoice_checkout
        and bool((settings.stripe_secret_key or "").strip())
        and invoice.status == "unpaid"
        and invoice.total_cents > 0
        and connect_ready
    )

    return {
        "shop_name": shop_name,
        "job_number": job.job_number,
        "job_title": job.title,
        "invoice_number": invoice.invoice_number,
        "status": invoice.status,
        "subtotal_cents": invoice.subtotal_cents,
        "tax_cents": invoice.tax_cents,
        "total_cents": invoice.total_cents,
        "currency": invoice.currency,
        "line_items": line_payload,
        "created_at": invoice.created_at.isoformat() if invoice.created_at else None,
        "can_pay_online": pay_online,
    }


def _stripe_checkout_client():
    if not (settings.stripe_secret_key or "").strip():
        return None
    try:
        import stripe as stripe_mod

        stripe_mod.api_key = settings.stripe_secret_key.strip()
        return stripe_mod
    except ImportError:
        return None


@router.post("/auto-key-invoice/{token}/checkout")
def create_public_auto_key_invoice_checkout(token: str, session: Session = Depends(get_session)):
    """Start Stripe Checkout for a Mobile Services invoice (customer pays online)."""
    if not settings.enable_stripe_invoice_checkout:
        raise HTTPException(status_code=503, detail="Online invoice payment is disabled.")
    stripe = _stripe_checkout_client()
    if not stripe:
        raise HTTPException(status_code=503, detail="Card payment is not configured for this shop.")

    invoice = session.exec(
        select(AutoKeyInvoice).where(AutoKeyInvoice.customer_view_token == token)
    ).first()
    if not invoice:
        raise HTTPException(status_code=404, detail="Invalid or expired link")

    if invoice.status != "unpaid":
        raise HTTPException(status_code=409, detail="This invoice is already paid or void.")
    if invoice.total_cents <= 0:
        raise HTTPException(status_code=400, detail="Nothing to pay on this invoice.")

    job = session.get(AutoKeyJob, invoice.auto_key_job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Invalid or expired link")

    tenant = session.get(Tenant, invoice.tenant_id)
    if not tenant or not (tenant.stripe_connect_account_id or "").strip():
        raise HTTPException(
            status_code=503,
            detail="This shop has not finished Stripe Connect setup; online card payment is unavailable.",
        )
    if not tenant.stripe_connect_charges_enabled:
        raise HTTPException(
            status_code=503,
            detail="This shop cannot accept card payments yet. Complete Stripe Connect onboarding in workspace settings.",
        )
    shop = (tenant.name if tenant else "Shop").strip() or "Shop"
    currency = (invoice.currency or "AUD").lower().strip()[:3]
    if len(currency) != 3:
        raise HTTPException(status_code=400, detail="Invalid invoice currency.")

    # Stripe minimum amounts (e.g. ~A$0.50); keep simple threshold
    if invoice.total_cents < 50:
        raise HTTPException(
            status_code=400,
            detail="Amount is below the minimum for card payment. Pay the shop directly.",
        )

    base = settings.public_base_url.rstrip("/")
    product_name = f"{shop} — Invoice {invoice.invoice_number} (total incl. tax)"
    if len(product_name) > 120:
        product_name = product_name[:117] + "…"

    params: dict = {
        "mode": "payment",
        "line_items": [
            {
                "price_data": {
                    "currency": currency,
                    "unit_amount": invoice.total_cents,
                    "product_data": {"name": product_name},
                },
                "quantity": 1,
            }
        ],
        "metadata": {
            "purpose": "auto_key_invoice",
            "tenant_id": str(invoice.tenant_id),
            "auto_key_invoice_id": str(invoice.id),
            "customer_view_token": token,
        },
        "success_url": f"{base}/mobile-invoice/{token}?paid=1&session_id={{CHECKOUT_SESSION_ID}}",
        "cancel_url": f"{base}/mobile-invoice/{token}?canceled=1",
        "payment_intent_data": {"transfer_data": {"destination": tenant.stripe_connect_account_id.strip()}},
    }

    customer = session.get(Customer, job.customer_id)
    if customer and (customer.email or "").strip():
        params["customer_email"] = (customer.email or "").strip()

    try:
        checkout = stripe.checkout.Session.create(**params)
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=502, detail="Could not start payment. Try again later.") from exc

    url = getattr(checkout, "url", None)
    if not url:
        raise HTTPException(status_code=502, detail="Could not start payment session.")

    return {"checkout_url": url}


@router.get("/auto-key-jobs/{status_token}")
def get_public_auto_key_job_status(status_token: str, session: Session = Depends(get_session)):
    """Public job summary for customer portal detail view (status_token is the opaque link id)."""
    job = session.exec(select(AutoKeyJob).where(AutoKeyJob.status_token == status_token)).first()
    if not job:
        raise HTTPException(status_code=404, detail="Invalid or expired link")

    tenant = session.get(Tenant, job.tenant_id)
    quote = session.exec(
        select(AutoKeyQuote)
        .where(AutoKeyQuote.auto_key_job_id == job.id)
        .order_by(AutoKeyQuote.created_at.desc())
    ).first()

    return {
        "job_number": job.job_number,
        "title": job.title,
        "status": job.status,
        "description": job.description,
        "vehicle_make": job.vehicle_make,
        "vehicle_model": job.vehicle_model,
        "vehicle_year": job.vehicle_year,
        "job_address": job.job_address,
        "scheduled_at": isoformat_z_utc(job.scheduled_at),
        "created_at": isoformat_z_utc(naive_utc_from_any(job.created_at)),
        "shop_name": tenant.name if tenant else "Mobile Services",
        "shop_phone": tenant.shop_phone if tenant else None,
        "shop_email": tenant.shop_email if tenant else None,
        "quote_total_cents": quote.total_cents if quote else 0,
        "currency": quote.currency if quote else "AUD",
        "pending_actions": _portal_pending_actions_for_auto_key(session, job),
    }


# ── Customer portal lookup ───────────────────────────────────────────────────

_PORTAL_WATCH_HISTORY_STATUSES = frozenset({"collected", "cancelled"})
_PORTAL_SHOE_HISTORY_STATUSES = frozenset({"collected", "no_go"})
_PORTAL_AUTO_KEY_HISTORY_STATUSES = frozenset({
    "booking_completed",
    "work_completed",
    "invoice_paid",
    "failed_job",
    "cancelled",
})
_PORTAL_MAX_JOBS_PER_SHOP = 50


class CustomerPortalJobRead(SQLModel):
    type: str  # watch | shoe | auto_key
    job_number: str
    title: str
    status: str
    created_at: str
    status_token: str
    status_url: str
    detail: Optional[str] = None
    pending_actions: list[dict[str, Any]] = Field(default_factory=list)


class CustomerPortalShopRead(SQLModel):
    tenant_id: str
    shop_name: str
    logo_url: Optional[str] = None
    brand_color: Optional[str] = None
    shop_phone: Optional[str] = None
    shop_email: Optional[str] = None
    jobs: list[CustomerPortalJobRead] = Field(default_factory=list)


class CustomerPortalLookupResponse(SQLModel):
    email: Optional[str] = None
    shops: list[CustomerPortalShopRead] = Field(default_factory=list)


def _portal_pending_actions_for_watch(session: Session, job: RepairJob) -> list[dict[str, Any]]:
    quote = session.exec(
        select(Quote)
        .where(Quote.repair_job_id == job.id)
        .where(Quote.status == "sent")
        .order_by(Quote.created_at.desc())
    ).first()
    if quote:
        return [{
            "kind": "watch_quote_decision",
            "token": quote.approval_token,
            "url": f"/approve/{quote.approval_token}",
        }]
    return []


def _portal_pending_actions_for_shoe(job: ShoeRepairJob) -> list[dict[str, Any]]:
    if job.quote_status == "sent" and job.quote_approval_token:
        return [{
            "kind": "shoe_quote_decision",
            "token": job.quote_approval_token,
            "url": f"/shoe-approve/{job.quote_approval_token}",
        }]
    return []


def _portal_pending_actions_for_auto_key(session: Session, job: AutoKeyJob) -> list[dict[str, Any]]:
    actions: list[dict[str, Any]] = []

    quote = session.exec(
        select(AutoKeyQuote)
        .where(AutoKeyQuote.auto_key_job_id == job.id)
        .where(AutoKeyQuote.status.in_(("draft", "sent")))  # type: ignore[attr-defined]
        .order_by(AutoKeyQuote.created_at.desc())
    ).first()
    if quote and quote.status == "sent" and quote.quote_approval_token:
        actions.append({
            "kind": "auto_key_quote_decision",
            "token": quote.quote_approval_token,
            "url": f"/mobile-quote/{quote.quote_approval_token}",
        })

    if job.status == "pending_booking" and job.booking_confirmation_token:
        actions.append({
            "kind": "auto_key_booking_confirm",
            "token": job.booking_confirmation_token,
            "url": f"/mobile-booking/{job.booking_confirmation_token}",
        })

    invoice = session.exec(
        select(AutoKeyInvoice)
        .where(AutoKeyInvoice.auto_key_job_id == job.id)
        .where(AutoKeyInvoice.status == "unpaid")
        .order_by(AutoKeyInvoice.created_at.desc())
    ).first()
    if invoice and invoice.customer_view_token:
        actions.append({
            "kind": "auto_key_invoice_checkout",
            "token": invoice.customer_view_token,
            "url": f"/mobile-invoice/{invoice.customer_view_token}",
        })

    return actions


def _serialize_portal_watch_job(session: Session, job: RepairJob) -> CustomerPortalJobRead:
    watch = session.get(Watch, job.watch_id) if job.watch_id else None
    detail = f"{watch.brand} {watch.model}".strip() if watch else None
    return CustomerPortalJobRead(
        type="watch",
        job_number=job.job_number,
        title=job.title,
        status=job.status,
        created_at=isoformat_z_utc(naive_utc_from_any(job.created_at)),
        status_token=job.status_token,
        status_url=f"/status/{job.status_token}",
        detail=detail or None,
        pending_actions=_portal_pending_actions_for_watch(session, job),
    )


def _serialize_portal_shoe_job(session: Session, job: ShoeRepairJob) -> CustomerPortalJobRead:
    shoe = session.get(Shoe, job.shoe_id)
    detail = " ".join(filter(None, [shoe.brand if shoe else None, shoe.shoe_type if shoe else None])) or None
    return CustomerPortalJobRead(
        type="shoe",
        job_number=job.job_number,
        title=job.title,
        status=job.status,
        created_at=isoformat_z_utc(naive_utc_from_any(job.created_at)),
        status_token=job.status_token,
        status_url=f"/shoe-status/{job.status_token}",
        detail=detail,
        pending_actions=_portal_pending_actions_for_shoe(job),
    )


def _serialize_portal_auto_key_job(session: Session, job: AutoKeyJob) -> CustomerPortalJobRead:
    vehicle_bits = [job.vehicle_make, str(job.vehicle_year) if job.vehicle_year else None, job.vehicle_model]
    detail = " ".join(filter(None, vehicle_bits)) or None
    return CustomerPortalJobRead(
        type="auto_key",
        job_number=job.job_number,
        title=job.title,
        status=job.status,
        created_at=isoformat_z_utc(naive_utc_from_any(job.created_at)),
        status_token=job.status_token,
        status_url=f"/customer-portal/job/auto_key/{job.status_token}",
        detail=detail,
        pending_actions=_portal_pending_actions_for_auto_key(session, job),
    )


def _collect_customer_jobs(
    session: Session,
    email: str,
    *,
    include_history: bool = False,
) -> CustomerPortalLookupResponse:
    """Cross-tenant job lookup grouped by shop. OTP gate can wrap this later."""
    normalized = (email or "").strip().lower()
    customers = session.exec(
        select(Customer).where(Customer.email.ilike(normalized))  # type: ignore[attr-defined]
    ).all()
    if not customers:
        return CustomerPortalLookupResponse(email=normalized, shops=[])

    customers_by_tenant: dict[UUID, list[Customer]] = {}
    for customer in customers:
        customers_by_tenant.setdefault(customer.tenant_id, []).append(customer)

    shops: list[CustomerPortalShopRead] = []
    for tenant_id, tenant_customers in customers_by_tenant.items():
        tenant = session.get(Tenant, tenant_id)
        shop_jobs: list[CustomerPortalJobRead] = []
        seen_job_keys: set[tuple[str, str]] = set()

        for customer in tenant_customers:
            watch_ids = session.exec(select(Watch.id).where(Watch.customer_id == customer.id)).all()
            if watch_ids:
                watch_query = (
                    select(RepairJob)
                    .where(RepairJob.watch_id.in_(watch_ids))  # type: ignore[attr-defined]
                    .order_by(RepairJob.created_at.desc())
                    .limit(20)
                )
                if not include_history:
                    watch_query = watch_query.where(
                        RepairJob.status.not_in(list(_PORTAL_WATCH_HISTORY_STATUSES))  # type: ignore[attr-defined]
                    )
                for job in session.exec(watch_query).all():
                    key = ("watch", job.job_number)
                    if key in seen_job_keys:
                        continue
                    seen_job_keys.add(key)
                    shop_jobs.append(_serialize_portal_watch_job(session, job))

            shoe_ids = session.exec(select(Shoe.id).where(Shoe.customer_id == customer.id)).all()
            if shoe_ids:
                shoe_query = (
                    select(ShoeRepairJob)
                    .where(ShoeRepairJob.shoe_id.in_(shoe_ids))  # type: ignore[attr-defined]
                    .order_by(ShoeRepairJob.created_at.desc())
                    .limit(20)
                )
                if not include_history:
                    shoe_query = shoe_query.where(
                        ShoeRepairJob.status.not_in(list(_PORTAL_SHOE_HISTORY_STATUSES))  # type: ignore[attr-defined]
                    )
                for job in session.exec(shoe_query).all():
                    key = ("shoe", job.job_number)
                    if key in seen_job_keys:
                        continue
                    seen_job_keys.add(key)
                    shop_jobs.append(_serialize_portal_shoe_job(session, job))

            auto_key_query = (
                select(AutoKeyJob)
                .where(AutoKeyJob.customer_id == customer.id)
                .where(AutoKeyJob.tenant_id == tenant_id)
                .order_by(AutoKeyJob.created_at.desc())
                .limit(20)
            )
            if not include_history:
                auto_key_query = auto_key_query.where(
                    AutoKeyJob.status.not_in(list(_PORTAL_AUTO_KEY_HISTORY_STATUSES))  # type: ignore[attr-defined]
                )
            for job in session.exec(auto_key_query).all():
                key = ("auto_key", job.job_number)
                if key in seen_job_keys:
                    continue
                seen_job_keys.add(key)
                shop_jobs.append(_serialize_portal_auto_key_job(session, job))

        if shop_jobs:
            shop_jobs.sort(key=lambda j: j.created_at, reverse=True)
            shops.append(
                CustomerPortalShopRead(
                    tenant_id=str(tenant_id),
                    shop_name=(tenant.name if tenant else None) or "Shop",
                    logo_url=tenant.logo_url if tenant else None,
                    brand_color=tenant.brand_color if tenant else None,
                    shop_phone=tenant.shop_phone if tenant else None,
                    shop_email=tenant.shop_email if tenant else None,
                    jobs=shop_jobs[:_PORTAL_MAX_JOBS_PER_SHOP],
                )
            )

    shops.sort(key=lambda s: s.shop_name.lower())
    return CustomerPortalLookupResponse(email=normalized, shops=shops)


class CustomerLookupRequest(SQLModel):
    email: str
    include_history: bool = False


@router.post("/customer-lookup", response_model=CustomerPortalLookupResponse)
def customer_lookup(
    payload: CustomerLookupRequest,
    include_history: bool = Query(default=False),
    session: Session = Depends(get_session),
):
    """Return all jobs for a customer by email address (cross-tenant, grouped by shop)."""
    email = (payload.email or "").strip().lower()
    if not email or "@" not in email:
        raise HTTPException(status_code=422, detail="Please enter a valid email address.")
    return _collect_customer_jobs(
        session,
        email,
        include_history=include_history or payload.include_history,
    )


# ── Customer portal sessions ─────────────────────────────────────────────────

_PORTAL_SESSION_TTL_DAYS = 30


class PortalSessionRequest(SQLModel):
    email: str


@router.post("/portal/create-session")
def create_portal_session(payload: PortalSessionRequest, session: Session = Depends(get_session)):
    """Create a 30-day bookmarkable portal session for the given email."""
    email = (payload.email or "").strip().lower()
    if not email or "@" not in email:
        raise HTTPException(status_code=422, detail="Please enter a valid email address.")

    # Check at least one customer exists
    customer = session.exec(
        select(Customer).where(Customer.email.ilike(email))  # type: ignore[attr-defined]
    ).first()
    if not customer:
        raise HTTPException(status_code=404, detail="No repairs found for this email address.")

    portal_session = PortalSession(
        email=email,
        expires_at=datetime.now(timezone.utc) + timedelta(days=_PORTAL_SESSION_TTL_DAYS),
    )
    session.add(portal_session)
    session.commit()
    session.refresh(portal_session)

    portal_url = f"{settings.public_base_url}/customer-portal/s/{portal_session.token}"

    from ..email_client import send_portal_bookmark_email

    send_portal_bookmark_email(
        to_email=email,
        portal_url=portal_url,
        expires_days=_PORTAL_SESSION_TTL_DAYS,
    )

    return {"session_token": portal_session.token, "portal_url": portal_url, "expires_days": _PORTAL_SESSION_TTL_DAYS}


@router.get("/portal/session/{token}", response_model=CustomerPortalLookupResponse)
def get_portal_session_jobs(
    token: str,
    include_history: bool = Query(default=False),
    session: Session = Depends(get_session),
):
    """Return jobs for a portal session token (same as customer-lookup but token-auth)."""
    portal = session.exec(select(PortalSession).where(PortalSession.token == token)).first()
    if not portal:
        raise HTTPException(status_code=404, detail="Session not found or expired.")

    exp = portal.expires_at
    if exp.tzinfo is None:
        exp = exp.replace(tzinfo=timezone.utc)
    if datetime.now(timezone.utc) > exp:
        raise HTTPException(status_code=410, detail="This portal link has expired. Please request a new one.")

    return _collect_customer_jobs(session, portal.email, include_history=include_history)


# ── Public auto-key quote portal ─────────────────────────────────────────────

@router.get("/auto-key-quote/{token}")
def get_public_auto_key_quote(token: str, session: Session = Depends(get_session)):
    quote = session.exec(
        select(AutoKeyQuote).where(AutoKeyQuote.quote_approval_token == token)
    ).first()
    if not quote:
        raise HTTPException(status_code=404, detail="Invalid or expired link")

    job = session.get(AutoKeyJob, quote.auto_key_job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")

    tenant = session.get(Tenant, job.tenant_id)
    customer = session.get(Customer, job.customer_id) if job.customer_id else None

    items = session.exec(
        select(AutoKeyQuoteLineItem)
        .where(AutoKeyQuoteLineItem.auto_key_quote_id == quote.id)
        .order_by(AutoKeyQuoteLineItem.created_at)
    ).all()

    return {
        "quote_id": str(quote.id),
        "status": quote.status,
        "job_number": job.job_number,
        "title": job.title,
        "vehicle_make": job.vehicle_make,
        "vehicle_model": job.vehicle_model,
        "vehicle_year": job.vehicle_year,
        "job_address": job.job_address,
        "scheduled_at": isoformat_z_utc(job.scheduled_at),
        "shop_name": tenant.name if tenant else "Mobile Services",
        "shop_phone": None,
        "customer_name": customer.full_name if customer else None,
        "subtotal_cents": quote.subtotal_cents,
        "tax_cents": quote.tax_cents,
        "total_cents": quote.total_cents,
        "currency": quote.currency or "AUD",
        "signed_at": isoformat_z_utc(quote.signed_at) if quote.signed_at else None,
        "signer_name": quote.signer_name,
        "has_signature": bool(quote.signature_storage_key),
        "line_items": [
            {
                "description": i.description,
                "quantity": i.quantity,
                "unit_price_cents": i.unit_price_cents,
                "total_price_cents": i.total_price_cents,
            }
            for i in items
        ],
    }


class AutoKeyQuoteDecision(SQLModel):
    decision: str  # "approved" | "declined"
    signature_data: Optional[str] = None  # base64 PNG (no data: prefix)
    signer_name: Optional[str] = None


@router.post("/auto-key-quote/{token}/decision")
def decide_public_auto_key_quote(
    token: str,
    body: AutoKeyQuoteDecision,
    session: Session = Depends(get_session),
):
    decision = body.decision.strip().lower()
    if decision not in ("approved", "declined"):
        raise HTTPException(status_code=422, detail="decision must be 'approved' or 'declined'")

    quote = session.exec(
        select(AutoKeyQuote).where(AutoKeyQuote.quote_approval_token == token)
    ).first()
    if not quote:
        raise HTTPException(status_code=404, detail="Invalid or expired link")

    if quote.status not in ("draft", "sent"):
        return {"ok": True, "status": quote.status, "message": f"Quote already {quote.status}."}

    job = session.get(AutoKeyJob, quote.auto_key_job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")

    quote.status = decision
    if decision == "approved" and job.status in ("quote_sent", "awaiting_quote"):
        job.status = "booking_confirmed"

    if decision == "approved" and body.signature_data:
        try:
            # Strip data URI prefix if present
            raw_b64 = body.signature_data
            if "," in raw_b64:
                raw_b64 = raw_b64.split(",", 1)[1]
            png_bytes = base64.b64decode(raw_b64)
            storage_key = f"quote-signatures/{quote.id}/{uuid4().hex}_signature.png"
            attachment_storage.save_bytes(storage_key, png_bytes, content_type="image/png")
            quote.signature_storage_key = storage_key
            quote.signed_at = datetime.now(timezone.utc)
            quote.signer_name = (body.signer_name or "").strip() or None
        except Exception:
            logger.exception("quote_signature_upload_failed quote=%s", quote.id)

    # Auto-create invoice when customer approves
    if decision == "approved":
        existing_invoice = session.exec(
            select(AutoKeyInvoice).where(AutoKeyInvoice.auto_key_quote_id == quote.id)
        ).first()
        if not existing_invoice:
            session.add(AutoKeyInvoice(
                tenant_id=job.tenant_id,
                auto_key_job_id=job.id,
                auto_key_quote_id=quote.id,
                invoice_number=_next_aki_invoice_number(session, job.tenant_id),
                subtotal_cents=quote.subtotal_cents,
                tax_cents=quote.tax_cents,
                total_cents=quote.total_cents,
                currency=quote.currency,
                customer_view_token=uuid4().hex,
            ))

    session.add(TenantEventLog(
        tenant_id=job.tenant_id,
        entity_type="auto_key_job",
        entity_id=job.id,
        event_type=f"quote_{decision}_portal",
        event_summary=f"Customer {decision} quote for job #{job.job_number} via portal"
        + (f" — signed by {quote.signer_name}" if quote.signer_name else ""),
    ))
    session.commit()

    if decision == "approved":
        created_invoice = session.exec(
            select(AutoKeyInvoice).where(AutoKeyInvoice.auto_key_quote_id == quote.id)
        ).first()
        if created_invoice:
            from ..xero_service import sync_auto_key_invoice_after_create

            sync_auto_key_invoice_after_create(session, created_invoice)
        return {"ok": True, "status": "approved", "message": "Quote accepted! We'll be in touch to confirm your appointment."}
    return {"ok": True, "status": "declined", "message": "Your quote has been declined. Contact us if you change your mind."}


@router.get("/auto-key-quote/{token}/signature")
def get_quote_signature(token: str, session: Session = Depends(get_session)):
    """Returns a short-lived redirect to the signature image in Supabase Storage."""
    quote = session.exec(
        select(AutoKeyQuote).where(AutoKeyQuote.quote_approval_token == token)
    ).first()
    if not quote or not quote.signature_storage_key:
        raise HTTPException(status_code=404, detail="No signature found")
    signed_url = attachment_storage.get_signed_url(quote.signature_storage_key, expires_in_seconds=120)
    if not signed_url:
        raise HTTPException(status_code=404, detail="Signature not available")
    return RedirectResponse(url=signed_url, status_code=302)
