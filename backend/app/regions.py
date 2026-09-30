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
