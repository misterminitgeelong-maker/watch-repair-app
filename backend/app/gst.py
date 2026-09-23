"""Australian GST calculation shared by the watch-repair and Mobile Services (auto-key) quote/invoice flows.

Everything here is whole-cent integer arithmetic with round-half-up, which is
what Xero does. The previous float version (``round(cents * 0.1)``) used
Python's round-half-to-even, so e.g. $0.25 ex-GST gave 2c GST where Xero gives
3c, and the two systems disagreed by a cent on the same invoice.
"""
from __future__ import annotations

from decimal import ROUND_HALF_UP, Decimal

GST_RATE = 0.10  # informational; the maths below uses the exact fraction 1/10

# GST is an Australian tax. A shop billing in another currency is not charging
# Australian GST, so no tax is added whatever the gst_enabled flag says.
GST_CURRENCIES = frozenset({"AUD"})


def gst_applies(currency: str | None) -> bool:
    """True when GST should be charged for amounts in ``currency`` (None = AUD)."""
    code = (currency or "AUD").strip().upper() or "AUD"
    return code in GST_CURRENCIES


def _div_half_up(numerator: int, denominator: int) -> int:
    """Integer division rounding half away from zero (half-up for positives)."""
    if numerator < 0:
        return -_div_half_up(-numerator, denominator)
    return (2 * numerator + denominator) // (2 * denominator)


def gst_on_exclusive(cents: int) -> int:
    """GST (10%) on a GST-exclusive amount, rounded half-up to the cent."""
    return _div_half_up(int(cents), 10)


def gst_in_inclusive(cents: int) -> int:
    """GST component (1/11) of a GST-inclusive amount, rounded half-up to the cent."""
    cents = int(cents)
    return cents - _div_half_up(cents * 10, 11)


def line_total_cents(quantity: float | int | Decimal, unit_price_cents: int | None) -> int:
    """Quantity × unit price in whole cents, rounded half-up.

    Quantity is a float column, so it goes through ``str`` into Decimal to avoid
    binary float error (0.3 * 5 is 1.4999999999999998 in float).
    """
    value = Decimal(str(quantity)) * Decimal(int(unit_price_cents or 0))
    return int(value.quantize(Decimal(1), rounding=ROUND_HALF_UP))


def compute_gst_amounts(
    entered_cents: int,
    gst_enabled: bool,
    gst_inclusive: bool,
    currency: str | None = None,
) -> tuple[int, int, int]:
    """Given the total of the entered line-item prices, return (subtotal_cents, tax_cents, total_cents).

    subtotal_cents is always GST-exclusive and total_cents is always what the customer pays,
    so total_cents == subtotal_cents + tax_cents in every case.
    """
    entered_cents = int(entered_cents)
    if not gst_enabled or not gst_applies(currency):
        return entered_cents, 0, entered_cents
    if gst_inclusive:
        # entered_cents already includes GST; back it out.
        tax_cents = gst_in_inclusive(entered_cents)
        return entered_cents - tax_cents, tax_cents, entered_cents
    # entered_cents is GST-exclusive; add GST on top.
    tax_cents = gst_on_exclusive(entered_cents)
    return entered_cents, tax_cents, entered_cents + tax_cents
