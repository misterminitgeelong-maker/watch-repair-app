"""Turn VSWT comparison numbers into signals and sentences.

Two things live here so the shop cockpit, the region cockpit and the weekly
emails all say the same thing about the same numbers:

* **Anomalies** — a value is judged against that shop's (or region's) own
  recent distribution, not a fixed percentage. A steady $40k shop dropping 6%
  is unusual; a volatile $8k shop dropping 12% may not be.
* **Narrative** — a short, deterministic paragraph built from the sales
  bridge, the category drivers and the anomalies. Templates, not a model, so
  the numbers in the prose are always the numbers on the page.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Any, Optional

#: Fewer prior points than this and a z-score is noise, not a signal.
MIN_BASELINE_POINTS = 6
#: |z| at or above this is an anomaly; between WARN and this, a watch item.
ANOMALY_Z = 2.0
WARN_Z = 1.5


@dataclass(frozen=True)
class Baseline:
    mean: Optional[float]
    stdev: Optional[float]
    count: int
    zscore: Optional[float]
    #: "high" | "low" | None
    anomaly: Optional[str]
    #: "high" | "low" | None — a softer signal (|z| >= WARN_Z)
    watch: Optional[str]


def baseline_for(current: Optional[float], prior: list[Optional[float]]) -> Baseline:
    """Sample mean/stdev of the prior values and where ``current`` sits in them."""
    points = [v for v in prior if v is not None]
    n = len(points)
    if current is None or n < MIN_BASELINE_POINTS:
        return Baseline(mean=_mean(points), stdev=None, count=n, zscore=None, anomaly=None, watch=None)
    mean = sum(points) / n
    variance = sum((v - mean) ** 2 for v in points) / (n - 1)
    stdev = math.sqrt(variance)
    if stdev <= 0:
        z = 0.0 if current == mean else (math.inf if current > mean else -math.inf)
    else:
        z = (current - mean) / stdev
    if math.isinf(z):
        z = 4.0 if z > 0 else -4.0
    anomaly = "high" if z >= ANOMALY_Z else "low" if z <= -ANOMALY_Z else None
    watch = None if anomaly else ("high" if z >= WARN_Z else "low" if z <= -WARN_Z else None)
    return Baseline(mean=mean, stdev=stdev, count=n, zscore=round(z, 2), anomaly=anomaly, watch=watch)


def _mean(values: list[float]) -> Optional[float]:
    return sum(values) / len(values) if values else None


# ── formatting ────────────────────────────────────────────────────────────────


def fmt_money(value: Optional[float]) -> str:
    if value is None:
        return "—"
    return f"-${abs(value):,.0f}" if value < 0 else f"${value:,.0f}"


def fmt_money_signed(value: Optional[float]) -> str:
    if value is None:
        return "—"
    return f"+{fmt_money(value)}" if value > 0 else fmt_money(value)


def fmt_count(value: Optional[float]) -> str:
    if value is None:
        return "—"
    return f"{value:,.0f}"


def fmt_pct(value: Optional[float], *, signed: bool = True) -> str:
    if value is None:
        return "—"
    return f"{value * 100:+.1f}%" if signed else f"{abs(value) * 100:.1f}%"


def _direction(delta: Optional[float]) -> str:
    if delta is None:
        return "held"
    if delta > 0:
        return "up"
    if delta < 0:
        return "down"
    return "flat"


# ── shop narrative ────────────────────────────────────────────────────────────


def build_shop_narrative(
    *,
    shop_name: str,
    week: int,
    comparison_label: str,
    sales: dict[str, Any],
    customers: dict[str, Any],
    avg_sale: dict[str, Any],
    bridge: dict[str, Optional[float]],
    category_drivers: list[dict[str, Any]],
    anomalies: list[dict[str, Any]],
    target_variance: Optional[float],
    excluded_note: Optional[str] = None,
) -> str:
    """One paragraph a manager can read instead of the table.

    Every number is taken from the same rows the cockpit renders, so the
    prose and the tiles can never disagree.
    """
    parts: list[str] = []
    delta_pct = sales.get("delta_pct")
    current = sales.get("current")
    if current is None:
        return f"No sales figure was reported for {shop_name} in week {week}."

    if delta_pct is None:
        parts.append(f"{shop_name} took {fmt_money(current)} in week {week}; there is no {comparison_label} figure to compare against.")
    else:
        parts.append(
            f"{shop_name} took {fmt_money(current)} in week {week}, {fmt_pct(delta_pct, signed=False)} "
            f"{'above' if delta_pct > 0 else 'below' if delta_pct < 0 else 'in line with'} the {comparison_label}."
        )

    volume = bridge.get("customer_volume_effect")
    value = bridge.get("average_sale_effect")
    cust_delta = customers.get("delta")
    avg_delta = avg_sale.get("delta")
    if volume is not None and value is not None and (abs(volume) > 1 or abs(value) > 1):
        if abs(volume) >= abs(value) * 1.5:
            parts.append(
                f"That is mostly a customer story: {fmt_count(abs(cust_delta) if cust_delta is not None else None)} "
                f"{'more' if (cust_delta or 0) >= 0 else 'fewer'} customers came through, worth about {fmt_money(abs(volume))}, "
                f"while the average sale {'rose' if (avg_delta or 0) > 0 else 'fell' if (avg_delta or 0) < 0 else 'held'}"
                f"{f' by {fmt_money(abs(avg_delta))}' if avg_delta else ''}."
            )
        elif abs(value) >= abs(volume) * 1.5:
            parts.append(
                f"Customer count {'held' if abs(cust_delta or 0) < 1 else ('grew' if (cust_delta or 0) > 0 else 'slipped')}, "
                f"but the average sale {'rose' if (avg_delta or 0) > 0 else 'fell'} by {fmt_money(abs(avg_delta or 0))} "
                f"— about {fmt_money(abs(value))} of the movement."
            )
        elif (volume > 0) == (value > 0):
            parts.append(
                f"Customer volume ({fmt_money_signed(volume)}) and average sale ({fmt_money_signed(value)}) "
                f"moved together."
            )
        else:
            parts.append(
                f"Customer volume ({fmt_money_signed(volume)}) and average sale ({fmt_money_signed(value)}) "
                f"largely offset each other."
            )

    with_delta = [d for d in category_drivers if d.get("delta") is not None]
    if with_delta:
        weakest = min(with_delta, key=lambda d: d["delta"])
        strongest = max(with_delta, key=lambda d: d["delta"])
        if weakest["delta"] < 0 and (delta_pct or 0) <= 0:
            share = weakest.get("share_of_sales")
            parts.append(
                f"{weakest['label']} was the largest drag at {fmt_money(weakest['delta'])}"
                f"{f' ({share * 100:.0f}% of sales)' if share is not None else ''}."
            )
        elif strongest["delta"] > 0:
            parts.append(f"{strongest['label']} led, adding {fmt_money(strongest['delta'])}.")

    if anomalies:
        top = anomalies[0]
        parts.append(
            f"{top['label']} is unusual for this shop: {top['direction']} at {top['z']:+.1f} standard deviations "
            f"from its {top['weeks']}-week norm."
        )

    if target_variance is not None:
        parts.append(
            f"Against target the shop is {fmt_money(abs(target_variance))} {'ahead' if target_variance >= 0 else 'behind'}."
        )

    if excluded_note:
        parts.append(excluded_note)

    return " ".join(parts)


# ── region narrative ──────────────────────────────────────────────────────────


def build_region_narrative(
    *,
    region_name: str,
    week: int,
    comparison_label: str,
    sales: dict[str, Any],
    customers: dict[str, Any],
    shop_count: int,
    region_rank: Optional[int],
    region_count: int,
    movers_up: list[dict[str, Any]],
    movers_down: list[dict[str, Any]],
    anomalies: list[dict[str, Any]],
    target_attainment: dict[str, Any],
) -> str:
    parts: list[str] = []
    current = sales.get("current")
    delta_pct = sales.get("delta_pct")
    if current is None:
        return f"No sales were reported for {region_name} in week {week}."
    parts.append(
        f"{region_name}'s {shop_count} shops took {fmt_money(current)} in week {week}"
        + (
            f", {fmt_pct(delta_pct, signed=False)} {'above' if delta_pct > 0 else 'below' if delta_pct < 0 else 'in line with'} the {comparison_label}"
            if delta_pct is not None
            else ""
        )
        + (f", ranking #{region_rank} of {region_count} regions." if region_rank else ".")
    )
    cust_delta = customers.get("delta_pct")
    if cust_delta is not None and delta_pct is not None and abs(cust_delta - delta_pct) > 0.03:
        parts.append(
            f"Customer count moved {fmt_pct(cust_delta)}, so "
            + ("average sale did the rest of the work." if delta_pct > cust_delta else "average sale gave some back.")
        )
    if movers_down:
        worst = movers_down[0]
        parts.append(
            f"{worst['shop_name']} moved most against the trend at {fmt_pct(worst['delta_pct'])}"
            + (f" ({fmt_money(worst['delta'])})." if worst.get("delta") is not None else ".")
        )
    if movers_up:
        best = movers_up[0]
        parts.append(f"{best['shop_name']} led the region at {fmt_pct(best['delta_pct'])}.")
    if anomalies:
        names = ", ".join(a["shop_name"] for a in anomalies[:3])
        parts.append(
            f"{len(anomalies)} shop{'s' if len(anomalies) != 1 else ''} posted an unusual week for {'themselves' if len(anomalies) != 1 else 'itself'}: {names}."
        )
    met = target_attainment.get("shops_met")
    with_target = target_attainment.get("shops_with_target")
    if with_target:
        parts.append(f"{met} of {with_target} shops with a sales target met it.")
    return " ".join(parts)


# ── alerts ────────────────────────────────────────────────────────────────────


def shop_alerts(
    *,
    sales: dict[str, Any],
    sales_baseline: Baseline,
    sales_history: list[Optional[float]],
    anomalies: list[dict[str, Any]],
    category_drivers: list[dict[str, Any]],
) -> list[dict[str, str]]:
    """Exceptions ranked by how unusual they are for *this* shop."""
    alerts: list[dict[str, str]] = []
    z = sales_baseline.zscore
    delta_pct = sales.get("delta_pct")
    if z is not None and z <= -ANOMALY_Z:
        alerts.append(
            {
                "severity": "critical",
                "title": "Sales unusually low for this shop",
                "message": (
                    f"{z:+.1f} standard deviations below the shop's {sales_baseline.count}-week norm"
                    f"{f' ({fmt_pct(delta_pct)} vs baseline)' if delta_pct is not None else ''}."
                ),
            }
        )
    elif z is not None and z <= -WARN_Z:
        alerts.append(
            {
                "severity": "warning",
                "title": "Sales softer than this shop's norm",
                "message": f"{z:+.1f} standard deviations below the {sales_baseline.count}-week norm.",
            }
        )
    elif z is None and delta_pct is not None and delta_pct <= -0.10:
        # Not enough history for a z-score yet: fall back to the plain threshold.
        alerts.append(
            {
                "severity": "warning",
                "title": "Sales below comparison",
                "message": f"Sales are {fmt_pct(delta_pct, signed=False)} below the selected baseline (not enough history for a norm yet).",
            }
        )
    if z is not None and z >= ANOMALY_Z:
        alerts.append(
            {
                "severity": "positive",
                "title": "Sales unusually strong for this shop",
                "message": f"{z:+.1f} standard deviations above the shop's {sales_baseline.count}-week norm.",
            }
        )

    if sales.get("rank_change") is not None and sales["rank_change"] <= -10:
        alerts.append(
            {
                "severity": "warning",
                "title": "Regional rank fell",
                "message": f"Sales rank dropped {abs(sales['rank_change'])} places from the previous week.",
            }
        )
    if sales.get("target_variance") is not None and sales["target_variance"] < 0:
        alerts.append(
            {
                "severity": "warning",
                "title": "Sales target at risk",
                "message": f"The shop is {fmt_money(abs(sales['target_variance']))} below its weekly sales target.",
            }
        )

    present = [v for v in sales_history if v is not None]
    if len(present) >= 3 and all(present[i] < present[i - 1] for i in range(1, len(present))):
        alerts.append(
            {
                "severity": "critical",
                "title": "Three-week sales decline",
                "message": "Sales have fallen in each of the last three reported weeks.",
            }
        )

    for item in anomalies[:3]:
        if item["key"] == "sales_ty":
            continue
        alerts.append(
            {
                "severity": "warning" if item["direction"] == "low" else "info",
                "title": f"{item['label']} {'unusually low' if item['direction'] == 'low' else 'unusually high'}",
                "message": f"{item['z']:+.1f} standard deviations from the shop's {item['weeks']}-week norm.",
            }
        )

    with_delta = [d for d in category_drivers if d.get("delta") is not None]
    if with_delta:
        weakest = min(with_delta, key=lambda d: d["delta"])
        strongest = max(with_delta, key=lambda d: d["delta"])
        if weakest["delta"] < 0:
            alerts.append(
                {
                    "severity": "info",
                    "title": f"{weakest['label']} is the largest drag",
                    "message": f"Category sales fell {fmt_money(abs(weakest['delta']))} from the previous week.",
                }
            )
        if strongest["delta"] > 0:
            alerts.append(
                {
                    "severity": "positive",
                    "title": f"{strongest['label']} led growth",
                    "message": f"Category sales increased {fmt_money(strongest['delta'])} from the previous week.",
                }
            )
    if not alerts:
        alerts.append(
            {
                "severity": "positive",
                "title": "No material exceptions",
                "message": "Nothing unusual for this shop against the selected comparison.",
            }
        )
    return alerts
