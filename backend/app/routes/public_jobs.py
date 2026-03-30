import io
import importlib
import json
from datetime import datetime
from typing import Any, Optional

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import Response
from sqlmodel import Field, Session, SQLModel, select

from ..config import settings
from ..database import get_session
from ..datetime_utils import isoformat_z_utc, naive_utc_from_any
from ..models import (
    AutoKeyInvoice,
    AutoKeyJob,
    AutoKeyQuote,
    AutoKeyQuoteLineItem,
    Customer,
    JobStatusHistory,
    RepairJob,
    Shoe,
    ShoeRepairJob,
    ShoeRepairJobItem,
    Tenant,
    Watch,
)

router = APIRouter(prefix="/v1/public", tags=["public-jobs"])


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


@router.post("/auto-key-booking/{token}/confirm")
def confirm_public_auto_key_booking(token: str, session: Session = Depends(get_session)):
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
