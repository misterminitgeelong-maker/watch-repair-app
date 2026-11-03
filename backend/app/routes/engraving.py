"""Medal engraving events — QR ordering, operator queue, laser CSV export, ready alerts.

Operator endpoints live under /v1/engraving (tenant-scoped, signed in).
Parent-facing endpoints live under /v1/public/engraving (no sign-in; reached
from the event's QR code and from the order status link).
"""
import csv
import io
import logging
import re
import zipfile
from datetime import datetime, timezone
from uuid import UUID, uuid4

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from fastapi.responses import Response
from sqlalchemy.exc import IntegrityError
from sqlmodel import Session, select

from ..config import settings
from ..database import get_session
from ..dependencies import AuthContext, get_auth_context, require_tech_or_above
from ..limiter import limiter
from ..models import (
    ENGRAVING_BATCH_MAX,
    ENGRAVING_TICKET_MAX,
    ENGRAVING_LINE2_MAX,
    ENGRAVING_NAME_MAX,
    ENGRAVING_PLACES,
    EngravingBatchCreate,
    EngravingEvent,
    EngravingEventCreate,
    EngravingEventRead,
    EngravingEventStats,
    EngravingEventUpdate,
    EngravingOperatorOrderCreate,
    EngravingOrder,
    EngravingOrderCreate,
    EngravingOrderRead,
    EngravingOrderUpdate,
    EngravingQueueRead,
    PublicEngravingEvent,
    PublicEngravingGroupMember,
    PublicEngravingOrder,
    Tenant,
)
from ..phone_utils import normalize_phone
from ..sms import notify_engraving_ready
from .public_jobs import get_public_read_rate_limit, get_public_write_rate_limit

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/v1/engraving", tags=["engraving"])
public_router = APIRouter(prefix="/v1/public/engraving", tags=["public-engraving"])

ACTIVE_STATUSES = ("waiting", "engraving")
MAX_QTY = 20


def _now() -> datetime:
    return datetime.now(timezone.utc)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _public_url(event: EngravingEvent) -> str:
    return f"{settings.public_base_url}/engrave/{event.public_token}"


def _clean_text(value: str | None, *, field: str, max_len: int, required: bool) -> str | None:
    text = re.sub(r"\s+", " ", (value or "")).strip()
    if not text:
        if required:
            raise HTTPException(status_code=422, detail=f"{field} is required")
        return None
    if len(text) > max_len:
        raise HTTPException(status_code=422, detail=f"{field} must be {max_len} characters or fewer")
    return text


def _clean_place(value: str | None) -> str:
    place = (value or "None").strip() or "None"
    for allowed in ENGRAVING_PLACES:
        if place.lower() == allowed.lower():
            return allowed
    raise HTTPException(status_code=422, detail=f"Place must be one of: {', '.join(ENGRAVING_PLACES)}")


def _clean_qty(value: int) -> int:
    if value < 1 or value > MAX_QTY:
        raise HTTPException(status_code=422, detail=f"Quantity must be between 1 and {MAX_QTY}")
    return value


def _clean_ticket(value: str | None) -> str:
    ticket = (value or "").strip().upper()
    if not ticket:
        raise HTTPException(status_code=422, detail="Enter the number on your ticket")
    if len(ticket) > ENGRAVING_TICKET_MAX:
        raise HTTPException(status_code=422, detail="That ticket number looks too long")
    return ticket


def _clean_phone(value: str | None) -> str | None:
    if value is None or not value.strip():
        return None
    normalized = normalize_phone(value)
    if not normalized:
        raise HTTPException(status_code=422, detail="Mobile number doesn't look right")
    return normalized


def _sms_number(phone: str) -> str:
    """Normalised AU numbers are stored as 04xxxxxxxx; Twilio wants E.164."""
    if len(phone) == 10 and phone.startswith("0"):
        return "+61" + phone[1:]
    return phone


def _mask_phone(phone: str | None) -> str | None:
    if not phone:
        return None
    if len(phone) <= 4:
        return phone
    return f"{phone[:4]} ••• {phone[-3:]}"


def _place_text(place: str) -> str:
    if place == "None":
        return ""
    if place == "Participant":
        return "Participant"
    return f"{place} Place"


def _remaining(order: EngravingOrder) -> int:
    return max(0, order.qty - order.medals_done)


def _event_stats(session: Session, event_id: UUID) -> EngravingEventStats:
    orders = session.exec(select(EngravingOrder).where(EngravingOrder.event_id == event_id)).all()
    stats = EngravingEventStats()
    for o in orders:
        if o.status in {"waiting", "engraving", "ready", "collected", "cancelled"}:
            setattr(stats, o.status, getattr(stats, o.status) + 1)
        if o.status == "cancelled":
            continue
        stats.medals_total += o.qty
        if o.status in ACTIVE_STATUSES:
            stats.medals_remaining += _remaining(o)
        if o.paid:
            stats.paid_cents += o.amount_cents
        else:
            stats.unpaid_cents += o.amount_cents
    return stats


def _connect_ready(tenant: Tenant | None) -> bool:
    return bool(
        tenant
        and (tenant.stripe_connect_account_id or "").strip()
        and tenant.stripe_connect_charges_enabled
    )


def _card_payments_ready(session: Session, event: EngravingEvent) -> bool:
    """True when a parent could actually pay by card for this event right now."""
    if not (event.online_payments and settings.enable_stripe_invoice_checkout):
        return False
    if not (settings.stripe_secret_key or "").strip():
        return False
    return _connect_ready(session.get(Tenant, event.tenant_id))


def _event_read(session: Session, event: EngravingEvent) -> EngravingEventRead:
    return EngravingEventRead(
        id=event.id,
        name=event.name,
        event_date=event.event_date,
        location=event.location,
        price_cents=event.price_cents,
        minutes_per_medal=event.minutes_per_medal,
        status=event.status,
        sms_enabled=event.sms_enabled,
        online_payments=event.online_payments,
        online_payments_ready=_card_payments_ready(session, event),
        public_token=event.public_token,
        public_url=_public_url(event),
        created_at=event.created_at,
        stats=_event_stats(session, event.id),
    )


def _order_read(order: EngravingOrder) -> EngravingOrderRead:
    return EngravingOrderRead(**order.model_dump())


def _get_event(session: Session, event_id: UUID, tenant_id: UUID) -> EngravingEvent:
    event = session.get(EngravingEvent, event_id)
    if not event or event.tenant_id != tenant_id:
        raise HTTPException(status_code=404, detail="Event not found")
    return event


def _get_order(session: Session, order_id: UUID, tenant_id: UUID) -> EngravingOrder:
    order = session.get(EngravingOrder, order_id)
    if not order or order.tenant_id != tenant_id:
        raise HTTPException(status_code=404, detail="Order not found")
    return order


def _active_orders(session: Session, event_id: UUID) -> list[EngravingOrder]:
    return list(
        session.exec(
            select(EngravingOrder)
            .where(EngravingOrder.event_id == event_id)
            .where(EngravingOrder.status.in_(ACTIVE_STATUSES))
            .order_by(EngravingOrder.order_seq)
        ).all()
    )


def _medals_ahead(session: Session, event_id: UUID, before_seq: int | None = None) -> int:
    return sum(
        _remaining(o)
        for o in _active_orders(session, event_id)
        if before_seq is None or o.order_seq < before_seq
    )


def _create_order(
    session: Session,
    event: EngravingEvent,
    payload: EngravingOrderCreate,
    *,
    source: str,
    paid: bool = False,
    notes: str | None = None,
    group_id: UUID | None = None,
    ticket_number: str | None = None,
) -> EngravingOrder:
    athlete_name = _clean_text(payload.athlete_name, field="Athlete name", max_len=ENGRAVING_NAME_MAX, required=True)
    line2 = _clean_text(payload.line2, field="Second line", max_len=ENGRAVING_LINE2_MAX, required=False)
    place = _clean_place(payload.place)
    qty = _clean_qty(payload.qty)
    phone = _clean_phone(payload.phone)

    for _attempt in range(5):
        # Lock the event row so two parents ordering at once get different numbers
        # (FOR UPDATE is a no-op on sqlite; the unique constraint backs it up).
        locked = session.exec(
            select(EngravingEvent).where(EngravingEvent.id == event.id).with_for_update()
        ).one()
        seq = locked.next_order_seq
        locked.next_order_seq = seq + 1
        locked.updated_at = _now()
        now = _now()
        order = EngravingOrder(
            tenant_id=event.tenant_id,
            event_id=event.id,
            order_seq=seq,
            order_number=f"A-{seq:03d}",
            athlete_name=athlete_name,
            line2=line2,
            place=place,
            qty=qty,
            phone=phone,
            paid=paid,
            paid_at=now if paid else None,
            payment_method="stall" if paid else None,
            amount_cents=event.price_cents * qty,
            source=source,
            notes=notes,
            group_id=group_id,
            ticket_number=ticket_number,
        )
        session.add(locked)
        session.add(order)
        try:
            session.commit()
        except IntegrityError:
            session.rollback()
            continue
        session.refresh(order)
        return order
    raise HTTPException(status_code=409, detail="Couldn't number this order, please try again")


def _mark_ready(session: Session, order: EngravingOrder, event: EngravingEvent) -> None:
    """Move an order to ready and text the parent once (if SMS is on and we have a number)."""
    order.status = "ready"
    order.medals_done = max(order.medals_done, order.qty)
    if order.ready_at is None:
        order.ready_at = _now()
    if order.ready_sms_status in {"sent", "dry_run"}:
        return
    if not (event.sms_enabled and order.phone):
        order.ready_sms_status = "skipped"
        return
    tenant = session.get(Tenant, order.tenant_id)
    try:
        order.ready_sms_status = notify_engraving_ready(
            session,
            tenant_id=order.tenant_id,
            to_phone=_sms_number(order.phone),
            shop_name=tenant.name if tenant else "Engraving",
            athlete_name=order.athlete_name,
            order_number=order.order_number,
            status_token=order.status_token,
        )
    except Exception:  # noqa: BLE001 — a failed text must never block the queue
        logger.exception("Engraving ready SMS failed for order %s", order.id)
        order.ready_sms_status = "failed"


# ---------------------------------------------------------------------------
# Operator: events
# ---------------------------------------------------------------------------

@router.get("/events", response_model=list[EngravingEventRead])
def list_events(
    session: Session = Depends(get_session),
    auth: AuthContext = Depends(get_auth_context),
):
    events = session.exec(
        select(EngravingEvent)
        .where(EngravingEvent.tenant_id == auth.tenant_id)
        .order_by(EngravingEvent.created_at.desc())
    ).all()
    return [_event_read(session, e) for e in events]


@router.post("/events", response_model=EngravingEventRead)
def create_event(
    payload: EngravingEventCreate,
    session: Session = Depends(get_session),
    auth: AuthContext = Depends(get_auth_context),
    _: None = Depends(require_tech_or_above),
):
    name = _clean_text(payload.name, field="Event name", max_len=120, required=True)
    if payload.price_cents < 0:
        raise HTTPException(status_code=422, detail="Price can't be negative")
    event = EngravingEvent(
        tenant_id=auth.tenant_id,
        name=name,
        event_date=payload.event_date,
        location=_clean_text(payload.location, field="Location", max_len=160, required=False),
        price_cents=payload.price_cents,
        minutes_per_medal=max(1, payload.minutes_per_medal),
        sms_enabled=payload.sms_enabled,
        online_payments=payload.online_payments,
    )
    session.add(event)
    session.commit()
    session.refresh(event)
    return _event_read(session, event)


@router.patch("/events/{event_id}", response_model=EngravingEventRead)
def update_event(
    event_id: UUID,
    payload: EngravingEventUpdate,
    session: Session = Depends(get_session),
    auth: AuthContext = Depends(get_auth_context),
    _: None = Depends(require_tech_or_above),
):
    event = _get_event(session, event_id, auth.tenant_id)
    data = payload.model_dump(exclude_unset=True)
    if "name" in data:
        data["name"] = _clean_text(data["name"], field="Event name", max_len=120, required=True)
    if "location" in data:
        data["location"] = _clean_text(data["location"], field="Location", max_len=160, required=False)
    if "price_cents" in data and (data["price_cents"] is None or data["price_cents"] < 0):
        raise HTTPException(status_code=422, detail="Price can't be negative")
    if "minutes_per_medal" in data and data["minutes_per_medal"] is not None:
        data["minutes_per_medal"] = max(1, data["minutes_per_medal"])
    for field, value in data.items():
        if value is None and field in {"name", "price_cents", "minutes_per_medal", "status", "sms_enabled", "online_payments"}:
            continue
        setattr(event, field, value)
    event.updated_at = _now()
    session.add(event)
    session.commit()
    session.refresh(event)
    return _event_read(session, event)


@router.get("/events/{event_id}/queue", response_model=EngravingQueueRead)
def get_queue(
    event_id: UUID,
    session: Session = Depends(get_session),
    auth: AuthContext = Depends(get_auth_context),
):
    event = _get_event(session, event_id, auth.tenant_id)
    orders = session.exec(
        select(EngravingOrder).where(EngravingOrder.event_id == event.id)
    ).all()
    rank = {"engraving": 0, "waiting": 1, "ready": 2, "collected": 3, "cancelled": 4}
    ordered = sorted(
        orders,
        key=lambda o: (rank.get(o.status, 9), o.order_seq if o.status in ACTIVE_STATUSES else -o.order_seq),
    )
    return EngravingQueueRead(event=_event_read(session, event), orders=[_order_read(o) for o in ordered])


@router.post("/events/{event_id}/orders", response_model=EngravingOrderRead)
def create_walk_up_order(
    event_id: UUID,
    payload: EngravingOperatorOrderCreate,
    session: Session = Depends(get_session),
    auth: AuthContext = Depends(get_auth_context),
    _: None = Depends(require_tech_or_above),
):
    event = _get_event(session, event_id, auth.tenant_id)
    notes = _clean_text(payload.notes, field="Notes", max_len=500, required=False)
    order = _create_order(session, event, payload, source="walk_up", paid=payload.paid, notes=notes)
    return _order_read(order)


def _medal_rows(session: Session, event: EngravingEvent, *, paid_only: bool, limit: int | None) -> list[list[str]]:
    """One row per medal still to engrave, in queue order: Name, Line2, Place, Order, Medal."""
    rows: list[list[str]] = []
    for order in _active_orders(session, event.id):
        if paid_only and not order.paid:
            continue
        for n in range(order.medals_done + 1, order.qty + 1):
            rows.append([
                order.athlete_name,
                order.line2 or "",
                _place_text(order.place),
                order.order_number,
                f"{n} of {order.qty}",
            ])
    return rows[:limit] if limit else rows


def _event_slug(event: EngravingEvent) -> str:
    return re.sub(r"[^a-z0-9]+", "-", event.name.lower()).strip("-") or "engraving"


def _csv_text(rows: list[list[str]], *, header: bool) -> str:
    buf = io.StringIO()
    writer = csv.writer(buf, lineterminator="\r\n")
    if header:
        writer.writerow(["Name", "Line2", "Place", "Order", "Medal"])
    writer.writerows(rows)
    return buf.getvalue()


@router.get("/events/{event_id}/export.csv")
def export_laser_csv(
    event_id: UUID,
    paid_only: bool = Query(default=False),
    session: Session = Depends(get_session),
    auth: AuthContext = Depends(get_auth_context),
):
    """One row per medal still to engrave, in queue order.

    Columns: Name, Line2, Place, Order, Medal. For other laser programs use
    /export, which can also shape the file for LightBurn, xTool and EZCad2.
    """
    event = _get_event(session, event_id, auth.tenant_id)
    rows = _medal_rows(session, event, paid_only=paid_only, limit=None)
    return Response(
        content=_csv_text(rows, header=True),
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="{_event_slug(event)}-medals.csv"'},
    )


@router.get("/events/{event_id}/export")
def export_laser_file(
    event_id: UUID,
    software: str = Query(default="csv", pattern="^(csv|lightburn|xtool|ezcad2)$"),
    paid_only: bool = Query(default=False),
    limit: int | None = Query(default=None, ge=1, le=500),
    session: Session = Depends(get_session),
    auth: AuthContext = Depends(get_auth_context),
):
    """Laser file shaped for the chosen program, optionally only the next `limit` medals.

    - csv: header row plus Name, Line2, Place, Order, Medal.
    - lightburn: the same without the header row (LightBurn counts every line as a row).
    - xtool: header row; empty cells become a single space (xTool skips a row with a blank cell).
    - ezcad2: a zip of names.txt, line2.txt and places.txt, one value per line (EZCad2 reads
      TXT or old-format XLS, not CSV).
    """
    event = _get_event(session, event_id, auth.tenant_id)
    rows = _medal_rows(session, event, paid_only=paid_only, limit=limit)
    slug = _event_slug(event)
    if software == "ezcad2":
        buf = io.BytesIO()
        with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
            for filename, col in (("names.txt", 0), ("line2.txt", 1), ("places.txt", 2)):
                zf.writestr(filename, "\r\n".join((r[col] or " ") for r in rows) + ("\r\n" if rows else ""))
        return Response(
            content=buf.getvalue(),
            media_type="application/zip",
            headers={"Content-Disposition": f'attachment; filename="{slug}-ezcad2.zip"'},
        )
    if software == "xtool":
        rows = [[cell if cell != "" else " " for cell in r] for r in rows]
    text = _csv_text(rows, header=software != "lightburn")
    return Response(
        content=text,
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="{slug}-{software}.csv"'},
    )


# ---------------------------------------------------------------------------
# Operator: orders
# ---------------------------------------------------------------------------

@router.patch("/orders/{order_id}", response_model=EngravingOrderRead)
def update_order(
    order_id: UUID,
    payload: EngravingOrderUpdate,
    session: Session = Depends(get_session),
    auth: AuthContext = Depends(get_auth_context),
    _: None = Depends(require_tech_or_above),
):
    order = _get_order(session, order_id, auth.tenant_id)
    event = _get_event(session, order.event_id, auth.tenant_id)
    data = payload.model_dump(exclude_unset=True)

    if "athlete_name" in data:
        order.athlete_name = _clean_text(data["athlete_name"], field="Athlete name", max_len=ENGRAVING_NAME_MAX, required=True)
    if "line2" in data:
        order.line2 = _clean_text(data["line2"], field="Second line", max_len=ENGRAVING_LINE2_MAX, required=False)
    if "place" in data:
        order.place = _clean_place(data["place"])
    if "qty" in data and data["qty"] is not None:
        order.qty = _clean_qty(data["qty"])
        order.medals_done = min(order.medals_done, order.qty)
        order.amount_cents = event.price_cents * order.qty
    if "phone" in data:
        order.phone = _clean_phone(data["phone"])
    if "notes" in data:
        order.notes = _clean_text(data["notes"], field="Notes", max_len=500, required=False)
    if "paid" in data and data["paid"] is not None:
        if data["paid"] != order.paid:
            order.paid = data["paid"]
            order.paid_at = _now() if order.paid else None
            order.payment_method = "stall" if order.paid else None
            if not order.paid:
                order.stripe_checkout_id = None

    new_status = data.get("status")
    if new_status and new_status != order.status:
        if new_status == "ready":
            _mark_ready(session, order, event)
        elif new_status == "collected":
            order.status = "collected"
            order.collected_at = _now()
            if order.ready_at is None:
                order.ready_at = order.collected_at
        else:
            order.status = new_status
            if new_status in ACTIVE_STATUSES:
                order.collected_at = None
                if order.medals_done >= order.qty:
                    order.medals_done = 0
                order.ready_at = None
                order.ready_sms_status = None

    order.updated_at = _now()
    session.add(order)
    session.commit()
    session.refresh(order)
    return _order_read(order)


@router.post("/orders/{order_id}/medal-done", response_model=EngravingOrderRead)
def medal_done(
    order_id: UUID,
    session: Session = Depends(get_session),
    auth: AuthContext = Depends(get_auth_context),
    _: None = Depends(require_tech_or_above),
):
    """The operator finished one medal. When the last one is done the order is ready
    and the parent is texted."""
    order = _get_order(session, order_id, auth.tenant_id)
    if order.status not in ACTIVE_STATUSES:
        raise HTTPException(status_code=409, detail=f"Order is already {order.status}")
    event = _get_event(session, order.event_id, auth.tenant_id)
    order.medals_done = min(order.qty, order.medals_done + 1)
    if order.medals_done >= order.qty:
        _mark_ready(session, order, event)
    else:
        order.status = "engraving"
    order.updated_at = _now()
    session.add(order)
    session.commit()
    session.refresh(order)
    return _order_read(order)


@router.post("/orders/{order_id}/start", response_model=EngravingOrderRead)
def start_order(
    order_id: UUID,
    session: Session = Depends(get_session),
    auth: AuthContext = Depends(get_auth_context),
    _: None = Depends(require_tech_or_above),
):
    """Put this order on the laser. Any other order marked engraving goes back to waiting,
    so there is only ever one "now engraving"."""
    order = _get_order(session, order_id, auth.tenant_id)
    if order.status not in ACTIVE_STATUSES:
        raise HTTPException(status_code=409, detail=f"Order is already {order.status}")
    others = session.exec(
        select(EngravingOrder)
        .where(EngravingOrder.event_id == order.event_id)
        .where(EngravingOrder.status == "engraving")
        .where(EngravingOrder.id != order.id)
    ).all()
    for other in others:
        other.status = "waiting"
        other.updated_at = _now()
        session.add(other)
    order.status = "engraving"
    order.updated_at = _now()
    session.add(order)
    session.commit()
    session.refresh(order)
    return _order_read(order)


@router.post("/orders/{order_id}/resend-ready", response_model=EngravingOrderRead)
def resend_ready_text(
    order_id: UUID,
    session: Session = Depends(get_session),
    auth: AuthContext = Depends(get_auth_context),
    _: None = Depends(require_tech_or_above),
):
    order = _get_order(session, order_id, auth.tenant_id)
    if order.status != "ready":
        raise HTTPException(status_code=409, detail="Only ready orders can be re-notified")
    if not order.phone:
        raise HTTPException(status_code=422, detail="This order has no mobile number")
    event = _get_event(session, order.event_id, auth.tenant_id)
    order.ready_sms_status = None
    _mark_ready(session, order, event)
    order.updated_at = _now()
    session.add(order)
    session.commit()
    session.refresh(order)
    return _order_read(order)


# ---------------------------------------------------------------------------
# Public (parents)
# ---------------------------------------------------------------------------

def _public_event(session: Session, token: str) -> EngravingEvent:
    event = session.exec(select(EngravingEvent).where(EngravingEvent.public_token == token)).first()
    if not event:
        raise HTTPException(status_code=404, detail="Event not found")
    return event


def _shop_name(session: Session, tenant_id: UUID) -> str:
    tenant = session.get(Tenant, tenant_id)
    return tenant.name if tenant else ""


@public_router.get("/events/{token}", response_model=PublicEngravingEvent)
@limiter.limit(get_public_read_rate_limit)
def get_public_event(request: Request, token: str, session: Session = Depends(get_session)):
    event = _public_event(session, token)
    ahead = _medals_ahead(session, event.id)
    return PublicEngravingEvent(
        name=event.name,
        shop_name=_shop_name(session, event.tenant_id),
        event_date=event.event_date,
        location=event.location,
        price_cents=event.price_cents,
        accepting_orders=event.status == "open",
        status=event.status,
        wait_minutes=ahead * event.minutes_per_medal,
        medals_ahead=ahead,
    )


@public_router.post("/events/{token}/orders", response_model=PublicEngravingOrder)
@limiter.limit(get_public_write_rate_limit)
def create_public_order(
    request: Request,
    token: str,
    payload: EngravingOrderCreate,
    session: Session = Depends(get_session),
):
    event = _public_event(session, token)
    if event.status != "open":
        raise HTTPException(status_code=409, detail="This stall isn't taking orders right now")
    order = _create_order(session, event, payload, source="online")
    return _public_order(session, order, event)


@public_router.post("/events/{token}/orders/batch", response_model=list[PublicEngravingOrder])
@limiter.limit(get_public_write_rate_limit)
def create_public_order_batch(
    request: Request,
    token: str,
    payload: EngravingBatchCreate,
    session: Session = Depends(get_session),
):
    """Order several different medals in one go. Every medal is checked before any is
    created, so a typo in the third one doesn't leave the first two half-ordered."""
    event = _public_event(session, token)
    if event.status != "open":
        raise HTTPException(status_code=409, detail="This stall isn't taking orders right now")
    if not payload.orders:
        raise HTTPException(status_code=422, detail="Add at least one medal")
    if len(payload.orders) > ENGRAVING_BATCH_MAX:
        raise HTTPException(status_code=422, detail=f"You can order up to {ENGRAVING_BATCH_MAX} different medals at once")
    ticket = _clean_ticket(payload.ticket_number)
    in_use = session.exec(
        select(EngravingOrder)
        .where(EngravingOrder.event_id == event.id)
        .where(EngravingOrder.ticket_number == ticket)
        .where(EngravingOrder.status.in_(["waiting", "engraving", "ready"]))
    ).first()
    if in_use:
        raise HTTPException(status_code=409, detail=f"Ticket {ticket} is already in use. Please check the number on your ticket.")
    items = []
    for item in payload.orders:
        item = EngravingOrderCreate(
            athlete_name=item.athlete_name, line2=item.line2, place=item.place, qty=item.qty, phone=payload.phone
        )
        # Validate up front (raises 422 on bad input) without creating anything.
        _clean_text(item.athlete_name, field="Athlete name", max_len=ENGRAVING_NAME_MAX, required=True)
        _clean_text(item.line2, field="Second line", max_len=ENGRAVING_LINE2_MAX, required=False)
        _clean_place(item.place)
        _clean_qty(item.qty)
        _clean_phone(item.phone)
        items.append(item)
    group_id = uuid4() if len(items) > 1 else None
    orders = [
        _create_order(session, event, item, source="online", group_id=group_id, ticket_number=ticket) for item in items
    ]
    return [_public_order(session, order, event) for order in orders]


def _public_order(session: Session, order: EngravingOrder, event: EngravingEvent) -> PublicEngravingOrder:
    position: int | None = None
    wait: int | None = None
    if order.status in ACTIVE_STATUSES:
        active = _active_orders(session, event.id)
        position = 1 + sum(1 for o in active if o.order_seq < order.order_seq)
        ahead = sum(_remaining(o) for o in active if o.order_seq < order.order_seq)
        wait = (ahead + _remaining(order)) * event.minutes_per_medal
    members: list[PublicEngravingGroupMember] = []
    due_orders = [order] if _payable(order) else []
    if order.group_id:
        siblings = session.exec(
            select(EngravingOrder)
            .where(EngravingOrder.group_id == order.group_id)
            .where(EngravingOrder.id != order.id)
            .order_by(EngravingOrder.order_seq)
        ).all()
        due_orders += [o for o in siblings if _payable(o)]
        members = [
            PublicEngravingGroupMember(
                order_number=o.order_number, athlete_name=o.athlete_name, status_token=o.status_token, status=o.status
            )
            for o in siblings
        ]
    return PublicEngravingOrder(
        group_members=members,
        order_number=order.order_number,
        status_token=order.status_token,
        event_name=event.name,
        shop_name=_shop_name(session, event.tenant_id),
        athlete_name=order.athlete_name,
        line2=order.line2,
        place=order.place,
        qty=order.qty,
        medals_done=order.medals_done,
        status=order.status,
        paid=order.paid,
        amount_cents=order.amount_cents,
        can_pay_online=bool(due_orders) and _card_payments_ready(session, event),
        amount_due_cents=sum(o.amount_cents for o in due_orders),
        queue_position=position,
        wait_minutes=wait,
        phone_masked=_mask_phone(order.phone),
        ticket_number=order.ticket_number,
        created_at=order.created_at,
        ready_at=order.ready_at,
    )


@public_router.get("/orders/{status_token}", response_model=PublicEngravingOrder)
@limiter.limit(get_public_read_rate_limit)
def get_public_order(request: Request, status_token: str, session: Session = Depends(get_session)):
    order = session.exec(select(EngravingOrder).where(EngravingOrder.status_token == status_token)).first()
    if not order:
        raise HTTPException(status_code=404, detail="Order not found")
    event = session.get(EngravingEvent, order.event_id)
    if not event:
        raise HTTPException(status_code=404, detail="Order not found")
    return _public_order(session, order, event)


# ---------------------------------------------------------------------------
# Public: pay by card
# ---------------------------------------------------------------------------

def _payable(order: EngravingOrder) -> bool:
    return not order.paid and order.status != "cancelled" and order.amount_cents > 0


def _stripe_client():
    if not (settings.stripe_secret_key or "").strip():
        return None
    try:
        import stripe as stripe_mod

        stripe_mod.api_key = settings.stripe_secret_key.strip()
        return stripe_mod
    except ImportError:
        return None


@public_router.post("/orders/{status_token}/checkout")
@limiter.limit(get_public_write_rate_limit)
def create_public_order_checkout(request: Request, status_token: str, session: Session = Depends(get_session)):
    """Start Stripe Checkout for this order plus any unpaid medals ordered with it.

    The card is charged on the shop's own Stripe account (a direct charge, like Mobile Services
    invoices). The order is marked paid when Stripe's Connect webhook reports the payment."""
    order = session.exec(select(EngravingOrder).where(EngravingOrder.status_token == status_token)).first()
    if not order:
        raise HTTPException(status_code=404, detail="Order not found")
    event = session.get(EngravingEvent, order.event_id)
    if not event:
        raise HTTPException(status_code=404, detail="Order not found")
    tenant = session.get(Tenant, order.tenant_id)
    if not _card_payments_ready(session, event):
        raise HTTPException(status_code=503, detail="Card payment isn't available here. Please pay at the stall.")
    stripe = _stripe_client()
    if not stripe:
        raise HTTPException(status_code=503, detail="Card payment isn't available here. Please pay at the stall.")

    orders = [order]
    if order.group_id:
        orders += session.exec(
            select(EngravingOrder).where(EngravingOrder.group_id == order.group_id).where(EngravingOrder.id != order.id)
        ).all()
    orders = sorted((o for o in orders if _payable(o)), key=lambda o: o.order_seq)
    if not orders:
        raise HTTPException(status_code=409, detail="This order is already paid.")
    total = sum(o.amount_cents for o in orders)
    if total < 50:
        raise HTTPException(status_code=400, detail="That's below the minimum for card payment. Please pay at the stall.")

    base = settings.public_base_url.rstrip("/")
    shop = (tenant.name if tenant else "Engraving").strip() or "Engraving"
    line_items = [
        {
            "price_data": {
                "currency": "aud",
                "unit_amount": o.amount_cents,
                "product_data": {
                    "name": f"{shop}: medal {o.order_number}, {o.athlete_name}"[:120]
                    + (f" x{o.qty}" if o.qty > 1 else "")
                },
            },
            "quantity": 1,
        }
        for o in orders
    ]
    params: dict = {
        "mode": "payment",
        "line_items": line_items,
        "metadata": {
            "purpose": "engraving_orders",
            "tenant_id": str(order.tenant_id),
            "engraving_order_ids": ",".join(str(o.id) for o in orders),
        },
        "success_url": f"{base}/engrave/o/{status_token}?paid=1",
        "cancel_url": f"{base}/engrave/o/{status_token}?canceled=1",
        "stripe_account": tenant.stripe_connect_account_id.strip(),
    }
    try:
        checkout = stripe.checkout.Session.create(**params)
    except Exception as exc:  # noqa: BLE001
        logger.exception("Engraving checkout could not start for order %s", order.id)
        raise HTTPException(status_code=502, detail="Could not start payment. Try again, or pay at the stall.") from exc
    url = getattr(checkout, "url", None)
    if not url:
        raise HTTPException(status_code=502, detail="Could not start payment. Try again, or pay at the stall.")
    return {"checkout_url": url}


def apply_engraving_checkout(session: Session, obj, *, connect_account: str | None) -> None:
    """Mark engraving orders paid from a completed Checkout session (called by the Stripe webhook).

    Trust rules match invoices: the money must have landed in the shop that owns the orders.
    A payment that can't be matched to still-unpaid orders for the right amount is logged to the
    shop's inbox so someone can refund it."""
    from ..models import TenantEventLog

    meta = obj.get("metadata") or {}
    raw_ids = [x for x in str(meta.get("engraving_order_ids") or "").split(",") if x.strip()]
    ids: list[UUID] = []
    for raw in raw_ids:
        try:
            ids.append(UUID(raw.strip()))
        except ValueError:
            return
    if not ids or (obj.get("payment_status") or "") != "paid":
        return
    orders = [o for o in (session.get(EngravingOrder, i) for i in ids) if o]
    if not orders:
        return
    tenant_id = orders[0].tenant_id
    if any(o.tenant_id != tenant_id for o in orders):
        return
    if connect_account is not None:
        owner = session.get(Tenant, tenant_id)
        if not owner or (owner.stripe_connect_account_id or "").strip() != connect_account:
            logger.warning("stripe.engraving_checkout_wrong_account orders=%s account=%s", ids, connect_account)
            return
    checkout_id = str(obj.get("id") or "")
    if checkout_id and any(o.stripe_checkout_id == checkout_id for o in orders):
        return  # redelivered event
    amount_total = obj.get("amount_total")
    expected = sum(o.amount_cents for o in orders)
    problem: str | None = None
    if any(o.paid for o in orders):
        problem = "included medals that were already paid"
    elif amount_total is not None and int(amount_total) != expected:
        problem = f"was for {expected} cents but {amount_total} cents was charged"
    if problem:
        logger.error("stripe.engraving_payment_unmatched orders=%s session=%s problem=%s", ids, checkout_id, problem)
        numbers = ", ".join(o.order_number for o in orders)
        session.add(
            TenantEventLog(
                tenant_id=tenant_id,
                entity_type="engraving_order",
                entity_id=orders[0].id,
                event_type="engraving_payment_needs_attention",
                event_summary=(
                    f"A card payment of ${int(amount_total or 0) / 100:.2f} for engraving orders {numbers} {problem}. "
                    "Check it in Stripe and refund if needed."
                ),
            )
        )
        session.commit()
        return
    now = _now()
    for o in orders:
        o.paid = True
        o.paid_at = now
        o.payment_method = "stripe"
        o.stripe_checkout_id = checkout_id or None
        o.updated_at = now
        session.add(o)
    session.commit()
