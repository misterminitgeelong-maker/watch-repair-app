"""Shared constants for the VSWT regional intelligence feature.

Single source of truth for the weekly "VSWT-WSS" Excel export's column layout and the KPI
list/grouping used for ranking and the Reports UI. Mirrors the reference standalone dashboard's
`COLUMN_MAP` / `KPI_DEFS` (see the brief this feature was built from), ported field-for-field so
the ranking behaviour matches exactly.

Used by both the upload parser (`routes/vswt_reports.py`) and the read endpoints (same file) —
keep the two lists (`COLUMN_MAP`, `KPI_DEFS`) as the only place these field names are spelled out.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

# Peer group for "fair comparison" ranking: franchise + comparable stores only.
PEER_FORMAT = "FR"
PEER_COMP_STATUS = "Comp"

# Cell values the source workbook uses for blanks/errors — treat all of these as null.
_NULL_CELL_VALUES = {"#DIV/0!", "#REF!", "#N/A", "#VALUE!", ""}


def clean_cell(value: object) -> float | str | None:
    """Normalise one Excel cell: Excel error strings / empty string / non-finite floats -> None."""
    if value is None:
        return None
    if isinstance(value, str):
        if value in _NULL_CELL_VALUES:
            return None
        return value
    if isinstance(value, float) and (value != value or value in (float("inf"), float("-inf"))):
        return None
    return value


# Identity/metadata columns: (field name on VswtWeeklyShopMetric, 1-based Excel column).
IDENTITY_COLUMN_MAP: list[tuple[str, int]] = [
    ("shop_number", 2),
    ("shop_name", 3),
    ("area_num", 4),
    ("area_name", 5),
    ("store_format", 6),
    ("comp_status", 7),
]

# Metric columns: (field name on VswtWeeklyShopMetric, 1-based Excel column). Higher is always
# better for every one of these — see `rank_of` in routes/vswt_reports.py.
METRIC_COLUMN_MAP: list[tuple[str, int]] = [
    ("budget_sales_target", 8),
    ("sales_ty", 9), ("sales_ly", 10), ("sales_pct_change", 11),
    ("customer_ty", 12), ("customer_ly", 13), ("customer_pct_change", 14),
    ("jobs_ty", 15), ("jobs_ly", 16), ("jobs_pct_change", 17),
    ("jobs_per_100", 19), ("keys_per_100", 21), ("engrave_per_100", 22),
    ("auto_remote_per_100", 24), ("sharpen_per_100", 25), ("shoe_per_100", 26),
    ("jewellery_repairs_per_100", 27),
    ("shoe_sales_ty", 38), ("shoe_jobs_ty", 41),
    ("key_sales_ty", 44), ("key_jobs_ty", 47),
    ("engrave_sales_ty", 50), ("engrave_jobs_ty", 53),
    ("watch_sales_ty", 56), ("watch_jobs_ty", 59),
    ("merch_sales_ty", 62), ("merch_jobs_ty", 65),
    ("auto_key_jobs_ty", 69), ("gg_remotes_jobs_ty", 70),
    ("watch_batt_fitted_jobs_ty", 71), ("watch_band_jobs_ty", 72),
    ("third_party_watch_repair_jobs_ty", 73), ("watch_repair_jobs_ty", 74),
    ("sharpening_jobs_ty", 75), ("jewellery_serv_jobs_ty", 76),
]

COLUMN_MAP: list[tuple[str, int]] = IDENTITY_COLUMN_MAP + METRIC_COLUMN_MAP

KpiType = Literal["currency", "percent", "count", "ratio"]
KpiGroup = Literal[
    "Headline", "Budget & Last Year", "Conversion", "Category Sales",
    "Category Jobs", "Watch & Service Detail",
]


@dataclass(frozen=True)
class KpiDef:
    key: str
    label: str
    group: KpiGroup
    type: KpiType


KPI_DEFS: list[KpiDef] = [
    KpiDef("sales_ty", "Sales $", "Headline", "currency"),
    KpiDef("sales_pct_change", "Sales % chg", "Headline", "percent"),
    KpiDef("customer_ty", "Customers", "Headline", "count"),
    KpiDef("customer_pct_change", "Customers % chg", "Headline", "percent"),
    KpiDef("jobs_ty", "Jobs", "Headline", "count"),
    KpiDef("jobs_pct_change", "Jobs % chg", "Headline", "percent"),

    KpiDef("budget_sales_target", "Budget Sales Target", "Budget & Last Year", "currency"),
    KpiDef("sales_ly", "Sales $ (LY)", "Budget & Last Year", "currency"),
    KpiDef("customer_ly", "Customers (LY)", "Budget & Last Year", "count"),
    KpiDef("jobs_ly", "Jobs (LY)", "Budget & Last Year", "count"),

    KpiDef("jobs_per_100", "Jobs per 100", "Conversion", "ratio"),
    KpiDef("keys_per_100", "Keys per 100", "Conversion", "ratio"),
    KpiDef("engrave_per_100", "Engrave per 100", "Conversion", "ratio"),
    KpiDef("auto_remote_per_100", "Auto-Remote per 100", "Conversion", "ratio"),
    KpiDef("shoe_per_100", "Shoe per 100", "Conversion", "ratio"),
    KpiDef("jewellery_repairs_per_100", "Jewellery per 100", "Conversion", "ratio"),

    KpiDef("shoe_sales_ty", "Shoe Sales $", "Category Sales", "currency"),
    KpiDef("key_sales_ty", "Key Sales $", "Category Sales", "currency"),
    KpiDef("engrave_sales_ty", "Engrave Sales $", "Category Sales", "currency"),
    KpiDef("watch_sales_ty", "Watch Sales $", "Category Sales", "currency"),
    KpiDef("merch_sales_ty", "Merch Sales $", "Category Sales", "currency"),

    KpiDef("shoe_jobs_ty", "Shoe Jobs", "Category Jobs", "count"),
    KpiDef("key_jobs_ty", "Key Jobs", "Category Jobs", "count"),
    KpiDef("engrave_jobs_ty", "Engrave Jobs", "Category Jobs", "count"),
    KpiDef("watch_jobs_ty", "Watch Jobs", "Category Jobs", "count"),
    KpiDef("merch_jobs_ty", "Merch Jobs", "Category Jobs", "count"),
    KpiDef("auto_key_jobs_ty", "Auto Key Jobs", "Category Jobs", "count"),
    KpiDef("gg_remotes_jobs_ty", "G&G Remotes Jobs", "Category Jobs", "count"),

    KpiDef("sharpen_per_100", "Sharpening per 100", "Watch & Service Detail", "ratio"),
    KpiDef("watch_batt_fitted_jobs_ty", "Watch Battery Fitted Jobs", "Watch & Service Detail", "count"),
    KpiDef("watch_band_jobs_ty", "Watch Band Jobs", "Watch & Service Detail", "count"),
    KpiDef("third_party_watch_repair_jobs_ty", "3rd Party Watch Repair Jobs", "Watch & Service Detail", "count"),
    KpiDef("watch_repair_jobs_ty", "Watch Repair Jobs", "Watch & Service Detail", "count"),
    KpiDef("sharpening_jobs_ty", "Sharpening Jobs", "Watch & Service Detail", "count"),
    KpiDef("jewellery_serv_jobs_ty", "Jewellery Service Jobs", "Watch & Service Detail", "count"),
]

KPI_BY_KEY: dict[str, KpiDef] = {k.key: k for k in KPI_DEFS}

KPI_GROUPS: list[KpiGroup] = [
    "Headline", "Budget & Last Year", "Conversion", "Category Sales",
    "Category Jobs", "Watch & Service Detail",
]

# Category-sales KPI keys, in display order, for the "category sales" trend chart.
CATEGORY_SALES_KEYS: list[tuple[str, str]] = [
    ("shoe_sales_ty", "Shoe"),
    ("key_sales_ty", "Key"),
    ("engrave_sales_ty", "Engrave"),
    ("watch_sales_ty", "Watch"),
    ("merch_sales_ty", "Merch"),
]
