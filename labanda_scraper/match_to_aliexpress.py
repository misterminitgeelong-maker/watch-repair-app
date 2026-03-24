#!/usr/bin/env python3
"""
Match Labanda movements to AliExpress listings and set purchase_cost_cents.
Uses AliExpress grouped CSV (and clean CSV for extra coverage) as cost source.
Run after: python parse_catalogue_md.py --import
"""

import csv
import json
import re
from pathlib import Path

LABANDA_JSON = Path(__file__).parent / "data" / "labanda_movements.json"
ALIEXPRESS_GROUPED = Path(__file__).parent.parent / "aliexpress_watch_movements_scraper" / "data" / "aliexpress_watch_movements_grouped.csv"
ALIEXPRESS_CLEAN = Path(__file__).parent.parent / "aliexpress_watch_movements_scraper" / "data" / "aliexpress_watch_movements_clean.csv"
APP_MOVEMENTS = Path(__file__).parent.parent / "backend" / "seed" / "watch_movements.json"

# Labanda brand -> AliExpress brand(s) for matching
LABANDA_TO_ALIEXPRESS_BRAND = {
    "ETA": ["ETA"],
    "FE": ["ETA"],
    "Swiss": ["ETA"],
    "Seiko/TMI": ["Seiko/TMI", "Seiko/Hattori/Epson"],
    "Miyota": ["Miyota"],
    "Ronda": ["Ronda"],
    "ISA": ["ISA"],
    "China": ["unknown", "ETA", "Miyota"],
}


def _to_key(brand: str, model: str) -> str:
    """Same as parse_catalogue_md._to_key for consistent lookup."""
    b = re.sub(r"[^a-z0-9]+", "_", brand.lower().replace("/", "_")).strip("_")[:20]
    m = re.sub(r"[^a-z0-9]+", "_", model.lower().replace(".", "_").replace("=", "_")).strip("_")[:40]
    return f"labanda_{b}_{m}" if b and m else ""


def _extract_price_from_url(url: str) -> float | None:
    """Extract first price from AliExpress pdp_npi URL (AUD or USD)."""
    if not url:
        return None
    for m in re.findall(r"[A-Z]{2,3}%21([\d.]+)", url):
        try:
            v = float(m)
            if 0.5 < v < 5000:
                return v
        except ValueError:
            pass
    return None


def _normalize_calibre(model: str) -> list[str]:
    """
    Return possible calibre strings to match against AliExpress.
    E.g. E955.112-D3 -> [955.112, 955112], M2025 -> [2025, m2025]
    """
    if not model or not model.strip():
        return []
    m = model.strip()
    m = re.sub(r"\s*\([^)]*\)\s*\*?\s*$", "", m).strip()
    m = re.sub(r"\s*=\s*[^=]+$", "", m).strip()
    m = re.sub(r"\s*\*+$", "", m).strip()

    # Ronda: extract calibre early before generic prefix strip (R505-D3 -> 505)
    r_match = re.match(r"^R(\d+)[-_\s]", m, re.I)
    if r_match:
        base = r_match.group(1)
    else:
        base = m
    base = re.sub(r"^RONDA\s+", "", base, flags=re.I).strip()

    # Strip ETA-style prefixes: E, EE, EF, EG, P
    base = re.sub(r"^(E{1,2}|EF|EG|P)(\d)", r"\2", base, flags=re.I)
    base = re.sub(r"^([A-Z])(\d)", r"\2", base) if re.match(r"^[A-Z]\d", base, re.I) else base

    # Strip common suffixes: -D3, -D6, -HD4, -RD4, -2H, -3H, AIG1, etc.
    base = re.sub(r"[-_](D3|D6|HD4|RD4|2H|3H|DD3|DD6)[-\dA-Z.]*\s*$", "", base, flags=re.I).strip()
    base = re.sub(r"[-_]?(BE|2H)\s*$", "", base, flags=re.I).strip()
    base = re.sub(r"\s+AIG[\dA-Z]*$", "", base, flags=re.I).strip()
    base = re.sub(r"[AFJ]$", "", base, flags=re.I).strip()

    # Miyota M-prefix: M2025 -> 2025
    if re.match(r"^M\d", base, re.I):
        base = base[1:]

    # ISA prefix
    base = re.sub(r"^ISA\s+", "", base, flags=re.I).strip()

    # Ronda fallback: R505 (no suffix) -> 505
    if re.match(r"^R\d", base, re.I) and not re.match(r"^R\d+[-_\s]", base, re.I):
        base = base[1:]
    # Seiko/Hattori H-prefix: HPC21, HVX12 -> PC21, VX12
    if re.match(r"^H[A-Z]{2}\d", base, re.I):
        base = base[1:]

    candidates = []
    core = re.sub(r"[^a-zA-Z0-9.]", "", base)
    if core:
        candidates.append(core)
    normalized = re.sub(r"[^a-z0-9]", "", base.lower())
    if normalized:
        candidates.append(normalized)

    # For dotted numbers: 955.112 and 955112
    if "." in core:
        candidates.append(core.replace(".", ""))
    if len(candidates) > 1 and "." not in candidates[0]:
        dotted = re.sub(r"(\d{3})(\d{3})", r"\1.\2", candidates[0])
        if dotted != candidates[0]:
            candidates.append(dotted)

    return list(dict.fromkeys(candidates))


def build_aliexpress_lookup() -> dict[tuple[str, str], int]:
    """(brand, calibre) -> cost_cents. Uses min price when multiple."""
    lookup = {}
    for path in [ALIEXPRESS_GROUPED, ALIEXPRESS_CLEAN]:
        if not path.exists():
            continue
        with open(path, encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for row in reader:
                brand = (row.get("brand") or "").strip()
                calibre = (row.get("calibre") or "").strip()
                if not calibre or calibre.lower() == "unknown":
                    continue
                if not brand:
                    brand = "unknown"
                cost_cents = None
                min_usd = row.get("min_price_usd")
                if min_usd and str(min_usd).strip():
                    try:
                        cost_cents = int(float(min_usd) * 100)
                    except (ValueError, TypeError):
                        pass
                if cost_cents is None and row.get("median_price_usd"):
                    try:
                        cost_cents = int(float(row["median_price_usd"]) * 100)
                    except (ValueError, TypeError):
                        pass
                if cost_cents is None:
                    sample = row.get("sample_urls") or row.get("sample_listing_url") or row.get("listing_url") or ""
                    price = _extract_price_from_url(sample)
                    if price is not None:
                        cost_cents = int(price * 100)
                if cost_cents is None and row.get("estimated_price_usd_min"):
                    try:
                        cost_cents = int(float(row["estimated_price_usd_min"]) * 100)
                    except (ValueError, TypeError):
                        pass
                if cost_cents is None and row.get("estimated_price_usd_max"):
                    try:
                        cost_cents = int(float(row["estimated_price_usd_max"]) * 100)
                    except (ValueError, TypeError):
                        pass
                if cost_cents is not None and cost_cents > 0:
                    for key in [
                        (brand.lower(), calibre.upper()),
                        (brand.lower(), calibre.upper().replace(" ", "").replace(".", "_")),
                        (brand.lower(), re.sub(r"[^A-Z0-9]", "", calibre.upper())),
                    ]:
                        if key not in lookup or cost_cents < lookup[key]:
                            lookup[key] = cost_cents
    return lookup


def main():
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--force", action="store_true", help="Overwrite existing costs")
    args = parser.parse_args()

    if not LABANDA_JSON.exists():
        print(f"Labanda data not found: {LABANDA_JSON}")
        print("Run: python parse_catalogue_md.py --import")
        return 1
    if not ALIEXPRESS_GROUPED.exists() and not ALIEXPRESS_CLEAN.exists():
        print("AliExpress data not found. Run the AliExpress scraper first.")
        return 1

    with open(LABANDA_JSON, encoding="utf-8") as f:
        labanda_data = json.load(f)
    labanda_movements = labanda_data.get("movements", [])

    lookup = build_aliexpress_lookup()
    print(f"AliExpress lookup: {len(lookup)} (brand, calibre) -> cost entries")

    with open(APP_MOVEMENTS, encoding="utf-8") as f:
        app_data = json.load(f)

    key_to_movement = {m["key"]: m for m in app_data["movements"]}
    matched = 0
    updated = []

    for lm in labanda_movements:
        brand = lm.get("brand", "")
        model = lm.get("model", "")
        app_key = _to_key(brand, model)
        if app_key not in key_to_movement:
            continue
        app_m = key_to_movement[app_key]
        if not args.force and app_m.get("purchase_cost_cents", 0) != 0:
            continue
        ae_brands = LABANDA_TO_ALIEXPRESS_BRAND.get(brand, [brand])
        candidates = _normalize_calibre(model)
        cost_cents = None
        for cb in candidates:
            cb_upper = cb.upper()
            cb_nodots = cb_upper.replace(".", "_")
            cb_compact = re.sub(r"[^A-Z0-9]", "", cb_upper)
            for cal_key in [cb_upper, cb_nodots, cb_compact]:
                for ab in ae_brands:
                    if (ab.lower(), cal_key) in lookup:
                        c = lookup[(ab.lower(), cal_key)]
                        if cost_cents is None or c < cost_cents:
                            cost_cents = c
        if cost_cents is None:
            for cb in candidates:
                cb_upper = cb.upper()
                cb_nodots = cb_upper.replace(".", "_")
                cb_compact = re.sub(r"[^A-Z0-9]", "", cb_upper)
                for cal_key in [cb_upper, cb_nodots, cb_compact]:
                    if ("unknown", cal_key) in lookup:
                        c = lookup[("unknown", cal_key)]
                        if cost_cents is None or c < cost_cents:
                            cost_cents = c
        if cost_cents is not None:
            app_m["purchase_cost_cents"] = cost_cents
            matched += 1
            updated.append(f"{lm['brand']} {lm['model']} -> {cost_cents}¢")

    with open(APP_MOVEMENTS, "w", encoding="utf-8") as f:
        json.dump(app_data, f, indent=2)

    print(f"Matched {matched} Labanda movements to AliExpress costs")
    for u in updated[:30]:
        print(f"  {u}")
    if len(updated) > 30:
        print(f"  ... and {len(updated) - 30} more")
    return 0


if __name__ == "__main__":
    exit(main())
