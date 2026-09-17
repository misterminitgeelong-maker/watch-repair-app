"""Generate mobile operator suburb territories from hub coordinates + distance."""

from __future__ import annotations

import csv
import io
import json
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import BinaryIO, Iterable, TextIO

import httpx

from .dispatch_utils import haversine_km
from .minit_mobile_operators import (
    DEFAULT_OPERATORS_SEED_PATH,
    ResolvedMobileOperator,
    index_tss_shops_by_number,
    load_mobile_operators_seed,
    resolve_mobile_operators,
)
from .minit_mobile_routing import AU_STATES, normalize_suburb_name
from .minit_shops import DEFAULT_TSS_XLSX_PATH, MinitShopRow, derive_au_state_from_area_region, parse_minit_shops_xlsx
from .startup_seed import SUBURBS_CSV_URL

DEFAULT_TERRITORY_OUTPUT = (
    Path(__file__).resolve().parents[1] / "seed" / "minit_mobile_territory_routes_au_2026.json"
)

# Generous caps — conflicts are flagged when two hubs are similarly close.
DEFAULT_MAX_RADIUS_KM = 100.0
DEFAULT_CONFLICT_GAP_KM = 12.0

_HUB_LOCALITY_ALIASES: dict[str, str] = {
    "pacific fair": "Broadbeach",
    "kawana": "Maroochydore",
    "riverside": "Queanbeyan",
    "northpark": "Salisbury Downs",
    "cairns central": "Cairns",
    "narellan town centre 1": "Narellan",
    "noosa": "Noosa Heads",
    "warringah": "Brookvale",
    "warringah mall": "Brookvale",
}

# TSS area/region is wrong for some hubs — pin AU state for postcode lookup.
_OPERATOR_STATE_OVERRIDES: dict[str, str] = {
    "2146": "NSW",  # Lismore
    "8142": "NT",  # Casuarina
}


@dataclass(frozen=True)
class PostcodeLocality:
    name: str
    state_code: str
    lat: float
    lng: float

    @property
    def normalized(self) -> str:
        return normalize_suburb_name(self.name)


@dataclass(frozen=True)
class OperatorHub:
    shop_number: str
    operator_label: str
    tenant_slug: str
    state_code: str
    hub_locality: str
    lat: float
    lng: float
    tss_area: str | None = None
    tss_region: str | None = None


@dataclass(frozen=True)
class TerritoryRoute:
    suburb: str
    state_code: str
    suburb_normalized: str
    shop_number: str
    operator_label: str
    tenant_slug: str
    distance_km: float


@dataclass
class TerritoryConflict:
    suburb: str
    state_code: str
    suburb_normalized: str
    candidates: list[dict[str, object]] = field(default_factory=list)


@dataclass
class TerritoryGenerationResult:
    operators: list[OperatorHub]
    routes: list[TerritoryRoute]
    conflicts: list[TerritoryConflict]
    skipped_operators: list[dict[str, str]]
    unassigned_localities: int
    params: dict[str, float]


def _title_locality(name: str) -> str:
    cleaned = name.strip()
    if not cleaned:
        return ""
    if cleaned.isupper() and len(cleaned) <= 4:
        return cleaned
    return cleaned.title()


def _parse_float(value: str | None) -> float | None:
    if value is None:
        return None
    text = str(value).strip()
    if not text:
        return None
    try:
        return float(text)
    except ValueError:
        return None


def load_postcode_localities(
    source: str | Path | BinaryIO | TextIO | None = None,
) -> list[PostcodeLocality]:
    """Load AU localities with coordinates from the public postcodes CSV."""
    if source is None:
        with httpx.Client(timeout=60.0) as client:
            resp = client.get(SUBURBS_CSV_URL)
            resp.raise_for_status()
            text = resp.text
    elif isinstance(source, (str, Path)):
        text = Path(source).read_text(encoding="utf-8")
    elif hasattr(source, "read"):
        text = source.read()
        if isinstance(text, bytes):
            text = text.decode("utf-8")
    else:
        raise TypeError("Unsupported postcodes source")

    by_key: dict[tuple[str, str], PostcodeLocality] = {}
    for row in csv.DictReader(io.StringIO(text)):
        locality = (row.get("locality") or "").strip()
        state = (row.get("state") or "").strip().upper()
        if not locality or state not in AU_STATES:
            continue
        lat = _parse_float(row.get("Lat_precise")) or _parse_float(row.get("lat"))
        lng = _parse_float(row.get("Long_precise")) or _parse_float(row.get("long"))
        if lat is None or lng is None:
            continue
        name = _title_locality(locality)
        key = (normalize_suburb_name(name), state)
        existing = by_key.get(key)
        if existing is None:
            by_key[key] = PostcodeLocality(name=name, state_code=state, lat=lat, lng=lng)
    return list(by_key.values())


def _locality_index(localities: Iterable[PostcodeLocality]) -> dict[tuple[str, str], PostcodeLocality]:
    return {(loc.normalized, loc.state_code): loc for loc in localities}


def _hub_search_names(operator: ResolvedMobileOperator) -> list[str]:
    names = [
        operator.seed.operator_label,
        operator.tss.name,
        _HUB_LOCALITY_ALIASES.get(normalize_suburb_name(operator.tss.name), ""),
        _HUB_LOCALITY_ALIASES.get(normalize_suburb_name(operator.seed.operator_label), ""),
    ]
    out: list[str] = []
    seen: set[str] = set()
    for raw in names:
        norm = normalize_suburb_name(raw)
        if not norm or norm in seen:
            continue
        seen.add(norm)
        out.append(_title_locality(raw))
    return out


def build_operator_hubs(
    operators: list[ResolvedMobileOperator],
    localities: list[PostcodeLocality],
) -> tuple[list[OperatorHub], list[dict[str, str]]]:
    """Resolve operator hub coordinates from postcode localities."""
    index = _locality_index(localities)
    hubs: list[OperatorHub] = []
    skipped: list[dict[str, str]] = []

    for operator in operators:
        state = _OPERATOR_STATE_OVERRIDES.get(operator.shop_number)
        if not state:
            region = (operator.tss.region or "").strip().upper()
            if region in AU_STATES:
                state = region
            else:
                state = derive_au_state_from_area_region(operator.tss.area, operator.tss.region)
        if not state or state not in AU_STATES:
            skipped.append(
                {
                    "shop_number": operator.shop_number,
                    "operator_label": operator.seed.operator_label,
                    "reason": f"non-AU or unknown state (area={operator.tss.area}, region={operator.tss.region})",
                }
            )
            continue

        hub_loc: PostcodeLocality | None = None
        hub_name = ""
        for candidate in _hub_search_names(operator):
            hub_loc = index.get((normalize_suburb_name(candidate), state))
            if hub_loc:
                hub_name = hub_loc.name
                break
        if not hub_loc:
            skipped.append(
                {
                    "shop_number": operator.shop_number,
                    "operator_label": operator.seed.operator_label,
                    "reason": f"hub locality not found in postcodes for {state}",
                }
            )
            continue

        hubs.append(
            OperatorHub(
                shop_number=operator.shop_number,
                operator_label=operator.seed.operator_label,
                tenant_slug=operator.tenant_slug,
                state_code=state,
                hub_locality=hub_name,
                lat=hub_loc.lat,
                lng=hub_loc.lng,
                tss_area=operator.tss.area,
                tss_region=operator.tss.region,
            )
        )
    return hubs, skipped


def assign_territories(
    hubs: list[OperatorHub],
    localities: list[PostcodeLocality],
    *,
    max_radius_km: float = DEFAULT_MAX_RADIUS_KM,
    conflict_gap_km: float = DEFAULT_CONFLICT_GAP_KM,
) -> TerritoryGenerationResult:
    """Assign each locality to the nearest operator hub in the same state."""
    hubs_by_state: dict[str, list[OperatorHub]] = {}
    for hub in hubs:
        hubs_by_state.setdefault(hub.state_code, []).append(hub)

    routes: list[TerritoryRoute] = []
    conflicts: list[TerritoryConflict] = []
    unassigned = 0

    for loc in localities:
        state_hubs = hubs_by_state.get(loc.state_code)
        if not state_hubs:
            continue

        ranked: list[tuple[float, OperatorHub]] = []
        for hub in state_hubs:
            dist = haversine_km(hub.lat, hub.lng, loc.lat, loc.lng)
            if dist <= max_radius_km:
                ranked.append((dist, hub))
        if not ranked:
            unassigned += 1
            continue

        ranked.sort(key=lambda item: item[0])
        best_dist, best_hub = ranked[0]
        if len(ranked) > 1:
            second_dist, second_hub = ranked[1]
            if second_dist - best_dist <= conflict_gap_km:
                conflicts.append(
                    TerritoryConflict(
                        suburb=loc.name,
                        state_code=loc.state_code,
                        suburb_normalized=loc.normalized,
                        candidates=[
                            {
                                "shop_number": best_hub.shop_number,
                                "operator_label": best_hub.operator_label,
                                "distance_km": round(best_dist, 2),
                            },
                            {
                                "shop_number": second_hub.shop_number,
                                "operator_label": second_hub.operator_label,
                                "distance_km": round(second_dist, 2),
                            },
                        ],
                    )
                )

        routes.append(
            TerritoryRoute(
                suburb=loc.name,
                state_code=loc.state_code,
                suburb_normalized=loc.normalized,
                shop_number=best_hub.shop_number,
                operator_label=best_hub.operator_label,
                tenant_slug=best_hub.tenant_slug,
                distance_km=round(best_dist, 2),
            )
        )

    return TerritoryGenerationResult(
        operators=hubs,
        routes=routes,
        conflicts=conflicts,
        skipped_operators=[],
        unassigned_localities=unassigned,
        params={"max_radius_km": max_radius_km, "conflict_gap_km": conflict_gap_km},
    )


def generate_territory_routes(
    *,
    operators_seed_path: Path | None = None,
    tss_path: Path | None = None,
    postcodes_source: str | Path | None = None,
    max_radius_km: float = DEFAULT_MAX_RADIUS_KM,
    conflict_gap_km: float = DEFAULT_CONFLICT_GAP_KM,
) -> TerritoryGenerationResult:
    seeds = load_mobile_operators_seed(operators_seed_path)
    tss_shops = parse_minit_shops_xlsx(tss_path or Path(DEFAULT_TSS_XLSX_PATH))
    operators, errors = resolve_mobile_operators(seeds, index_tss_shops_by_number(tss_shops))
    if errors:
        raise ValueError(f"Operator seed/TSS errors: {errors}")

    localities = load_postcode_localities(postcodes_source)
    hubs, skipped = build_operator_hubs(operators, localities)
    result = assign_territories(
        hubs,
        localities,
        max_radius_km=max_radius_km,
        conflict_gap_km=conflict_gap_km,
    )
    result.skipped_operators = skipped
    return result


def territory_result_to_dict(result: TerritoryGenerationResult) -> dict[str, object]:
    return {
        "version": 1,
        "method": "nearest_operator_hub",
        "params": result.params,
        "operators": [
            {
                "shop_number": hub.shop_number,
                "operator_label": hub.operator_label,
                "tenant_slug": hub.tenant_slug,
                "state_code": hub.state_code,
                "hub_locality": hub.hub_locality,
                "lat": hub.lat,
                "lng": hub.lng,
                "tss_area": hub.tss_area,
                "tss_region": hub.tss_region,
            }
            for hub in result.operators
        ],
        "skipped_operators": result.skipped_operators,
        "route_count": len(result.routes),
        "conflict_count": len(result.conflicts),
        "unassigned_locality_count": result.unassigned_localities,
        "routes": [
            {
                "suburb": route.suburb,
                "state_code": route.state_code,
                "suburb_normalized": route.suburb_normalized,
                "shop_number": route.shop_number,
                "operator_label": route.operator_label,
                "tenant_slug": route.tenant_slug,
                "distance_km": route.distance_km,
            }
            for route in result.routes
        ],
        "conflicts": [
            {
                "suburb": conflict.suburb,
                "state_code": conflict.state_code,
                "suburb_normalized": conflict.suburb_normalized,
                "candidates": conflict.candidates,
            }
            for conflict in result.conflicts
        ],
    }


def write_territory_json(result: TerritoryGenerationResult, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(territory_result_to_dict(result), indent=2), encoding="utf-8")


def write_conflicts_csv(result: TerritoryGenerationResult, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow(
            [
                "suburb",
                "state_code",
                "suburb_normalized",
                "winner_shop_number",
                "winner_label",
                "winner_distance_km",
                "runner_up_shop_number",
                "runner_up_label",
                "runner_up_distance_km",
            ]
        )
        for conflict in result.conflicts:
            if len(conflict.candidates) < 2:
                continue
            winner, runner_up = conflict.candidates[0], conflict.candidates[1]
            writer.writerow(
                [
                    conflict.suburb,
                    conflict.state_code,
                    conflict.suburb_normalized,
                    winner.get("shop_number"),
                    winner.get("operator_label"),
                    winner.get("distance_km"),
                    runner_up.get("shop_number"),
                    runner_up.get("operator_label"),
                    runner_up.get("distance_km"),
                ]
            )
