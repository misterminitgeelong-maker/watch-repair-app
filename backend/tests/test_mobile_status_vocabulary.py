"""The Mobile Services status vocabulary is defined once and used consistently.

Every stored ``AutoKeyJob.status`` value must resolve to exactly one canonical
stage, one user-facing label and one reporting category. The frontend mirror
(``frontend/src/lib/mobileStatus.ts``) is pinned to the same table by
``frontend/src/lib/mobileStatus.test.ts``; the expected mapping below is the
contract both sides must match.
"""
from __future__ import annotations

import typing

import pytest

from app.auto_key_status import (
    AUTO_KEY_ACTIVE_STATUSES,
    AUTO_KEY_CANONICAL_STATUSES,
    AUTO_KEY_FINAL_STATUSES,
    AUTO_KEY_LEGACY_STATUS_MAP,
    MOBILE_STATUS_DEFINITIONS,
    canonical_auto_key_status,
    mobile_status_category,
    mobile_status_label,
    mobile_status_vocabulary,
    statuses_in_category,
)
from app.models.base import JobStatus


EXPECTED = {
    # canonical key: (label, category)
    "awaiting_quote": ("Awaiting Quote", "pipeline"),
    "awaiting_customer_details": ("Awaiting Customer Details", "pipeline"),
    "quote_sent": ("Quote Sent", "pipeline"),
    "awaiting_booking_confirmation": ("Awaiting Booking Confirmation", "booking"),
    "booking_confirmed": ("Booking Confirmed", "booking"),
    "booking_on_hold": ("Booking on Hold", "booking"),
    "en_route": ("En Route", "field"),
    "on_site": ("On Site", "field"),
    "work_completed": ("Work Completed", "completed"),
    "invoice_paid": ("Invoice Paid", "paid"),
    "failed_job": ("Failed Job", "lost"),
    "no_go": ("No Go", "lost"),
}

EXPECTED_ALIASES = {
    "pending_booking": "awaiting_booking_confirmation",
    "booked": "booking_confirmed",
    "job_delayed": "booking_on_hold",
    "booking_completed": "work_completed",
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


def test_canonical_labels_and_categories_match_the_contract():
    assert {d.key: (d.label, d.category) for d in MOBILE_STATUS_DEFINITIONS} == EXPECTED
    assert list(AUTO_KEY_CANONICAL_STATUSES) == list(EXPECTED)  # lifecycle order is part of the contract


def test_every_alias_resolves_to_exactly_one_canonical_stage():
    assert AUTO_KEY_LEGACY_STATUS_MAP == EXPECTED_ALIASES
    seen: dict[str, str] = {}
    for definition in MOBILE_STATUS_DEFINITIONS:
        for value in (definition.key, *definition.aliases):
            assert value not in seen, f"{value} appears under both {seen[value]} and {definition.key}"
            seen[value] = definition.key
    # A canonical key is never also an alias of another stage.
    assert not set(AUTO_KEY_LEGACY_STATUS_MAP) & set(AUTO_KEY_CANONICAL_STATUSES)


def test_every_job_status_literal_has_one_label_and_one_category():
    for status in typing.get_args(JobStatus):
        assert mobile_status_label(status), status
        assert mobile_status_category(status) is not None, f"{status} has no reporting category"


@pytest.mark.parametrize("legacy,canonical", sorted(EXPECTED_ALIASES.items()))
def test_alias_presents_as_its_canonical_stage(legacy: str, canonical: str):
    assert canonical_auto_key_status(legacy) == canonical
    assert mobile_status_label(legacy) == EXPECTED[canonical][0]
    assert mobile_status_category(legacy) == EXPECTED[canonical][1]


def test_closed_and_active_sets_partition_every_status():
    every = set(AUTO_KEY_CANONICAL_STATUSES) | set(AUTO_KEY_LEGACY_STATUS_MAP)
    assert AUTO_KEY_FINAL_STATUSES | AUTO_KEY_ACTIVE_STATUSES == every
    assert not AUTO_KEY_FINAL_STATUSES & AUTO_KEY_ACTIVE_STATUSES
    assert AUTO_KEY_FINAL_STATUSES == (
        statuses_in_category("completed") | statuses_in_category("paid") | statuses_in_category("lost")
    )
    assert "work_completed" in AUTO_KEY_FINAL_STATUSES  # done-but-unpaid is out of the active directory
    assert "booking_on_hold" in AUTO_KEY_ACTIVE_STATUSES


def test_vocabulary_payload_is_json_friendly_and_ordered():
    payload = mobile_status_vocabulary()
    assert [row["key"] for row in payload] == list(EXPECTED)
    assert payload[3] == {
        "key": "awaiting_booking_confirmation",
        "label": "Awaiting Booking Confirmation",
        "category": "booking",
        "closed": False,
        "aliases": ["pending_booking", "go_ahead"],
    }
