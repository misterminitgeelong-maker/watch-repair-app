"""Shared imports and Literal/type aliases for the models package."""
from datetime import date, datetime, timezone
from typing import Any, Literal, Optional
from uuid import UUID, uuid4
from pydantic import field_serializer
from sqlalchemy import CheckConstraint, UniqueConstraint
from sqlmodel import Field, SQLModel
from ..datetime_utils import as_utc_for_json

FleetAccountType = Literal["Dealership", "Rental Fleet", "Government Fleet", "Corporate Fleet", "Car Auctions", "Other"]
FleetBillingCycle = Literal["Monthly", "Fortnightly", "Weekly"]
SubscriptionPlan = Literal["starter", "pro", "fleet", "none"]
JobStatus = Literal[
    # Watch repair pipeline
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
    # Mobile Services / Auto-key statuses
    "en_route",
    "on_site",
    "pending_booking",
    "booked",
    "awaiting_customer_details",
    "quote_sent",
    "awaiting_booking_confirmation",
    "booking_confirmed",
    "booking_on_hold",
    "booking_completed",
    "job_delayed",
    "work_completed",
    "invoice_paid",
    "failed_job",
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
    "booking_only",
    "minit_hq",
    "pro",
]
ShopMobileBookingStatus = Literal["pending", "accepted", "declined", "cancelled", "expired"]
ShopMobileVisitLocationType = Literal["customer_site", "at_shop"]
AutoKeyProgrammingStatus = Literal["pending", "in_progress", "programmed", "failed", "not_required"]
CustomerAccountSourceType = Literal["watch", "shoe", "auto_key"]
StocktakeStatus = Literal["draft", "in_progress", "completed", "approved"]
