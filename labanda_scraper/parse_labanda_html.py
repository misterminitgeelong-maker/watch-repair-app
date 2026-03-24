#!/usr/bin/env python3
"""
Parse Labanda category HTML (from scraper) into movement records with prices.
Output: labanda_movements_from_html.json compatible with parse_catalogue_md --import format.
"""

import json
import re
from pathlib import Path

from bs4 import BeautifulSoup

DATA_DIR = Path(__file__).parent / "data"
RAW_HTML_DIR = DATA_DIR / "raw_html"
OUTPUT_JSON = DATA_DIR / "labanda_movements_from_html.json"

# Category slug (from filename) -> brand for app
SLUG_TO_BRAND = {
    "eta": "ETA",
    "france_ebauches": "FE",
    "hattori": "Seiko/TMI",
    "isa": "ISA",
    "citizen_and_miyota": "Miyota",
    "ronda": "Ronda",
    "swiss_ebauches": "Swiss Ebauches",
    "china": "China",
}


def _parse_price(text: str) -> float | None:
    if not text:
        return None
    m = re.search(r"\$?\s*([\d,]+\.?\d*)", text.replace(",", ""))
    if m:
        try:
            v = float(m.group(1))
            return v if v >= 0 else None
        except ValueError:
            pass
    return None


def parse_category_html(html: str, category_slug: str) -> list[dict]:
    """Extract movements from a Labanda category page HTML."""
    soup = BeautifulSoup(html, "lxml")
    rows = soup.select("table.views-table tbody tr.nostyle")
    movements = []
    brand = SLUG_TO_BRAND.get(category_slug, category_slug.replace("_", " ").title())

    for tr in rows:
        td = tr.select_one("td.views-field.views-field-nothing")
        if not td:
            continue

        # Model: h2 in div.sku
        h2 = td.select_one("div.clearfix.field-label.sku h2")
        model = h2.get_text(strip=True) if h2 else ""

        # Price: div.field-name-commerce-price .field-item
        price_el = td.select_one("div.field-name-commerce-price .field-item")
        price_text = price_el.get_text(strip=True) if price_el else ""
        price_usd = _parse_price(price_text)
        purchase_cost_cents = int(price_usd * 100) if price_usd and price_usd > 0 else None

        # Size, Height, Power, Notes
        size = height = power = notes = ""
        for div in td.select("div.clearfix"):
            lbl = div.select_one("span.field-label")
            cnt = div.select_one("span.field-content")
            if lbl and cnt:
                l = lbl.get_text(strip=True).rstrip(":")
                v = cnt.get_text(strip=True)
                if l == "Size":
                    size = v
                elif l == "Height":
                    height = v
                elif l == "Power":
                    power = v
                elif l == "Notes":
                    notes = v

        if not model:
            continue

        movements.append({
            "brand": brand,
            "model": model,
            "size": size,
            "height": height,
            "power": power,
            "notes": notes,
            "purchase_cost_cents": purchase_cost_cents,
            "source": "labanda_html",
        })

    return movements


def parse_all_html(html_dir: Path) -> list[dict]:
    """Parse all category HTML files."""
    all_movements = []
    seen = set()

    # Category files: labanda_eta.html, labanda_eta_p1.html, labanda_hattori.html, etc.
    for path in sorted(html_dir.glob("labanda_*.html")):
        if "movements.html" in path.name and "labanda_movements.html" == path.name:
            continue  # Skip hub page
        stem = path.stem
        if stem.startswith("labanda_movements"):
            continue
        # labanda_eta, labanda_eta_p1 -> eta
        slug = stem.replace("labanda_", "").replace("_p1", "").replace("_p2", "").replace("_p3", "")
        slug = re.sub(r"_p\d+$", "", slug)

        html = path.read_text(encoding="utf-8")
        items = parse_category_html(html, slug)
        for m in items:
            key = (m["brand"], m["model"])
            if key in seen:
                continue
            seen.add(key)
            all_movements.append(m)

    return all_movements


APP_MOVEMENTS = Path(__file__).parent.parent / "backend" / "seed" / "watch_movements.json"


def _to_key(brand: str, model: str) -> str:
    b = re.sub(r"[^a-z0-9]+", "_", brand.lower().replace("/", "_")).strip("_")[:20]
    m = re.sub(r"[^a-z0-9]+", "_", model.lower().replace(".", "_").replace("=", "_")).strip("_")[:40]
    return f"labanda_{b}_{m}" if b and m else ""


def _normalize_model_for_match(model: str) -> str:
    """Simplify model for matching (e.g. 'E251.242-RD4 (Phase Out)' -> '251.242')."""
    m = re.sub(r"\s*\([^)]*\)\s*$", "", model).strip()
    m = re.sub(r"\s*-\s*Special Order\s*$", "", m, flags=re.I).strip()
    m = re.sub(r"^E", "", m, flags=re.I)
    return m.strip()


def import_to_app(movements: list[dict]) -> tuple[int, int]:
    """Merge into watch_movements.json. Update prices for existing, add new. Returns (added, updated)."""
    with open(APP_MOVEMENTS, encoding="utf-8") as f:
        app_data = json.load(f)
    key_to_idx = {m["key"]: i for i, m in enumerate(app_data["movements"])}
    added = updated = 0
    for m in movements:
        key = _to_key(m["brand"], m["model"])
        if not key:
            continue
        cost = m.get("purchase_cost_cents")
        if key in key_to_idx:
            idx = key_to_idx[key]
            if cost is not None and cost > 0:
                app_data["movements"][idx]["purchase_cost_cents"] = cost
                updated += 1
        else:
            name = m["model"] if m["model"].upper().startswith(m["brand"].upper()) else f"{m['brand']} {m['model']}"
            app_data["movements"].append({
                "key": key,
                "name": name,
                "purchase_cost_cents": cost if cost else 0,
            })
            key_to_idx[key] = len(app_data["movements"]) - 1
            added += 1
    with open(APP_MOVEMENTS, "w", encoding="utf-8") as f:
        json.dump(app_data, f, indent=2)
    return added, updated


def main():
    import argparse
    p = argparse.ArgumentParser()
    p.add_argument("--html-dir", default=RAW_HTML_DIR, type=Path)
    p.add_argument("--output", default=OUTPUT_JSON, type=Path)
    p.add_argument("--import", dest="do_import", action="store_true", help="Merge into watch_movements.json + update prices")
    args = p.parse_args()

    movements = parse_all_html(args.html_dir)
    out = {"source": "labanda_html", "movements": movements}
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(out, indent=2), encoding="utf-8")
    with_price = sum(1 for m in movements if m.get("purchase_cost_cents"))
    print(f"Parsed {len(movements)} movements ({with_price} with prices) -> {args.output}")

    if args.do_import:
        added, updated = import_to_app(movements)
        print(f"Imported: {added} new, {updated} prices updated in {APP_MOVEMENTS}")


if __name__ == "__main__":
    main()
