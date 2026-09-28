"""The "all weeks" VSWT Excel workbook: every uploaded week for every shop in one download.

Laid out so a person can find a shop without scrolling through thousands of rows:

* **Contents** — what the file covers, then one row per shop with a link to its own tab.
* **Network by week** — region totals for each week (sales, budget, LY, customers, jobs).
* **All data** — every week x shop row with every KPI, filterable, for pivot tables.
* **One tab per shop** — that shop's weeks as rows, KPIs as columns, with totals/averages.

A full history is hundreds of shops x dozens of weeks x ~40 KPIs, written twice (All data and
the shop tabs), so this uses XlsxWriter in constant-memory mode: rows stream to disk as they are
written, which is about three times faster than openpyxl at this size and keeps memory flat.
Constant-memory mode requires each sheet's rows to be written top to bottom, in order.
"""
from __future__ import annotations

import io
import re
from collections import defaultdict
from datetime import datetime, timezone
from typing import Any, Iterable, Optional

import xlsxwriter

from .models import VswtWeeklyShopMetric
from .vswt_kpis import KPI_DEFS, KpiDef

_NUMBER_FORMATS = {
    "currency": '"$"#,##0;-"$"#,##0',
    "count": "#,##0",
    "ratio": "0.0",
    "percent": "+0.0%;-0.0%;0.0%",
}
_BAND = "#F7F9FB"
_TOTAL = "#EEF2F6"

_SHEET_NAME_BAD_CHARS = re.compile(r"[\[\]:*?/\\]")
_RESERVED_SHEET_NAMES = {"contents", "network by week", "all data"}


def _shop_sort_key(shop_number: str) -> tuple[int, int | str]:
    return (0, int(shop_number)) if shop_number.isdigit() else (1, shop_number)


def _sheet_name(shop_number: str, shop_name: Optional[str], taken: set[str]) -> str:
    """A valid, unique Excel tab name: at most 31 chars, none of []:*?/\\, no edge apostrophes."""
    base = _SHEET_NAME_BAD_CHARS.sub(" ", f"{shop_number} {shop_name or ''}")
    base = re.sub(r"\s+", " ", base)[:31].strip().strip("'") or shop_number[:31]
    name, n = base, 2
    while name.lower() in taken or name.lower() in _RESERVED_SHEET_NAMES:
        suffix = f" ({n})"
        name = base[: 31 - len(suffix)].rstrip().strip("'") + suffix
        n += 1
    taken.add(name.lower())
    return name


def _sum(values: Iterable[Optional[float]]) -> Optional[float]:
    vals = [v for v in values if v is not None]
    return sum(vals) if vals else None


def _mean(values: Iterable[Optional[float]]) -> Optional[float]:
    vals = [v for v in values if v is not None]
    return sum(vals) / len(vals) if vals else None


def _ratio_change(current: Optional[float], baseline: Optional[float]) -> Optional[float]:
    if current is None or not baseline:
        return None
    return current / baseline - 1


def _kpi_width(kpi: KpiDef) -> float:
    return max(11.0, min(18.0, len(kpi.label) * 0.9))


class _Formats:
    """Every cell format the workbook uses, created once (XlsxWriter formats are workbook-wide)."""

    def __init__(self, wb: xlsxwriter.Workbook):
        self.title = wb.add_format({"bold": True, "font_size": 16})
        self.subtitle = wb.add_format({"font_color": "#5B6573"})
        self.link = wb.add_format({"font_color": "#1072BA", "underline": 1})
        self.header = wb.add_format({
            "bold": True, "font_color": "#FFFFFF", "bg_color": "#1F2A37", "text_wrap": True, "valign": "vcenter",
        })
        self.plain = {False: None, True: wb.add_format({"bg_color": _BAND})}
        self.bold = {False: wb.add_format({"bold": True}), True: wb.add_format({"bold": True, "bg_color": _BAND})}
        self.link_row = {
            False: self.link,
            True: wb.add_format({"font_color": "#1072BA", "underline": 1, "bg_color": _BAND}),
        }
        self.num = {
            (kind, banded): wb.add_format({"num_format": fmt, **({"bg_color": _BAND} if banded else {})})
            for kind, fmt in _NUMBER_FORMATS.items() for banded in (False, True)
        }
        total = {"bold": True, "bg_color": _TOTAL, "top": 1, "top_color": "#9AA5B1"}
        self.total_label = wb.add_format(total)
        self.total_num = {kind: wb.add_format({**total, "num_format": fmt}) for kind, fmt in _NUMBER_FORMATS.items()}


def _link(ws, row: int, col: int, sheet: str, text: str, fmt) -> None:
    target = sheet.replace("'", "''")
    ws.write_url(row, col, f"internal:'{target}'!A1", fmt, string=text)


def _set_widths(ws, widths: list[float]) -> None:
    for i, width in enumerate(widths):
        ws.set_column(i, i, width)


def build_all_weeks_workbook(
    rows: list[VswtWeeklyShopMetric],
    sales_ranks: dict[tuple[int, str], int],
    generated_at: Optional[datetime] = None,
) -> bytes:
    """Render every week x shop row as a navigable .xlsx.

    `sales_ranks` maps (week, shop_number) to that shop's region sales rank for the week, using
    the same tie rule as the rest of the regional report so the numbers match the app.
    """
    generated_at = generated_at or datetime.now(timezone.utc)
    weeks = sorted({r.week_seq for r in rows})
    by_shop: dict[str, list[VswtWeeklyShopMetric]] = defaultdict(list)
    by_week: dict[int, list[VswtWeeklyShopMetric]] = defaultdict(list)
    for r in rows:
        by_shop[r.shop_number].append(r)
        by_week[r.week_seq].append(r)
    shop_numbers = sorted(by_shop, key=_shop_sort_key)
    for history in by_shop.values():
        history.sort(key=lambda r: r.week_seq)
    shops_in_week = {w: len(by_week[w]) for w in weeks}

    taken: set[str] = set()
    tab_for = {sn: _sheet_name(sn, by_shop[sn][-1].shop_name, taken) for sn in shop_numbers}

    buf = io.BytesIO()
    wb = xlsxwriter.Workbook(buf, {"constant_memory": True})
    f = _Formats(wb)
    _write_contents(wb, f, weeks, shop_numbers, by_shop, tab_for, len(rows), generated_at)
    _write_network(wb, f, weeks, by_week)
    _write_all_data(wb, f, weeks, by_week, sales_ranks, shops_in_week)
    for sn in shop_numbers:
        _write_shop(wb, f, tab_for[sn], by_shop[sn], sales_ranks, shops_in_week)
    wb.close()
    return buf.getvalue()


def _write_contents(wb, f: _Formats, weeks, shop_numbers, by_shop, tab_for, row_count, generated_at) -> None:
    ws = wb.add_worksheet("Contents")
    ws.set_tab_color("#1F2A37")
    headers = [
        "Shop #", "Shop (click to open)", "Area", "Format", "Comp status",
        "Weeks on file", "First week", "Latest week",
        "Total sales $", "Avg weekly sales $", "Latest week sales $", "Total jobs", "Total customers",
    ]
    _set_widths(ws, [9, 34, 20, 11, 12, 10, 10, 10, 15, 15, 15, 12, 13])
    header_row = 6  # 0-based
    ws.freeze_panes(header_row + 1, 2)
    if shop_numbers:
        ws.autofilter(header_row, 0, header_row + len(shop_numbers), len(headers) - 1)

    week_span = f"Week {weeks[0]} to week {weeks[-1]}" if weeks else "No weeks"
    ws.write(0, 0, "VSWT regional report — all weeks", f.title)
    ws.write(1, 0, (
        f"{week_span} · {len(weeks)} week{'s' if len(weeks) != 1 else ''} · "
        f"{len(shop_numbers)} shops · {row_count:,} shop-week rows"
    ), f.subtitle)
    ws.write(2, 0, f"Generated {generated_at.strftime('%d %b %Y %H:%M')} UTC", f.subtitle)
    _link(ws, 3, 0, "Network by week", "Network by week", f.link)
    ws.write(3, 2, "Region totals for every week", f.subtitle)
    _link(ws, 4, 0, "All data", "All data", f.link)
    ws.write(4, 2, "Every shop and week in one filterable table (for pivots)", f.subtitle)
    ws.write_row(header_row, 0, headers, f.header)

    for i, sn in enumerate(shop_numbers):
        row, band = header_row + 1 + i, bool(i % 2)
        history = by_shop[sn]
        latest = history[-1]
        money, count = f.num[("currency", band)], f.num[("count", band)]
        ws.write(row, 0, sn, f.plain[band])
        _link(ws, row, 1, tab_for[sn], latest.shop_name or sn, f.link_row[band])
        ws.write(row, 2, latest.area_name, f.plain[band])
        ws.write(row, 3, latest.store_format, f.plain[band])
        ws.write(row, 4, latest.comp_status, f.plain[band])
        ws.write(row, 5, len(history), f.plain[band])
        ws.write(row, 6, history[0].week_seq, f.plain[band])
        ws.write(row, 7, latest.week_seq, f.plain[band])
        ws.write(row, 8, _sum(r.sales_ty for r in history), money)
        ws.write(row, 9, _mean(r.sales_ty for r in history), money)
        ws.write(row, 10, latest.sales_ty, money)
        ws.write(row, 11, _sum(r.jobs_ty for r in history), count)
        ws.write(row, 12, _sum(r.customer_ty for r in history), count)


def _write_network(wb, f: _Formats, weeks, by_week) -> None:
    ws = wb.add_worksheet("Network by week")
    headers = [
        "Week", "Shops reporting", "Sales $", "Sales $ (LY)", "Sales % chg vs LY",
        "Budget $", "Sales vs budget", "Customers", "Customers (LY)", "Jobs", "Jobs (LY)",
        "Avg sales per shop $", "Avg jobs per 100", "Top shop by sales", "Top shop sales $",
    ]
    _set_widths(ws, [8, 10, 15, 15, 12, 15, 12, 12, 12, 11, 11, 14, 11, 30, 15])
    ws.freeze_panes(2, 1)
    _link(ws, 0, 0, "Contents", "← Contents", f.link)
    ws.write_row(1, 0, headers, f.header)
    for i, w in enumerate(weeks):
        row, band = 2 + i, bool(i % 2)
        money, count, pct, ratio = (f.num[(k, band)] for k in ("currency", "count", "percent", "ratio"))
        week_rows = by_week[w]
        # Compare like with like: only shops reporting both figures count towards a % change.
        both = [r for r in week_rows if r.sales_ty is not None and r.sales_ly is not None]
        budgeted = [r for r in week_rows if r.sales_ty is not None and r.budget_sales_target is not None]
        top = max((r for r in week_rows if r.sales_ty is not None), key=lambda r: r.sales_ty, default=None)
        ws.write(row, 0, w, f.bold[band])
        ws.write(row, 1, len(week_rows), count)
        ws.write(row, 2, _sum(r.sales_ty for r in week_rows), money)
        ws.write(row, 3, _sum(r.sales_ly for r in week_rows), money)
        ws.write(row, 4, _ratio_change(_sum(r.sales_ty for r in both), _sum(r.sales_ly for r in both)), pct)
        ws.write(row, 5, _sum(r.budget_sales_target for r in week_rows), money)
        ws.write(row, 6, _ratio_change(
            _sum(r.sales_ty for r in budgeted), _sum(r.budget_sales_target for r in budgeted)), pct)
        ws.write(row, 7, _sum(r.customer_ty for r in week_rows), count)
        ws.write(row, 8, _sum(r.customer_ly for r in week_rows), count)
        ws.write(row, 9, _sum(r.jobs_ty for r in week_rows), count)
        ws.write(row, 10, _sum(r.jobs_ly for r in week_rows), count)
        ws.write(row, 11, _mean(r.sales_ty for r in week_rows), money)
        ws.write(row, 12, _mean(r.jobs_per_100 for r in week_rows), ratio)
        ws.write(row, 13, f"{top.shop_number} {top.shop_name or ''}".strip() if top else None, f.plain[band])
        ws.write(row, 14, top.sales_ty if top else None, money)


def _write_all_data(wb, f: _Formats, weeks, by_week, sales_ranks, shops_in_week) -> None:
    ws = wb.add_worksheet("All data")
    identity = ["Week", "Shop #", "Shop", "Area #", "Area", "Format", "Comp status", "Sales rank", "Shops in week"]
    headers = identity + [k.label for k in KPI_DEFS]
    _set_widths(ws, [8, 9, 28, 8, 18, 10, 11, 9, 9] + [_kpi_width(k) for k in KPI_DEFS])
    ws.freeze_panes(2, 3)
    _link(ws, 0, 0, "Contents", "← Contents", f.link)
    ws.write_row(1, 0, headers, f.header)
    total = sum(len(by_week[w]) for w in weeks)
    if total:
        ws.autofilter(1, 0, total + 1, len(headers) - 1)
    kpi_formats = [f.num[(k.type, False)] for k in KPI_DEFS]
    row = 2
    for w in weeks:
        for r in sorted(by_week[w], key=lambda r: _shop_sort_key(r.shop_number)):
            ws.write_row(row, 0, [
                w, r.shop_number, r.shop_name, r.area_num, r.area_name, r.store_format, r.comp_status,
                sales_ranks.get((w, r.shop_number)), shops_in_week[w],
            ])
            for c, (k, fmt) in enumerate(zip(KPI_DEFS, kpi_formats), start=len(identity)):
                ws.write(row, c, getattr(r, k.key), fmt)
            row += 1


def _write_shop(wb, f: _Formats, tab: str, history: list[VswtWeeklyShopMetric], sales_ranks, shops_in_week) -> None:
    ws = wb.add_worksheet(tab)
    latest = history[-1]
    lead = ["Week", "Sales rank", "Shops in week"]
    headers = lead + [k.label for k in KPI_DEFS]
    _set_widths(ws, [16, 9, 9] + [_kpi_width(k) for k in KPI_DEFS])
    header_row = 4  # 0-based
    ws.freeze_panes(header_row + 1, 1)

    details = " · ".join(p for p in (
        f"Area {latest.area_name}" if latest.area_name else None,
        latest.store_format, latest.comp_status,
        f"{len(history)} week{'s' if len(history) != 1 else ''} on file",
    ) if p)
    ws.write(0, 0, f"{latest.shop_number} · {latest.shop_name or 'Unnamed shop'}", f.title)
    ws.write(1, 0, details, f.subtitle)
    _link(ws, 2, 0, "Contents", "← Contents", f.link)
    ws.write_row(header_row, 0, headers, f.header)

    row = header_row + 1
    for i, r in enumerate(history):
        band = bool(i % 2)
        ws.write(row, 0, r.week_seq, f.bold[band])
        ws.write(row, 1, sales_ranks.get((r.week_seq, r.shop_number)), f.plain[band])
        ws.write(row, 2, shops_in_week[r.week_seq], f.plain[band])
        for c, k in enumerate(KPI_DEFS, start=len(lead)):
            ws.write(row, c, getattr(r, k.key), f.num[(k.type, band)])
        row += 1

    # Totals only make sense for money and counts; rates and % changes get an average instead.
    ranks = [sales_ranks.get((r.week_seq, r.shop_number)) for r in history]
    for label, summable_only in (("Total", True), ("Weekly average", False)):
        ws.write(row, 0, label, f.total_label)
        ws.write(row, 1, None if summable_only else _mean(ranks), f.total_num["ratio"])
        ws.write(row, 2, None, f.total_label)
        for c, k in enumerate(KPI_DEFS, start=len(lead)):
            values = [getattr(r, k.key) for r in history]
            if summable_only:
                value: Any = _sum(values) if k.type in ("currency", "count") else None
            else:
                value = _mean(values)
            ws.write(row, c, value, f.total_num[k.type])
        row += 1
