"""Minit HQ bundled monthly billing: pure calculation, no Stripe, no I/O.

Agreed terms (all amounts ex-GST, in cents):
  * Core platform: $55 per billable operator per month.
  * Routing add-on and Prospecting add-on: $15 per operator per month up to and
    including 2027-02-28, then $25. The price is chosen by the billing month
    (its first day), so the whole of February 2027 is $15 and March 2027 is $25.

A billable operator is a tenant linked to the HQ network with network_role
"operator" that is active and not billing_exempt. The HQ tenant itself, retail
shops, exempt and inactive tenants are never billed.

Add-ons are not stored anywhere yet (HqSettings has no per-HQ add-on flags), so
callers pass ``routing`` / ``prospecting`` explicitly; they apply to every
billed operator.
"""

from __future__ import annotations

import csv
import io
from dataclasses import dataclass, field
from datetime import date
from typing import Iterable

CORE_CENTS = 5500
ADDON_CENTS_EARLY = 1500
ADDON_CENTS_LATE = 2500
#: Last day (inclusive) the early add-on price applies.
ADDON_STEP_DATE = date(2027, 2, 28)

GST_RATE_BP_AU = 1000
GST_RATE_BP_NZ = 1500

ROLE_OPERATOR = "operator"
ROLE_HQ = "hq"


def addon_price_cents(on: date) -> int:
    """Per-operator monthly price of each add-on for the given (billing month) date."""
    return ADDON_CENTS_EARLY if on <= ADDON_STEP_DATE else ADDON_CENTS_LATE


def parse_month(value: str) -> date:
    """'YYYY-MM' -> first day of that month."""
    try:
        y, m = value.strip().split("-")
        return date(int(y), int(m), 1)
    except (ValueError, AttributeError) as exc:
        raise ValueError("month must look like YYYY-MM") from exc


def gst_cents(amount_cents: int, rate_bp: int) -> int:
    """GST on an ex-GST amount, rate in basis points, rounded half up."""
    return (amount_cents * rate_bp + 5000) // 10000


@dataclass(frozen=True)
class SiteForBilling:
    tenant_id: str
    name: str
    network_role: str
    is_active: bool = True
    billing_exempt: bool = False
    shop_number: str | None = None
    is_nz: bool = False


@dataclass(frozen=True)
class LineItem:
    tenant_id: str
    name: str
    shop_number: str | None
    gst_rate_bp: int
    core_cents: int
    routing_cents: int
    prospecting_cents: int

    @property
    def subtotal_cents(self) -> int:
        return self.core_cents + self.routing_cents + self.prospecting_cents

    @property
    def gst_cents(self) -> int:
        return gst_cents(self.subtotal_cents, self.gst_rate_bp)


@dataclass(frozen=True)
class InvoiceSummary:
    billing_month: date
    routing: bool
    prospecting: bool
    addon_unit_cents: int
    lines: tuple[LineItem, ...]
    excluded: tuple[tuple[str, str, str], ...] = field(default_factory=tuple)  # (tenant_id, name, reason)

    @property
    def operator_count(self) -> int:
        return len(self.lines)

    @property
    def subtotal_cents(self) -> int:
        return sum(l.subtotal_cents for l in self.lines)

    @property
    def gst_by_rate_bp(self) -> dict[int, int]:
        out: dict[int, int] = {}
        for l in self.lines:
            out[l.gst_rate_bp] = out.get(l.gst_rate_bp, 0) + l.gst_cents
        return out

    @property
    def gst_total_cents(self) -> int:
        return sum(self.gst_by_rate_bp.values())

    @property
    def total_cents(self) -> int:
        return self.subtotal_cents + self.gst_total_cents


def exclusion_reason(site: SiteForBilling) -> str | None:
    if site.network_role == ROLE_HQ:
        return "hq"
    if site.network_role != ROLE_OPERATOR:
        return "not_operator"
    if site.billing_exempt:
        return "billing_exempt"
    if not site.is_active:
        return "inactive"
    return None


def billable_operators(sites: Iterable[SiteForBilling]) -> list[SiteForBilling]:
    seen: set[str] = set()
    out: list[SiteForBilling] = []
    for s in sites:
        if exclusion_reason(s) is None and s.tenant_id not in seen:  # a tenant is billed once
            seen.add(s.tenant_id)
            out.append(s)
    return out


def compute_invoice(
    sites: Iterable[SiteForBilling],
    billing_month: date,
    *,
    routing: bool = False,
    prospecting: bool = False,
) -> InvoiceSummary:
    sites = list(sites)
    unit = addon_price_cents(billing_month)
    lines = tuple(
        LineItem(
            tenant_id=s.tenant_id,
            name=s.name,
            shop_number=s.shop_number,
            gst_rate_bp=GST_RATE_BP_NZ if s.is_nz else GST_RATE_BP_AU,
            core_cents=CORE_CENTS,
            routing_cents=unit if routing else 0,
            prospecting_cents=unit if prospecting else 0,
        )
        for s in sorted(billable_operators(sites), key=lambda s: ((s.shop_number or ""), s.name))
    )
    excluded = tuple(
        (s.tenant_id, s.name, r) for s in sites if (r := exclusion_reason(s)) is not None
    )
    return InvoiceSummary(billing_month, routing, prospecting, unit, lines, excluded)


def _dollars(cents: int) -> str:
    return f"{cents / 100:.2f}"


def summary_to_dict(inv: InvoiceSummary) -> dict:
    return {
        "billing_month": inv.billing_month.strftime("%Y-%m"),
        "note": "Amounts are integer cents, ex-GST unless named otherwise. GST is 10%; 15% for NZ operators.",
        "routing": inv.routing,
        "prospecting": inv.prospecting,
        "addon_unit_cents": inv.addon_unit_cents,
        "operator_count": inv.operator_count,
        "lines": [
            {
                "tenant_id": l.tenant_id,
                "name": l.name,
                "shop_number": l.shop_number,
                "core_cents": l.core_cents,
                "routing_cents": l.routing_cents,
                "prospecting_cents": l.prospecting_cents,
                "subtotal_ex_gst_cents": l.subtotal_cents,
                "gst_rate_percent": l.gst_rate_bp / 100,
                "gst_cents": l.gst_cents,
            }
            for l in inv.lines
        ],
        "subtotal_ex_gst_cents": inv.subtotal_cents,
        "gst": [
            {"rate_percent": bp / 100, "label": "GST (NZ)" if bp == GST_RATE_BP_NZ else "GST", "amount_cents": amt}
            for bp, amt in sorted(inv.gst_by_rate_bp.items())
        ],
        "gst_total_cents": inv.gst_total_cents,
        "total_inc_gst_cents": inv.total_cents,
        "excluded": [{"tenant_id": t, "name": n, "reason": r} for t, n, r in inv.excluded],
    }


def summary_to_csv(inv: InvoiceSummary) -> str:
    buf = io.StringIO()
    w = csv.writer(buf, lineterminator="\n")
    w.writerow(["billing_month", "shop_number", "operator", "core", "routing", "prospecting",
                "subtotal_ex_gst", "gst_rate_percent", "gst", "total_inc_gst"])
    month = inv.billing_month.strftime("%Y-%m")
    for l in inv.lines:
        w.writerow([month, l.shop_number or "", l.name, _dollars(l.core_cents), _dollars(l.routing_cents),
                    _dollars(l.prospecting_cents), _dollars(l.subtotal_cents), l.gst_rate_bp / 100,
                    _dollars(l.gst_cents), _dollars(l.subtotal_cents + l.gst_cents)])
    w.writerow([month, "", "TOTAL", "", "", "", _dollars(inv.subtotal_cents), "",
                _dollars(inv.gst_total_cents), _dollars(inv.total_cents)])
    return buf.getvalue()
