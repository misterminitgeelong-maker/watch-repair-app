"""Read-only endpoints for the watch repair price-book catalogue.

The catalogue is loaded once from the JSON seed file at import time.
"""
import json
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, Query

router = APIRouter(prefix="/v1/watch-catalogue", tags=["watch-catalogue"])

# Load watch repairs catalogue
_CATALOGUE_PATH = Path(__file__).parent.parent.parent / "seed" / "watch_repairs_catalogue.json"
with open(_CATALOGUE_PATH, encoding="utf-8") as _f:
    _CATALOGUE: dict = json.load(_f)

# Flat index for repairs
_ITEM_INDEX: dict[str, dict] = {}
for _group in _CATALOGUE["groups"]:
    for _item in _group["items"]:
        enriched = {**_item, "group_id": _group["id"], "group_label": _group["label"]}
        _ITEM_INDEX[_item["key"]] = enriched

# Load watch movements (for cost + margin)
_MOVEMENTS_PATH = Path(__file__).parent.parent.parent / "seed" / "watch_movements.json"
with open(_MOVEMENTS_PATH, encoding="utf-8") as _f:
    _MOVEMENTS: dict = json.load(_f)
_MOVEMENT_INDEX = {m["key"]: m for m in _MOVEMENTS["movements"]}


def _movement_quote(m: dict) -> int:
    """Compute quote_cents: RRP = max(minimum_rrp_cents, cost × 2.75)."""
    cost = m.get("purchase_cost_cents", 0)
    margin_pct = _MOVEMENTS.get("default_margin_percent", 175)
    min_rrp = _MOVEMENTS.get("minimum_rrp_cents", 0)
    quoted = int(cost * (1 + margin_pct / 100))
    return max(min_rrp, quoted)


@router.get("/groups")
def list_groups():
    """All repair category groups (id + label)."""
    return [{"id": g["id"], "label": g["label"]} for g in _CATALOGUE["groups"]]


@router.get("/items")
def search_items(
    q: Optional[str] = Query(default=None, description="Search name (case-insensitive)"),
    group: Optional[str] = Query(default=None, description="Filter by group id"),
):
    """Searchable flat list of catalogue items."""
    results = list(_ITEM_INDEX.values())
    if group:
        results = [r for r in results if r["group_id"] == group]
    if q:
        q_lower = q.lower()
        results = [r for r in results if q_lower in r["name"].lower()]
    return results


@router.get("/items/{key}")
def get_item(key: str):
    """Single catalogue item by key."""
    from fastapi import HTTPException
    item = _ITEM_INDEX.get(key)
    if not item:
        raise HTTPException(status_code=404, detail=f"Catalogue item '{key}' not found")
    return item


@router.get("/movements")
def list_movements():
    """All mechanical movements with purchase cost. Used for cost + margin when updating jobs."""
    movements = [
        {**m, "quote_cents": _movement_quote(m)}
        for m in _MOVEMENTS["movements"]
    ]
    return {
        "currency": _MOVEMENTS["currency"],
        "default_margin_percent": _MOVEMENTS["default_margin_percent"],
        "movements": movements,
    }


@router.get("/movements/{key}/quote")
def get_movement_quote(key: str):
    """Return quoted price in cents. RRP = max(minimum_rrp_cents, cost * (1 + margin/100))."""
    from fastapi import HTTPException
    m = _MOVEMENT_INDEX.get(key)
    if not m:
        raise HTTPException(status_code=404, detail=f"Movement '{key}' not found")
    return {"key": key, "name": m["name"], "quote_cents": _movement_quote(m)}
