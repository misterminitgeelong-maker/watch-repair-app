"""Shared types and type aliases for backend models.

Do not add table classes here. Tables live in ``models/tables.py`` and
request/response DTOs live in ``models/schemas.py``. This module only
hosts the cross-cutting type vocabulary (status literals, plan codes,
job-status strings, etc.).
"""
from __future__ import annotations

from datetime import date, datetime, timezone
from typing import Any, Literal, Optional
from uuid import UUID, uuid4

from pydantic import BaseModel, field_serializer
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
    # Mobile Services / Auto-key shared vocabulary
    "en_route",                      # tech driving to job
    "on_site",                       # tech arrived at location
    "pending_booking",               # quote + time sent; customer must confirm
    "booked",                        # customer confirmed booking; on calendar
    "awaiting_customer_details",     # quick-add; customer fills link
    # Mobile Services specific statuses (also used by the frontend STATUSES list
    # in AutoKeyJobsPage.tsx). These were previously missing from the Literal,
    # so every Mobile Services status update with one of these strings failed
    # Pydantic validation — that's the root cause of most failing auto-key tests.
    "quote_sent",                    # quote delivered to customer, awaiting response
    "awaiting_booking_confirmation", # customer viewed quote, booking-link pending
    "booking_confirmed",             # customer confirmed; ready to dispatch
    "job_delayed",                   # tech-reported delay
    "work_completed",                # work done; invoice to follow
    "invoice_paid",                  # customer paid; final
    "failed_job",                    # tech/dispatcher marked job unrecoverable; final
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



# Tenant-scoped prospect pipeline ("saved lead" from the global ProspectBusiness
# catalogue or from free-form entry). Each tenant owns their own list + status.
ProspectLeadStatus = Literal["new", "contacted", "qualified", "won", "lost", "unqualified"]



# ── Auto Key Jobs ────────────────────────────────────────────────────────────

AutoKeyProgrammingStatus = Literal["pending", "in_progress", "programmed", "failed", "not_required"]



CustomerAccountSourceType = Literal["watch", "shoe", "auto_key"]



# ── Stocktake ────────────────────────────────────────────────────────────────

StocktakeStatus = Literal["draft", "in_progress", "completed", "approved"]
