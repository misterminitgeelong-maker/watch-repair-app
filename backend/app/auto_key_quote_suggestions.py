"""Suggested retail line items for Mobile Services quotes by job type."""
from __future__ import annotations

# Unit prices AUD cents — retail baseline. Tiers apply a discount multiplier.
_JOB_TYPE_DEFAULT_CENTS: dict[str, tuple[str, int]] = {
    "Key Cutting (in-store)": ("Key cutting (in-store)", 3500),
    "Transponder Programming": ("Transponder programming", 12000),
    "Lockout – Car": ("Vehicle lockout service", 18900),
    "Lockout – Boot/Trunk": ("Boot/trunk lockout", 18900),
    "Lockout – Roadside": ("Roadside lockout", 22000),
    "All Keys Lost": ("All keys lost — supply & program", 44900),
    "Remote / Fob Sync": ("Remote / fob programming", 9900),
    "Ignition Repair": ("Ignition repair", 15900),
    "Ignition Replace": ("Ignition replacement", 34900),
    "Duplicate Key": ("Duplicate key — cut & program", 8900),
    "Broken Key Extraction": ("Broken key extraction", 12900),
    "Door Lock Change": ("Door lock service", 19900),
    "Diagnostic": ("Automotive key / immobiliser diagnostic", 15900),
}

# Tier discount multipliers (from Locksmith Master Database Job_Pricing sheet)
_TIER_MULTIPLIERS: dict[str, float] = {
    "retail": 1.0,
    "b2b":    0.80,  # B2B flat — 20% off
    "tier1":  0.75,  # MinitKey T1 — 25% off
    "tier2":  0.70,  # MinitKey T2 — 30% off
    "tier3":  0.65,  # MinitKey T3 — 35% off
}

_FALLBACK_DESCRIPTION = "Mobile key service"
_FALLBACK_UNIT_CENTS = 15000


def suggest_line_items(
    job_type: str | None,
    key_quantity: int,
    pricing_tier: str = "retail",
    additional_presets: list[str] | None = None,
) -> list[tuple[str, float, int]]:
    """Return (description, quantity, unit_price_cents) per line."""
    qty = max(1, int(key_quantity))
    multiplier = _TIER_MULTIPLIERS.get(pricing_tier, 1.0)

    if job_type and job_type in _JOB_TYPE_DEFAULT_CENTS:
        desc, base_unit = _JOB_TYPE_DEFAULT_CENTS[job_type]
        unit = int(round(base_unit * multiplier))
        lines: list[tuple[str, float, int]] = [(desc, float(qty), unit)]
    else:
        unit = int(round(_FALLBACK_UNIT_CENTS * multiplier))
        lines = [(_FALLBACK_DESCRIPTION, float(qty), unit)]

    for preset in (additional_presets or []):
        if preset and preset in _JOB_TYPE_DEFAULT_CENTS:
            a_desc, a_base = _JOB_TYPE_DEFAULT_CENTS[preset]
            a_unit = int(round(a_base * multiplier))
            lines.append((a_desc, 1.0, a_unit))

    return lines


def suggested_subtotal_cents(
    job_type: str | None,
    key_quantity: int,
    pricing_tier: str = "retail",
) -> int:
    return int(round(sum(q * p for _, q, p in suggest_line_items(job_type, key_quantity, pricing_tier))))


def gst_tax_cents(subtotal: int) -> int:
    """Australian GST 10% (round to nearest cent)."""
    return int(round(subtotal * 0.1))
