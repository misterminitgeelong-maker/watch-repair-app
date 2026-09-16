"""Roll the per-shop VSWT week up to a region.

A region's week is the sum of its shops' additive metrics (sales, customers,
jobs, category sales) and the mean of their rates (per-100 conversions). The
same comparison contract as the shop cockpit — current / baseline / rolling /
rank — but the field it is ranked in is the other regions, and the table
underneath it is the region's shops.

Pure functions over already-loaded rows; the route layer does the queries.
"""

from __future__ import annotations

from collections import defaultdict
from typing import Any, Optional
from uuid import UUID

from .models import VswtWeeklyShopMetric
from .vswt_insights import Baseline, baseline_for, fmt_money, fmt_pct
from .vswt_kpis import CATEGORY_SALES_KEYS, KPI_BY_KEY, KPI_DEFS

#: Derived metrics the shop cockpit adds on top of KPI_DEFS.
DERIVED_DEFS: list[dict[str, str]] = [
    {"key": "avg_sale", "label": "Average sale", "group": "Headline", "type": "currency"},
    {"key": "jobs_per_customer", "label": "Jobs per customer", "group": "Conversion", "type": "ratio"},
]
METRIC_DEFS: list[dict[str, str]] = [
    {"key": k.key, "label": k.label, "group": k.group, "type": k.type} for k in KPI_DEFS
] + DERIVED_DEFS
HEADLINE_KEYS = ("sales_ty", "customer_ty", "jobs_ty", "avg_sale")
_LAST_YEAR_KEYS = {"sales_ty": "sales_ly", "customer_ty": "customer_ly", "jobs_ty": "jobs_ly"}


def shop_value(row: Optional[VswtWeeklyShopMetric], key: str) -> Optional[float]:
    if row is None:
        return None
    if key == "avg_sale":
        return row.sales_ty / row.customer_ty if row.sales_ty is not None and row.customer_ty else None
    if key == "jobs_per_customer":
        return row.jobs_ty / row.customer_ty if row.jobs_ty is not None and row.customer_ty else None
    return getattr(row, key, None)


def rollup(rows: list[VswtWeeklyShopMetric]) -> dict[str, Optional[float]]:
    """One region-week from its shops' rows. Sums for money and counts, means
    for rates, and the derived ratios recomputed from the sums so the
    region's average sale is its real average sale, not the mean of averages."""
    out: dict[str, Optional[float]] = {}
    if not rows:
        return {d["key"]: None for d in METRIC_DEFS}
    for d in KPI_DEFS:
        values = [getattr(r, d.key) for r in rows if getattr(r, d.key) is not None]
        if not values:
            out[d.key] = None
        elif d.type in ("currency", "count"):
            out[d.key] = float(sum(values))
        else:
            out[d.key] = sum(values) / len(values)
    for ly in _LAST_YEAR_KEYS.values():
        values = [getattr(r, ly) for r in rows if getattr(r, ly) is not None]
        out[ly] = float(sum(values)) if values else None
    sales, customers, jobs = out.get("sales_ty"), out.get("customer_ty"), out.get("jobs_ty")
    out["avg_sale"] = sales / customers if sales is not None and customers else None
    out["jobs_per_customer"] = jobs / customers if jobs is not None and customers else None
    return out


def rank_among(values_by_id: dict[Any, Optional[float]], target: Any) -> Optional[int]:
    value = values_by_id.get(target)
    if value is None:
        return None
    return 1 + sum(1 for v in values_by_id.values() if v is not None and v > value)


def pct_delta(current: Optional[float], baseline: Optional[float]) -> Optional[float]:
    if current is None or baseline in (None, 0):
        return None
    return (current - baseline) / abs(baseline)


def _mean(values: list[Optional[float]]) -> Optional[float]:
    present = [v for v in values if v is not None]
    return sum(present) / len(present) if present else None


def build_region_rows(
    *,
    current: dict[str, Optional[float]],
    previous: dict[str, Optional[float]],
    weekly_rollups: dict[int, dict[str, Optional[float]]],
    prior_weeks: list[int],
    comparison: str,
    region_values_by_key: dict[str, dict[UUID, Optional[float]]],
    prev_region_values_by_key: dict[str, dict[UUID, Optional[float]]],
    region_id: UUID,
    network_avg_by_key: dict[str, Optional[float]],
) -> tuple[list[dict[str, Any]], dict[str, Baseline]]:
    """The KPI table for a region: one row per metric with the shop cockpit's shape."""
    rows: list[dict[str, Any]] = []
    baselines: dict[str, Baseline] = {}
    for d in METRIC_DEFS:
        key = d["key"]
        cur = current.get(key)
        prev = previous.get(key)
        rolling: dict[int, Optional[float]] = {}
        counts: dict[int, int] = {}
        for window in (4, 13, 52):
            vals = [weekly_rollups.get(w, {}).get(key) for w in prior_weeks[-window:]]
            rolling[window] = _mean(vals)
            counts[window] = len([v for v in vals if v is not None])
        base = baseline_for(cur, [weekly_rollups.get(w, {}).get(key) for w in prior_weeks[-13:]])
        baselines[key] = base
        ly_key = _LAST_YEAR_KEYS.get(key)
        last_year = current.get(ly_key) if ly_key else None
        comparison_value = {
            "previous": prev,
            "4w": rolling[4],
            "13w": rolling[13],
            "52w": rolling[52],
            "last_year": last_year,
        }.get(comparison, prev)
        rank = rank_among(region_values_by_key.get(key, {}), region_id)
        prev_rank = rank_among(prev_region_values_by_key.get(key, {}), region_id)
        rows.append(
            {
                **d,
                "current": cur,
                "previous": prev,
                "rolling_4": rolling[4],
                "rolling_13": rolling[13],
                "rolling_52": rolling[52],
                "rolling_counts": {str(k): v for k, v in counts.items()},
                "last_year": last_year,
                "comparison": comparison_value,
                "delta": cur - comparison_value if cur is not None and comparison_value is not None else None,
                "delta_pct": pct_delta(cur, comparison_value),
                "network_avg": network_avg_by_key.get(key),
                "rank": rank,
                "previous_rank": prev_rank,
                "rank_change": prev_rank - rank if rank is not None and prev_rank is not None else None,
                "zscore": base.zscore,
                "anomaly": base.anomaly,
                "watch": base.watch,
                "baseline_weeks": base.count,
            }
        )
    return rows, baselines


def build_shop_table(
    *,
    shop_numbers: list[str],
    current_by_shop: dict[str, VswtWeeklyShopMetric],
    previous_by_shop: dict[str, VswtWeeklyShopMetric],
    history_by_shop: dict[str, dict[int, VswtWeeklyShopMetric]],
    prior_weeks: list[int],
    network_current_rows: list[VswtWeeklyShopMetric],
    targets_by_shop: dict[str, dict[str, float]],
    tenant_by_shop: dict[str, UUID],
) -> list[dict[str, Any]]:
    """One line per shop in the region for the selected week."""
    region_sales = {sn: shop_value(current_by_shop.get(sn), "sales_ty") for sn in shop_numbers}
    network_sales = {r.shop_number: r.sales_ty for r in network_current_rows}
    table: list[dict[str, Any]] = []
    for sn in shop_numbers:
        cur = current_by_shop.get(sn)
        prev = previous_by_shop.get(sn)
        history = history_by_shop.get(sn, {})
        sales = shop_value(cur, "sales_ty")
        prev_sales = shop_value(prev, "sales_ty")
        base = baseline_for(sales, [shop_value(history.get(w), "sales_ty") for w in prior_weeks[-13:]])
        target = targets_by_shop.get(sn, {}).get("sales_ty")
        table.append(
            {
                "shop_number": sn,
                "tenant_id": str(tenant_by_shop[sn]) if sn in tenant_by_shop else None,
                "shop_name": cur.shop_name if cur else (prev.shop_name if prev else f"Shop {sn}"),
                "area_name": cur.area_name if cur else None,
                "reported": cur is not None,
                "sales": sales,
                "previous_sales": prev_sales,
                "delta": sales - prev_sales if sales is not None and prev_sales is not None else None,
                "delta_pct": pct_delta(sales, prev_sales),
                "customers": shop_value(cur, "customer_ty"),
                "jobs": shop_value(cur, "jobs_ty"),
                "avg_sale": shop_value(cur, "avg_sale"),
                "rank_in_region": rank_among(region_sales, sn),
                "rank_in_network": rank_among(network_sales, sn),
                "zscore": base.zscore,
                "anomaly": base.anomaly,
                "watch": base.watch,
                "baseline_weeks": base.count,
                "target": target,
                "target_variance": sales - target if sales is not None and target is not None else None,
                "target_met": (sales >= target) if sales is not None and target is not None else None,
            }
        )
    table.sort(key=lambda r: (r["sales"] is None, -(r["sales"] or 0)))
    return table


def movers(table: list[dict[str, Any]], limit: int = 5) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    with_delta = [r for r in table if r["delta_pct"] is not None]
    up = sorted((r for r in with_delta if r["delta_pct"] > 0), key=lambda r: -r["delta_pct"])[:limit]
    down = sorted((r for r in with_delta if r["delta_pct"] < 0), key=lambda r: r["delta_pct"])[:limit]
    return up, down


def target_attainment(table: list[dict[str, Any]]) -> dict[str, Any]:
    with_target = [r for r in table if r["target"] is not None]
    met = [r for r in with_target if r["target_met"]]
    total_target = sum(r["target"] for r in with_target) if with_target else None
    total_current = sum(r["sales"] or 0 for r in with_target) if with_target else None
    return {
        "shops_with_target": len(with_target),
        "shops_met": len(met),
        "total_target": total_target,
        "total_current": total_current,
        "attainment_pct": (total_current / total_target) if total_target else None,
    }


def region_alerts(
    *,
    rows_by_key: dict[str, dict[str, Any]],
    baselines: dict[str, Baseline],
    table: list[dict[str, Any]],
    movers_down: list[dict[str, Any]],
    region_count: int,
) -> list[dict[str, str]]:
    alerts: list[dict[str, str]] = []
    sales = rows_by_key["sales_ty"]
    base = baselines["sales_ty"]
    if base.zscore is not None and base.zscore <= -2.0:
        alerts.append(
            {
                "severity": "critical",
                "title": "Region sales unusually low",
                "message": f"{base.zscore:+.1f} standard deviations below the region's {base.count}-week norm.",
            }
        )
    elif base.zscore is not None and base.zscore <= -1.5:
        alerts.append(
            {
                "severity": "warning",
                "title": "Region sales softer than its norm",
                "message": f"{base.zscore:+.1f} standard deviations below the {base.count}-week norm.",
            }
        )
    elif base.zscore is None and sales.get("delta_pct") is not None and sales["delta_pct"] <= -0.10:
        alerts.append(
            {
                "severity": "warning",
                "title": "Region sales below comparison",
                "message": f"Sales are {fmt_pct(sales['delta_pct'], signed=False)} below the selected baseline.",
            }
        )
    if base.zscore is not None and base.zscore >= 2.0:
        alerts.append(
            {
                "severity": "positive",
                "title": "Region sales unusually strong",
                "message": f"{base.zscore:+.1f} standard deviations above the region's {base.count}-week norm.",
            }
        )
    if sales.get("rank_change") is not None and sales["rank_change"] < 0 and region_count > 1:
        alerts.append(
            {
                "severity": "warning" if sales["rank_change"] <= -2 else "info",
                "title": "Region rank fell",
                "message": f"Sales rank moved {sales['rank_change']} among {region_count} regions.",
            }
        )
    low = [r for r in table if r["anomaly"] == "low"]
    if low:
        names = ", ".join(r["shop_name"] for r in low[:4])
        alerts.append(
            {
                "severity": "warning",
                "title": f"{len(low)} shop{'s' if len(low) != 1 else ''} unusually low for themselves",
                "message": names + (" …" if len(low) > 4 else ""),
            }
        )
    not_reported = [r for r in table if not r["reported"]]
    if not_reported:
        alerts.append(
            {
                "severity": "info",
                "title": f"{len(not_reported)} shop{'s' if len(not_reported) != 1 else ''} missing from this week's upload",
                "message": ", ".join(r["shop_name"] for r in not_reported[:4]) + (" …" if len(not_reported) > 4 else ""),
            }
        )
    for r in movers_down[:2]:
        if r["delta_pct"] is not None and r["delta_pct"] <= -0.15:
            alerts.append(
                {
                    "severity": "warning",
                    "title": f"{r['shop_name']} down {fmt_pct(r['delta_pct'], signed=False)}",
                    "message": f"{fmt_money(r['delta'])} against the previous week.",
                }
            )
    if not alerts:
        alerts.append(
            {
                "severity": "positive",
                "title": "No material exceptions",
                "message": "Nothing unusual for this region against the selected comparison.",
            }
        )
    return alerts


def group_rows_by_region(
    rows: list[VswtWeeklyShopMetric], region_by_shop: dict[str, UUID]
) -> dict[UUID, list[VswtWeeklyShopMetric]]:
    grouped: dict[UUID, list[VswtWeeklyShopMetric]] = defaultdict(list)
    for r in rows:
        rid = region_by_shop.get(r.shop_number)
        if rid is not None:
            grouped[rid].append(r)
    return grouped


def category_drivers(
    current: dict[str, Optional[float]], previous: dict[str, Optional[float]]
) -> list[dict[str, Any]]:
    out = []
    sales = current.get("sales_ty")
    for key, label in CATEGORY_SALES_KEYS:
        cur, prev = current.get(key), previous.get(key)
        out.append(
            {
                "key": key,
                "label": label,
                "current": cur,
                "previous": prev,
                "delta": cur - prev if cur is not None and prev is not None else None,
                "share_of_sales": cur / sales if cur is not None and sales else None,
            }
        )
    out.sort(key=lambda d: abs(d["delta"] or 0), reverse=True)
    return out


__all__ = [
    "DERIVED_DEFS",
    "HEADLINE_KEYS",
    "KPI_BY_KEY",
    "METRIC_DEFS",
    "build_region_rows",
    "build_shop_table",
    "category_drivers",
    "group_rows_by_region",
    "movers",
    "pct_delta",
    "rank_among",
    "region_alerts",
    "rollup",
    "shop_value",
    "target_attainment",
]
