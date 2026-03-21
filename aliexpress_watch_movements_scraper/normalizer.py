"""
Clean, classify, normalize, and deduplicate raw listings.
Extracts brand/calibre, classifies listing_kind and movement_type.
"""

import logging
import re
from collections import defaultdict

from config import PRICE_BUCKET_USD

logger = logging.getLogger(__name__)

# Brand normalization: alias -> canonical
BRAND_ALIASES = {
    "tmi": "Seiko/TMI",
    "seiko instruments": "Seiko/TMI",
    "sii": "Seiko/TMI",
    "seiko": "Seiko/TMI",
    "hattori": "Seiko/Hattori/Epson",
    "s. epson": "Seiko/Hattori/Epson",
    "epson": "Seiko/Hattori/Epson",
    "citizen": "Miyota",
    "miyota": "Miyota",
    "ronda": "Ronda",
    "eta": "ETA",
    "isa": "ISA",
}

# Calibre formatting patterns: (regex, replacement)
CALIBRE_NORMALIZE = [
    (r"\b955\s*112\b", "955.112"),
    (r"\b955\s*412\b", "955.412"),
    (r"\bOS\s*[- ]?\s*10\b", "OS10"),
    (r"\bOS\s*[- ]?\s*20\b", "OS20"),
    (r"\bVK\s*[- ]?\s*63\b", "VK63"),
    (r"\bVK\s*[- ]?\s*64\b", "VK64"),
    (r"\bVX\s*[- ]?\s*12\b", "VX12"),
    (r"\bVX\s*[- ]?\s*32\b", "VX32"),
    (r"\bVD\s*[- ]?\s*53\b", "VD53"),
    (r"\bVD\s*[- ]?\s*54\b", "VD54"),
    (r"\bPC\s*[- ]?\s*21\b", "PC21"),
    (r"\bPC\s*[- ]?\s*32\b", "PC32"),
    (r"\b955112\b", "955.112"),
    (r"\b955412\b", "955.412"),
]

# Mechaquartz calibres (chronograph hybrids)
MECHAQUARTZ_CALIBRES = {"VK63", "VK64", "VK23", "VK43", "7T92", "7T62"}

# Quartz keywords
QUARTZ_KEYWORDS = ["quartz", "crystal", "battery", "pc21", "pc32", "vx12", "vx32", "vd53", "vd54", "955", "ronda", "miyota", "os10", "os20", "hattori", "sl68", "pe50", "isa"]

# Mechanical keywords
MECHANICAL_KEYWORDS = ["mechanical", "automatic", "manual", "hand wind", "seiko nh", "eta 2824", "eta 2892", "miyota 8", "caliber"]

# Full watch indicators (suggest watch_with_movement)
WATCH_INDICATORS = ["watch", "wristwatch", "wrist watch", "men's watch", "women's watch", "ladies watch", "complete watch", "full watch", "whole watch", "ready to wear"]

# Bare movement indicators
BARE_INDICATORS = ["movement only", "bare movement", "loose movement", "replacement movement", "spare movement", "mechanism only", "calibre only", "module only", "no case", "without case", "without dial"]


def _normalize_calibre(text: str) -> str:
    if not text:
        return ""
    t = text.upper().strip()
    for pat, repl in CALIBRE_NORMALIZE:
        t = re.sub(pat, repl, t, flags=re.IGNORECASE)
    return t


def _extract_calibre_from_title(title: str) -> str:
    """Extract calibre-like tokens from title (e.g. 955.112, VK63, PC21)."""
    if not title:
        return ""
    # Common patterns
    patterns = [
        r"\b(955\.112|955\.412)\b",
        r"\b(OS\s*10|OS10|OS\s*20|OS20)\b",
        r"\b(VK\s*63|VK63|VK\s*64|VK64)\b",
        r"\b(VX\s*12|VX12|VX\s*32|VX32)\b",
        r"\b(VD\s*53|VD53|VD\s*54|VD54)\b",
        r"\b(PC\s*21|PC21|PC\s*32|PC32)\b",
        r"\b(Ronda\s*515|Ronda\s*505|515|505)\b",
        r"\b(Miyota\s*2035|2035|2115|2315|2305)\b",
        r"\b(PE50|SL68)\b",
        r"\b(955112|955412)\b",
    ]
    for pat in patterns:
        m = re.search(pat, title, re.IGNORECASE)
        if m:
            return _normalize_calibre(m.group(1))
    return ""


def _extract_brand_from_title(title: str) -> str:
    if not title:
        return ""
    t = title.lower()
    for alias, canonical in BRAND_ALIASES.items():
        if alias in t:
            return canonical
    return ""


def _classify_listing_kind(title: str) -> str:
    if not title:
        return "unclear"
    t = title.lower()
    for w in BARE_INDICATORS:
        if w in t:
            return "bare_movement"
    for w in WATCH_INDICATORS:
        if w in t:
            return "watch_with_movement"
    if "bundle" in t or "kit" in t or "set" in t or "lot" in t:
        return "parts_bundle"
    return "unclear"


def _classify_mechanical_or_quartz(title: str, calibre: str) -> str:
    if not title and not calibre:
        return "unknown"
    t = (title + " " + calibre).lower()
    for k in QUARTZ_KEYWORDS:
        if k in t:
            return "quartz"
    for k in MECHANICAL_KEYWORDS:
        if k in t:
            return "mechanical"
    return "unknown"


def _is_mechaquartz(title: str, calibre: str) -> bool:
    c = calibre.upper().replace(" ", "").replace("-", "")
    if c in MECHAQUARTZ_CALIBRES:
        return True
    t = title.lower()
    return "mechaquartz" in t or "mecha quartz" in t or "chronograph quartz" in t


def _price_to_usd(price_min: float | None, price_max: float | None, currency: str) -> tuple[float | None, float | None]:
    """Rough USD conversion. AliExpress often shows USD already."""
    if price_min is None and price_max is None:
        return None, None
    # Simple: assume USD if currency is USD or empty; otherwise use as-is (user may need to tune)
    if currency and currency.upper() not in ("USD", "US$", ""):
        # Could add real conversion rates
        pass
    return price_min, price_max


def _canonical_key(row: dict) -> str:
    """Key for deduplication: brand + calibre + seller + price_bucket."""
    brand = (row.get("brand") or "").strip()
    calibre = (row.get("calibre") or "").strip()
    seller = (row.get("seller_name") or row.get("seller_name", "")).strip()[:100]
    p = row.get("estimated_price_usd_min") or row.get("estimated_price_usd_max") or 0
    bucket = round(float(p) / PRICE_BUCKET_USD) * PRICE_BUCKET_USD if p else 0
    return f"{brand}|{calibre}|{seller}|{bucket}"


def clean_and_normalize(raw: list[dict]) -> list[dict]:
    """Transform raw listings into cleaned records with classification."""
    cleaned = []
    for r in raw:
        title = r.get("listing_title") or ""
        raw_calibre = _extract_calibre_from_title(title)
        calibre = _normalize_calibre(raw_calibre) if raw_calibre else ""
        brand = _extract_brand_from_title(title) or (r.get("raw_brand") or "")
        pmin = r.get("price_min")
        pmax = r.get("price_max")
        if pmin is None and pmax is not None:
            pmin = pmax
        if pmax is None and pmin is not None:
            pmax = pmin
        usd_min, usd_max = _price_to_usd(pmin, pmax, r.get("currency") or "USD")
        c = {
            "brand": brand,
            "calibre": calibre,
            "movement_family": "",
            "movement_type": "",
            "display_type": "",
            "hands": "",
            "has_date": None,
            "has_day": None,
            "has_chronograph": None,
            "has_small_seconds": None,
            "has_gmt": None,
            "mechanical_or_quartz": _classify_mechanical_or_quartz(title, calibre),
            "mechaquartz": _is_mechaquartz(title, calibre),
            "listing_kind": _classify_listing_kind(title),
            "estimated_price_usd_min": usd_min,
            "estimated_price_usd_max": usd_max,
            "seller_count_for_same_calibre": None,
            "sample_listing_url": r.get("listing_url") or "",
            "listing_count": 1,
            "confidence_score": 0.5,
            **{k: r.get(k) for k in ["source_site", "search_term", "listing_title", "listing_url", "seller_name", "seller_url", "price_text", "shipping_text", "orders_text", "rating_text", "store_rating_text", "image_url"]},
        }
        c["raw_calibre"] = raw_calibre or r.get("raw_calibre", "")
        c["raw_type"] = r.get("raw_type", "")
        c["description_snippet"] = r.get("description_snippet", "")
        if c["calibre"]:
            c["confidence_score"] = 0.8
        if c["listing_kind"] != "unclear":
            c["confidence_score"] = min(1.0, c["confidence_score"] + 0.1)
        cleaned.append(c)
    return cleaned


def deduplicate(cleaned: list[dict]) -> list[dict]:
    """Remove duplicates by canonical key. Keep first occurrence."""
    seen = set()
    result = []
    for row in cleaned:
        key = _canonical_key(row)
        if key in seen:
            continue
        seen.add(key)
        result.append(row)
    return result


def build_grouped_report(cleaned: list[dict]) -> list[dict]:
    """Aggregate by brand+calibre for grouped cost report."""
    groups = defaultdict(lambda: {
        "listings": [],
        "prices": [],
        "urls": set(),
        "titles": [],
        "sellers": set(),
    })
    for row in cleaned:
        brand = row.get("brand") or "unknown"
        calibre = row.get("calibre") or "unknown"
        key = f"{brand}|{calibre}"
        g = groups[key]
        g["listings"].append(row)
        pmin = row.get("estimated_price_usd_min")
        pmax = row.get("estimated_price_usd_max")
        if pmin is not None:
            g["prices"].append(pmin)
        if pmax is not None:
            g["prices"].append(pmax)
        url = row.get("listing_url") or row.get("sample_listing_url")
        if url:
            g["urls"].add(url)
        t = row.get("listing_title", "")
        if t and t not in g["titles"]:
            g["titles"].append(t[:80])
        seller = row.get("seller_name", "")
        if seller:
            g["sellers"].add(seller)

    report = []
    for key, g in sorted(groups.items()):
        brand, calibre = key.split("|", 1)
        prices = sorted(g["prices"])
        listing_kinds = [x.get("listing_kind", "unclear") for x in g["listings"]]
        kinds_summary = ", ".join(f"{k}:{listing_kinds.count(k)}" for k in ["bare_movement", "watch_with_movement", "parts_bundle", "unclear"] if listing_kinds.count(k))
        mech_or_q = list(set(x.get("mechanical_or_quartz", "unknown") for x in g["listings"]))
        report.append({
            "brand": brand,
            "calibre": calibre,
            "movement_type": g["listings"][0].get("movement_type", "") if g["listings"] else "",
            "mechanical_or_quartz": mech_or_q[0] if len(mech_or_q) == 1 else "mixed",
            "listing_kind_summary": kinds_summary,
            "listing_count": len(g["listings"]),
            "unique_seller_count": len(g["sellers"]),
            "min_price_usd": min(prices) if prices else None,
            "median_price_usd": prices[len(prices) // 2] if prices else None,
            "max_price_usd": max(prices) if prices else None,
            "representative_titles": " | ".join(g["titles"][:3]),
            "sample_urls": " | ".join(list(g["urls"])[:3]),
            "confidence_score": 0.7 if calibre != "unknown" else 0.4,
        })
    return report
