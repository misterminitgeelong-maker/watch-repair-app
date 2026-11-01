"""Medal engraving events — QR ordering, operator queue, laser CSV export, ready alerts.

Operator endpoints live under /v1/engraving (tenant-scoped, signed in).
Parent-facing endpoints live under /v1/public/engraving (no sign-in; reached
from the event's QR code and from the order status link).
"""
import csv
import io
import logging
import re
from datetime import datetime, timezone
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from fastapi.responses import Response
from sqlalchemy.exc import IntegrityError
from sqlmodel import Session, select

from ..config import settings
from ..database import get_session
from ..dependencies import AuthContext, get_auth_context, require_tech_or_above
from ..limiter import limiter
from ..models import (
    ENGRAVING_LINE2_MAX,
    ENGRAVING_NAME_MAX,
    ENGRAVING_PLACES,
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
            amount_cents=event.price_cents * qty,
            source=source,
            notes=notes,
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
        if value is None and field in {"name", "price_cents", "minutes_per_medal", "status", "sms_enabled"}:
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


@router.get("/events/{event_id}/export.csv")
def export_laser_csv(
    event_id: UUID,
    paid_only: bool = Query(default=False),
    session: Session = Depends(get_session),
    auth: AuthContext = Depends(get_auth_context),
):
    """One row per medal still to engrave, in queue order.

    Columns: Name, Line2, Place, Order, Medal. In LightBurn use Variable Text →
    Merge/CSV with Auto Advance (column 0 = Name, 1 = Line2, 2 = Place). In xTool
    Studio's batch processing mode, import the CSV and map Name/Line2/Place to the
    text variables.
    """
    event = _get_event(session, event_id, auth.tenant_id)
    buf = io.StringIO()
    writer = csv.writer(buf, lineterminator="\r\n")
    writer.writerow(["Name", "Line2", "Place", "Order", "Medal"])
    for order in _active_orders(session, event.id):
        if paid_only and not order.paid:
            continue
        for n in range(order.medals_done + 1, order.qty + 1):
            writer.writerow([
                order.athlete_name,
                order.line2 or "",
                _place_text(order.place),
                order.order_number,
                f"{n} of {order.qty}",
            ])
    slug = re.sub(r"[^a-z0-9]+", "-", event.name.lower()).strip("-") or "engraving"
    return Response(
        content=buf.getvalue(),
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="{slug}-medals.csv"'},
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
        order.paid = data["paid"]
        order.paid_at = _now() if order.paid else None

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


def _public_order(session: Session, order: EngravingOrder, event: EngravingEvent) -> PublicEngravingOrder:
    position: int | None = None
    wait: int | None = None
    if order.status in ACTIVE_STATUSES:
        active = _active_orders(session, event.id)
        position = 1 + sum(1 for o in active if o.order_seq < order.order_seq)
        ahead = sum(_remaining(o) for o in active if o.order_seq < order.order_seq)
        wait = (ahead + _remaining(order)) * event.minutes_per_medal
    return PublicEngravingOrder(
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
        queue_position=position,
        wait_minutes=wait,
        phone_masked=_mask_phone(order.phone),
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
