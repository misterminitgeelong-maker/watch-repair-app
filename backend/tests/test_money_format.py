"""Server-rendered money must match what the app shows for the same amount.

The frontend routes every amount through `frontend/src/lib/money.ts`
(`Intl.NumberFormat('en-AU', {style: 'currency', ...})`). PDFs, emails and SMS
are rendered server-side, so if the two drift a customer sees one number in the
portal and a differently formatted one on the invoice they were emailed.

The expected strings below are what `Intl.NumberFormat('en-AU', {style:
'currency', currency: 'AUD'})` produces for the same input. If a change here
makes one of these fail, check the frontend formatter before changing the
expectation.
"""
import pytest

from app.money import DEFAULT_CURRENCY, currency_symbol, format_cents


@pytest.mark.parametrize(
    "cents,expected",
    [
        (0, "$0.00"),
        (99, "$0.99"),
        (100, "$1.00"),
        (4500, "$45.00"),
        (123456, "$1,234.56"),          # grouping: the bug this module fixed
        (100000000, "$1,000,000.00"),
        (-123456, "-$1,234.56"),
    ],
)
def test_matches_frontend_rendering_for_aud(cents, expected):
    assert format_cents(cents, "AUD") == expected


def test_defaults_to_aud():
    assert format_cents(123456) == format_cents(123456, DEFAULT_CURRENCY) == "$1,234.56"


def test_none_is_zero_not_a_crash():
    assert format_cents(None) == "$0.00"


def test_unknown_currency_is_prefixed_never_symbol_less():
    """Two of the three implementations this replaced returned "" for an unknown
    currency, printing a bare amount with no indication of denomination."""
    assert format_cents(123456, "EUR") == "EUR 1,234.56"
    assert format_cents(123456, "ZZZ") == "ZZZ 1,234.56"
    assert currency_symbol("EUR") == "EUR "
    assert currency_symbol(None) == "$"
    assert currency_symbol("") == "$"


def test_usd_keeps_a_bare_dollar_sign():
    """Deliberate divergence from the frontend — see the note in app/money.py.

    Intl in en-AU renders USD as "USD 1,234.56". Quote, Invoice and Payment all
    default to currency="USD" in the model, so matching that would make an
    Australian shop's invoices suddenly read "USD". That is a data problem to
    fix in the data, not something a formatting change should surface.
    """
    assert format_cents(123456, "USD") == "$1,234.56"


def test_half_up_rounding_not_binary_float():
    """round(2.675, 2) is 2.67 under binary float; invoices must not inherit that."""
    assert format_cents(267500) == "$2,675.00"
    assert format_cents(1) == "$0.01"
    assert format_cents(5) == "$0.05"
