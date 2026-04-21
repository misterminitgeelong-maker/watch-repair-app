"""Request/response DTOs for the Mainspring API.

These are SQLModel / pydantic models without ``table=True``. They're kept
separate from the database tables in ``models/tables.py`` so API-surface
changes don't force a look at schema migrations.
"""
from __future__ import annotations

from datetime import date, datetime, timezone
from typing import Any, Literal, Optional
from uuid import UUID, uuid4

from pydantic import BaseModel, field_serializer
from sqlalchemy import CheckConstraint, UniqueConstraint
from sqlmodel import Field, SQLModel

from ..datetime_utils import as_utc_for_json
from ._types import *  # noqa: F401,F403
from .tables import *  # noqa: F401,F403  — DTOs reference table types in hints




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



class ProspectLeadCreate(SQLModel):
    place_id: Optional[str] = None
    name: str
    address: Optional[str] = None
    phone: Optional[str] = None
    website: Optional[str] = None
    category: Optional[str] = None
    state_code: Optional[str] = None
    suburb_name: Optional[str] = None
    notes: Optional[str] = None



class ProspectLeadUpdate(SQLModel):
    status: Optional[ProspectLeadStatus] = None
    notes: Optional[str] = None
    next_follow_up_on: Optional[date] = None
    phone: Optional[str] = None
    website: Optional[str] = None
    address: Optional[str] = None



class ProspectLeadRead(SQLModel):
    id: UUID
    tenant_id: UUID
    place_id: Optional[str] = None
    name: str
    address: Optional[str] = None
    phone: Optional[str] = None
    website: Optional[str] = None
    category: Optional[str] = None
    state_code: Optional[str] = None
    suburb_name: Optional[str] = None
    status: str
    notes: Optional[str] = None
    next_follow_up_on: Optional[date] = None
    customer_account_id: Optional[UUID] = None
    created_at: datetime
    updated_at: datetime



class ProspectLeadConvertRequest(SQLModel):
    account_name: str
    contact_name: Optional[str] = None
    contact_phone: Optional[str] = None
    contact_email: Optional[str] = None



class SmsLogRead(SQLModel):
    id: UUID
    to_phone: str
    body: str
    event: str
    status: str
    created_at: datetime



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
    created_at: datetime
    claimed_by_user_id: Optional[UUID] = None
    claimed_by_name: Optional[str] = None
    customer_name: Optional[str] = None



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
    cost_cents: Optional[int] = None
    pre_quote_cents: Optional[int] = None
    priority: Optional[str] = None
    salesperson: Optional[str] = None
    collection_date: Optional[date] = None
    deposit_cents: Optional[int] = None
    description: Optional[str] = None
    assigned_user_id: Optional[UUID] = None
    clear_assigned_user: bool = False



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
    customer_name: Optional[str] = None
    customer_phone: Optional[str] = None

    @field_serializer("scheduled_at", "created_at")
    def _serialize_dt_as_utc(self, v: Optional[datetime]) -> Optional[datetime]:
        """Naive DB datetimes are UTC; expose as timezone-aware so JSON is unambiguous for browsers."""
        return as_utc_for_json(v) if v is not None else None



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
