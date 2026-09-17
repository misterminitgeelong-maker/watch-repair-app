"""Canonical Mobile Services status vocabulary and legacy compatibility.

This module is the single definition of the Mobile Services job lifecycle:
which stored ``AutoKeyJob.status`` values are canonical, what each one is
called to a user, which reporting category it rolls into, and which older
stored values present as the same stage. ``frontend/src/lib/mobileStatus.ts``
mirrors it for presentation; ``tests/test_mobile_status_vocabulary.py`` pins
the two together.

Older CSV imports stored watch-repair statuses on ``AutoKeyJob`` rows, and two
booking flows (SMS confirmation vs. quote approval) grew parallel values for the
same stage. Keep every stored value readable while operational queries, new
transitions and imports use one canonical value per stage.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

MobileStatusCategory = Literal["pipeline", "booking", "field", "completed", "paid", "lost"]


@dataclass(frozen=True)
class MobileStatusDefinition:
    key: str
    label: str
    category: MobileStatusCategory
    aliases: tuple[str, ...] = ()

    @property
    def closed(self) -> bool:
        """The physical work is finished (or abandoned); only money may be open."""
        return self.category in ("completed", "paid", "lost")


# Lifecycle order. Each stored status appears exactly once, either as a key or
# as an alias, so every job has one label and one reporting category.
MOBILE_STATUS_DEFINITIONS: tuple[MobileStatusDefinition, ...] = (
    MobileStatusDefinition("awaiting_quote", "Awaiting Quote", "pipeline"),
    MobileStatusDefinition("awaiting_customer_details", "Awaiting Customer Details", "pipeline"),
    MobileStatusDefinition("quote_sent", "Quote Sent", "pipeline", ("awaiting_go_ahead",)),
    MobileStatusDefinition(
        "awaiting_booking_confirmation",
        "Awaiting Booking Confirmation",
        "booking",
        ("pending_booking", "go_ahead"),
    ),
    MobileStatusDefinition("booking_confirmed", "Booking Confirmed", "booking", ("booked",)),
    MobileStatusDefinition(
        "booking_on_hold",
        "Booking on Hold",
        "booking",
        (
            "job_delayed",
            "awaiting_parts",
            "parts_to_order",
            "sent_to_labanda",
            "quoted_by_labanda",
            "at_third_party_for_quoting",
            "third_party_quote_approved",
            "at_third_party_repairer",
        ),
    ),
    MobileStatusDefinition("en_route", "En Route", "field"),
    MobileStatusDefinition("on_site", "On Site", "field", ("working_on", "service")),
    MobileStatusDefinition(
        "work_completed",
        "Work Completed",
        "completed",
        ("booking_completed", "completed", "awaiting_collection"),
    ),
    MobileStatusDefinition("invoice_paid", "Invoice Paid", "paid", ("collected",)),
    MobileStatusDefinition("failed_job", "Failed Job", "lost"),
    MobileStatusDefinition("no_go", "No Go", "lost"),
)

MOBILE_STATUS_BY_KEY: dict[str, MobileStatusDefinition] = {d.key: d for d in MOBILE_STATUS_DEFINITIONS}

# Any stored value (canonical or alias) -> its canonical key.
AUTO_KEY_LEGACY_STATUS_MAP: dict[str, str] = {
    alias: definition.key for definition in MOBILE_STATUS_DEFINITIONS for alias in definition.aliases
}

AUTO_KEY_CANONICAL_STATUSES: tuple[str, ...] = tuple(d.key for d in MOBILE_STATUS_DEFINITIONS)
AUTO_KEY_CANONICAL_FINAL_STATUSES = frozenset(d.key for d in MOBILE_STATUS_DEFINITIONS if d.closed)
AUTO_KEY_LEGACY_FINAL_STATUSES = frozenset(
    alias for alias, canonical in AUTO_KEY_LEGACY_STATUS_MAP.items() if canonical in AUTO_KEY_CANONICAL_FINAL_STATUSES
)
AUTO_KEY_FINAL_STATUSES = AUTO_KEY_CANONICAL_FINAL_STATUSES | AUTO_KEY_LEGACY_FINAL_STATUSES
AUTO_KEY_ACTIVE_STATUSES = frozenset(
    {d.key for d in MOBILE_STATUS_DEFINITIONS if not d.closed}
    | {alias for alias, canonical in AUTO_KEY_LEGACY_STATUS_MAP.items() if canonical not in AUTO_KEY_CANONICAL_FINAL_STATUSES}
)

#: Stored values that mean "the customer has been asked to confirm a booking".
AUTO_KEY_AWAITING_CONFIRMATION_STATUSES = frozenset(
    {"awaiting_booking_confirmation"} | set(MOBILE_STATUS_BY_KEY["awaiting_booking_confirmation"].aliases)
)
#: Stored values that mean "the booking is confirmed".
AUTO_KEY_BOOKED_STATUSES = frozenset({"booking_confirmed"} | set(MOBILE_STATUS_BY_KEY["booking_confirmed"].aliases))
#: Work is done but the money is still open.
AUTO_KEY_COMPLETED_UNPAID_STATUSES = frozenset(
    {"work_completed"} | set(MOBILE_STATUS_BY_KEY["work_completed"].aliases)
)


def canonical_auto_key_status(status: str) -> str:
    """Return the canonical Mobile Services status for any stored value."""

    return AUTO_KEY_LEGACY_STATUS_MAP.get(status, status)


def mobile_status_definition(status: str) -> MobileStatusDefinition | None:
    return MOBILE_STATUS_BY_KEY.get(canonical_auto_key_status(status))


def mobile_status_label(status: str) -> str:
    definition = mobile_status_definition(status)
    return definition.label if definition else status.replace("_", " ").title()


def mobile_status_category(status: str) -> MobileStatusCategory | None:
    definition = mobile_status_definition(status)
    return definition.category if definition else None


def statuses_in_category(category: MobileStatusCategory) -> frozenset[str]:
    """Every stored value (canonical + aliases) that reports under ``category``."""

    return frozenset(
        value
        for definition in MOBILE_STATUS_DEFINITIONS
        if definition.category == category
        for value in (definition.key, *definition.aliases)
    )


def mobile_status_vocabulary() -> list[dict]:
    """JSON-friendly vocabulary for API consumers (labels, categories, aliases)."""

    return [
        {
            "key": d.key,
            "label": d.label,
            "category": d.category,
            "closed": d.closed,
            "aliases": list(d.aliases),
        }
        for d in MOBILE_STATUS_DEFINITIONS
    ]
