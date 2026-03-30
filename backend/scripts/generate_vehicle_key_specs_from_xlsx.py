"""
Build backend/seed/vehicle_key_specs.json from Locksmith Master Database Vehicle_Systems sheet.

Usage:
  python scripts/generate_vehicle_key_specs_from_xlsx.py --input path/to/Locksmith_Master_Database_v9_populated.xlsx
"""
from __future__ import annotations

import argparse
import json
import re
from pathlib import Path

import pandas as pd

_YEAR_RANGE = re.compile(r"^\s*(\d{4})\s*[\u2013\-\u2014]\s*(\d{4})\s*$")
_YEAR_SINGLE = re.compile(r"^\s*(\d{4})\s*$")


def parse_year_range(cell) -> tuple[int | None, int | None]:
    if cell is None or (isinstance(cell, float) and pd.isna(cell)):
        return None, None
    s = str(cell).strip()
    m = _YEAR_RANGE.match(s)
    if m:
        a, b = int(m.group(1)), int(m.group(2))
        return (a, b) if a <= b else (b, a)
    m = _YEAR_SINGLE.match(s)
    if m:
        y = int(m.group(1))
        return y, y
    return None, None


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--input", required=True)
    ap.add_argument(
        "--output",
        default=str(Path(__file__).resolve().parent.parent / "seed" / "vehicle_key_specs.json"),
    )
    args = ap.parse_args()
    in_path = Path(args.input)
    out_path = Path(args.output)

    df = pd.read_excel(in_path, sheet_name="Vehicle_Systems")
    entries: list[dict] = []
    for _, row in df.iterrows():
        make = row.get("Make")
        model = row.get("Model")
        if pd.isna(make) or pd.isna(model):
            continue
        make_s = str(make).strip()
        model_s = str(model).strip()
        variant = row.get("Variant / Platform")
        variant_s = str(variant).strip() if pd.notna(variant) else ""
        ylabel = row.get("Years")
        yf, yt = parse_year_range(ylabel)

        def cell_str(k: str) -> str | None:
            v = row.get(k)
            if v is None or (isinstance(v, float) and pd.isna(v)):
                return None
            t = str(v).strip()
            return t or None

        entries.append(
            {
                "make": make_s,
                "model": model_s,
                "variant": variant_s or None,
                "years_label": str(ylabel).strip() if pd.notna(ylabel) else None,
                "year_from": yf,
                "year_to": yt,
                "region": cell_str("Region / Market"),
                "immobiliser_family": cell_str("Immobiliser Family"),
                "transponder_system": cell_str("Transponder / System"),
                "key_type": cell_str("Key Type"),
                "start_type": cell_str("Start Type"),
                "akl_complexity": cell_str("AKL Complexity"),
                "likely_method": cell_str("Likely Method"),
                "typical_notes": cell_str("Typical Notes"),
            }
        )

    out = {
        "version": 1,
        "source_sheet": "Vehicle_Systems",
        "entry_count": len(entries),
        "entries": entries,
    }
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(out, f, indent=2, ensure_ascii=False)
        f.write("\n")
    print(f"Wrote {out_path} ({len(entries)} entries)")


if __name__ == "__main__":
    main()
