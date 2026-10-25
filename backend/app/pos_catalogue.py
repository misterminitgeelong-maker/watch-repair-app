"""What a POS price book contains, and the checks a draft must pass before it can be published.

The content is one JSON document per version (groups -> categories -> items,
plus combo deals) because HQ edits it as a whole: rearranging the till layout,
renaming a category or re-pricing a list are all edits to the same document,
and tills always download a complete, consistent version. Sales copy item and
category names onto their lines, so reports never need the catalogue.

Combo deals are data, not code: each has a ``type`` the till's engine knows and
the parameters for it. ``COMBO_PARAMS`` lists the types and checks their
parameters, so HQ can change a percentage or a tag but can't publish a deal
the tills can't run.
"""
from __future__ import annotations

import json
from typing import Any, Literal, Optional

from pydantic import BaseModel, Field, ValidationError, field_validator, model_validator

Key = str
JobType = Literal["watch", "shoe", "autokey"]


class TileGroup(BaseModel):
    key: Key = Field(min_length=1, max_length=120)
    label: str = Field(min_length=1, max_length=60)
    #: A colour name the till maps to its palette (shoes, keys, watches, workshop, merch) or a #hex.
    color: str = Field(default="workshop", max_length=16)
    sort: int = 0


class Category(BaseModel):
    key: Key = Field(min_length=1, max_length=120)
    name: str = Field(min_length=1, max_length=60)
    group: Key
    icon: str = Field(default="dots", max_length=32)
    color: Optional[str] = Field(default=None, max_length=16)
    sort: int = 0


class Item(BaseModel):
    key: Key = Field(min_length=1, max_length=120)
    category: Key
    name: str = Field(min_length=1, max_length=120)
    #: GST-inclusive. None = quoted on inspection (staff key in the price).
    price_cents: Optional[int] = Field(default=None, ge=0)
    #: The price is a minimum; staff may charge more.
    from_price: bool = False
    unit: Optional[str] = Field(default=None, max_length=24)
    tags: list[str] = Field(default_factory=list)
    job_type: Optional[JobType] = None
    is_service: bool = True
    gst_free: bool = False
    favourite: bool = False
    sku: Optional[str] = Field(default=None, max_length=64)
    barcode: Optional[str] = Field(default=None, max_length=64)
    active: bool = True
    sort: int = 0


class Combo(BaseModel):
    key: Key = Field(min_length=1, max_length=120)
    name: str = Field(min_length=1, max_length=80)
    type: str
    params: dict[str, Any] = Field(default_factory=dict)
    active: bool = True

    @model_validator(mode="after")
    def _known_type(self) -> "Combo":
        check = COMBO_PARAMS.get(self.type)
        if check is None:
            raise ValueError(f"unknown combo type '{self.type}' (known: {', '.join(sorted(COMBO_PARAMS))})")
        check.model_validate(self.params)
        return self


class Catalogue(BaseModel):
    groups: list[TileGroup] = Field(default_factory=list)
    categories: list[Category] = Field(default_factory=list)
    items: list[Item] = Field(default_factory=list)
    combos: list[Combo] = Field(default_factory=list)

    @model_validator(mode="after")
    def _references(self) -> "Catalogue":
        problems: list[str] = []
        for label, rows in (("group", self.groups), ("category", self.categories), ("item", self.items), ("combo", self.combos)):
            seen: set[str] = set()
            for row in rows:
                if row.key in seen:
                    problems.append(f"duplicate {label} key '{row.key}'")
                seen.add(row.key)
        groups = {g.key for g in self.groups}
        categories = {c.key for c in self.categories}
        problems += [f"category '{c.key}' is in unknown group '{c.group}'" for c in self.categories if c.group not in groups]
        problems += [f"item '{i.key}' is in unknown category '{i.category}'" for i in self.items if i.category not in categories]
        if problems:
            raise ValueError("; ".join(problems[:20]))
        return self


# ── Combo deal types ─────────────────────────────────────────────────────────
# Mirrors packages/core/src/combos.ts in the till. Add a type in both places.

class _Percent(BaseModel):
    percent: float = Field(gt=0, le=100)


class TagPercent(_Percent):
    """X% off items tagged ``target_tag`` when the order also has a qualifying item."""

    target_tag: str
    #: Qualifies when another line carries this tag ...
    requires_tag: Optional[str] = None
    #: ... or when any service line does NOT carry this tag (e.g. any non key-cutting service).
    requires_service_without_tag: Optional[str] = None

    @model_validator(mode="after")
    def _one_condition(self) -> "TagPercent":
        if not (self.requires_tag or self.requires_service_without_tag):
            raise ValueError("tag_percent needs requires_tag or requires_service_without_tag")
        return self


class CopyTiers(BaseModel):
    """Copies of the same item: per-copy percentages, then one bulk rate on every copy."""

    tag: str
    #: Percent off the 1st, 2nd, 3rd... copy. [0, 10, 15, 20, 25]
    per_copy: list[float] = Field(min_length=1)
    #: [[min_qty, percent], ...] applied to every copy once qty >= min_qty.
    bulk: list[tuple[int, float]] = Field(default_factory=list)


class NthCopyPercent(_Percent):
    """X% off the nth copy of the same item (2nd remote 25%, 2nd RFID tag 50%)."""

    tag: str
    nth: int = Field(default=2, ge=2)


class AfterNFixedPrice(BaseModel):
    """The first ``n`` units at full price, every further unit at ``price_cents`` (cheapest first)."""

    tag: str
    n: int = Field(ge=1)
    price_cents: int = Field(ge=0)


class QtyTierPercent(BaseModel):
    """Percent off every unit by total quantity across lines: [[2, 10], [5, 15]]."""

    tag: str
    tiers: list[tuple[int, float]] = Field(min_length=1)


COMBO_PARAMS: dict[str, type[BaseModel]] = {
    "tag_percent": TagPercent,
    "copy_tiers": CopyTiers,
    "nth_copy_percent": NthCopyPercent,
    "after_n_fixed_price": AfterNFixedPrice,
    "qty_tier_percent": QtyTierPercent,
}


# ── Parsing and resolution ───────────────────────────────────────────────────

class CatalogueError(ValueError):
    pass


def parse_catalogue(raw: str | dict | None) -> Catalogue:
    data = json.loads(raw) if isinstance(raw, str) else (raw or {})
    try:
        return Catalogue.model_validate(data)
    except ValidationError as exc:
        messages = [f"{'.'.join(str(p) for p in e['loc']) or 'catalogue'}: {e['msg']}" for e in exc.errors()[:20]]
        raise CatalogueError("; ".join(messages)) from exc


def apply_overrides(catalogue: Catalogue, overrides: dict[str, dict]) -> Catalogue:
    """A shop's local prices and hidden items, laid over the published book."""
    if not overrides:
        return catalogue
    items = []
    for item in catalogue.items:
        o = overrides.get(item.key) or {}
        if o.get("hidden"):
            continue
        if "price_cents" in o:
            item = item.model_copy(update={"price_cents": o["price_cents"]})
        items.append(item)
    return catalogue.model_copy(update={"items": items})


class OverrideIn(BaseModel):
    price_cents: Optional[int] = Field(default=None, ge=0)
    hidden: bool = False

    @field_validator("price_cents")
    @classmethod
    def _cap(cls, v: Optional[int]) -> Optional[int]:
        if v is not None and v > 10_000_000:
            raise ValueError("price over $100,000")
        return v
