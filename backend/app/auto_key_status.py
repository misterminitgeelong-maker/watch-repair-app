"""Canonical Mobile Services status vocabulary and legacy compatibility.

Older CSV imports stored watch-repair statuses on ``AutoKeyJob`` rows. Keep
those values readable while operational queries and new imports use the
Mobile Services lifecycle.
"""

from __future__ import annotations


AUTO_KEY_LEGACY_STATUS_MAP: dict[str, str] = {
    "awaiting_go_ahead": "quote_sent",
    "go_ahead": "awaiting_booking_confirmation",
    "working_on": "on_site",
    "service": "on_site",
    "awaiting_parts": "booking_on_hold",
    "parts_to_order": "booking_on_hold",
    "sent_to_labanda": "booking_on_hold",
    "quoted_by_labanda": "booking_on_hold",
    "at_third_party_for_quoting": "booking_on_hold",
    "third_party_quote_approved": "booking_on_hold",
    "at_third_party_repairer": "booking_on_hold",
    "completed": "work_completed",
    "awaiting_collection": "work_completed",
    "collected": "invoice_paid",
}

AUTO_KEY_CANONICAL_FINAL_STATUSES = frozenset(
    {"booking_completed", "work_completed", "invoice_paid", "failed_job", "no_go"}
)
AUTO_KEY_LEGACY_FINAL_STATUSES = frozenset(
    status
    for status, canonical in AUTO_KEY_LEGACY_STATUS_MAP.items()
    if canonical in AUTO_KEY_CANONICAL_FINAL_STATUSES
)
AUTO_KEY_FINAL_STATUSES = AUTO_KEY_CANONICAL_FINAL_STATUSES | AUTO_KEY_LEGACY_FINAL_STATUSES


def canonical_auto_key_status(status: str) -> str:
    """Return the Mobile Services equivalent for an imported legacy status."""

    return AUTO_KEY_LEGACY_STATUS_MAP.get(status, status)
