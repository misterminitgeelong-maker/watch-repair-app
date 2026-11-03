"""Warranty status for a shoe from its proof of purchase.

Birkenstock's real warranty rules are not agreed yet; until they are, a pair is
in warranty for ``DEFAULT_WARRANTY_MONTHS`` after purchase. The result is a
guide for staff, not an approval: they still decide whether a repair is free.
"""
from __future__ import annotations

import calendar
from datetime import date

DEFAULT_WARRANTY_MONTHS = 24

IN_WARRANTY = "in_warranty"
EXPIRED = "expired"
UNKNOWN = "unknown"  # no purchase date recorded


def _add_months(start: date, months: int) -> date:
    month_index = start.month - 1 + months
    year = start.year + month_index // 12
    month = month_index % 12 + 1
    return date(year, month, min(start.day, calendar.monthrange(year, month)[1]))


def warranty_expiry(purchase_date: date | None, months: int = DEFAULT_WARRANTY_MONTHS) -> date | None:
    return _add_months(purchase_date, months) if purchase_date else None


def warranty_status(purchase_date: date | None, today: date | None = None, months: int = DEFAULT_WARRANTY_MONTHS) -> str:
    expiry = warranty_expiry(purchase_date, months)
    if expiry is None:
        return UNKNOWN
    return IN_WARRANTY if (today or date.today()) <= expiry else EXPIRED
