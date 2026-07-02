"""Pydantic request/response and read schemas (non-table models)."""
from datetime import date, datetime, timezone
from typing import Any, Literal, Optional
from uuid import UUID, uuid4
from pydantic import field_serializer
from sqlalchemy import CheckConstraint, UniqueConstraint
from sqlmodel import Field, SQLModel
from ..datetime_utils import as_utc_for_json

from .base import *  # noqa: F401,F403
from .tables import *  # noqa: F401,F403

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

class SmsLogRead(SQLModel):
    id: UUID
    to_phone: str
    body: str
    event: str
    status: str
    created_at: datetime

class JobMessageRead(SQLModel):
    id: UUID
    direction: str
    body: str
    from_phone: Optional[str] = None
    to_phone: Optional[str] = None
    created_at: datetime

class JobThreadMessage(SQLModel):
    """Unified view of a job's message thread: manual outbound, customer inbound, and automated system SMS."""
    id: UUID
    direction: str  # "outbound" | "inbound" | "system"
    body: str
    from_phone: Optional[str] = None
    to_phone: Optional[str] = None
    event: Optional[str] = None   # set for system messages
    status: Optional[str] = None  # set for system messages
    created_at: datetime

class CustomerOrderCreate(SQLModel):
    title: str
    description: Optional[str] = None
    supplier: Optional[str] = None
    customer_id: Optional[UUID] = None
    priority: str = "normal"
    estimated_cost_cents: int = 0
    notes: Optional[str] = None

class CustomerOrderUpdate(SQLModel):
    title: Optional[str] = None
    description: Optional[str] = None
    supplier: Optional[str] = None
    customer_id: Optional[UUID] = None
    status: Optional[str] = None
    priority: Optional[str] = None
    estimated_cost_cents: Optional[int] = None
    notes: Optional[str] = None

class CustomerOrderRead(SQLModel):
    id: UUID
    tenant_id: UUID
    customer_id: Optional[UUID]
    customer_name: Optional[str]
    title: str
    description: Optional[str]
    supplier: Optional[str]
    status: str
    priority: str
    estimated_cost_cents: int
    notes: Optional[str]
    created_at: datetime
    updated_at: datetime

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
    mobile_commission_rules_json: Optional[str] = None

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
    #: ``minit`` for Mister Minit network tenants; ``mainspring`` for standard shops.
    product: str = "mainspring"
    #: When true, the SPA renders the six-item Minit HQ navigation (authoritative server signal).
    is_minit_hq_ui: bool = False
    plan_code: PlanCode
    enabled_features: list[str]
    active_site_tenant_id: UUID
    available_sites: list[AuthSessionSiteOption] = Field(default_factory=list)
    #: IANA zone for schedule/SMS (same as backend settings.schedule_calendar_timezone).
    schedule_calendar_timezone: str
    #: Today's date YYYY-MM-DD in schedule_calendar_timezone (dispatch/map filters use this zone).
    shop_calendar_today_ymd: str
    signup_payment_pending: bool = False
    #: Mirrors Stripe subscription status: "trialing", "active", "past_due", "canceled", or None.
    subscription_status: Optional[str] = None
    #: ISO-8601 UTC string when the trial ends; None when not on a trial.
    trial_end: Optional[str] = None
    #: When False, the shop does not send SMS to customers for mobile services (auto key) jobs.
    mobile_services_customer_sms_enabled: bool = True
    tenant_business_address: Optional[str] = None

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
    shop_number: Optional[str] = None
    area: Optional[str] = None
    region: Optional[str] = None
    plan_code: str
    owner_user_id: UUID
    owner_email: str
    owner_full_name: str

class ParentAccountSummaryResponse(SQLModel):
    parent_account_id: UUID
    parent_account_name: str
    owner_email: str
    sites: list[ParentAccountSiteRead] = Field(default_factory=list)
    mobile_lead_ingest_public_id: Optional[UUID] = None
    mobile_lead_webhook_secret_configured: bool = False
    mobile_lead_default_tenant_id: Optional[UUID] = None

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
    stripe_connect_account_present: bool = False
    stripe_connect_charges_enabled: bool = False
    stripe_connect_payouts_enabled: bool = False
    stripe_connect_details_submitted: bool = False
    xero_configured: bool = False
    xero_connected: bool = False
    xero_connection_status: Optional[str] = None

class BillingCheckoutRequest(SQLModel):
    price_id: str

class BillingCheckoutPlanRequest(SQLModel):
    plan_code: PlanCode

class ParentAccountLinkTenantRequest(SQLModel):
    tenant_slug: str
    owner_email: str
    shop_number: Optional[str] = Field(default=None, max_length=10)

class ParentAccountCreateTenantRequest(SQLModel):
    tenant_name: str
    tenant_slug: str
    plan_code: Optional[PlanCode] = None
    business_address: Optional[str] = Field(default=None, max_length=2000)
    shop_number: Optional[str] = Field(default=None, max_length=10)

class ShopBookingUsageShopBreakdown(SQLModel):
    tenant_id: UUID
    tenant_name: str
    shop_number: Optional[str] = None
    accepted_bookings_count: int
    pending_count: int

class ShopBookingUsageResponse(SQLModel):
    month: str
    booking_tenant_count: int
    shops: list[ShopBookingUsageShopBreakdown]

class ParentProvisionShopRequest(SQLModel):
    shop_number: str = Field(..., min_length=1, max_length=10)
    tenant_name: str = Field(..., min_length=1, max_length=200)
    business_address: Optional[str] = Field(default=None, max_length=2000)

class ParentImportShopsResponse(SQLModel):
    created_count: int = 0
    updated_count: int = 0
    skipped_count: int = 0
    parsed_count: int = 0
    sheet_name: Optional[str] = None
    errors: list[str] = Field(default_factory=list)

class ParentDashboardBookingSnippet(SQLModel):
    id: UUID
    customer_name: str
    status: str
    requesting_shop_name: str
    requesting_shop_number: Optional[str] = None
    target_operator_name: str
    region: Optional[str] = None
    area: Optional[str] = None
    created_at: datetime

class ParentRegionDashboardStat(SQLModel):
    region: str
    shop_count: int
    bookings_30d: int
    pending: int
    active_shops_30d: int

class ParentOperationsOverview(SQLModel):
    retail_shop_count: int
    operator_count: int
    pending_bookings: int
    active_mobile_jobs: int
    shops_without_recent_booking: int
    problem_bookings_7d: int
    operators_missing_dispatch_phone: int
    bookings_7d: int = 0
    accepted_7d: int = 0
    declined_7d: int = 0
    bookings_30d: int = 0
    accepted_30d: int = 0
    stale_pending_count: int = 0
    acceptance_rate_7d: Optional[float] = None
    region_stats: list[ParentRegionDashboardStat] = Field(default_factory=list)
    recent_bookings: list[ParentDashboardBookingSnippet] = Field(default_factory=list)
    attention_items: list["ParentTroubleshootingItem"] = Field(default_factory=list)

class ParentShopBookingVolume(SQLModel):
    tenant_id: UUID
    tenant_name: str
    shop_number: Optional[str] = None
    area: Optional[str] = None
    region: Optional[str] = None
    total: int
    pending: int
    accepted: int
    declined: int
    cancelled: int
    expired: int

class ParentShopBookingsReport(SQLModel):
    from_date: Optional[datetime] = None
    to_date: Optional[datetime] = None
    totals: ParentShopBookingVolume
    by_shop: list[ParentShopBookingVolume] = Field(default_factory=list)
    bookings: list["ShopMobileBookingRead"] = Field(default_factory=list)

class ParentMobileJobNetworkRead(SQLModel):
    id: UUID
    job_number: str
    status: str
    title: str
    operator_tenant_id: UUID
    operator_name: str
    operator_shop_number: Optional[str] = None
    referring_shop_tenant_id: Optional[UUID] = None
    referring_shop_name: Optional[str] = None
    referring_shop_number: Optional[str] = None
    shop_mobile_booking_request_id: Optional[UUID] = None
    scheduled_at: Optional[datetime] = None
    created_at: datetime

class ParentMobileJobsReport(SQLModel):
    from_date: Optional[datetime] = None
    to_date: Optional[datetime] = None
    active_count: int
    total_count: int
    jobs: list[ParentMobileJobNetworkRead] = Field(default_factory=list)

class ParentTroubleshootingItem(SQLModel):
    kind: str
    severity: str
    title: str
    detail: str
    tenant_id: Optional[UUID] = None
    tenant_slug: Optional[str] = None
    related_id: Optional[UUID] = None
    created_at: Optional[datetime] = None

class ParentTroubleshootingResponse(SQLModel):
    items: list[ParentTroubleshootingItem] = Field(default_factory=list)

class ParentMobileLeadWebhookSecretBody(SQLModel):
    webhook_secret: str = Field(..., min_length=16, max_length=512)

class ParentMobileLeadDefaultTenantBody(SQLModel):
    tenant_id: Optional[UUID] = None

class MobileSuburbRouteRead(SQLModel):
    id: UUID
    state_code: str
    suburb_normalized: str
    target_tenant_id: UUID

class MobileSuburbRouteCreateRequest(SQLModel):
    state_code: str = Field(..., min_length=2, max_length=8)
    suburb: str = Field(..., min_length=1, max_length=200)
    target_tenant_id: UUID

class InboundEmailListItem(SQLModel):
    id: UUID
    from_email: Optional[str] = None
    subject: Optional[str] = None
    status: str
    auto_key_job_id: Optional[UUID] = None
    created_at: datetime

class InboundEmailDetail(InboundEmailListItem):
    to_email: Optional[str] = None
    message_id: Optional[str] = None
    text_body: Optional[str] = None
    html_body: Optional[str] = None
    spf_result: Optional[str] = None
    sender_ip: Optional[str] = None

class InboundEmailStatusUpdateRequest(SQLModel):
    status: str = Field(..., min_length=1, max_length=20)

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

class PlatformTenantRead(SQLModel):
    id: UUID
    slug: str
    name: str
    plan_code: str
    is_active: bool
    signup_payment_pending: bool
    user_count: int
    created_at: datetime

class PlatformEnterShopResponse(SQLModel):
    access_token: str
    refresh_token: str
    expires_in_seconds: int
    refresh_expires_in_seconds: int
    tenant_id: UUID
    tenant_name: str

class PlatformTenantStatusUpdateRequest(SQLModel):
    is_active: bool
    reason: Optional[str] = None

class PlatformTenantForceLogoutRequest(SQLModel):
    reason: Optional[str] = None

class PlatformTenantPlanUpdateRequest(SQLModel):
    plan_code: str
    reason: Optional[str] = None

class PlatformTenantUpdateRequest(SQLModel):
    name: Optional[str] = None
    slug: Optional[str] = None
    owner_email: Optional[str] = None
    new_password: Optional[str] = None

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
    mobile_commission_rules_json: Optional[str] = None

class UserUpdateRequest(SQLModel):
    full_name: Optional[str] = None
    role: Optional[str] = None
    password: Optional[str] = None
    is_active: Optional[bool] = None
    mobile_commission_rules_json: Optional[str] = None

class ImportSummaryResponse(SQLModel):
    import_id: UUID
    imported: int
    skipped: int
    customers_created: int
    total_rows: int
    skipped_reasons: dict[str, int] = Field(default_factory=dict)
    dry_run: bool = False
    duplicate_customer_rows_in_file: int = 0
    # Excel only: worksheet used (auto-selected or from sheet_name query param).
    source_sheet: Optional[str] = None
    # Which product tab was targeted: watch | shoe | mobile
    import_target: Optional[str] = None

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

class CustomerUpdate(SQLModel):
    full_name: Optional[str] = None
    email: Optional[str] = None
    phone: Optional[str] = None
    address: Optional[str] = None
    notes: Optional[str] = None

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

class WatchUpdate(SQLModel):
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
    job_number_override: Optional[str] = None

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
    internal_notes: Optional[str] = None
    parts_eta: Optional[date] = None
    status_changed_at: Optional[datetime] = None
    created_at: datetime
    claimed_by_user_id: Optional[UUID] = None
    claimed_by_name: Optional[str] = None
    customer_name: Optional[str] = None
    customer_phone: Optional[str] = None
    customer_email: Optional[str] = None

class RepairJobCreateResponse(RepairJobRead):
    """POST /repair-jobs — includes whether tracking SMS was sent."""

    tracking_sms_sent: bool = False
    tracking_sms_skipped_reason: Optional[str] = None

class RepairJobStatusUpdate(SQLModel):
    status: JobStatus
    note: Optional[str] = None

class JobNotePayload(SQLModel):
    """Lightweight payload for adding a free-text note without changing status."""
    note: str

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
    title: Optional[str] = None
    cost_cents: Optional[int] = None
    pre_quote_cents: Optional[int] = None
    priority: Optional[str] = None
    salesperson: Optional[str] = None
    collection_date: Optional[date] = None
    deposit_cents: Optional[int] = None
    description: Optional[str] = None
    assigned_user_id: Optional[UUID] = None
    clear_assigned_user: bool = False
    internal_notes: Optional[str] = None
    parts_eta: Optional[date] = None

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
    xero_invoice_id: Optional[str] = None
    xero_sync_status: Optional[str] = None
    xero_sync_error: Optional[str] = None
    xero_synced_at: Optional[datetime] = None
    xero_online_invoice_url: Optional[str] = None

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

class InvoiceSendResponse(SQLModel):
    invoice_id: UUID
    email_sent: bool
    email_skipped_reason: Optional[str] = None
    email_error_detail: Optional[str] = None

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

class ShoeUpdate(SQLModel):
    shoe_type: Optional[str] = None
    brand: Optional[str] = None
    color: Optional[str] = None
    description_notes: Optional[str] = None

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
    quote_approval_token: str
    quote_approval_token_expires_at: Optional[datetime] = None
    quote_status: str
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
    claimed_by_user_id: Optional[UUID] = None
    claimed_by_name: Optional[str] = None

class ShoeRepairJobCreateResponse(ShoeRepairJobRead):
    """POST /shoe-repair-jobs — includes whether tracking SMS was sent."""

    tracking_sms_sent: bool = False
    tracking_sms_skipped_reason: Optional[str] = None

class ShoeRepairJobStatusUpdate(SQLModel):
    status: str
    note: Optional[str] = None

class ShoeJobStatusHistoryRead(SQLModel):
    id: UUID
    shoe_repair_job_id: UUID
    old_status: Optional[str] = None
    new_status: str
    changed_by_user_id: Optional[UUID] = None
    change_note: Optional[str] = None
    created_at: datetime

class ShoeRepairJobFieldUpdate(SQLModel):
    customer_account_id: Optional[UUID] = None
    title: Optional[str] = None
    description: Optional[str] = None
    priority: Optional[str] = None
    salesperson: Optional[str] = None
    collection_date: Optional[date] = None
    deposit_cents: Optional[int] = None
    cost_cents: Optional[int] = None

class ShopMobileBookingCreate(SQLModel):
    suburb: str = Field(min_length=1, max_length=200)
    state_code: str = Field(min_length=2, max_length=8)
    target_operator_tenant_id: Optional[UUID] = None
    customer_name: str = Field(min_length=1, max_length=300)
    phone: Optional[str] = Field(default=None, max_length=80)
    email: Optional[str] = Field(default=None, max_length=320)
    vehicle_make: Optional[str] = Field(default=None, max_length=120)
    vehicle_model: Optional[str] = Field(default=None, max_length=120)
    registration_plate: Optional[str] = Field(default=None, max_length=32)
    visit_location_type: ShopMobileVisitLocationType = "customer_site"
    job_address: str = Field(min_length=1, max_length=2000)
    preferred_scheduled_at: Optional[datetime] = None
    job_type: Optional[str] = Field(default=None, max_length=120)
    notes: Optional[str] = Field(default=None, max_length=4000)

class ShopMobileOperatorOption(SQLModel):
    tenant_id: UUID
    tenant_slug: str
    tenant_name: str
    shop_number: Optional[str] = None
    plan_code: str
    routing_rule: Optional[str] = None

class ShopMobileBookingRead(SQLModel):
    id: UUID
    parent_account_id: UUID
    requesting_tenant_id: UUID
    requesting_shop_name: str
    requesting_shop_number: Optional[str] = None
    target_operator_tenant_id: UUID
    target_operator_name: str
    target_operator_shop_number: Optional[str] = None
    created_by_user_id: UUID
    status: ShopMobileBookingStatus
    customer_name: str
    phone: Optional[str] = None
    email: Optional[str] = None
    vehicle_make: Optional[str] = None
    vehicle_model: Optional[str] = None
    registration_plate: Optional[str] = None
    visit_location_type: ShopMobileVisitLocationType
    job_address: str
    job_suburb: Optional[str] = None
    job_state_code: Optional[str] = None
    operator_routing_rule: Optional[str] = None
    preferred_scheduled_at: Optional[datetime] = None
    job_type: Optional[str] = None
    notes: Optional[str] = None
    operator_response_at: Optional[datetime] = None
    operator_response_by_user_id: Optional[UUID] = None
    decline_reason: Optional[str] = None
    resulting_auto_key_job_id: Optional[UUID] = None
    resulting_job_number: Optional[str] = None
    job_status: Optional[str] = None
    job_scheduled_at: Optional[datetime] = None
    schedule_conflict_warning: Optional[str] = None
    created_at: datetime

    @field_serializer("preferred_scheduled_at", "operator_response_at", "job_scheduled_at", "created_at")
    def _serialize_dt_as_utc(self, v: Optional[datetime]) -> Optional[datetime]:
        return as_utc_for_json(v) if v is not None else None

class ShopMobileBookingDeclineBody(SQLModel):
    decline_reason: Optional[str] = Field(default=None, max_length=2000)

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
    blade_code: Optional[str] = None
    chip_type: Optional[str] = None
    tech_notes: Optional[str] = None
    key_quantity: int = 1
    programming_status: AutoKeyProgrammingStatus = "not_required"
    priority: Literal["low", "normal", "high", "urgent"] = "normal"
    status: JobStatus = "awaiting_quote"
    salesperson: Optional[str] = None
    collection_date: Optional[date] = None
    deposit_cents: int = 0
    cost_cents: int = 0
    apply_suggested_quote: bool = False
    send_booking_sms: bool = False
    additional_services: list[dict[str, Any]] = Field(default_factory=list)
    commission_lead_source: str = Field(default="shop_referred", max_length=64)
    pricing_ref_id: Optional[UUID] = None
    pricing_type: Optional[Literal["oem_key", "service", "garage"]] = None
    quoted_price: Optional[float] = None
    callout_inclusive: Optional[bool] = None

class AutoKeyQuickIntakeCreate(SQLModel):
    full_name: str = Field(max_length=500)
    phone: str = Field(max_length=80)

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
    additional_services_json: Optional[str] = None
    commission_lead_source: str = "shop_referred"
    referring_shop_tenant_id: Optional[UUID] = None
    shop_mobile_booking_request_id: Optional[UUID] = None
    customer_name: Optional[str] = None
    customer_phone: Optional[str] = None
    pricing_ref_id: Optional[UUID] = None
    pricing_type: Optional[str] = None
    quoted_price: Optional[float] = None
    callout_inclusive: Optional[bool] = None

    @field_serializer("scheduled_at", "created_at")
    def _serialize_dt_as_utc(self, v: Optional[datetime]) -> Optional[datetime]:
        """Naive DB datetimes are UTC; expose as timezone-aware so JSON is unambiguous for browsers."""
        return as_utc_for_json(v) if v is not None else None

class AutoKeyJobStatusUpdateResult(AutoKeyJobRead):
    """Job after a status change, plus the auto-invoice outcome so the UI can
    report it directly instead of inferring it by diffing invoice counts."""
    #: True when this status change auto-created an invoice.
    invoice_created: bool = False
    #: When no invoice was created on completion, a stable machine code for why
    #: (``already_invoiced``); ``None`` otherwise (e.g. non-completion changes).
    invoice_skip_reason: Optional[str] = None

class OemKeyPricingRow(SQLModel):
    id: UUID
    make: str
    model_variant: Optional[str] = None
    job_type: str
    key_type: Optional[str] = None
    service_location: Optional[str] = None
    tool_required: Optional[str] = None
    retail_price: Optional[float] = None
    is_poa: bool
    callout_inclusive: bool
    notes: Optional[str] = None

class ServicePricingRow(SQLModel):
    id: UUID
    category: str
    service_name: str
    unit: Optional[str] = None
    retail_price: Optional[float] = None
    is_poa: bool
    callout_inclusive: bool
    notes: Optional[str] = None

class GarageServicingPricingRow(SQLModel):
    id: UUID
    service_name: str
    description: Optional[str] = None
    part_cost_notes: Optional[str] = None
    labour_time: Optional[str] = None
    retail_price: float
    callout_inclusive: bool
    notes: Optional[str] = None

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
    additional_services_json: Optional[str] = None
    commission_lead_source: Optional[str] = Field(default=None, max_length=64)
    pricing_ref_id: Optional[UUID] = None
    pricing_type: Optional[Literal["oem_key", "service", "garage"]] = None
    quoted_price: Optional[float] = None
    callout_inclusive: Optional[bool] = None

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
    signed_at: Optional[datetime] = None
    signer_name: Optional[str] = None
    has_signature: bool = False
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
    xero_invoice_id: Optional[str] = None
    xero_sync_status: Optional[str] = None
    xero_sync_error: Optional[str] = None
    xero_synced_at: Optional[datetime] = None

class AutoKeyQuoteSendResponse(SQLModel):
    quote: AutoKeyQuoteRead
    email_sent: bool
    email_skipped_reason: Optional[str] = None
    email_error_detail: Optional[str] = None

class AutoKeyInvoiceSendResponse(SQLModel):
    invoice: AutoKeyInvoiceRead
    email_sent: bool
    email_skipped_reason: Optional[str] = None
    email_error_detail: Optional[str] = None

class XeroConnectionStatusResponse(SQLModel):
    configured: bool
    connected: bool
    connection_status: Optional[str] = None
    xero_tenant_id: Optional[str] = None
    default_sales_account_code: Optional[str] = None
    default_tax_type: Optional[str] = None

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
    xero_invoice_id: Optional[str] = None
    xero_sync_status: Optional[str] = None
    xero_sync_error: Optional[str] = None
    xero_synced_at: Optional[datetime] = None

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

class LoyaltyTierRead(SQLModel):
    id: int
    name: str
    label: str
    min_spend_cents: int
    earn_multiplier_x100: int
    points_expiry_months: Optional[int]

class PointsLedgerRead(SQLModel):
    id: UUID
    entry_type: str
    points_delta: int
    source_invoice_id: Optional[UUID]
    note: Optional[str]
    occurred_at: datetime

class CustomerLoyaltyRead(SQLModel):
    customer_id: UUID
    tier_id: int
    tier_name: str
    tier_label: str
    points_balance: int
    points_dollar_value: float  # points_balance / 100
    rolling_12m_spend_cents: int
    joined_at: datetime

class LoyaltyProfileResponse(SQLModel):
    loyalty: CustomerLoyaltyRead
    recent_ledger: list[PointsLedgerRead]

class PointsAdjustRequest(SQLModel):
    points_delta: int
    note: str
