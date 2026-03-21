#!/usr/bin/env python3
"""
Parse the existing Labanda movements catalogue markdown and import into watch_movements.json.
Run this to immediately add all ~500 Labanda movements to the app (no live scrape needed).
You can then edit watch_movements.json to add your Labanda purchase costs for each.
"""

import json
import re
from pathlib import Path

CATALOGUE_MD = Path(__file__).parent.parent / "docs" / "labanda_movements_catalogue.md"
APP_MOVEMENTS = Path(__file__).parent.parent / "backend" / "seed" / "watch_movements.json"
OUTPUT_JSON = Path(__file__).parent / "data" / "labanda_movements.json"
OUTPUT_CSV = Path(__file__).parent / "data" / "labanda_movements.csv"

# Map section headers to brand prefix for key/name
CATEGORY_TO_BRAND = {
    "ETA & OTHER SWISS": "ETA",
    "FRANCE EBAUCHES": "FE",
    "SEIKO, HATTORI, TMI & EPSON": "Seiko/TMI",
    "ISA": "ISA",
    "CITIZEN & MIYOTA": "Miyota",
    "RONDA & HARLEY": "Ronda",
    "SWISS EBAUCHES": "Swiss",
    "CHINA": "China",
}


def _to_key(brand: str, model: str) -> str:
    """Generate movement key. Uses labanda_ prefix to avoid clashes with existing app keys."""
    b = re.sub(r"[^a-z0-9]+", "_", brand.lower().replace("/", "_")).strip("_")[:20]
    m = re.sub(r"[^a-z0-9]+", "_", model.lower().replace(".", "_").replace("=", "_")).strip("_")[:40]
    return f"labanda_{b}_{m}" if b and m else ""


def parse_catalogue(md_path: Path) -> list[dict]:
    """Parse the markdown catalogue into movement records."""
    text = md_path.read_text(encoding="utf-8")
    movements = []
    current_brand = ""
    in_table = False
    for line in text.splitlines():
        if line.startswith("## "):
            section = line[3:].strip()
            current_brand = CATEGORY_TO_BRAND.get(section, section.split("&")[0].strip())
            in_table = False
            continue
        if line.startswith("| Model |"):
            in_table = True
            continue
        if in_table and line.startswith("|") and not line.startswith("|-------"):
            parts = [p.strip() for p in line.split("|")[1:-1]]
            if len(parts) >= 1 and parts[0]:
                model_raw = parts[0]
                model = re.sub(r"\s*\([^)]*\)\s*$", "", model_raw).strip()
                model = re.sub(r"\s*=\s*[^=]+$", "", model).strip()
                model = model.strip()
                if model and not model.startswith("-"):
                    size = parts[1] if len(parts) > 1 else ""
                    height = parts[2] if len(parts) > 2 else ""
                    power = parts[3] if len(parts) > 3 else ""
                    movements.append({
                        "brand": current_brand,
                        "model": model,
                        "size": size,
                        "height": height,
                        "power": power,
                        "source": "labanda",
                    })
        if line.strip() == "---":
            in_table = False
    return movements


def import_to_app(movements: list[dict], merge: bool = True) -> int:
    """Merge Labanda movements into watch_movements.json. Returns count added."""
    with open(APP_MOVEMENTS, encoding="utf-8") as f:
        app_data = json.load(f)
    existing_keys = {m["key"] for m in app_data["movements"]}
    added = 0
    for m in movements:
        key = _to_key(m["brand"], m["model"])
        if not key or key in existing_keys:
            continue
        name = m["model"] if m["model"].upper().startswith(m["brand"].upper()) else f"{m['brand']} {m['model']}"
        app_data["movements"].append({
            "key": key,
            "name": name,
            "purchase_cost_cents": 0,
        })
        existing_keys.add(key)
        added += 1
    with open(APP_MOVEMENTS, "w", encoding="utf-8") as f:
        json.dump(app_data, f, indent=2)
    return added


def main():
    import argparse
    parser = argparse.ArgumentParser(description="Parse Labanda catalogue and optionally import to app")
    parser.add_argument("--import", dest="do_import", action="store_true", help="Merge into watch_movements.json")
    parser.add_argument("--no-import", action="store_true", help="Only parse and save to data/ (default)")
    args = parser.parse_args()
    do_import = args.do_import and not args.no_import

    if not CATALOGUE_MD.exists():
        print(f" Catalogue not found: {CATALOGUE_MD}")
        return 1

    movements = parse_catalogue(CATALOGUE_MD)
    print(f"Parsed {len(movements)} movements from {CATALOGUE_MD.name}")

    OUTPUT_JSON.parent.mkdir(parents=True, exist_ok=True)
    with open(OUTPUT_JSON, "w", encoding="utf-8") as f:
        json.dump({"source": "labanda.com.au", "movements": movements}, f, indent=2)
    print(f"Saved to {OUTPUT_JSON}")

    import csv
    with open(OUTPUT_CSV, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=["brand", "model", "size", "height", "power", "source"])
        w.writeheader()
        w.writerows(movements)
    print(f"Saved to {OUTPUT_CSV}")

    if do_import:
        added = import_to_app(movements)
        print(f"Imported {added} new movements into {APP_MOVEMENTS}")
        print("Edit purchase_cost_cents for each to add your Labanda prices.")
    else:
        print("Run with --import to merge into watch_movements.json")

    return 0


if __name__ == "__main__":
    exit(main())
