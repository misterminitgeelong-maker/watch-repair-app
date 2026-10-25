"""Shop counter POS: price books (layout, items, prices, combos) and the sales ledger.

A price book belongs to an HQ network (``parent_account_id``) or to a single
independent shop (``tenant_id``). HQ edits a draft and publishes it; each
publish is an immutable version, and tills download the published version
assigned to their shop. Sales are written by tills (often after the fact, from
an offline queue), so every sale carries the till's own ``client_sale_id`` and
posting the same sale twice is a no-op.
"""
from datetime import date, datetime, timezone
from typing import Optional
from uuid import UUID, uuid4

from sqlalchemy import CheckConstraint, UniqueConstraint
from sqlmodel import Field, SQLModel


def _now() -> datetime:
    return datetime.now(timezone.utc)


class PosPriceBook(SQLModel, table=True):
    __table_args__ = (
        CheckConstraint(
            "(parent_account_id IS NULL) <> (tenant_id IS NULL)",
            name="ck_pospricebook_one_owner",
        ),
    )

    id: UUID = Field(default_factory=uuid4, primary_key=True)
    parent_account_id: Optional[UUID] = Field(default=None, index=True, foreign_key="parentaccount.id", ondelete="CASCADE")
    tenant_id: Optional[UUID] = Field(default=None, index=True, foreign_key="tenant.id", ondelete="CASCADE")
    name: str = Field(max_length=120)
    region: str = Field(default="AU", max_length=2)  # AU | NZ
    currency: str = Field(default="AUD", max_length=3)
    gst_rate_bp: int = 1000  # 1000 = 10%
    cash_rounding_cents: int = 5
    #: The book a shop in this network gets when it has no explicit assignment.
    is_default: bool = False
    archived: bool = False
    #: Working copy HQ edits; tills never see it until it is published.
    draft_json: str = "{}"
    draft_updated_at: datetime = Field(default_factory=_now)
    published_version: int = 0
    created_at: datetime = Field(default_factory=_now)


class PosPriceBookVersion(SQLModel, table=True):
    __table_args__ = (UniqueConstraint("price_book_id", "version", name="uq_pospricebookversion_book_version"),)

    id: UUID = Field(default_factory=uuid4, primary_key=True)
    price_book_id: UUID = Field(index=True, foreign_key="pospricebook.id", ondelete="CASCADE")
    version: int
    content_json: str
    note: Optional[str] = Field(default=None, max_length=500)
    published_by_user_id: Optional[UUID] = Field(default=None, foreign_key="user.id", ondelete="SET NULL")
    published_at: datetime = Field(default_factory=_now)


class PosShopSettings(SQLModel, table=True):
    """Per-shop POS setup: which price book it sells from, and its local price overrides."""

    id: UUID = Field(default_factory=uuid4, primary_key=True)
    tenant_id: UUID = Field(index=True, unique=True, foreign_key="tenant.id", ondelete="CASCADE")
    price_book_id: Optional[UUID] = Field(default=None, index=True, foreign_key="pospricebook.id", ondelete="SET NULL")
    #: {"<item key>": {"price_cents": 1995} | {"hidden": true}}
    overrides_json: str = "{}"
    updated_at: datetime = Field(default_factory=_now)


class PosSale(SQLModel, table=True):
    __table_args__ = (UniqueConstraint("tenant_id", "client_sale_id", name="uq_possale_tenant_client_sale"),)

    id: UUID = Field(default_factory=uuid4, primary_key=True)
    tenant_id: UUID = Field(index=True, foreign_key="tenant.id", ondelete="CASCADE")
    client_sale_id: str = Field(max_length=64)
    till_id: str = Field(max_length=64, index=True)
    staff_user_id: Optional[UUID] = Field(default=None, foreign_key="user.id", ondelete="SET NULL")
    staff_name: Optional[str] = Field(default=None, max_length=120)
    customer_id: Optional[UUID] = Field(default=None, index=True, foreign_key="customer.id", ondelete="SET NULL")
    status: str = Field(default="paid", max_length=16)  # paid | refund
    #: When the till rang it up (may be well before it reached the server).
    occurred_at: datetime
    #: occurred_at as a date in the shop's timezone; what end-of-day reports group by.
    business_date: date = Field(index=True)
    price_book_id: Optional[UUID] = Field(default=None, foreign_key="pospricebook.id", ondelete="SET NULL")
    price_book_version: Optional[int] = None
    gst_rate_bp: int
    gross_cents: int  # sum of lines at shelf price
    combo_cents: int = 0
    discount_cents: int = 0
    discount_reason: Optional[str] = Field(default=None, max_length=200)
    total_cents: int
    gst_cents: int
    #: Cash rounding to the nearest coin; positive = customer paid more than total.
    rounding_cents: int = 0
    note: Optional[str] = Field(default=None, max_length=2000)
    #: For refunds: the sale being refunded.
    refund_of_sale_id: Optional[UUID] = Field(default=None, foreign_key="possale.id", ondelete="SET NULL")
    loyalty_points_earned: int = 0
    received_at: datetime = Field(default_factory=_now)


class PosSaleLine(SQLModel, table=True):
    id: UUID = Field(default_factory=uuid4, primary_key=True)
    tenant_id: UUID = Field(index=True, foreign_key="tenant.id", ondelete="CASCADE")
    sale_id: UUID = Field(index=True, foreign_key="possale.id", ondelete="CASCADE")
    position: int = 0
    item_key: str = Field(max_length=120)
    item_name: str = Field(max_length=200)
    category_key: Optional[str] = Field(default=None, max_length=120)
    category_name: Optional[str] = Field(default=None, max_length=120)
    group_key: Optional[str] = Field(default=None, max_length=120)
    unit_price_cents: int
    qty: int
    combo_cents: int = 0
    combo_label: Optional[str] = Field(default=None, max_length=120)
    gst_free: bool = False
    is_service: bool = True
    job_type: Optional[str] = Field(default=None, max_length=16)
    job_id: Optional[UUID] = None


class PosTender(SQLModel, table=True):
    id: UUID = Field(default_factory=uuid4, primary_key=True)
    tenant_id: UUID = Field(index=True, foreign_key="tenant.id", ondelete="CASCADE")
    sale_id: UUID = Field(index=True, foreign_key="possale.id", ondelete="CASCADE")
    position: int = 0
    tender_type: str = Field(max_length=16)  # eftpos | cash | voucher | account | points
    amount_cents: int
    tendered_cents: Optional[int] = None
    provider: Optional[str] = Field(default=None, max_length=32)
    reference: Optional[str] = Field(default=None, max_length=64)
    auth_code: Optional[str] = Field(default=None, max_length=32)
    card_type: Optional[str] = Field(default=None, max_length=32)
    masked_pan: Optional[str] = Field(default=None, max_length=32)
