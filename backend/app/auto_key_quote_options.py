"""Two-outcome auto key quotes (e.g. BMW CAS3 vs CAS3++).

A quote may carry options "A" and "B". Each line item is tagged with its option key, or left
untagged when it applies to both. The customer approves once; the tech picks the outcome on
site, which fixes the quote totals and decides what gets invoiced.
"""
from __future__ import annotations

from uuid import UUID

from sqlmodel import Session, or_, select

from .gst import compute_gst_amounts
from .models import AutoKeyQuote, AutoKeyQuoteLineItem

OPTION_KEYS = ("A", "B")


def has_options(quote: AutoKeyQuote) -> bool:
    return bool(quote.option_a_label and quote.option_b_label)


def needs_option_choice(quote: AutoKeyQuote) -> bool:
    return has_options(quote) and quote.selected_option not in OPTION_KEYS


def option_label(quote: AutoKeyQuote, key: str) -> str:
    return (quote.option_a_label if key == "A" else quote.option_b_label) or f"Option {key}"


def invoice_line_items(session: Session, quote_id: UUID, selected_option: str | None) -> list[AutoKeyQuoteLineItem]:
    """Line items that make up the quote's invoice: shared lines plus the chosen option's lines."""
    stmt = select(AutoKeyQuoteLineItem).where(AutoKeyQuoteLineItem.auto_key_quote_id == quote_id)
    if selected_option in OPTION_KEYS:
        stmt = stmt.where(
            or_(AutoKeyQuoteLineItem.option_key.is_(None), AutoKeyQuoteLineItem.option_key == selected_option)
        )
    return list(session.exec(stmt.order_by(AutoKeyQuoteLineItem.created_at)).all())


def option_totals(quote: AutoKeyQuote, items: list[AutoKeyQuoteLineItem]) -> dict[str, tuple[int, int, int]]:
    """(subtotal, tax, total) per option key, shared lines counted in both."""
    out: dict[str, tuple[int, int, int]] = {}
    for key in OPTION_KEYS:
        entered = sum(i.total_price_cents for i in items if i.option_key in (None, key))
        out[key] = compute_gst_amounts(entered, quote.gst_enabled, quote.gst_inclusive, currency=quote.currency)
    return out


def apply_totals(quote: AutoKeyQuote, items: list[AutoKeyQuoteLineItem]) -> None:
    """Set quote totals: the chosen option once picked, otherwise the higher option."""
    totals = option_totals(quote, items)
    if quote.selected_option in OPTION_KEYS:
        chosen = totals[quote.selected_option]
    else:
        chosen = max(totals.values(), key=lambda t: t[2])
    quote.subtotal_cents, quote.tax_cents, quote.total_cents = chosen
