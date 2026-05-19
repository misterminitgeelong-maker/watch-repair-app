"""Parse Mister Minit shop rows from TSS / shop-list Excel exports."""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable

from openpyxl import load_workbook

# Default local path for the Dec 2025 TSS export (do not commit the workbook).
DEFAULT_TSS_XLSX_PATH = r"c:\Users\samme\Downloads\TSS Dec25 Report (1).xlsx"

_SHOP_HEADER_MARKERS = ("shop #", "shop#")
_SUBHEADER_MARKERS = ("raw score", "tss score")


@dataclass(frozen=True)
class MinitShopRow:
    shop_number: str
    name: str
    area: str | None
    region: str | None  # AU state code when present (VIC, NSW, …)

    @property
    def business_address(self) -> str:
        parts = [p for p in (self.name, self.area, self.region) if p]
        return ", ".join(parts)

    @property
    def state_code(self) -> str | None:
        if not self.region:
            return None
        code = self.region.strip().upper()
        if re.fullmatch(r"[A-Z]{2,3}", code):
            return code
        return None


def _cell_str(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, float) and value.is_integer():
        return str(int(value))
    return str(value).strip()


def _normalize_shop_number(raw: Any) -> str | None:
    text = _cell_str(raw)
    if not text or text.lower() in {"nan", "shop #"}:
        return None
    if re.fullmatch(r"\d+\.0", text):
        text = text[:-2]
    if not re.fullmatch(r"\d{1,10}", text):
        return None
    return text


def _find_header_row(rows: Iterable[tuple[Any, ...]]) -> int | None:
    for idx, row in enumerate(rows):
        first = _cell_str(row[0] if row else "").lower()
        if first in _SHOP_HEADER_MARKERS:
            return idx
    return None


def _row_is_subheader(row: tuple[Any, ...]) -> bool:
    joined = " ".join(_cell_str(c).lower() for c in row[:6])
    return any(m in joined for m in _SUBHEADER_MARKERS)


def parse_minit_shops_xlsx(
    path: str | Path,
    *,
    sheet_name: str | None = None,
) -> list[MinitShopRow]:
    """Load shop rows from a Minit TSS-style workbook (header row contains ``Shop #``)."""
    workbook_path = Path(path)
    wb = load_workbook(workbook_path, read_only=True, data_only=True)
    try:
        ws = wb[sheet_name] if sheet_name else wb.active
        raw_rows = list(ws.iter_rows(values_only=True))
    finally:
        wb.close()

    header_idx = _find_header_row(raw_rows)
    if header_idx is None:
        raise ValueError(f"No 'Shop #' header row found in {workbook_path}")

    headers = [_cell_str(c) for c in raw_rows[header_idx]]
    col_index = {h.lower(): i for i, h in enumerate(headers) if h}

    def col(name: str, fallback: int) -> int:
        return col_index.get(name.lower(), fallback)

    i_shop = col("shop #", 0)
    i_name = col("shop name", 1)
    i_area = col("area", 2)
    i_region = col("region", 3)

    shops: list[MinitShopRow] = []
    seen: set[str] = set()

    for row in raw_rows[header_idx + 1 :]:
        if not row or _row_is_subheader(row):
            continue
        shop_number = _normalize_shop_number(row[i_shop] if i_shop < len(row) else None)
        name = _cell_str(row[i_name] if i_name < len(row) else "")
        if not shop_number or not name:
            continue
        if shop_number in seen:
            continue
        seen.add(shop_number)
        area = _cell_str(row[i_area] if i_area < len(row) else "") or None
        region = _cell_str(row[i_region] if i_region < len(row) else "") or None
        shops.append(
            MinitShopRow(
                shop_number=shop_number,
                name=name,
                area=area,
                region=region,
            )
        )

    return shops


def tenant_slug_for_shop(shop: MinitShopRow, *, prefix: str = "minit") -> str:
    """Stable slug: minit-{shop_number} (unique, DNS-safe)."""
    return f"{prefix}-{shop.shop_number}"
