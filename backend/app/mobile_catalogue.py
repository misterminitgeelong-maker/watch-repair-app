"""Mobile Services POS catalogue categories.

The pricing catalogues are separate tables (OEM keys, general services, garage
door servicing) and stay untouched; what a shop *sells* is a per-tenant choice.
A mobile-key technician sees vehicle-key and general services by default, and
an owner can switch on garage door work when that shop offers it.
"""
from __future__ import annotations

import json
from dataclasses import dataclass

from .models import Tenant


@dataclass(frozen=True)
class CatalogueCategory:
    key: str
    label: str
    description: str


MOBILE_CATALOGUE_CATEGORIES: tuple[CatalogueCategory, ...] = (
    CatalogueCategory("vehicle_key", "Vehicle keys", "OEM key pricing by make and model (Add Key, AKL, programming)."),
    CatalogueCategory("general_service", "General services", "Callouts, entry, diagnostics, cutting and other mobile services."),
    CatalogueCategory("garage_door", "Garage door servicing", "Door services, springs, cables, motors and seals."),
)
CATALOGUE_CATEGORY_KEYS: tuple[str, ...] = tuple(c.key for c in MOBILE_CATALOGUE_CATEGORIES)
DEFAULT_CATALOGUE_CATEGORIES: tuple[str, ...] = ("vehicle_key", "general_service")


def parse_catalogue_categories(raw: str | None) -> list[str]:
    """Stored JSON -> ordered, de-duplicated list of known category keys.

    Unknown keys are dropped rather than failing the request, and an empty or
    malformed value falls back to the default so the POS never ends up with no
    catalogue at all.
    """
    if not raw:
        return list(DEFAULT_CATALOGUE_CATEGORIES)
    try:
        values = json.loads(raw)
    except (TypeError, ValueError):
        return list(DEFAULT_CATALOGUE_CATEGORIES)
    if not isinstance(values, list):
        return list(DEFAULT_CATALOGUE_CATEGORIES)
    seen: list[str] = []
    for value in values:
        if isinstance(value, str) and value in CATALOGUE_CATEGORY_KEYS and value not in seen:
            seen.append(value)
    return seen or list(DEFAULT_CATALOGUE_CATEGORIES)


def enabled_catalogue_categories(tenant: Tenant | None) -> list[str]:
    return parse_catalogue_categories(getattr(tenant, "mobile_catalogue_categories_json", None) if tenant else None)


def normalise_catalogue_categories(values: list[str]) -> list[str]:
    """Validate an owner's selection; raises ValueError naming the bad key."""
    seen: list[str] = []
    for value in values:
        if value not in CATALOGUE_CATEGORY_KEYS:
            raise ValueError(f"Unknown catalogue category: {value}")
        if value not in seen:
            seen.append(value)
    if not seen:
        raise ValueError("At least one catalogue category must stay enabled")
    # Keep canonical order so the stored value is stable regardless of click order.
    return [key for key in CATALOGUE_CATEGORY_KEYS if key in seen]


def serialise_catalogue_categories(values: list[str]) -> str | None:
    """NULL when the selection equals the default, so un-touched tenants stay NULL."""
    if list(values) == list(DEFAULT_CATALOGUE_CATEGORIES):
        return None
    return json.dumps(list(values))
