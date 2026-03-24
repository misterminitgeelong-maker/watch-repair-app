"""Read-only endpoints for the shoe repair price-book catalogue.

The catalogue is loaded once from the JSON seed file at import time.
No authentication is required — prices are not sensitive.
"""
import json
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, Query

router = APIRouter(prefix="/v1/shoe-catalogue", tags=["shoe-catalogue"])

# Load catalogue once at startup
_CATALOGUE_PATH = Path(__file__).parent.parent.parent / "seed" / "shoe_repairs_catalogue.json"
with open(_CATALOGUE_PATH, encoding="utf-8") as _f:
    _CATALOGUE: dict = json.load(_f)

# Flat index: key → item dict (with group_id, group_label, and defaults injected)
_DEFAULTS = _CATALOGUE.get("defaults", {})
_ITEM_INDEX: dict[str, dict] = {}
for _group in _CATALOGUE["groups"]:
    for _item in _group["items"]:
        enriched = {**_item, "group_id": _group["id"], "group_label": _group["label"]}
        # Apply defaults for complexity and estimated_days if missing
        enriched.setdefault("complexity", _DEFAULTS.get("complexity", "standard"))
        enriched.setdefault("estimated_days_min", _DEFAULTS.get("estimated_days_min", 3))
        enriched.setdefault("estimated_days_max", _DEFAULTS.get("estimated_days_max", 7))
        _ITEM_INDEX[_item["key"]] = enriched


# ── Endpoints ─────────────────────────────────────────────────────────────────

@router.get("/groups")
def list_groups():
    """All category groups (id + label)."""
    return [{"id": g["id"], "label": g["label"]} for g in _CATALOGUE["groups"]]


@router.get("/items")
def search_items(
    q: Optional[str] = Query(default=None, description="Search name (case-insensitive)"),
    group: Optional[str] = Query(default=None, description="Filter by group id"),
):
    """Searchable flat list of all catalogue items.

    Optionally filter by *group* id and/or fuzzy-search the item *name*.
    """
    results = list(_ITEM_INDEX.values())

    if group:
        results = [r for r in results if r["group_id"] == group]

    if q:
        q_lower = q.lower()
        results = [r for r in results if q_lower in r["name"].lower()]

    return results


@router.get("/items/{key}")
def get_item(key: str):
    """Single catalogue item by its key."""
    from fastapi import HTTPException
    item = _ITEM_INDEX.get(key)
    if not item:
        raise HTTPException(status_code=404, detail=f"Catalogue item '{key}' not found")
    return item


@router.get("/combos")
def list_combos():
    """All combo discount rules."""
    return _CATALOGUE["combos"]


@router.get("/guarantee")
def get_guarantee():
    """Guarantee text for shoe repairs."""
    return _CATALOGUE["guarantee"]
