"""Load and resolve Mister Minit mobile operator seed data against TSS shop rows."""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path

from .minit_shops import MinitShopRow, tenant_slug_for_mobile_operator

DEFAULT_OPERATORS_SEED_PATH = (
    Path(__file__).resolve().parents[1] / "seed" / "minit_mobile_operators_2026.json"
)

_PHONE_RE = re.compile(r"[^\d+]+")


@dataclass(frozen=True)
class MobileOperatorSeed:
    shop_number: str
    operator_label: str
    dispatch_phone: str
    dispatch_email: str | None = None
    match_confidence: str | None = None
    match_notes: str | None = None


@dataclass(frozen=True)
class ResolvedMobileOperator:
    seed: MobileOperatorSeed
    tss: MinitShopRow
    tenant_name: str
    tenant_slug: str
    dispatch_phone: str

    @property
    def shop_number(self) -> str:
        return self.seed.shop_number


def normalize_dispatch_phone(phone: str) -> str:
    """Strip spaces/formatting; keep digits and leading +."""
    stripped = phone.strip()
    if not stripped:
        return ""
    if stripped.startswith("+"):
        return "+" + _PHONE_RE.sub("", stripped[1:])
    return _PHONE_RE.sub("", stripped)


def operator_tenant_name(label: str) -> str:
    base = label.strip()
    if not base:
        return "Mobile Services"
    if base.lower().startswith("mobile services"):
        return base
    return f"Mobile Services {base}"


def load_mobile_operators_seed(path: Path | None = None) -> list[MobileOperatorSeed]:
    seed_path = path or DEFAULT_OPERATORS_SEED_PATH
    payload = json.loads(seed_path.read_text(encoding="utf-8"))
    rows = payload.get("operators") or []
    operators: list[MobileOperatorSeed] = []
    for row in rows:
        shop_number = str(row["shop_number"]).strip()
        operators.append(
            MobileOperatorSeed(
                shop_number=shop_number,
                operator_label=str(row["operator_label"]).strip(),
                dispatch_phone=str(row["dispatch_phone"]).strip(),
                dispatch_email=(row.get("dispatch_email") or None),
                match_confidence=row.get("match_confidence"),
                match_notes=row.get("match_notes"),
            )
        )
    return operators


def index_tss_shops_by_number(shops: list[MinitShopRow]) -> dict[str, MinitShopRow]:
    return {shop.shop_number: shop for shop in shops}


def resolve_mobile_operators(
    seeds: list[MobileOperatorSeed],
    tss_by_number: dict[str, MinitShopRow],
) -> tuple[list[ResolvedMobileOperator], list[dict[str, str]]]:
    """Match seed rows to TSS metadata. Returns (resolved, errors)."""
    resolved: list[ResolvedMobileOperator] = []
    errors: list[dict[str, str]] = []
    for seed in seeds:
        tss = tss_by_number.get(seed.shop_number)
        if not tss:
            errors.append(
                {
                    "shop_number": seed.shop_number,
                    "operator_label": seed.operator_label,
                    "error": "shop_number not found in TSS export",
                }
            )
            continue
        phone = normalize_dispatch_phone(seed.dispatch_phone)
        if not phone:
            errors.append(
                {
                    "shop_number": seed.shop_number,
                    "operator_label": seed.operator_label,
                    "error": "dispatch_phone is empty after normalization",
                }
            )
            continue
        resolved.append(
            ResolvedMobileOperator(
                seed=seed,
                tss=tss,
                tenant_name=operator_tenant_name(seed.operator_label),
                tenant_slug=tenant_slug_for_mobile_operator(seed.shop_number),
                dispatch_phone=phone,
            )
        )
    return resolved, errors


def to_minit_shop_row(operator: ResolvedMobileOperator) -> MinitShopRow:
    """Build a MinitShopRow for tenant metadata (area/region from TSS)."""
    return MinitShopRow(
        shop_number=operator.shop_number,
        name=operator.tenant_name,
        area=operator.tss.area,
        region=operator.tss.region,
    )
