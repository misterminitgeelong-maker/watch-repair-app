"""Medal engraving events: on-the-spot engraving stalls at sporting meets.

An EngravingEvent is one stall on one day (e.g. a Little Athletics meet). Parents
order from their phone via the event's public QR link; each EngravingOrder is one
athlete's text, engraved on `qty` medals. The operator works the queue, exports
the remaining medals as CSV for LightBurn / xTool Studio, and the parent is told
when the order is ready (live status page + optional SMS).
"""
from datetime import date, datetime, timezone
from typing import Literal, Optional
from uuid import UUID, uuid4

from sqlalchemy import UniqueConstraint
from sqlmodel import Field, SQLModel

__all__ = [
    "ENGRAVING_LINE2_MAX",
    "ENGRAVING_NAME_MAX",
    "ENGRAVING_PLACES",
    "EngravingEvent",
    "EngravingEventCreate",
    "EngravingEventRead",
    "EngravingEventStats",
    "EngravingEventStatus",
    "EngravingEventUpdate",
    "EngravingOperatorOrderCreate",
    "EngravingOrder",
    "EngravingOrderCreate",
    "EngravingOrderRead",
    "EngravingOrderStatus",
    "EngravingOrderUpdate",
    "EngravingQueueRead",
    "PublicEngravingEvent",
    "PublicEngravingOrder",
]

EngravingEventStatus = Literal["open", "paused", "closed"]
EngravingOrderStatus = Literal["waiting", "engraving", "ready", "collected", "cancelled"]
ENGRAVING_PLACES = ("1st", "2nd", "3rd", "Participant", "None")

# Field limits, shared by the API and the order form (long text will not fit a medal).
ENGRAVING_NAME_MAX = 24
ENGRAVING_LINE2_MAX = 28


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _public_token() -> str:
    return uuid4().hex[:12]


class EngravingEvent(SQLModel, table=True):
    __tablename__ = "engravingevent"

    id: UUID = Field(default_factory=uuid4, primary_key=True)
    tenant_id: UUID = Field(index=True, foreign_key="tenant.id")
    name: str
    event_date: Optional[date] = None
    location: Optional[str] = None
    price_cents: int = 1500
    # Used for the wait estimate shown to parents (medals ahead × this).
    minutes_per_medal: int = 3
    status: str = Field(default="open")  # open | paused | closed
    sms_enabled: bool = True
    public_token: str = Field(default_factory=_public_token, index=True, unique=True)
    next_order_seq: int = 1
    created_at: datetime = Field(default_factory=_utcnow)
    updated_at: datetime = Field(default_factory=_utcnow)


class EngravingOrder(SQLModel, table=True):
    __tablename__ = "engravingorder"
    __table_args__ = (UniqueConstraint("event_id", "order_seq", name="uq_engravingorder_event_seq"),)

    id: UUID = Field(default_factory=uuid4, primary_key=True)
    tenant_id: UUID = Field(index=True, foreign_key="tenant.id")
    event_id: UUID = Field(index=True, foreign_key="engravingevent.id")
    order_seq: int
    order_number: str  # e.g. A-024
    status_token: str = Field(default_factory=lambda: uuid4().hex, index=True, unique=True)
    athlete_name: str
    line2: Optional[str] = None
    place: str = "None"
    qty: int = 1
    medals_done: int = 0
    phone: Optional[str] = None
    status: str = Field(default="waiting", index=True)  # waiting | engraving | ready | collected | cancelled
    paid: bool = False
    paid_at: Optional[datetime] = None
    amount_cents: int = 0
    source: str = "online"  # online | walk_up
    notes: Optional[str] = None
    ready_at: Optional[datetime] = None
    ready_sms_status: Optional[str] = None  # sent | dry_run | failed | skipped
    collected_at: Optional[datetime] = None
    created_at: datetime = Field(default_factory=_utcnow, index=True)
    updated_at: datetime = Field(default_factory=_utcnow)


# ---------------------------------------------------------------------------
# API schemas
# ---------------------------------------------------------------------------

class EngravingEventCreate(SQLModel):
    name: str
    event_date: Optional[date] = None
    location: Optional[str] = None
    price_cents: int = 1500
    minutes_per_medal: int = 3
    sms_enabled: bool = True


class EngravingEventUpdate(SQLModel):
    name: Optional[str] = None
    event_date: Optional[date] = None
    location: Optional[str] = None
    price_cents: Optional[int] = None
    minutes_per_medal: Optional[int] = None
    status: Optional[EngravingEventStatus] = None
    sms_enabled: Optional[bool] = None


class EngravingEventStats(SQLModel):
    waiting: int = 0
    engraving: int = 0
    ready: int = 0
    collected: int = 0
    cancelled: int = 0
    medals_total: int = 0
    medals_remaining: int = 0
    paid_cents: int = 0
    unpaid_cents: int = 0


class EngravingEventRead(SQLModel):
    id: UUID
    name: str
    event_date: Optional[date]
    location: Optional[str]
    price_cents: int
    minutes_per_medal: int
    status: str
    sms_enabled: bool
    public_token: str
    public_url: str
    created_at: datetime
    stats: EngravingEventStats


class EngravingOrderCreate(SQLModel):
    athlete_name: str
    line2: Optional[str] = None
    place: str = "None"
    qty: int = 1
    phone: Optional[str] = None


class EngravingOperatorOrderCreate(EngravingOrderCreate):
    paid: bool = False
    notes: Optional[str] = None


class EngravingOrderUpdate(SQLModel):
    athlete_name: Optional[str] = None
    line2: Optional[str] = None
    place: Optional[str] = None
    qty: Optional[int] = None
    phone: Optional[str] = None
    paid: Optional[bool] = None
    status: Optional[EngravingOrderStatus] = None
    notes: Optional[str] = None


class EngravingOrderRead(SQLModel):
    id: UUID
    event_id: UUID
    order_number: str
    order_seq: int
    status_token: str
    athlete_name: str
    line2: Optional[str]
    place: str
    qty: int
    medals_done: int
    phone: Optional[str]
    status: str
    paid: bool
    paid_at: Optional[datetime]
    amount_cents: int
    source: str
    notes: Optional[str]
    ready_at: Optional[datetime]
    ready_sms_status: Optional[str]
    collected_at: Optional[datetime]
    created_at: datetime


class EngravingQueueRead(SQLModel):
    event: EngravingEventRead
    orders: list[EngravingOrderRead]


class PublicEngravingEvent(SQLModel):
    name: str
    shop_name: str
    event_date: Optional[date]
    location: Optional[str]
    price_cents: int
    accepting_orders: bool
    status: str
    wait_minutes: int
    medals_ahead: int
    name_max: int = ENGRAVING_NAME_MAX
    line2_max: int = ENGRAVING_LINE2_MAX
    places: list[str] = list(ENGRAVING_PLACES)


class PublicEngravingOrder(SQLModel):
    order_number: str
    status_token: str
    event_name: str
    shop_name: str
    athlete_name: str
    line2: Optional[str]
    place: str
    qty: int
    medals_done: int
    status: str
    paid: bool
    amount_cents: int
    queue_position: Optional[int]
    wait_minutes: Optional[int]
    phone_masked: Optional[str]
    created_at: datetime
    ready_at: Optional[datetime]
