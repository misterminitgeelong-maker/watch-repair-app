"""Australian / NZ GST calculation shared by the watch-repair and Mobile Services (auto-key) quote/invoice flows.

Everything here is whole-cent integer arithmetic with round-half-up, which is
what Xero does. The previous float version (``round(cents * 0.1)``) used
Python's round-half-to-even, so e.g. $0.25 ex-GST gave 2c GST where Xero gives
3c, and the two systems disagreed by a cent on the same invoice.
"""
from __future__ import annotations

from decimal import ROUND_HALF_UP, Decimal

# GST/VAT-style sales tax by billing currency, as (numerator, denominator).
# AUD = Australian GST 10%; NZD = New Zealand GST 15%. A currency not listed
# here (e.g. USD) is not charged any tax whatever the gst_enabled flag says.
GST_RATES: dict[str, tuple[int, int]] = {"AUD": (1, 10), "NZD": (3, 20)}
GST_RATE = 0.10  # informational, AUD default
GST_CURRENCIES = frozenset(GST_RATES)


def _code(currency: str | None) -> str:
    return (currency or "AUD").strip().upper() or "AUD"


def gst_applies(currency: str | None) -> bool:
    """True when GST should be charged for amounts in ``currency`` (None = AUD)."""
    return _code(currency) in GST_RATES


def gst_rate(currency: str | None) -> float:
    num, den = GST_RATES.get(_code(currency), GST_RATES["AUD"])
    return num / den


def _div_half_up(numerator: int, denominator: int) -> int:
    """Integer division rounding half away from zero (half-up for positives)."""
    if numerator < 0:
        return -_div_half_up(-numerator, denominator)
    return (2 * numerator + denominator) // (2 * denominator)


def gst_on_exclusive(cents: int, currency: str | None = None) -> int:
    """GST on a GST-exclusive amount (10% AUD, 15% NZD), rounded half-up to the cent."""
    num, den = GST_RATES.get(_code(currency), GST_RATES["AUD"])
    return _div_half_up(int(cents) * num, den)


def gst_in_inclusive(cents: int, currency: str | None = None) -> int:
    """GST component (1/11 AUD, 3/23 NZD) of a GST-inclusive amount, rounded half-up to the cent."""
    num, den = GST_RATES.get(_code(currency), GST_RATES["AUD"])
    cents = int(cents)
    return _div_half_up(cents * num, den + num)


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
        tax_cents = gst_in_inclusive(entered_cents, currency)
        return entered_cents - tax_cents, tax_cents, entered_cents
    # entered_cents is GST-exclusive; add GST on top.
    tax_cents = gst_on_exclusive(entered_cents, currency)
    return entered_cents, tax_cents, entered_cents + tax_cents
