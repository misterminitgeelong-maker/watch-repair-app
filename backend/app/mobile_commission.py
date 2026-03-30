"""Configurable Mobile Services (auto_key) technician commission rules and period reporting."""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any, Optional
from uuid import UUID

# Basis points: 3000 = 30%, 5000 = 50%
DEFAULT_RATES_BP: dict[str, int] = {
    "shop_referred": 3000,
    "tech_sourced": 5000,
}

DEFAULT_LABELS: dict[str, str] = {
    "shop_referred": "Shop / referred work",
    "tech_sourced": "Tech sourced (own lead)",
}

DEFAULT_ELIGIBLE_STATUSES = ("completed", "collected")


def default_mobile_commission_rules_json() -> str:
    """JSON string used when enabling commission for a new technician (30% / 50%, $360 retainer)."""
    payload = {
        "enabled": True,
        "retainer_cents_per_period": 36_000,
        "revenue_basis": "invoice_total",
        "eligible_job_statuses": list(DEFAULT_ELIGIBLE_STATUSES),
        "rates_bp": dict(DEFAULT_RATES_BP),
        "labels": dict(DEFAULT_LABELS),
    }
    return json.dumps(payload, separators=(",", ":"))


def _coerce_rates_bp(raw: Any) -> dict[str, int]:
    if not isinstance(raw, dict):
        return dict(DEFAULT_RATES_BP)
    out: dict[str, int] = {}
    for k, v in raw.items():
        key = str(k).strip()
        if not key or len(key) > 64:
            continue
        try:
            bp = int(v)
        except (TypeError, ValueError):
            continue
        bp = max(0, min(bp, 100_000))
        out[key] = bp
    for dk, dv in DEFAULT_RATES_BP.items():
        out.setdefault(dk, dv)
    return out


def _coerce_statuses(raw: Any) -> list[str]:
    if not isinstance(raw, list):
        return list(DEFAULT_ELIGIBLE_STATUSES)
    out: list[str] = []
    for x in raw:
        s = str(x).strip().lower()
        if s and s not in out:
            out.append(s)
    return out if out else list(DEFAULT_ELIGIBLE_STATUSES)


def parse_mobile_commission_rules(raw: str | None) -> dict[str, Any] | None:
    """Return normalized rules dict or None if unset / invalid JSON."""
    if raw is None or not str(raw).strip():
        return None
    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        return None
    if not isinstance(data, dict):
        return None
    return normalize_mobile_commission_rules(data)


def normalize_mobile_commission_rules(data: dict[str, Any]) -> dict[str, Any]:
    enabled = bool(data.get("enabled", False))
    try:
        retainer = int(data.get("retainer_cents_per_period", 0))
    except (TypeError, ValueError):
        retainer = 0
    retainer = max(0, retainer)
    basis = str(data.get("revenue_basis", "invoice_total")).strip() or "invoice_total"
    if basis not in ("invoice_total",):
        basis = "invoice_total"
    labels_in = data.get("labels") if isinstance(data.get("labels"), dict) else {}
    labels: dict[str, str] = {**DEFAULT_LABELS}
    for lk, lv in labels_in.items():
        k = str(lk).strip()
        if k and isinstance(lv, str) and lv.strip():
            labels[k] = lv.strip()[:120]
    return {
        "enabled": enabled,
        "retainer_cents_per_period": retainer,
        "revenue_basis": basis,
        "eligible_job_statuses": _coerce_statuses(data.get("eligible_job_statuses")),
        "rates_bp": _coerce_rates_bp(data.get("rates_bp")),
        "labels": labels,
    }


def serialize_rules_for_storage(rules: dict[str, Any]) -> str:
    normalized = normalize_mobile_commission_rules(rules)
    return json.dumps(normalized, separators=(",", ":"))


def rate_for_lead_source(rules: dict[str, Any], lead_source: Optional[str]) -> int:
    rates: dict[str, int] = rules.get("rates_bp") or {}
    key = (lead_source or "shop_referred").strip() or "shop_referred"
    if key in rates:
        return int(rates[key])
    return int(rates.get("shop_referred", 0))


@dataclass
class CommissionLine:
    job_id: UUID
    job_number: str
    invoice_id: UUID
    revenue_cents: int
    lead_source: str
    rate_bp: int
    commission_cents: int
    job_status: str


def commission_for_period_lines(
    *,
    rules: dict[str, Any],
    lines_data: list[tuple[UUID, str, UUID, int, str, str]],
) -> tuple[int, list[CommissionLine]]:
    """
    lines_data: (job_id, job_number, invoice_id, revenue_cents, lead_source, job_status)
    """
    commission_lines: list[CommissionLine] = []
    total_raw = 0
    for job_id, job_number, inv_id, revenue_cents, lead_source, job_status in lines_data:
        if revenue_cents <= 0:
            continue
        bp = rate_for_lead_source(rules, lead_source)
        comm = int(revenue_cents * bp / 10_000)
        total_raw += comm
        commission_lines.append(
            CommissionLine(
                job_id=job_id,
                job_number=job_number,
                invoice_id=inv_id,
                revenue_cents=revenue_cents,
                lead_source=lead_source,
                rate_bp=bp,
                commission_cents=comm,
                job_status=job_status,
            )
        )
    return total_raw, commission_lines
