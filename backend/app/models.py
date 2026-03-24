from datetime import date, datetime, timezone
from typing import Literal, Optional
from uuid import UUID, uuid4

FleetAccountType = Literal["Dealership", "Rental Fleet", "Government Fleet", "Corporate Fleet", "Car Auctions", "Other"]
FleetBillingCycle = Literal["Monthly", "Fortnightly", "Weekly"]
SubscriptionPlan = Literal["starter", "pro", "fleet", "none"]

from sqlmodel import Field, SQLModel

JobStatus = Literal[
    "awaiting_quote",
    "awaiting_go_ahead",
    "go_ahead",
    "no_go",
    "working_on",
    "awaiting_parts",
    "parts_to_order",
    "sent_to_labanda",
    "quoted_by_labanda",
    "service",
    "completed",
    "awaiting_collection",
    "collected",
    "en_route",   # Auto key mobile: tech driving to job
    "on_site",    # Auto key mobile: tech arrived at location
]
QuoteStatus = Literal["draft", "sent", "approved", "declined", "expired"]
QuoteDecision = Literal["approved", "declined"]
QuoteItemType = Literal["labor", "part", "fee"]
PlanCode = Literal[
    "watch",
    "shoe",
    "auto_key",
    "enterprise",
    "basic_watch",
    "basic_shoe",
    "basic_auto_key",
    "basic_watch_shoe",
    "basic_watch_auto_key",
    "basic_shoe_auto_key",
    "basic_all_tabs",
    "pro",
]


class Tenant(SQLModel, table=True):
    id: UUID = Field(default_factory=uuid4, primary_key=True)
    name: str
    slug: str = Field(index=True, unique=True)
    plan_tier: str = "starter"
    plan_code: str = "pro"
    stripe_customer_id: Optional[str] = Field(default=None, index=True)
    stripe_subscription_id: Optional[str] = Field(default=None, index=True)
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


class ParentAccount(SQLModel, table=True):
    id: UUID = Field(default_factory=uuid4, primary_key=True)
    name: str
    owner_email: str = Field(index=True)
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class ParentAccountMembership(SQLModel, table=True):
    id: UUID = Field(default_factory=uuid4, primary_key=True)
    parent_account_id: UUID = Field(index=True, foreign_key="parentaccount.id")
    tenant_id: UUID = Field(index=True, foreign_key="tenant.id")
    user_id: UUID = Field(index=True, foreign_key="user.id")
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class ParentAccountEventLog(SQLModel, table=True):
    id: UUID = Field(default_factory=uuid4, primary_key=True)
    parent_account_id: UUID = Field(index=True, foreign_key="parentaccount.id")
    tenant_id: Optional[UUID] = Field(default=None, index=True, foreign_key="tenant.id")
    actor_user_id: Optional[UUID] = Field(default=None, index=True, foreign_key="user.id")
    actor_email: Optional[str] = None
    event_type: str = Field(index=True)
    event_summary: str
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class TenantEventLog(SQLModel, table=True):
    """Per-tenant audit log for notable business and security events."""
    id: UUID = Field(default_factory=uuid4, primary_key=True)
    tenant_id: UUID = Field(index=True, foreign_key="tenant.id")
    actor_user_id: Optional[UUID] = Field(default=None, index=True, foreign_key="user.id")
    actor_email: Optional[str] = None
    entity_type: str = Field(index=True)  # "session", "user", "invoice", "tenant"
    entity_id: Optional[UUID] = Field(default=None, index=True)
    event_type: str = Field(index=True)  # "login", "user_created", "invoice_created", "plan_changed"
    event_summary: str
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class CustomService(SQLModel, table=True):
    """Tenant-defined service for watch or shoe repairs, shown alongside built-in catalogue."""
    id: UUID = Field(default_factory=uuid4, primary_key=True)
    tenant_id: UUID = Field(index=True, foreign_key="tenant.id")
    service_type: str = Field(index=True)  # "watch" | "shoe"
    name: str
    group_id: str = "custom"  # e.g. "custom" or an existing group id
    group_label: str = "Custom"
    price_cents: int
    pricing_type: str = "fixed"  # for shoe: fixed, from, quoted_upon_inspection, etc.
    notes: Optional[str] = None
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class CustomServiceCreate(SQLModel):
    service_type: str  # "watch" | "shoe"
    name: str
    group_id: str = "custom"
    group_label: str = "Custom"
    price_cents: int
    pricing_type: str = "fixed"
    notes: Optional[str] = None


class CustomServiceRead(SQLModel):
    id: UUID
    tenant_id: UUID
    service_type: str
    name: str
    group_id: str
    group_label: str
    price_cents: int
    pricing_type: str
    notes: Optional[str] = None
    created_at: datetime


class CustomServiceUpdate(SQLModel):
    name: Optional[str] = None
    group_id: Optional[str] = None
    group_label: Optional[str] = None
    price_cents: Optional[int] = None
    pricing_type: Optional[str] = None
    notes: Optional[str] = None


class Suburb(SQLModel, table=True):
    """Australian suburb/locality for prospect search. Populated from public data (e.g. matthewproctor/australianpostcodes)."""
    id: UUID = Field(default_factory=uuid4, primary_key=True)
    name: str = Field(index=True)
    state_code: str = Field(index=True)  # ACT, NSW, NT, QLD, SA, TAS, VIC, WA


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
    customer_account_id: Optional[UUID] = Field(default=None, index=True, foreign_key="customeraccount.id")
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
    shoe_repair_job_id: Optional[UUID] = Field(default=None, index=True, foreign_key="shoerepairjob.id")
    auto_key_job_id: Optional[UUID] = Field(default=None, index=True, foreign_key="autokeyjob.id")
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
    customer_signature_data_url: Optional[str] = None  # Base64 PNG data URL from signature pad
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
    event: str  # e.g. "quote_sent", "job_live", "status_ready"
    provider_sid: Optional[str] = None  # Twilio message SID
    status: str = "dry_run"  # "sent" | "dry_run" | "failed"
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class SmsLogRead(SQLModel):
    id: UUID
    to_phone: str
    body: str
    event: str
    status: str
    created_at: datetime


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
    plan_code: Optional[PlanCode] = None


class TenantSignupRequest(SQLModel):
    tenant_name: str
    tenant_slug: str
    email: str
    full_name: str
    password: str
    plan_code: Optional[PlanCode] = None


class LoginRequest(SQLModel):
    tenant_slug: str
    email: str
    password: str


class MultiSiteLoginRequest(SQLModel):
    email: str
    password: str


class RefreshRequest(SQLModel):
    refresh_token: str


class TokenResponse(SQLModel):
    access_token: str
    token_type: str = "bearer"
    expires_in_seconds: int
    refresh_token: Optional[str] = None
    refresh_expires_in_seconds: Optional[int] = None


class PublicUser(SQLModel):
    id: UUID
    tenant_id: UUID
    email: str
    full_name: str
    role: str
    is_active: bool


class AuthSessionSiteOption(SQLModel):
    tenant_id: UUID
    tenant_slug: str
    tenant_name: str
    user_id: UUID
    role: str


class AuthSessionResponse(SQLModel):
    user: PublicUser
    tenant_id: UUID
    tenant_slug: str
    plan_code: PlanCode
    enabled_features: list[str]
    active_site_tenant_id: UUID
    available_sites: list[AuthSessionSiteOption] = Field(default_factory=list)


class MultiSiteLoginResponse(SQLModel):
    access_token: str
    token_type: str = "bearer"
    expires_in_seconds: int
    refresh_token: Optional[str] = None
    refresh_expires_in_seconds: Optional[int] = None
    active_site_tenant_id: UUID
    available_sites: list[AuthSessionSiteOption] = Field(default_factory=list)


class ActiveSiteSwitchRequest(SQLModel):
    tenant_id: UUID


class ActiveSiteSwitchResponse(SQLModel):
    access_token: str
    token_type: str = "bearer"
    expires_in_seconds: int
    refresh_token: Optional[str] = None
    refresh_expires_in_seconds: Optional[int] = None
    active_site_tenant_id: UUID
    available_sites: list[AuthSessionSiteOption] = Field(default_factory=list)


class ParentAccountSiteRead(SQLModel):
    tenant_id: UUID
    tenant_slug: str
    tenant_name: str
    owner_user_id: UUID
    owner_email: str
    owner_full_name: str


class ParentAccountSummaryResponse(SQLModel):
    parent_account_id: UUID
    parent_account_name: str
    owner_email: str
    sites: list[ParentAccountSiteRead] = Field(default_factory=list)


class ParentAccountEventLogRead(SQLModel):
    id: UUID
    parent_account_id: UUID
    tenant_id: Optional[UUID] = None
    actor_user_id: Optional[UUID] = None
    actor_email: Optional[str] = None
    event_type: str
    event_summary: str
    created_at: datetime


class TenantEventLogRead(SQLModel):
    id: UUID
    tenant_id: UUID
    actor_user_id: Optional[UUID] = None
    actor_email: Optional[str] = None
    entity_type: str
    entity_id: Optional[UUID] = None
    event_type: str
    event_summary: str
    created_at: datetime


class BillingPlanLimits(SQLModel):
    max_users: int
    max_repair_jobs: int
    max_shoe_jobs: int
    max_auto_key_jobs: int


class BillingLimitsUsage(SQLModel):
    users: int
    repair_jobs: int
    shoe_jobs: int
    auto_key_jobs: int


class BillingLimitsResponse(SQLModel):
    plan_code: str
    limits: BillingPlanLimits
    usage: BillingLimitsUsage
    stripe_configured: bool
    stripe_subscription_id: Optional[str] = None
    stripe_customer_id: Optional[str] = None


class BillingCheckoutRequest(SQLModel):
    price_id: str


class BillingCheckoutPlanRequest(SQLModel):
    plan_code: PlanCode


class ParentAccountLinkTenantRequest(SQLModel):
    tenant_slug: str
    owner_email: str


class ParentAccountCreateTenantRequest(SQLModel):
    tenant_name: str
    tenant_slug: str
    plan_code: Optional[PlanCode] = None


class TenantPlanUpdateRequest(SQLModel):
    plan_code: PlanCode


class PlatformUserRead(SQLModel):
    id: UUID
    tenant_id: UUID
    tenant_slug: str
    tenant_name: str
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
    refresh_token: Optional[str] = None
    refresh_expires_in_seconds: Optional[int] = None


class UserCreateRequest(SQLModel):
    email: str
    full_name: str
    password: str
    role: str = "manager"


class UserUpdateRequest(SQLModel):
    full_name: Optional[str] = None
    role: Optional[str] = None
    password: Optional[str] = None
    is_active: Optional[bool] = None


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
    customer_account_id: Optional[UUID] = None
    title: str
    description: Optional[str] = None
    priority: Literal["low", "normal", "high", "urgent"] = "normal"
    status: Optional[str] = None  # If omitted, uses model default (awaiting_go_ahead)
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
    customer_account_id: Optional[UUID] = None
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


class RepairJobFieldUpdate(SQLModel):
    customer_account_id: Optional[UUID] = None
    cost_cents: Optional[int] = None
    pre_quote_cents: Optional[int] = None
    priority: Optional[str] = None
    salesperson: Optional[str] = None
    collection_date: Optional[date] = None
    deposit_cents: Optional[int] = None
    description: Optional[str] = None


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
    shoe_repair_job_id: Optional[UUID] = None
    file_name: str
    content_type: str
    file_size_bytes: int


class AttachmentRead(SQLModel):
    id: UUID
    tenant_id: UUID
    repair_job_id: Optional[UUID] = None
    watch_id: Optional[UUID] = None
    shoe_repair_job_id: Optional[UUID] = None
    auto_key_job_id: Optional[UUID] = None
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
    signature_data_url: Optional[str] = None  # Base64 PNG data URL from signature pad (optional)


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


# ── Shoe Repairs ──────────────────────────────────────────────────────────────

class Shoe(SQLModel, table=True):
    """A pair (or single) of shoes linked to a customer — parallel to Watch."""
    id: UUID = Field(default_factory=uuid4, primary_key=True)
    tenant_id: UUID = Field(index=True, foreign_key="tenant.id")
    customer_id: UUID = Field(index=True, foreign_key="customer.id")
    shoe_type: Optional[str] = None   # e.g. "boots", "sneakers", "dress", "sandals"
    brand: Optional[str] = None
    color: Optional[str] = None
    description_notes: Optional[str] = None
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class ShoeRepairJob(SQLModel, table=True):
    """A shoe repair job — parallel to RepairJob."""
    id: UUID = Field(default_factory=uuid4, primary_key=True)
    tenant_id: UUID = Field(index=True, foreign_key="tenant.id")
    shoe_id: UUID = Field(index=True, foreign_key="shoe.id")
    assigned_user_id: Optional[UUID] = Field(default=None, foreign_key="user.id")
    customer_account_id: Optional[UUID] = Field(default=None, index=True, foreign_key="customeraccount.id")
    job_number: str = Field(index=True)
    status_token: str = Field(default_factory=lambda: uuid4().hex, index=True, unique=True)
    title: str
    description: Optional[str] = None
    priority: str = "normal"
    status: str = "awaiting_go_ahead"
    salesperson: Optional[str] = None
    collection_date: Optional[date] = None
    deposit_cents: int = 0
    cost_cents: int = 0
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class ShoeRepairJobShoe(SQLModel, table=True):
    """Additional shoe pairs linked to a ShoeRepairJob beyond the primary shoe_id."""
    id: UUID = Field(default_factory=uuid4, primary_key=True)
    tenant_id: UUID = Field(index=True, foreign_key="tenant.id")
    shoe_repair_job_id: UUID = Field(index=True, foreign_key="shoerepairjob.id")
    shoe_id: UUID = Field(foreign_key="shoe.id")
    sort_order: int = Field(default=1)
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class ShoeRepairJobItem(SQLModel, table=True):
    """A catalogue line item selected for a shoe repair job."""
    id: UUID = Field(default_factory=uuid4, primary_key=True)
    tenant_id: UUID = Field(index=True, foreign_key="tenant.id")
    shoe_repair_job_id: UUID = Field(index=True, foreign_key="shoerepairjob.id")
    catalogue_key: str          # e.g. "heels__all_pegged_pin_heels"
    catalogue_group: str        # e.g. "heels"
    item_name: str
    pricing_type: str           # e.g. "fixed", "from", "pair", …
    unit_price_cents: Optional[int] = None  # null for quoted_upon_inspection
    quantity: float = 1.0
    notes: Optional[str] = None
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


# ── Shoe Repair — Pydantic schemas ────────────────────────────────────────────

class ShoeCreate(SQLModel):
    customer_id: UUID
    shoe_type: Optional[str] = None
    brand: Optional[str] = None
    color: Optional[str] = None
    description_notes: Optional[str] = None


class ShoeRead(SQLModel):
    id: UUID
    tenant_id: UUID
    customer_id: UUID
    shoe_type: Optional[str] = None
    brand: Optional[str] = None
    color: Optional[str] = None
    description_notes: Optional[str] = None
    created_at: datetime


class ShoeRepairJobItemCreate(SQLModel):
    catalogue_key: str
    catalogue_group: str
    item_name: str
    pricing_type: str
    unit_price_cents: Optional[int] = None
    quantity: float = 1.0
    notes: Optional[str] = None


class ShoeRepairJobItemsAppend(SQLModel):
    items: list[ShoeRepairJobItemCreate] = []


class ShoeRepairJobItemRead(SQLModel):
    id: UUID
    shoe_repair_job_id: UUID
    catalogue_key: str
    catalogue_group: str
    item_name: str
    pricing_type: str
    unit_price_cents: Optional[int] = None
    quantity: float
    notes: Optional[str] = None
    created_at: datetime


class ShoeRepairJobShoeRead(SQLModel):
    id: UUID
    shoe_id: UUID
    shoe: Optional['ShoeRead'] = None
    sort_order: int


class ShoeRepairJobCreate(SQLModel):
    shoe_id: UUID
    customer_account_id: Optional[UUID] = None
    title: str
    description: Optional[str] = None
    priority: str = "normal"
    status: str = "awaiting_go_ahead"
    salesperson: Optional[str] = None
    collection_date: Optional[date] = None
    deposit_cents: int = 0
    cost_cents: int = 0
    items: list[ShoeRepairJobItemCreate] = []


class ShoeRepairJobRead(SQLModel):
    id: UUID
    tenant_id: UUID
    shoe_id: UUID
    assigned_user_id: Optional[UUID] = None
    customer_account_id: Optional[UUID] = None
    job_number: str
    status_token: str
    title: str
    description: Optional[str] = None
    priority: str
    status: str
    salesperson: Optional[str] = None
    collection_date: Optional[date] = None
    deposit_cents: int
    cost_cents: int
    created_at: datetime
    items: list[ShoeRepairJobItemRead] = []
    shoe: Optional[ShoeRead] = None
    extra_shoes: list[ShoeRepairJobShoeRead] = []
    # Derived from catalogue: max complexity of items, longest estimated turnaround
    complexity: Optional[str] = None  # "simple" | "standard" | "complex"
    estimated_days_min: Optional[int] = None
    estimated_days_max: Optional[int] = None
    # Queue-based: when this job expected to be ready (FIFO, derived from jobs ahead)
    estimated_ready_by: Optional[date] = None


class ShoeRepairJobStatusUpdate(SQLModel):
    status: str
    note: Optional[str] = None


class ShoeRepairJobFieldUpdate(SQLModel):
    customer_account_id: Optional[UUID] = None
    title: Optional[str] = None
    description: Optional[str] = None
    priority: Optional[str] = None
    salesperson: Optional[str] = None
    collection_date: Optional[date] = None
    deposit_cents: Optional[int] = None
    cost_cents: Optional[int] = None


# ── Auto Key Jobs ────────────────────────────────────────────────────────────

AutoKeyProgrammingStatus = Literal["pending", "in_progress", "programmed", "failed", "not_required"]


class AutoKeyJob(SQLModel, table=True):
    id: UUID = Field(default_factory=uuid4, primary_key=True)
    tenant_id: UUID = Field(index=True, foreign_key="tenant.id")
    customer_id: UUID = Field(index=True, foreign_key="customer.id")
    assigned_user_id: Optional[UUID] = Field(default=None, foreign_key="user.id")
    customer_account_id: Optional[UUID] = Field(default=None, index=True, foreign_key="customeraccount.id")
    job_number: str = Field(index=True)
    status_token: str = Field(default_factory=lambda: uuid4().hex, index=True, unique=True)
    title: str
    description: Optional[str] = None
    vehicle_make: Optional[str] = None
    vehicle_model: Optional[str] = None
    vehicle_year: Optional[int] = None
    registration_plate: Optional[str] = None
    vin: Optional[str] = None
    key_type: Optional[str] = None
    blade_code: Optional[str] = None
    chip_type: Optional[str] = None
    tech_notes: Optional[str] = None
    key_quantity: int = 1
    programming_status: str = "pending"
    priority: str = "normal"
    status: str = "awaiting_quote"
    # ServiceM8-style scheduling and location
    scheduled_at: Optional[datetime] = None
    job_address: Optional[str] = None  # For mobile jobs; falls back to customer address
    job_type: Optional[str] = None  # e.g. Key Cutting (in-store), Lockout – Car, etc.
    visit_order: Optional[int] = None  # Route order for same-day jobs (lower = first)
    salesperson: Optional[str] = None
    collection_date: Optional[date] = None
    deposit_cents: int = 0
    cost_cents: int = 0
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class AutoKeyJobCreate(SQLModel):
    customer_id: UUID
    customer_account_id: Optional[UUID] = None
    assigned_user_id: Optional[UUID] = None
    title: str
    description: Optional[str] = None
    scheduled_at: Optional[datetime] = None
    job_address: Optional[str] = None
    job_type: Optional[str] = None
    vehicle_make: Optional[str] = None
    vehicle_model: Optional[str] = None
    vehicle_year: Optional[int] = None
    registration_plate: Optional[str] = None
    vin: Optional[str] = None
    key_type: Optional[str] = None
    key_quantity: int = 1
    programming_status: AutoKeyProgrammingStatus = "pending"
    priority: Literal["low", "normal", "high", "urgent"] = "normal"
    status: JobStatus = "awaiting_quote"
    salesperson: Optional[str] = None
    collection_date: Optional[date] = None
    deposit_cents: int = 0
    cost_cents: int = 0


class AutoKeyJobRead(SQLModel):
    id: UUID
    tenant_id: UUID
    customer_id: UUID
    assigned_user_id: Optional[UUID] = None
    customer_account_id: Optional[UUID] = None
    job_number: str
    status_token: str
    title: str
    description: Optional[str] = None
    vehicle_make: Optional[str] = None
    vehicle_model: Optional[str] = None
    vehicle_year: Optional[int] = None
    registration_plate: Optional[str] = None
    vin: Optional[str] = None
    key_type: Optional[str] = None
    blade_code: Optional[str] = None
    chip_type: Optional[str] = None
    tech_notes: Optional[str] = None
    key_quantity: int
    programming_status: AutoKeyProgrammingStatus
    priority: Literal["low", "normal", "high", "urgent"]
    status: JobStatus
    salesperson: Optional[str] = None
    collection_date: Optional[date] = None
    deposit_cents: int
    cost_cents: int
    created_at: datetime
    scheduled_at: Optional[datetime] = None
    job_address: Optional[str] = None
    job_type: Optional[str] = None
    visit_order: Optional[int] = None


class AutoKeyJobStatusUpdate(SQLModel):
    status: JobStatus
    note: Optional[str] = None


class AutoKeyJobFieldUpdate(SQLModel):
    customer_account_id: Optional[UUID] = None
    title: Optional[str] = None
    description: Optional[str] = None
    assigned_user_id: Optional[UUID] = None
    scheduled_at: Optional[datetime] = None
    job_address: Optional[str] = None
    job_type: Optional[str] = None
    visit_order: Optional[int] = None
    vehicle_make: Optional[str] = None
    vehicle_model: Optional[str] = None
    vehicle_year: Optional[int] = None
    registration_plate: Optional[str] = None
    vin: Optional[str] = None
    key_type: Optional[str] = None
    blade_code: Optional[str] = None
    chip_type: Optional[str] = None
    tech_notes: Optional[str] = None
    key_quantity: Optional[int] = None
    programming_status: Optional[AutoKeyProgrammingStatus] = None
    collection_date: Optional[date] = None
    priority: Optional[Literal["low", "normal", "high", "urgent"]] = None
    salesperson: Optional[str] = None
    deposit_cents: Optional[int] = None
    cost_cents: Optional[int] = None


class AutoKeyQuote(SQLModel, table=True):
    id: UUID = Field(default_factory=uuid4, primary_key=True)
    tenant_id: UUID = Field(index=True, foreign_key="tenant.id")
    auto_key_job_id: UUID = Field(index=True, foreign_key="autokeyjob.id")
    status: str = "draft"
    subtotal_cents: int = 0
    tax_cents: int = 0
    total_cents: int = 0
    currency: str = "AUD"
    sent_at: Optional[datetime] = None
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class AutoKeyQuoteLineItem(SQLModel, table=True):
    id: UUID = Field(default_factory=uuid4, primary_key=True)
    tenant_id: UUID = Field(index=True, foreign_key="tenant.id")
    auto_key_quote_id: UUID = Field(index=True, foreign_key="autokeyquote.id")
    description: str
    quantity: float = 1
    unit_price_cents: int
    total_price_cents: int
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class AutoKeyInvoice(SQLModel, table=True):
    id: UUID = Field(default_factory=uuid4, primary_key=True)
    tenant_id: UUID = Field(index=True, foreign_key="tenant.id")
    auto_key_job_id: UUID = Field(index=True, foreign_key="autokeyjob.id")
    auto_key_quote_id: Optional[UUID] = Field(default=None, foreign_key="autokeyquote.id")
    invoice_number: str = Field(index=True)
    status: str = "unpaid"
    subtotal_cents: int = 0
    tax_cents: int = 0
    total_cents: int = 0
    currency: str = "AUD"
    payment_method: Optional[str] = None  # cash, eftpos, bank
    paid_at: Optional[datetime] = None
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class AutoKeyQuoteLineItemCreate(SQLModel):
    description: str
    quantity: float = 1
    unit_price_cents: int


class AutoKeyQuoteCreate(SQLModel):
    line_items: list[AutoKeyQuoteLineItemCreate]
    tax_cents: int = 0


class AutoKeyQuoteLineItemRead(SQLModel):
    id: UUID
    auto_key_quote_id: UUID
    description: str
    quantity: float
    unit_price_cents: int
    total_price_cents: int


class AutoKeyQuoteRead(SQLModel):
    id: UUID
    tenant_id: UUID
    auto_key_job_id: UUID
    status: str
    subtotal_cents: int
    tax_cents: int
    total_cents: int
    currency: str
    sent_at: Optional[datetime] = None
    created_at: datetime
    line_items: list[AutoKeyQuoteLineItemRead] = []


class AutoKeyInvoiceRead(SQLModel):
    id: UUID
    tenant_id: UUID
    auto_key_job_id: UUID
    auto_key_quote_id: Optional[UUID] = None
    invoice_number: str
    status: str
    subtotal_cents: int
    tax_cents: int
    total_cents: int
    currency: str
    payment_method: Optional[str] = None
    paid_at: Optional[datetime] = None
    created_at: datetime


class CustomerAccount(SQLModel, table=True):
    subscription_plan: str = "none"  # "starter", "pro", "fleet", "none"
    subscription_active: bool = False
    subscription_start_date: Optional[date] = None
    id: UUID = Field(default_factory=uuid4, primary_key=True)
    tenant_id: UUID = Field(index=True, foreign_key="tenant.id")
    name: str
    account_code: Optional[str] = Field(default=None, index=True)
    contact_name: Optional[str] = None
    contact_email: Optional[str] = None
    contact_phone: Optional[str] = None
    billing_address: Optional[str] = None
    payment_terms_days: int = 30
    notes: Optional[str] = None
    is_active: bool = True
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    # Fleet/Dealer fields
    account_type: Optional[str] = Field(default=None, index=True)
    fleet_size: Optional[int] = None
    primary_contact_name: Optional[str] = None
    primary_contact_phone: Optional[str] = None
    billing_cycle: Optional[str] = Field(default=None, index=True)
    credit_limit: Optional[int] = None
    account_notes: Optional[str] = None


class CustomerAccountMembership(SQLModel, table=True):
    id: UUID = Field(default_factory=uuid4, primary_key=True)
    tenant_id: UUID = Field(index=True, foreign_key="tenant.id")
    customer_account_id: UUID = Field(index=True, foreign_key="customeraccount.id")
    customer_id: UUID = Field(index=True, foreign_key="customer.id")
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class CustomerAccountCreate(SQLModel):
    subscription_plan: Optional[SubscriptionPlan] = None
    subscription_active: Optional[bool] = None
    subscription_start_date: Optional[date] = None
    name: str
    account_code: Optional[str] = None
    contact_name: Optional[str] = None
    contact_email: Optional[str] = None
    contact_phone: Optional[str] = None
    billing_address: Optional[str] = None
    payment_terms_days: int = 30
    notes: Optional[str] = None
    # Fleet/Dealer fields
    account_type: Optional[FleetAccountType] = None
    fleet_size: Optional[int] = None
    primary_contact_name: Optional[str] = None
    primary_contact_phone: Optional[str] = None
    billing_cycle: Optional[FleetBillingCycle] = None
    credit_limit: Optional[int] = None
    account_notes: Optional[str] = None


class CustomerAccountUpdate(SQLModel):
    subscription_plan: Optional[SubscriptionPlan] = None
    subscription_active: Optional[bool] = None
    subscription_start_date: Optional[date] = None
    name: Optional[str] = None
    account_code: Optional[str] = None
    contact_name: Optional[str] = None
    contact_email: Optional[str] = None
    contact_phone: Optional[str] = None
    billing_address: Optional[str] = None
    payment_terms_days: Optional[int] = None
    notes: Optional[str] = None
    is_active: Optional[bool] = None
    # Fleet/Dealer fields
    account_type: Optional[FleetAccountType] = None
    fleet_size: Optional[int] = None
    primary_contact_name: Optional[str] = None
    primary_contact_phone: Optional[str] = None
    billing_cycle: Optional[FleetBillingCycle] = None
    credit_limit: Optional[int] = None
    account_notes: Optional[str] = None


class CustomerAccountRead(SQLModel):
    subscription_plan: Optional[SubscriptionPlan] = None
    subscription_active: Optional[bool] = None
    subscription_start_date: Optional[date] = None
    id: UUID
    tenant_id: UUID
    name: str
    account_code: Optional[str] = None
    contact_name: Optional[str] = None
    contact_email: Optional[str] = None
    contact_phone: Optional[str] = None
    billing_address: Optional[str] = None
    payment_terms_days: int
    notes: Optional[str] = None
    is_active: bool
    created_at: datetime
    customer_ids: list[UUID] = []
    # Fleet/Dealer fields
    account_type: Optional[FleetAccountType] = None
    fleet_size: Optional[int] = None
    primary_contact_name: Optional[str] = None
    primary_contact_phone: Optional[str] = None
    billing_cycle: Optional[FleetBillingCycle] = None
    credit_limit: Optional[int] = None
    account_notes: Optional[str] = None


class CustomerAccountMemberAdd(SQLModel):
    customer_id: UUID


CustomerAccountSourceType = Literal["watch", "shoe", "auto_key"]


class CustomerAccountInvoice(SQLModel, table=True):
    id: UUID = Field(default_factory=uuid4, primary_key=True)
    tenant_id: UUID = Field(index=True, foreign_key="tenant.id")
    customer_account_id: UUID = Field(index=True, foreign_key="customeraccount.id")
    invoice_number: str = Field(index=True)
    period_year: int
    period_month: int
    status: str = "unpaid"
    subtotal_cents: int = 0
    tax_cents: int = 0
    total_cents: int = 0
    currency: str = "AUD"
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class CustomerAccountInvoiceLine(SQLModel, table=True):
    id: UUID = Field(default_factory=uuid4, primary_key=True)
    tenant_id: UUID = Field(index=True, foreign_key="tenant.id")
    customer_account_invoice_id: UUID = Field(index=True, foreign_key="customeraccountinvoice.id")
    source_type: str
    source_job_id: UUID = Field(index=True)
    job_number: str
    description: str
    amount_cents: int
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class CustomerAccountStatementLine(SQLModel):
    source_type: CustomerAccountSourceType
    source_job_id: UUID
    job_number: str
    description: str
    amount_cents: int


class CustomerAccountStatementResponse(SQLModel):
    customer_account_id: UUID
    period_year: int
    period_month: int
    lines: list[CustomerAccountStatementLine] = []
    subtotal_cents: int = 0


class CustomerAccountMonthlyInvoiceCreate(SQLModel):
    period_year: int
    period_month: int
    tax_cents: int = 0


class CustomerAccountInvoiceRead(SQLModel):
    id: UUID
    tenant_id: UUID
    customer_account_id: UUID
    invoice_number: str
    period_year: int
    period_month: int
    status: str
    subtotal_cents: int
    tax_cents: int
    total_cents: int
    currency: str
    created_at: datetime
    lines: list[CustomerAccountStatementLine] = []


# ── Stocktake ────────────────────────────────────────────────────────────────

StocktakeStatus = Literal["draft", "in_progress", "completed", "approved"]


class StockItem(SQLModel, table=True):
    id: UUID = Field(default_factory=uuid4, primary_key=True)
    tenant_id: UUID = Field(index=True, foreign_key="tenant.id")
    item_code: str = Field(index=True)
    group_code: str = Field(default="", index=True)
    group_name: Optional[str] = None
    item_description: Optional[str] = None
    description2: Optional[str] = None
    description3: Optional[str] = None
    full_description: Optional[str] = None
    unit_description: Optional[str] = None
    pack_description: Optional[str] = None
    pack_qty: float = 0
    cost_price_cents: int = 0
    retail_price_cents: int = 0
    system_stock_qty: float = 0
    is_active: bool = True
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class StocktakeSession(SQLModel, table=True):
    id: UUID = Field(default_factory=uuid4, primary_key=True)
    tenant_id: UUID = Field(index=True, foreign_key="tenant.id")
    name: str
    status: str = Field(default="draft", index=True)
    created_by_user_id: Optional[UUID] = Field(default=None, foreign_key="user.id")
    completed_by_user_id: Optional[UUID] = Field(default=None, foreign_key="user.id")
    group_code_filter: Optional[str] = None
    group_name_filter: Optional[str] = None
    search_filter: Optional[str] = None
    notes: Optional[str] = None
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    completed_at: Optional[datetime] = None


class StocktakeLine(SQLModel, table=True):
    id: UUID = Field(default_factory=uuid4, primary_key=True)
    tenant_id: UUID = Field(index=True, foreign_key="tenant.id")
    stocktake_session_id: UUID = Field(index=True, foreign_key="stocktakesession.id")
    stock_item_id: UUID = Field(index=True, foreign_key="stockitem.id")
    expected_qty: float = 0
    counted_qty: Optional[float] = None
    variance_qty: Optional[float] = None
    variance_value_cents: Optional[int] = None
    counted_by_user_id: Optional[UUID] = Field(default=None, foreign_key="user.id")
    counted_at: Optional[datetime] = None
    notes: Optional[str] = None
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class StockAdjustment(SQLModel, table=True):
    id: UUID = Field(default_factory=uuid4, primary_key=True)
    tenant_id: UUID = Field(index=True, foreign_key="tenant.id")
    stock_item_id: UUID = Field(index=True, foreign_key="stockitem.id")
    stocktake_session_id: UUID = Field(index=True, foreign_key="stocktakesession.id")
    old_qty: float = 0
    new_qty: float = 0
    variance_qty: float = 0
    variance_value_cents: int = 0
    reason: Optional[str] = None
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class StockItemRead(SQLModel):
    id: UUID
    tenant_id: UUID
    item_code: str
    group_code: str
    group_name: Optional[str] = None
    item_description: Optional[str] = None
    description2: Optional[str] = None
    description3: Optional[str] = None
    full_description: Optional[str] = None
    unit_description: Optional[str] = None
    pack_description: Optional[str] = None
    pack_qty: float
    cost_price_cents: int
    retail_price_cents: int
    system_stock_qty: float
    is_active: bool
    created_at: datetime
    updated_at: datetime


class StockImportSummaryResponse(SQLModel):
    imported: int
    created: int
    updated: int
    sources: dict[str, int] = Field(default_factory=dict)
    sheet_names: list[str] = Field(default_factory=list)


class StocktakeSessionCreate(SQLModel):
    name: str
    group_code: Optional[str] = None
    group_name: Optional[str] = None
    search: Optional[str] = None
    hide_zero_stock: bool = False
    notes: Optional[str] = None


class StocktakeLineInput(SQLModel):
    stock_item_id: UUID
    counted_qty: float
    notes: Optional[str] = None
    allow_negative: bool = False


class StocktakeLineBulkUpsertRequest(SQLModel):
    lines: list[StocktakeLineInput]


class StocktakeLineUpdate(SQLModel):
    counted_qty: Optional[float] = None
    notes: Optional[str] = None
    allow_negative: bool = False


class StocktakeLineRead(SQLModel):
    id: UUID
    stocktake_session_id: UUID
    stock_item_id: UUID
    expected_qty: float
    counted_qty: Optional[float] = None
    variance_qty: Optional[float] = None
    variance_value_cents: Optional[int] = None
    counted_by_user_id: Optional[UUID] = None
    counted_at: Optional[datetime] = None
    notes: Optional[str] = None
    item_code: str
    group_code: str
    group_name: Optional[str] = None
    item_description: Optional[str] = None
    full_description: Optional[str] = None
    system_stock_qty: float
    cost_price_cents: int
    retail_price_cents: int


class StocktakeProgressRead(SQLModel):
    counted_items: int = 0
    total_items: int = 0


class StocktakeSessionRead(SQLModel):
    id: UUID
    tenant_id: UUID
    name: str
    status: StocktakeStatus
    created_by_user_id: Optional[UUID] = None
    completed_by_user_id: Optional[UUID] = None
    group_code_filter: Optional[str] = None
    group_name_filter: Optional[str] = None
    search_filter: Optional[str] = None
    notes: Optional[str] = None
    created_at: datetime
    completed_at: Optional[datetime] = None
    progress: StocktakeProgressRead = Field(default_factory=StocktakeProgressRead)


class StocktakeSessionDetailRead(StocktakeSessionRead):
    lines: list[StocktakeLineRead] = Field(default_factory=list)


class StocktakeGroupSummaryRead(SQLModel):
    group_code: str
    group_name: Optional[str] = None
    item_count: int = 0
    counted_count: int = 0
    variance_count: int = 0
    total_variance_qty: float = 0
    total_variance_value_cents: int = 0


class StocktakeReportRead(SQLModel):
    session: StocktakeSessionRead
    matched_item_count: int = 0
    missing_item_count: int = 0
    over_count_item_count: int = 0
    total_variance_qty: float = 0
    total_variance_value_cents: int = 0
    groups: list[StocktakeGroupSummaryRead] = Field(default_factory=list)

