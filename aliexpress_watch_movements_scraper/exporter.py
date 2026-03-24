"""
Export listings to CSV and JSON.
"""

import csv
import json
import logging
from pathlib import Path

from config import DATA_DIR, RAW_CSV, CLEAN_CSV, CLEAN_JSON, GROUPED_CSV
from parser import RAW_FIELDS

logger = logging.getLogger(__name__)

CLEAN_FIELDS = [
    "source_site", "search_term", "listing_title", "listing_url",
    "seller_name", "seller_url", "price_text", "shipping_text", "orders_text",
    "rating_text", "store_rating_text", "image_url",
    "brand", "calibre", "movement_family", "movement_type", "display_type",
    "hands", "has_date", "has_day", "has_chronograph", "has_small_seconds", "has_gmt",
    "mechanical_or_quartz", "mechaquartz", "listing_kind",
    "estimated_price_usd_min", "estimated_price_usd_max",
    "seller_count_for_same_calibre", "sample_listing_url", "listing_count",
    "confidence_score", "raw_brand", "raw_calibre", "raw_type", "description_snippet",
]

GROUPED_FIELDS = [
    "brand", "calibre", "movement_type", "mechanical_or_quartz", "listing_kind_summary",
    "listing_count", "unique_seller_count", "min_price_usd", "median_price_usd", "max_price_usd",
    "representative_titles", "sample_urls", "confidence_score",
]


def _safe_csv_val(val):
    if val is None:
        return ""
    v = str(val)
    if "," in v or '"' in v or "\n" in v:
        return '"' + v.replace('"', '""') + '"'
    return v


def export_raw_csv(listings: list[dict], path: str | Path) -> None:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=RAW_FIELDS, extrasaction="ignore")
        w.writeheader()
        for row in listings:
            w.writerow({k: row.get(k, "") for k in RAW_FIELDS})
    logger.info("Exported raw CSV: %s (%d rows)", path, len(listings))


def export_clean_csv(listings: list[dict], path: str | Path) -> None:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=CLEAN_FIELDS, extrasaction="ignore")
        w.writeheader()
        for row in listings:
            w.writerow({k: row.get(k, "") for k in CLEAN_FIELDS})
    logger.info("Exported clean CSV: %s (%d rows)", path, len(listings))


def export_clean_json(listings: list[dict], path: str | Path) -> None:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    # Convert for JSON (None -> null, bool stays)
    def _jval(v):
        if v is None:
            return None
        if isinstance(v, (dict, list)):
            return v
        return v
    data = []
    for row in listings:
        d = {}
        for k in CLEAN_FIELDS:
            v = row.get(k)
            d[k] = _jval(v)
        data.append(d)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
    logger.info("Exported clean JSON: %s (%d rows)", path, len(listings))


def export_grouped_csv(grouped: list[dict], path: str | Path) -> None:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=GROUPED_FIELDS, extrasaction="ignore")
        w.writeheader()
        for row in grouped:
            w.writerow({k: row.get(k, "") for k in GROUPED_FIELDS})
    logger.info("Exported grouped CSV: %s (%d rows)", path, len(grouped))


def export_all(raw: list[dict], cleaned: list[dict], grouped: list[dict]) -> None:
    """Export all output files."""
    export_raw_csv(raw, RAW_CSV)
    export_clean_csv(cleaned, CLEAN_CSV)
    export_clean_json(cleaned, CLEAN_JSON)
    export_grouped_csv(grouped, GROUPED_CSV)
