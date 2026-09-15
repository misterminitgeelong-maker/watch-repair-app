"""One currency formatter for everything the server renders.

The frontend routes every amount through ``frontend/src/lib/money.ts``
(``Intl.NumberFormat('en-AU', {style: 'currency', ...})``, which produces
``$1,234.56``). Anything the server renders — PDF invoices, quote and invoice
emails, customer SMS — has to agree with it, or the same invoice shows one
number in the app and a differently formatted one on the document the customer
is actually sent.

Before this module there were three divergent symbol implementations and
``:.2f`` with no thousands separator, so the server rendered ``$1234.56``
against the app's ``$1,234.56``. Two of those implementations also returned an
empty string for an unrecognised currency, which printed a bare amount with no
symbol at all.

Amounts are stored as integer cents throughout. Prefer ``format_cents``; use
``format_amount`` only where a caller already holds a decimal value.
"""
from __future__ import annotations

from decimal import ROUND_HALF_UP, Decimal

# Currencies rendered with a bare "$". Anything else is prefixed with its code
# ("EUR 1,234.56") rather than guessed at, and never rendered symbol-less.
#
# This deliberately keeps USD on a bare "$", which is the one place it diverges
# from the frontend: Intl.NumberFormat("en-AU") disambiguates USD as
# "USD 1,234.56" because a bare "$" means AUD in that locale. Matching it here
# would be more correct in the abstract and wrong in practice — Quote, Invoice
# and Payment all default to currency="USD" in the model, so an Australian shop
# whose rows carry that default would suddenly see every invoice read "USD".
# That is a data question (why is the default USD?), not a formatting one, and
# it should be fixed in the data rather than papered over or exposed by a
# formatting change.
_DOLLAR_CURRENCIES = frozenset({"AUD", "USD", "NZD", "CAD", "SGD", "HKD"})

DEFAULT_CURRENCY = "AUD"


def currency_symbol(currency: str | None) -> str:
    """Prefix for an amount in ``currency``. Never returns an empty string."""
    code = (currency or DEFAULT_CURRENCY).strip().upper() or DEFAULT_CURRENCY
    if code in _DOLLAR_CURRENCIES:
        return "$"
    return f"{code} "


def format_amount(amount: Decimal | float | int, currency: str | None = DEFAULT_CURRENCY) -> str:
    """Render a decimal amount as ``$1,234.56``.

    Uses Decimal with half-up rounding so money never inherits binary float
    rounding (``round(2.675, 2)`` is 2.67 in binary float; invoices must not be).
    """
    value = Decimal(str(amount)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    # The sign goes outside the symbol ("-$1,234.56"), matching Intl. Formatting
    # the signed value directly would produce "$-1,234.56".
    sign = "-" if value < 0 else ""
    return f"{sign}{currency_symbol(currency)}{abs(value):,.2f}"


def format_cents(cents: int | None, currency: str | None = DEFAULT_CURRENCY) -> str:
    """Render an integer cent amount as ``$1,234.56``. ``None`` is treated as zero."""
    return format_amount(Decimal(int(cents or 0)) / 100, currency)
