"""Issued monthly HQ invoices (the Minit bundled bill).

``app.minit_billing`` works out the numbers; this table freezes them. Once an
invoice leaves ``draft`` the snapshot never changes, so later operator changes
(a shop going exempt, the add-on price stepping up) cannot rewrite history.
"""
from datetime import date, datetime, timezone
from typing import Optional
from uuid import UUID, uuid4

from sqlalchemy import UniqueConstraint
from sqlmodel import Field, SQLModel

HQ_INVOICE_STATUSES = ("draft", "issued", "paid", "void")


class HqInvoice(SQLModel, table=True):
    __table_args__ = (UniqueConstraint("parent_account_id", "billing_month", name="uq_hqinvoice_parent_month"),)

    id: UUID = Field(default_factory=uuid4, primary_key=True)
    parent_account_id: UUID = Field(foreign_key="parentaccount.id", index=True, ondelete="CASCADE")
    #: First day of the billed month.
    billing_month: date
    invoice_number: str = Field(index=True)
    status: str = Field(default="draft", index=True)
    #: Frozen output of ``minit_billing.summary_to_dict`` (integer cents).
    snapshot_json: str = Field(default="{}")
    operator_count: int = 0
    subtotal_cents: int = 0
    gst_cents: int = 0
    total_cents: int = 0
    currency: str = Field(default="AUD", max_length=3)
    stripe_invoice_id: Optional[str] = Field(default=None, index=True)
    stripe_hosted_url: Optional[str] = None
    stripe_pdf_url: Optional[str] = None
    issued_at: Optional[datetime] = None
    due_at: Optional[datetime] = None
    paid_at: Optional[datetime] = None
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
