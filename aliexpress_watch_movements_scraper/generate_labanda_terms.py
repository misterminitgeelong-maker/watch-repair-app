#!/usr/bin/env python3
"""
Generate AliExpress search terms from all Labanda movements.
Reduces 695 movements to ~250 unique (brand + calibre) search queries.
"""

import json
import re
from pathlib import Path

LABANDA_JSON = Path(__file__).parent.parent / "labanda_scraper" / "data" / "labanda_movements.json"


def _normalize_to_calibre(model: str, brand: str) -> list[str]:
    """Extract searchable calibre(s) from Labanda model. Returns list of normalized strings."""
    if not model or not model.strip():
        return []
    m = model.strip()
    m = re.sub(r"\s*\([^)]*\)\s*\*?\s*$", "", m).strip()
    m = re.sub(r"\s*=\s*[^=]+$", "", m).strip()
    m = re.sub(r"\s*\*+$", "", m).strip()

    # Ronda: R505-D3 -> 505
    r_match = re.match(r"^R(\d+)[-_\s]", m, re.I)
    if r_match:
        base = r_match.group(1)
    else:
        base = m
    base = re.sub(r"^RONDA\s+", "", base, flags=re.I).strip()

    # ETA prefixes
    base = re.sub(r"^(E{1,2}|EF|EG|P)(\d)", r"\2", base, flags=re.I)
    base = re.sub(r"^([A-Z])(\d)", r"\2", base) if re.match(r"^[A-Z]\d", base, re.I) else base

    # Suffixes
    base = re.sub(r"[-_](D3|D6|HD4|RD4|2H|3H|DD3|DD6)[-\dA-Z.]*\s*$", "", base, flags=re.I).strip()
    base = re.sub(r"\s+AIG[\dA-Z]*$", "", base, flags=re.I).strip()
    base = re.sub(r"[AFJ]$", "", base, flags=re.I).strip()

    if re.match(r"^M\d", base, re.I):
        base = base[1:]
    base = re.sub(r"^ISA\s+", "", base, flags=re.I).strip()
    if re.match(r"^R\d", base, re.I) and not re.match(r"^R\d+[-_\s]", base, re.I):
        base = base[1:]
    if re.match(r"^H[A-Z]{2}\d", base, re.I):
        base = base[1:]

    core = re.sub(r"[^a-zA-Z0-9.]", "", base)
    if not core or len(core) < 2:
        return []
    return [core]


def _brand_to_search_prefix(brand: str) -> str:
    """Map Labanda brand to AliExpress search prefix."""
    m = {
        "ETA": "eta",
        "FE": "eta",
        "Swiss": "swiss",
        "Seiko/TMI": "seiko",
        "Miyota": "miyota",
        "Ronda": "ronda",
        "ISA": "isa",
        "China": "china",
    }
    return m.get(brand, brand.lower().split("/")[0])


def get_labanda_search_terms() -> list[str]:
    """Return unique AliExpress search terms derived from Labanda catalogue."""
    if not LABANDA_JSON.exists():
        return []
    data = json.loads(LABANDA_JSON.read_text(encoding="utf-8"))
    movements = data.get("movements", [])
    seen = set()
    terms = []
    for m in movements:
        brand = m.get("brand", "")
        model = m.get("model", "")
        calibres = _normalize_to_calibre(model, brand)
        prefix = _brand_to_search_prefix(brand)
        for cal in calibres:
            if not cal or len(cal) < 2:
                continue
            # Search as "brand calibre movement" - AliExpress expects this format
            term = f"{prefix} {cal} movement"
            key = term.lower()
            if key not in seen:
                seen.add(key)
                terms.append(term)
    return sorted(terms)


if __name__ == "__main__":
    terms = get_labanda_search_terms()
    print(f"Generated {len(terms)} unique search terms from Labanda")
    for t in terms[:30]:
        print(f"  {t}")
    if len(terms) > 30:
        print(f"  ... and {len(terms) - 30} more")
