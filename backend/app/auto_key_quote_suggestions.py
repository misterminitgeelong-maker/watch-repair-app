"""Suggested retail line items for Mobile Services quotes by job type (editable defaults)."""
from __future__ import annotations

# Unit prices AUD cents — adjust to your market; not sourced from xlsx in v1.
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

_FALLBACK_DESCRIPTION = "Mobile key service"
_FALLBACK_UNIT_CENTS = 15000


def suggest_line_items(job_type: str | None, key_quantity: int) -> list[tuple[str, float, int]]:
    """Return (description, quantity, unit_price_cents) per line."""
    qty = max(1, int(key_quantity))
    if job_type and job_type in _JOB_TYPE_DEFAULT_CENTS:
        desc, unit = _JOB_TYPE_DEFAULT_CENTS[job_type]
        return [(desc, float(qty), unit)]
    return [(_FALLBACK_DESCRIPTION, float(qty), _FALLBACK_UNIT_CENTS)]


def suggested_subtotal_cents(job_type: str | None, key_quantity: int) -> int:
    return int(round(sum(q * p for _, q, p in suggest_line_items(job_type, key_quantity))))


def gst_tax_cents(subtotal: int) -> int:
    """Australian GST 10% (round to nearest cent)."""
    return int(round(subtotal * 0.1))
