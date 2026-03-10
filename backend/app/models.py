from datetime import date, datetime, timezone
from typing import Literal, Optional
from uuid import UUID, uuid4

from sqlmodel import Field, SQLModel

JobStatus = Literal[
    "awaiting_go_ahead",
    "go_ahead",
    "no_go",
    "working_on",
    "awaiting_parts",
    "parts_to_order",
    "sent_to_labanda",
    "service",
    "completed",
    "awaiting_collection",
    "collected",
]
QuoteStatus = Literal["draft", "sent", "approved", "declined", "expired"]
QuoteDecision = Literal["approved", "declined"]
QuoteItemType = Literal["labor", "part", "fee"]


class Tenant(SQLModel, table=True):
    id: UUID = Field(default_factory=uuid4, primary_key=True)
    name: str
    slug: str = Field(index=True, unique=True)
    plan_tier: str = "starter"
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class User(SQLModel, table=True):
    id: UUID = Field(default_factory=uuid4, primary_key=True)
    tenant_id: UUID = Field(index=True, foreign_key="tenant.id")
    email: str = Field(index=True)
    full_name: str
    role: str = "owner"
    password_hash: str
    is_active: bool = True
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class Customer(SQLModel, table=True):
    id: UUID = Field(default_factory=uuid4, primary_key=True)
    tenant_id: UUID = Field(index=True, foreign_key="tenant.id")
    full_name: str
    email: Optional[str] = None
    phone: Optional[str] = None
    address: Optional[str] = None
    notes: Optional[str] = None
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class Watch(SQLModel, table=True):
    id: UUID = Field(default_factory=uuid4, primary_key=True)
    tenant_id: UUID = Field(index=True, foreign_key="tenant.id")
    customer_id: UUID = Field(foreign_key="customer.id")
    brand: Optional[str] = None
    model: Optional[str] = None
    serial_number: Optional[str] = None
    movement_type: Optional[str] = None
    condition_notes: Optional[str] = None
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class RepairJob(SQLModel, table=True):
    id: UUID = Field(default_factory=uuid4, primary_key=True)
    tenant_id: UUID = Field(index=True, foreign_key="tenant.id")
    watch_id: UUID = Field(index=True, foreign_key="watch.id")
    assigned_user_id: Optional[UUID] = Field(default=None, foreign_key="user.id")
    job_number: str = Field(index=True)
    status_token: str = Field(default_factory=lambda: uuid4().hex, index=True, unique=True)
    title: str
    description: Optional[str] = None
    priority: str = "normal"
    status: str = "awaiting_go_ahead"
    salesperson: Optional[str] = None
    collection_date: Optional[date] = None
    deposit_cents: int = 0
    pre_quote_cents: int = 0
    cost_cents: int = 0
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class JobStatusHistory(SQLModel, table=True):
    id: UUID = Field(default_factory=uuid4, primary_key=True)
    tenant_id: UUID = Field(index=True, foreign_key="tenant.id")
    repair_job_id: UUID = Field(index=True, foreign_key="repairjob.id")
    old_status: Optional[str] = None
    new_status: str
    changed_by_user_id: Optional[UUID] = Field(default=None, foreign_key="user.id")
    change_note: Optional[str] = None
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class WorkLog(SQLModel, table=True):
    id: UUID = Field(default_factory=uuid4, primary_key=True)
    tenant_id: UUID = Field(index=True, foreign_key="tenant.id")
    repair_job_id: UUID = Field(index=True, foreign_key="repairjob.id")
    user_id: Optional[UUID] = Field(default=None, foreign_key="user.id")
    note: Optional[str] = None
    minutes_spent: int = 0
    started_at: Optional[datetime] = None
    ended_at: Optional[datetime] = None
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class Attachment(SQLModel, table=True):
    id: UUID = Field(default_factory=uuid4, primary_key=True)
    tenant_id: UUID = Field(index=True, foreign_key="tenant.id")
    repair_job_id: Optional[UUID] = Field(default=None, index=True, foreign_key="repairjob.id")
    watch_id: Optional[UUID] = Field(default=None, index=True, foreign_key="watch.id")
    uploaded_by_user_id: Optional[UUID] = Field(default=None, foreign_key="user.id")
    storage_key: str = Field(index=True, unique=True)
    file_name: Optional[str] = None
    content_type: Optional[str] = None
    file_size_bytes: Optional[int] = None
    label: Optional[str] = None  # e.g. "watch_front", "watch_back"
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class Quote(SQLModel, table=True):
    id: UUID = Field(default_factory=uuid4, primary_key=True)
    tenant_id: UUID = Field(index=True, foreign_key="tenant.id")
    repair_job_id: UUID = Field(index=True, foreign_key="repairjob.id")
    status: str = "draft"
    subtotal_cents: int = 0
    tax_cents: int = 0
    total_cents: int = 0
    currency: str = "USD"
    approval_token: str = Field(default_factory=lambda: uuid4().hex, index=True, unique=True)
    sent_at: Optional[datetime] = None
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class QuoteLineItem(SQLModel, table=True):
    id: UUID = Field(default_factory=uuid4, primary_key=True)
    tenant_id: UUID = Field(index=True, foreign_key="tenant.id")
    quote_id: UUID = Field(index=True, foreign_key="quote.id")
    item_type: str
    description: str
    quantity: float = 1
    unit_price_cents: int
    total_price_cents: int
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class Approval(SQLModel, table=True):
    id: UUID = Field(default_factory=uuid4, primary_key=True)
    tenant_id: UUID = Field(index=True, foreign_key="tenant.id")
    quote_id: UUID = Field(index=True, foreign_key="quote.id")
    decision: str
    ip_address: Optional[str] = None
    user_agent: Optional[str] = None
    decided_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class Invoice(SQLModel, table=True):
    id: UUID = Field(default_factory=uuid4, primary_key=True)
    tenant_id: UUID = Field(index=True, foreign_key="tenant.id")
    repair_job_id: UUID = Field(index=True, foreign_key="repairjob.id")
    quote_id: Optional[UUID] = Field(default=None, foreign_key="quote.id")
    invoice_number: str = Field(index=True)
    status: str = "unpaid"
    subtotal_cents: int = 0
    tax_cents: int = 0
    total_cents: int = 0
    currency: str = "USD"
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class Payment(SQLModel, table=True):
    id: UUID = Field(default_factory=uuid4, primary_key=True)
    tenant_id: UUID = Field(index=True, foreign_key="tenant.id")
    invoice_id: UUID = Field(index=True, foreign_key="invoice.id")
    amount_cents: int
    currency: str = "USD"
    status: str = "succeeded"
    provider: str = "manual"
    provider_reference: Optional[str] = None
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class SmsLog(SQLModel, table=True):
    """Audit trail for every SMS sent (or attempted) by the system."""
    id: UUID = Field(default_factory=uuid4, primary_key=True)
    tenant_id: UUID = Field(index=True, foreign_key="tenant.id")
    repair_job_id: Optional[UUID] = Field(default=None, index=True, foreign_key="repairjob.id")
    to_phone: str
    body: str
    event: str  # e.g. "quote_sent", "status_ready"
    provider_sid: Optional[str] = None  # Twilio message SID
    status: str = "dry_run"  # "sent" | "dry_run" | "failed"
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class ImportLog(SQLModel, table=True):
    id: UUID = Field(default_factory=uuid4, primary_key=True)
    tenant_id: UUID = Field(index=True, foreign_key="tenant.id")
    uploaded_by_user_id: Optional[UUID] = Field(default=None, foreign_key="user.id")
    file_name: str
    file_type: str
    total_rows: int = 0
    imported_count: int = 0
    skipped_count: int = 0
    customers_created_count: int = 0
    status: str = "processing"  # "processing" | "completed" | "failed"
    error_message: Optional[str] = None
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class ImportLogDetail(SQLModel, table=True):
    id: UUID = Field(default_factory=uuid4, primary_key=True)
    import_log_id: UUID = Field(index=True, foreign_key="importlog.id")
    row_number: int
    skip_reason: Optional[str] = None
    created_repair_job_id: Optional[UUID] = Field(default=None, foreign_key="repairjob.id")
    created_customer_id: Optional[UUID] = Field(default=None, foreign_key="customer.id")
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class TenantBootstrap(SQLModel):
    tenant_name: str
    tenant_slug: str
    owner_email: str
    owner_full_name: str
    owner_password: str


class TenantSignupRequest(SQLModel):
    tenant_name: str
    tenant_slug: str
    email: str
    full_name: str
    password: str


class LoginRequest(SQLModel):
    tenant_slug: str
    email: str
    password: str


class TokenResponse(SQLModel):
    access_token: str
    token_type: str = "bearer"
    expires_in_seconds: int


class PublicUser(SQLModel):
    id: UUID
    tenant_id: UUID
    email: str
    full_name: str
    role: str
    is_active: bool


class BootstrapResponse(SQLModel):
    tenant_id: UUID
    owner_user: PublicUser


class TenantSignupResponse(SQLModel):
    tenant_id: UUID
    user: PublicUser
    access_token: str
    token_type: str = "bearer"
    expires_in_seconds: int


class ImportSummaryResponse(SQLModel):
    import_id: UUID
    imported: int
    skipped: int
    customers_created: int
    total_rows: int
    skipped_reasons: dict[str, int] = Field(default_factory=dict)


class CustomerCreate(SQLModel):
    full_name: str
    email: Optional[str] = None
    phone: Optional[str] = None
    address: Optional[str] = None
    notes: Optional[str] = None


class CustomerRead(SQLModel):
    id: UUID
    tenant_id: UUID
    full_name: str
    email: Optional[str] = None
    phone: Optional[str] = None
    address: Optional[str] = None
    notes: Optional[str] = None
    created_at: datetime


class WatchCreate(SQLModel):
    customer_id: UUID
    brand: Optional[str] = None
    model: Optional[str] = None
    serial_number: Optional[str] = None
    movement_type: Optional[str] = None
    condition_notes: Optional[str] = None


class WatchRead(SQLModel):
    id: UUID
    tenant_id: UUID
    customer_id: UUID
    brand: Optional[str] = None
    model: Optional[str] = None
    serial_number: Optional[str] = None
    movement_type: Optional[str] = None
    condition_notes: Optional[str] = None


class RepairJobCreate(SQLModel):
    watch_id: UUID
    title: str
    description: Optional[str] = None
    priority: Literal["low", "normal", "high", "urgent"] = "normal"
    assigned_user_id: Optional[UUID] = None
    salesperson: Optional[str] = None
    collection_date: Optional[date] = None
    deposit_cents: int = 0
    pre_quote_cents: int = 0
    cost_cents: int = 0


class RepairJobRead(SQLModel):
    id: UUID
    tenant_id: UUID
    watch_id: UUID
    assigned_user_id: Optional[UUID] = None
    job_number: str
    status_token: str
    title: str
    description: Optional[str] = None
    priority: Literal["low", "normal", "high", "urgent"]
    status: JobStatus
    salesperson: Optional[str] = None
    collection_date: Optional[date] = None
    deposit_cents: int
    pre_quote_cents: int
    cost_cents: int
    created_at: datetime


class RepairJobStatusUpdate(SQLModel):
    status: JobStatus
    note: Optional[str] = None


class RepairJobIntakeUpdate(SQLModel):
    intake_notes: Optional[str] = None
    pre_quote_cents: int = 0
    has_scratches: bool = False
    has_dents: bool = False
    has_cracked_crystal: bool = False
    crown_missing: bool = False
    strap_damage: bool = False


class JobStatusHistoryRead(SQLModel):
    id: UUID
    repair_job_id: UUID
    old_status: Optional[str] = None
    new_status: str
    changed_by_user_id: Optional[UUID] = None
    change_note: Optional[str] = None
    created_at: datetime


class WorkLogCreate(SQLModel):
    repair_job_id: UUID
    note: Optional[str] = None
    minutes_spent: int = 0
    started_at: Optional[datetime] = None
    ended_at: Optional[datetime] = None


class WorkLogRead(SQLModel):
    id: UUID
    tenant_id: UUID
    repair_job_id: UUID
    user_id: Optional[UUID] = None
    note: Optional[str] = None
    minutes_spent: int
    started_at: Optional[datetime] = None
    ended_at: Optional[datetime] = None
    created_at: datetime


class AttachmentCreate(SQLModel):
    repair_job_id: Optional[UUID] = None
    watch_id: Optional[UUID] = None
    file_name: str
    content_type: str
    file_size_bytes: int


class AttachmentRead(SQLModel):
    id: UUID
    tenant_id: UUID
    repair_job_id: Optional[UUID] = None
    watch_id: Optional[UUID] = None
    storage_key: str
    file_name: Optional[str] = None
    content_type: Optional[str] = None
    file_size_bytes: Optional[int] = None
    label: Optional[str] = None
    created_at: datetime


class AttachmentUrlResponse(SQLModel):
    attachment: AttachmentRead
    upload_url: str
    download_url: str


class QuoteLineItemCreate(SQLModel):
    item_type: QuoteItemType
    description: str
    quantity: float
    unit_price_cents: int


class QuoteCreate(SQLModel):
    repair_job_id: UUID
    line_items: list[QuoteLineItemCreate]
    tax_cents: int = 0


class QuoteRead(SQLModel):
    id: UUID
    tenant_id: UUID
    repair_job_id: UUID
    status: QuoteStatus
    subtotal_cents: int
    tax_cents: int
    total_cents: int
    currency: str
    approval_token: str
    sent_at: Optional[datetime] = None
    created_at: datetime


class QuoteSendResponse(SQLModel):
    id: UUID
    status: QuoteStatus
    sent_at: datetime
    approval_token: str


class QuoteDecisionRequest(SQLModel):
    decision: QuoteDecision


class QuoteDecisionResponse(SQLModel):
    quote_id: UUID
    status: QuoteStatus
    decision: QuoteDecision


class InvoiceRead(SQLModel):
    id: UUID
    tenant_id: UUID
    repair_job_id: UUID
    quote_id: Optional[UUID] = None
    invoice_number: str
    status: Literal["unpaid", "paid", "refunded", "void"]
    subtotal_cents: int
    tax_cents: int
    total_cents: int
    currency: str
    created_at: datetime


class PaymentCreate(SQLModel):
    amount_cents: int
    provider_reference: Optional[str] = None


class PaymentRead(SQLModel):
    id: UUID
    tenant_id: UUID
    invoice_id: UUID
    amount_cents: int
    currency: str
    status: Literal["pending", "succeeded", "failed", "refunded"]
    provider: str
    provider_reference: Optional[str] = None


class InvoiceWithPayments(SQLModel):
    invoice: InvoiceRead
    payments: list[PaymentRead]


class InvoiceCreateFromQuoteResponse(SQLModel):
    invoice: InvoiceRead
