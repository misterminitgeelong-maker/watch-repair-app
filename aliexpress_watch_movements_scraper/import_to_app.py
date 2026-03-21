#!/usr/bin/env python3
"""
Import scraped AliExpress movement data into the watch repair app's watch_movements.json.
Adds new calibres; keeps existing entries (your custom prices) unchanged.
"""

import csv
import json
import re
from pathlib import Path

SCRAPER_GROUPED = Path(__file__).parent / "data" / "aliexpress_watch_movements_grouped.csv"
APP_MOVEMENTS = Path(__file__).parent.parent / "backend" / "seed" / "watch_movements.json"


def _to_key(brand: str, calibre: str) -> str:
    """Generate movement key: miyota_2035, eta_955_112, etc."""
    b = re.sub(r"[^a-z0-9]+", "_", brand.lower().replace("/", "_").replace(".", "_")).strip("_")
    c = re.sub(r"[^a-z0-9]+", "_", calibre.lower().replace(".", "_")).strip("_")
    return f"{b}_{c}" if b and c else f"{b}_{c}".replace("__", "_").strip("_")


def _to_name(brand: str, calibre: str) -> str:
    return f"{brand} {calibre}".strip()


def main():
    if not SCRAPER_GROUPED.exists():
        print(f"Grouped CSV not found: {SCRAPER_GROUPED}")
        print("Run the scraper first: python main.py --html --html-dir data/raw_html")
        return 1

    with open(APP_MOVEMENTS, encoding="utf-8") as f:
        app_data = json.load(f)

    existing_keys = {m["key"] for m in app_data["movements"]}
    added = []

    with open(SCRAPER_GROUPED, encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            brand = (row.get("brand") or "").strip()
            calibre = (row.get("calibre") or "").strip()
            if not calibre or calibre.lower() == "unknown" or not brand or brand.lower() == "unknown":
                continue
            cost_cents = None
            try:
                min_usd = row.get("min_price_usd")
                if min_usd and str(min_usd).strip():
                    cost_cents = int(float(min_usd) * 100)
                if cost_cents is None:
                    median_usd = row.get("median_price_usd")
                    if median_usd and str(median_usd).strip():
                        cost_cents = int(float(median_usd) * 100)
                if cost_cents is None:
                    sample = row.get("sample_urls") or ""
                    for m in re.findall(r"[A-Z]{3}%21([\d.]+)", sample):
                        v = float(m)
                        if 0.5 < v < 5000:
                            cost_cents = int(v * 100)
                            break
            except (ValueError, TypeError):
                pass
            if cost_cents is None:
                cost_cents = 5000
            key = _to_key(brand, calibre)
            if not key or key in existing_keys:
                continue
            name = _to_name(brand, calibre)
            app_data["movements"].append({
                "key": key,
                "name": name,
                "purchase_cost_cents": cost_cents,
            })
            existing_keys.add(key)
            added.append(name)

    with open(APP_MOVEMENTS, "w", encoding="utf-8") as f:
        json.dump(app_data, f, indent=2)

    print(f"Imported {len(added)} new movements into {APP_MOVEMENTS}")
    for n in added[:20]:
        print(f"  + {n}")
    if len(added) > 20:
        print(f"  ... and {len(added) - 20} more")
    return 0


if __name__ == "__main__":
    exit(main())
