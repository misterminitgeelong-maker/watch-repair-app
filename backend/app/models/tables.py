"""SQLModel table definitions (table=True)."""
from datetime import date, datetime, timezone
from typing import Any, Literal, Optional
from uuid import UUID, uuid4
from pydantic import field_serializer
from sqlalchemy import CheckConstraint, Index, UniqueConstraint, text
from sqlmodel import Field, SQLModel
from ..datetime_utils import as_utc_for_json

from .base import *  # noqa: F401,F403

class Tenant(SQLModel, table=True):
    id: UUID = Field(default_factory=uuid4, primary_key=True)
    name: str
    slug: str = Field(index=True, unique=True)
    plan_tier: str = "starter"
    plan_code: str = "pro"
    default_currency: str = "AUD"
    timezone: str = "Australia/Melbourne"
    stripe_customer_id: Optional[str] = Field(default=None, index=True)
    stripe_subscription_id: Optional[str] = Field(default=None, index=True)
    # Stripe Connect (Express): customer invoice card payments settle to this connected account
    stripe_connect_account_id: Optional[str] = Field(default=None, index=True)
    stripe_connect_charges_enabled: bool = False
    stripe_connect_payouts_enabled: bool = False
    stripe_connect_details_submitted: bool = False
    # True when Stripe subscription is required after signup; cleared after first webhook confirms subscription.
    signup_payment_pending: bool = False
    # Mirrors Stripe subscription status: "trialing", "active", "past_due", "canceled", or None.
    subscription_status: Optional[str] = Field(default=None)
    # UTC timestamp when the Stripe trial ends (populated for trialing subscriptions).
    trial_end: Optional[datetime] = Field(default=None)
    is_active: bool = True
    auth_revoked_at: Optional[datetime] = None
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    # JSON array of tool keys from seed/mobile_services_tools.json (tenant van / kit inventory)
    toolkit_selected_keys: str = Field(default="[]")
    # When False, customer-facing SMS for mobile services (auto key) is skipped; tech reminders unchanged.
    mobile_services_customer_sms_enabled: bool = True
    # Ring-map dispatch: operator's base location for distance-based job routing
    base_lat: Optional[float] = None
    base_lng: Optional[float] = None
    ring_radius_km: int = Field(default=10)  # size of each priority ring in km
    # Xero OAuth (Mobile Services invoice sync)
    xero_tenant_id: Optional[str] = Field(default=None, index=True)
    xero_access_token: Optional[str] = None
    xero_refresh_token: Optional[str] = None
    xero_token_expires_at: Optional[datetime] = None
    xero_connection_status: Optional[str] = None  # disconnected, connected, error
    xero_default_sales_account_code: Optional[str] = None
    xero_default_tax_type: Optional[str] = None
    #: Physical store address for at-shop mobile bookings and provisioning.
    business_address: Optional[str] = Field(default=None, max_length=2000)
    #: SMS destination for new shop mobile booking alerts (operator dispatch).
    mobile_dispatch_phone: Optional[str] = Field(default=None, max_length=80)
    #: Minit shop or mobile-operator number (e.g. 3269 Chadstone, 3904 operator).
    shop_number: Optional[str] = Field(default=None, max_length=10, index=True)
    #: TSS export Area column (e.g. VIC SOUTH, QLD WEST).
    minit_area: Optional[str] = Field(default=None, max_length=120)
    #: TSS export Region column (AU state, SW, NZ, SEA, …).
    minit_region: Optional[str] = Field(default=None, max_length=40, index=True)
    #: Australian Business Number shown on invoices (e.g. "12 345 678 901").
    abn: Optional[str] = Field(default=None, max_length=20)
    #: Shop contact phone printed on invoices (distinct from mobile_dispatch_phone).
    shop_phone: Optional[str] = Field(default=None, max_length=40)
    #: Shop contact email printed on invoices.
    shop_email: Optional[str] = Field(default=None, max_length=200)
    #: Bank / payment instructions printed on PDF invoices (e.g. BSB, account, PayID).
    payment_instructions: Optional[str] = Field(default=None, max_length=500)
    #: Hosted https URL of the shop logo shown in branded emails and PDFs.
    logo_url: Optional[str] = Field(default=None, max_length=1000)
    #: Hex brand colour used to tint email/PDF accents (e.g. "#1F6FEB").
    brand_color: Optional[str] = Field(default=None, max_length=9)

class User(SQLModel, table=True):
    __table_args__ = (
        UniqueConstraint("tenant_id", "email", name="uq_user_tenant_email"),
    )

    id: UUID = Field(default_factory=uuid4, primary_key=True)
    tenant_id: UUID = Field(index=True, foreign_key="tenant.id")
    email: str = Field(index=True)
    full_name: str
    role: str = "owner"
    password_hash: str
    is_active: bool = True
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    #: JSON mobile commission rules (enabled, retainer_cents_per_period, rates_bp, eligible_job_statuses, …)
    mobile_commission_rules_json: Optional[str] = None

class ParentAccount(SQLModel, table=True):
    id: UUID = Field(default_factory=uuid4, primary_key=True)
    name: str
    owner_email: str = Field(index=True)
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    # Website → Mobile Services auto-routing (multi-site): public UUID for POST URL, secret verifies caller
    mobile_lead_ingest_public_id: Optional[UUID] = Field(default=None, index=True, unique=True)
    mobile_lead_webhook_secret_hash: Optional[str] = None
    mobile_lead_default_tenant_id: Optional[UUID] = Field(default=None, foreign_key="tenant.id")

class MobileSuburbRoute(SQLModel, table=True):
    """Maps customer suburb + state to a linked site (tenant) for automated mobile key web leads."""

    __table_args__ = (
        UniqueConstraint("parent_account_id", "state_code", "suburb_normalized", name="uq_mobile_suburb_route_parent_state_suburb"),
    )

    id: UUID = Field(default_factory=uuid4, primary_key=True)
    parent_account_id: UUID = Field(index=True, foreign_key="parentaccount.id")
    state_code: str = Field(index=True, max_length=8)
    suburb_normalized: str = Field(index=True, max_length=200)
    target_tenant_id: UUID = Field(index=True, foreign_key="tenant.id")
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

class IntakeJob(SQLModel, table=True):
    """Public website job submission waiting to be claimed by an operator via ring-map dispatch."""

    id: UUID = Field(default_factory=uuid4, primary_key=True)
    # Submitted by the website customer
    customer_name: str = Field(max_length=300)
    customer_phone: Optional[str] = Field(default=None, max_length=80)
    customer_email: Optional[str] = Field(default=None, max_length=320)
    job_address: str = Field(max_length=2000)
    job_lat: float
    job_lng: float
    vehicle_make: Optional[str] = Field(default=None, max_length=120)
    vehicle_model: Optional[str] = Field(default=None, max_length=120)
    vehicle_year: Optional[str] = Field(default=None, max_length=10)
    registration_plate: Optional[str] = Field(default=None, max_length=32)
    description: Optional[str] = Field(default=None, max_length=4000)
    # Dispatch state
    status: str = Field(default="unclaimed", index=True)  # unclaimed | claimed | admin_review
    current_ring: int = Field(default=1)  # escalates: ring 1 → 2 → 3 as time passes
    ring_escalated_at: Optional[datetime] = None  # next escalation due after this
    claimed_by_tenant_id: Optional[UUID] = Field(default=None, foreign_key="tenant.id", index=True)
    claimed_at: Optional[datetime] = None
    # If claimed, the resulting AutoKeyJob id
    resulting_job_id: Optional[UUID] = Field(default=None, foreign_key="autokeyjob.id")
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

class ParentAccountMembership(SQLModel, table=True):
    id: UUID = Field(default_factory=uuid4, primary_key=True)
    parent_account_id: UUID = Field(index=True, foreign_key="parentaccount.id")
    tenant_id: UUID = Field(index=True, foreign_key="tenant.id")
    user_id: UUID = Field(index=True, foreign_key="user.id")
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

class ShopMobileBookingRequest(SQLModel, table=True):
    """Shop-initiated request for a mobile operator to accept before a job is created."""

    id: UUID = Field(default_factory=uuid4, primary_key=True)
    parent_account_id: UUID = Field(index=True, foreign_key="parentaccount.id")
    requesting_tenant_id: UUID = Field(index=True, foreign_key="tenant.id")
    target_operator_tenant_id: UUID = Field(index=True, foreign_key="tenant.id")
    created_by_user_id: UUID = Field(index=True, foreign_key="user.id")
    status: str = Field(default="pending", index=True, max_length=32)
    customer_name: str = Field(max_length=300)
    phone: Optional[str] = Field(default=None, max_length=80)
    email: Optional[str] = Field(default=None, max_length=320)
    vehicle_make: Optional[str] = Field(default=None, max_length=120)
    vehicle_model: Optional[str] = Field(default=None, max_length=120)
    registration_plate: Optional[str] = Field(default=None, max_length=32)
    visit_location_type: str = Field(default="customer_site", max_length=32)
    job_address: str = Field(max_length=2000)
    preferred_scheduled_at: Optional[datetime] = None
    job_type: Optional[str] = Field(default=None, max_length=120)
    notes: Optional[str] = Field(default=None, max_length=4000)
    operator_response_at: Optional[datetime] = None
    operator_response_by_user_id: Optional[UUID] = Field(default=None, foreign_key="user.id")
    decline_reason: Optional[str] = Field(default=None, max_length=2000)
    resulting_auto_key_job_id: Optional[UUID] = Field(default=None, foreign_key="autokeyjob.id", unique=True)
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

class Suburb(SQLModel, table=True):
    """Australian suburb/locality for prospect search. Populated from public data (e.g. matthewproctor/australianpostcodes)."""
    id: UUID = Field(default_factory=uuid4, primary_key=True)
    name: str = Field(index=True)
    state_code: str = Field(index=True)  # ACT, NSW, NT, QLD, SA, TAS, VIC, WA

class ProspectBusiness(SQLModel, table=True):
    """Stored business prospect from Google Places API collector. Deduped by place_id."""
    id: UUID = Field(default_factory=uuid4, primary_key=True)
    place_id: str = Field(index=True, unique=True)
    name: str
    address: str = ""
    phone: Optional[str] = None
    website: Optional[str] = None
    rating: Optional[float] = None
    review_count: Optional[int] = None
    category: str = Field(index=True)
    suburb_name: str = Field(index=True)
    state_code: str = Field(index=True)
    fetched_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

class ProspectLead(SQLModel, table=True):
    """Per-tenant CRM lead created from prospect search results."""
    id: UUID = Field(default_factory=uuid4, primary_key=True)
    tenant_id: UUID = Field(index=True)
    place_id: Optional[str] = None
    name: str
    address: Optional[str] = None
    phone: Optional[str] = None
    website: Optional[str] = None
    rating: Optional[float] = None
    review_count: Optional[int] = None
    category: Optional[str] = None
    state_code: Optional[str] = None
    suburb_name: Optional[str] = None
    contact_name: Optional[str] = None
    contact_email: Optional[str] = None
    notes: Optional[str] = None
    status: str = Field(default="new")  # new | quote_needed | contacted | follow_up_due | won | lost
    visit_scheduled_at: Optional[datetime] = None
    next_follow_up_on: Optional[date] = None
    customer_account_id: Optional[UUID] = Field(default=None, index=True)
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

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
    __table_args__ = (
        UniqueConstraint("tenant_id", "job_number", name="uq_repairjob_tenant_job_number"),
        CheckConstraint("deposit_cents >= 0", name="ck_repairjob_deposit_cents_non_negative"),
    )

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
    claimed_by_user_id: Optional[UUID] = Field(default=None, foreign_key="user.id")
    internal_notes: Optional[str] = None
    parts_eta: Optional[date] = None
    status_changed_at: Optional[datetime] = None
    custom_fields_json: Optional[str] = None
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

class RepairJobNumberCounter(SQLModel, table=True):
    id: UUID = Field(default_factory=uuid4, primary_key=True)
    tenant_id: UUID = Field(index=True, unique=True, foreign_key="tenant.id")
    next_number: int = 1
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

class JobStatusHistory(SQLModel, table=True):
    id: UUID = Field(default_factory=uuid4, primary_key=True)
    tenant_id: UUID = Field(index=True, foreign_key="tenant.id")
    repair_job_id: UUID = Field(index=True, foreign_key="repairjob.id")
    old_status: Optional[str] = None
    new_status: str
    changed_by_user_id: Optional[UUID] = Field(default=None, foreign_key="user.id")
    change_note: Optional[str] = None
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

class RepairQueueDayState(SQLModel, table=True):
    """Per-user, per-tenant repair queue progress for one calendar day (tenant timezone)."""

    __tablename__ = "repairqueuedaystate"
    __table_args__ = (
        UniqueConstraint("tenant_id", "user_id", "mode", "shop_date", name="uq_repair_queue_day_state_scope"),
    )

    id: UUID = Field(default_factory=uuid4, primary_key=True)
    tenant_id: UUID = Field(index=True, foreign_key="tenant.id")
    user_id: UUID = Field(index=True, foreign_key="user.id")
    mode: str = Field(max_length=8)  # watch | shoe
    shop_date: str = Field(max_length=10)  # YYYY-MM-DD in tenant TZ
    done_ids_json: str = Field(default="[]")
    stats_json: str = Field(default="{}")
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

class WorkLog(SQLModel, table=True):
    __table_args__ = (
        CheckConstraint("minutes_spent >= 0", name="ck_worklog_minutes_spent_non_negative"),
    )

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
    __table_args__ = (
        CheckConstraint(
            "file_size_bytes IS NULL OR file_size_bytes >= 0",
            name="ck_attachment_file_size_bytes_non_negative",
        ),
    )

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
    approval_token_expires_at: Optional[datetime] = Field(default=None, index=True)
    sent_at: Optional[datetime] = None
    #: When the no-decision reminder SMS went out (one reminder per quote).
    reminder_sent_at: Optional[datetime] = None
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
    __table_args__ = (
        UniqueConstraint("tenant_id", "invoice_number", name="uq_invoice_tenant_invoice_number"),
        CheckConstraint("subtotal_cents >= 0", name="ck_invoice_subtotal_cents_non_negative"),
        CheckConstraint("tax_cents >= 0", name="ck_invoice_tax_cents_non_negative"),
        CheckConstraint("total_cents >= 0", name="ck_invoice_total_cents_non_negative"),
    )

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

class InvoiceNumberCounter(SQLModel, table=True):
    id: UUID = Field(default_factory=uuid4, primary_key=True)
    tenant_id: UUID = Field(index=True, unique=True, foreign_key="tenant.id")
    next_number: int = 1
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

class Payment(SQLModel, table=True):
    __table_args__ = (
        CheckConstraint("amount_cents >= 0", name="ck_payment_amount_cents_non_negative"),
    )

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
    shoe_repair_job_id: Optional[UUID] = Field(default=None, index=True, foreign_key="shoerepairjob.id")
    auto_key_job_id: Optional[UUID] = Field(default=None, index=True, foreign_key="autokeyjob.id")
    to_phone: str
    body: str
    event: str  # e.g. "quote_sent", "job_live", "status_ready"
    provider_sid: Optional[str] = None  # Twilio message SID
    status: str = "dry_run"  # "sent" | "dry_run" | "failed"
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

class JobMessage(SQLModel, table=True):
    """Manual two-way SMS messages between shop and customer, linked to a job."""
    id: UUID = Field(default_factory=uuid4, primary_key=True)
    tenant_id: UUID = Field(index=True, foreign_key="tenant.id")
    repair_job_id: Optional[UUID] = Field(default=None, index=True, foreign_key="repairjob.id")
    shoe_repair_job_id: Optional[UUID] = Field(default=None, index=True, foreign_key="shoerepairjob.id")
    auto_key_job_id: Optional[UUID] = Field(default=None, index=True, foreign_key="autokeyjob.id")
    direction: str  # "outbound" | "inbound"
    body: str
    from_phone: Optional[str] = None
    to_phone: Optional[str] = None
    twilio_sid: Optional[str] = None
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

class CustomerOrder(SQLModel, table=True):
    """Shop-sourced items ordered on a customer's behalf (bands, remotes, parts, etc.)."""

    id: UUID = Field(default_factory=uuid4, primary_key=True)
    tenant_id: UUID = Field(index=True, foreign_key="tenant.id")
    customer_id: Optional[UUID] = Field(default=None, index=True, foreign_key="customer.id")
    title: str
    description: Optional[str] = None
    supplier: Optional[str] = None
    status: str = Field(default="to_order")  # to_order | ordered | arrived | notified | collected
    priority: str = Field(default="normal")  # normal | high | urgent
    estimated_cost_cents: int = 0
    notes: Optional[str] = None
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

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
    # Quote approval
    quote_approval_token: str = Field(default_factory=lambda: uuid4().hex, index=True, unique=True)
    quote_approval_token_expires_at: Optional[datetime] = Field(default=None, index=True)
    quote_status: str = "none"  # "none" | "sent" | "approved" | "declined"
    claimed_by_user_id: Optional[UUID] = Field(default=None, foreign_key="user.id")
    custom_fields_json: Optional[str] = None
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

class ShoeJobStatusHistory(SQLModel, table=True):
    id: UUID = Field(default_factory=uuid4, primary_key=True)
    tenant_id: UUID = Field(index=True, foreign_key="tenant.id")
    shoe_repair_job_id: UUID = Field(index=True, foreign_key="shoerepairjob.id")
    old_status: Optional[str] = None
    new_status: str
    changed_by_user_id: Optional[UUID] = Field(default=None, foreign_key="user.id")
    change_note: Optional[str] = None
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

class AutoKeyJob(SQLModel, table=True):
    __table_args__ = (
        UniqueConstraint("tenant_id", "job_number", name="uq_autokeyjob_tenant_job_number"),
    )

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
    programming_status: str = "not_required"
    priority: str = "normal"
    status: str = "awaiting_quote"
    # ServiceM8-style scheduling and location
    scheduled_at: Optional[datetime] = None
    job_address: Optional[str] = None  # For mobile jobs; falls back to customer address
    job_type: Optional[str] = None  # e.g. Key Cutting (in-store), Lockout – Car, etc.
    visit_order: Optional[int] = None  # Route order for same-day jobs (lower = first)
    booking_confirmation_token: Optional[str] = Field(default=None, index=True, unique=True)
    customer_intake_token: Optional[str] = Field(default=None, index=True, unique=True)
    additional_services_json: Optional[str] = None  # JSON array of {preset?, custom?}
    salesperson: Optional[str] = None
    collection_date: Optional[date] = None
    deposit_cents: int = 0
    cost_cents: int = 0
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    #: Set the first time the job transitions to work_completed. Used for KPI cycle-time,
    #: schedule adherence, and same-day invoice metrics.
    work_completed_at: Optional[datetime] = None
    #: Revenue share tier key — must match keys in technician rates_bp (shop_referred, tech_sourced, minit_sourced).
    commission_lead_source: str = Field(default="shop_referred", max_length=64)
    referring_shop_tenant_id: Optional[UUID] = Field(default=None, index=True, foreign_key="tenant.id")
    shop_mobile_booking_request_id: Optional[UUID] = Field(
        default=None, foreign_key="shopmobilebookingrequest.id", unique=True
    )
    pricing_ref_id: Optional[UUID] = Field(default=None, index=True)
    pricing_type: Optional[str] = Field(default=None, max_length=32)  # oem_key | service | garage
    quoted_price: Optional[float] = Field(default=None)  # AUD dollars from pricing catalogue
    callout_inclusive: Optional[bool] = Field(default=None)
    custom_fields_json: Optional[str] = None

class OemKeyPricing(SQLModel, table=True):
    """Global OEM key price catalogue (Supabase-managed)."""
    __tablename__ = "oem_key_pricing"
    id: UUID = Field(default_factory=uuid4, primary_key=True)
    make: str = Field(index=True)
    model_variant: Optional[str] = None
    job_type: str  # Add Key | AKL
    chip_type: Optional[str] = None
    key_type: Optional[str] = None
    service_location: Optional[str] = None
    tool_required: Optional[str] = None
    retail_price: Optional[float] = None  # null = POA
    callout_inclusive: bool = False
    notes: Optional[str] = None
    active: bool = True

class ServicePricing(SQLModel, table=True):
    """General mobile service price catalogue (Supabase-managed)."""
    __tablename__ = "service_pricing"
    id: UUID = Field(default_factory=uuid4, primary_key=True)
    category: str = Field(index=True)
    service_name: str
    unit: Optional[str] = None
    retail_price: Optional[float] = None  # null = POA
    callout_inclusive: bool = False
    notes: Optional[str] = None
    active: bool = True

class GarageServicingPricing(SQLModel, table=True):
    """Garage door servicing price catalogue (Supabase-managed)."""
    __tablename__ = "garage_servicing_pricing"
    id: UUID = Field(default_factory=uuid4, primary_key=True)
    service_name: str = Field(index=True)
    description: Optional[str] = None
    part_cost_notes: Optional[str] = None
    labour_time: Optional[str] = None
    retail_price: float
    callout_inclusive: bool = False
    notes: Optional[str] = None
    active: bool = True

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
    #: When the no-decision reminder SMS went out (one reminder per quote).
    reminder_sent_at: Optional[datetime] = None
    quote_approval_token: str = Field(default_factory=lambda: uuid4().hex, index=True, unique=True)
    signature_storage_key: Optional[str] = None
    signed_at: Optional[datetime] = None
    signer_name: Optional[str] = None
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
    __table_args__ = (
        UniqueConstraint("tenant_id", "invoice_number", name="uq_autokeyinvoice_tenant_invoice_number"),
        # At most one invoice per quote (NULLs stay distinct, so cost-based invoices are unaffected).
        # Makes the manual "from quote", portal-approval, and completion auto-create paths race-safe.
        UniqueConstraint("auto_key_quote_id", name="uq_autokeyinvoice_quote"),
        CheckConstraint("subtotal_cents >= 0", name="ck_autokeyinvoice_subtotal_cents_non_negative"),
        CheckConstraint("tax_cents >= 0", name="ck_autokeyinvoice_tax_cents_non_negative"),
        CheckConstraint("total_cents >= 0", name="ck_autokeyinvoice_total_cents_non_negative"),
        # At most one cost-based (quoteless) invoice per job — closes the no-quote completion race
        # while still allowing a multi-quote job to carry one invoice per quote.
        Index(
            "uq_autokeyinvoice_costbased_per_job",
            "auto_key_job_id",
            unique=True,
            sqlite_where=text("auto_key_quote_id IS NULL"),
            postgresql_where=text("auto_key_quote_id IS NULL"),
        ),
    )

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
    #: Opaque token for customer-facing invoice page (SMS); not exposed on authenticated reads.
    customer_view_token: Optional[str] = Field(default=None, index=True, unique=True)
    xero_invoice_id: Optional[str] = Field(default=None, index=True)
    xero_sync_status: Optional[str] = None  # pending, synced, failed, skipped
    xero_sync_error: Optional[str] = None
    xero_synced_at: Optional[datetime] = None

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

class CustomerAccountInvoice(SQLModel, table=True):
    __table_args__ = (
        CheckConstraint("subtotal_cents >= 0", name="ck_customeraccountinvoice_subtotal_cents_non_negative"),
        CheckConstraint("tax_cents >= 0", name="ck_customeraccountinvoice_tax_cents_non_negative"),
        CheckConstraint("total_cents >= 0", name="ck_customeraccountinvoice_total_cents_non_negative"),
    )

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
    # Xero sync (one aggregated invoice per B2B statement; a line per job).
    xero_invoice_id: Optional[str] = Field(default=None, index=True)
    xero_sync_status: Optional[str] = None  # pending | synced | failed | skipped
    xero_sync_error: Optional[str] = None
    xero_synced_at: Optional[datetime] = None

class CustomerAccountInvoiceLine(SQLModel, table=True):
    __table_args__ = (
        CheckConstraint("amount_cents >= 0", name="ck_customeraccountinvoiceline_amount_cents_non_negative"),
    )

    id: UUID = Field(default_factory=uuid4, primary_key=True)
    tenant_id: UUID = Field(index=True, foreign_key="tenant.id")
    customer_account_invoice_id: UUID = Field(index=True, foreign_key="customeraccountinvoice.id")
    source_type: str
    source_job_id: UUID = Field(index=True)
    job_number: str
    description: str
    amount_cents: int
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

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

class PortalSession(SQLModel, table=True):
    """Short-lived session token for the customer self-service portal."""
    id: UUID = Field(default_factory=uuid4, primary_key=True)
    email: str = Field(index=True)
    token: str = Field(default_factory=lambda: uuid4().hex, index=True, unique=True)
    expires_at: datetime
    status_notify_email: bool = False
    status_notify_sms: bool = False
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class UserNotificationPreference(SQLModel, table=True):
    id: UUID = Field(default_factory=uuid4, primary_key=True)
    tenant_id: UUID = Field(index=True, foreign_key="tenant.id")
    user_id: UUID = Field(index=True, foreign_key="user.id")
    email_quote_approved: bool = True
    email_invoice_paid: bool = True
    email_sms_reply: bool = True
    email_daily_digest: bool = False
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class TenantApiKey(SQLModel, table=True):
    id: UUID = Field(default_factory=uuid4, primary_key=True)
    tenant_id: UUID = Field(index=True, foreign_key="tenant.id")
    name: str = Field(max_length=120)
    key_prefix: str = Field(max_length=16)
    key_hash: str = Field(max_length=128)
    is_active: bool = True
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class TenantWebhookSubscription(SQLModel, table=True):
    id: UUID = Field(default_factory=uuid4, primary_key=True)
    tenant_id: UUID = Field(index=True, foreign_key="tenant.id")
    url: str = Field(max_length=512)
    event_types: str = Field(max_length=512)  # comma-separated
    secret: str = Field(max_length=64)
    is_active: bool = True
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class RefreshSession(SQLModel, table=True):
    """A persisted refresh-token session (one per device/login).

    The primary key ``id`` is the session id (``sid``) carried by both the
    access token and its refresh token; ``jti`` is the refresh token id. Storing
    these enables true per-device revocation (``/auth/sessions/revoke-others``):
    revoking a row prevents that refresh token from minting new access tokens.
    Schema is created by migration 20260531_refresh_session.
    """
    id: UUID = Field(default_factory=uuid4, primary_key=True)
    tenant_id: UUID = Field(index=True)
    user_id: UUID = Field(index=True)
    jti: str = Field(max_length=64, index=True, unique=True)
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    last_used_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    expires_at: datetime
    revoked_at: Optional[datetime] = Field(default=None, index=True)
    user_agent: Optional[str] = Field(default=None, max_length=400)

class CustomerPortalSession(SQLModel, table=True):
    """Slug+phone session token for the mobile-key customer self-service portal.

    Distinct from PortalSession (email-based watch/shoe lookup); this backs the
    per-shop mobile key booking portal in routes/customer_portal_public.py.
    Schema is created by migration 20260426_customer_portal_session.
    """
    id: UUID = Field(default_factory=uuid4, primary_key=True)
    tenant_id: UUID = Field(index=True)
    customer_id: UUID = Field(index=True)
    token: str = Field(max_length=64, index=True, unique=True)
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    expires_at: datetime

class LoyaltyTier(SQLModel, table=True):
    id: int = Field(primary_key=True)  # 1=Bronze 2=Silver 3=Gold 4=Platinum
    name: str = Field(index=True, unique=True)
    label: str  # Fixer / Regular / Trusted / Master
    min_spend_cents: int  # rolling 12-month AUD threshold
    earn_multiplier_x100: int  # 100=1.0× 125=1.25× 150=1.5× 200=2.0×
    points_expiry_months: Optional[int] = None  # None = never expires

class CustomerLoyalty(SQLModel, table=True):
    __table_args__ = (
        UniqueConstraint("tenant_id", "customer_id", name="uq_customerloyalty_tenant_customer"),
    )
    id: UUID = Field(default_factory=uuid4, primary_key=True)
    tenant_id: UUID = Field(index=True, foreign_key="tenant.id")
    customer_id: UUID = Field(index=True, foreign_key="customer.id")
    tier_id: int = Field(default=1, foreign_key="loyaltytier.id")
    points_balance: int = 0
    joined_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

class PointsLedger(SQLModel, table=True):
    __table_args__ = (
        UniqueConstraint("tenant_id", "idempotency_key", name="uq_pointsledger_idempotency"),
    )
    id: UUID = Field(default_factory=uuid4, primary_key=True)
    tenant_id: UUID = Field(index=True, foreign_key="tenant.id")
    customer_loyalty_id: UUID = Field(index=True, foreign_key="customerloyalty.id")
    entry_type: str  # earn | adjust | signup_bonus
    points_delta: int  # signed
    source_invoice_id: Optional[UUID] = Field(default=None, foreign_key="invoice.id")
    source_amount_cents: Optional[int] = None  # invoice total for rolling spend calc
    note: Optional[str] = None
    idempotency_key: Optional[str] = Field(default=None, index=True)
    occurred_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
