"""Per-shop region (AU / NZ): currency, timezone and Stripe country travel together."""
from __future__ import annotations

REGION_DEFAULTS: dict[str, dict[str, str]] = {
    "AU": {"currency": "AUD", "timezone": "Australia/Melbourne"},
    "NZ": {"currency": "NZD", "timezone": "Pacific/Auckland"},
}
_REGION_BY_CURRENCY = {v["currency"]: k for k, v in REGION_DEFAULTS.items()}


def region_for_currency(currency: str | None) -> str:
    return _REGION_BY_CURRENCY.get((currency or "AUD").strip().upper(), "AU")


def stripe_country_for_tenant(tenant, fallback: str = "AU") -> str:
    """ISO country for a new Stripe Connect account: NZ shops bill in NZD → NZ, else the platform default."""
    if tenant is not None and (tenant.default_currency or "").strip().upper() == "NZD":
        return "NZ"
    return (fallback or "AU").strip().upper()[:2]


def is_nz_minit_placement(region: str | None, area: str | None) -> bool:
    """True when a Minit TSS placement is New Zealand (Region "NZ", Area "NZ NORTH"/"NZ SOUTH")."""
    return (region or "").strip().upper() == "NZ" or (area or "").strip().upper().startswith("NZ")


def apply_nz_defaults_from_placement(tenant) -> bool:
    """Preset NZD + Pacific/Auckland for a tenant HQ placed in an NZ region.

    Only moves a tenant still on the AU defaults, so a deliberate later choice is never
    overwritten. Returns True if the tenant changed.
    """
    if not is_nz_minit_placement(tenant.minit_region, tenant.minit_area):
        return False
    if (tenant.default_currency or "AUD").strip().upper() != "AUD":
        return False
    tenant.default_currency = REGION_DEFAULTS["NZ"]["currency"]
    tenant.timezone = REGION_DEFAULTS["NZ"]["timezone"]
    return True
