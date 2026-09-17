"""Territory generation and suburb route assignment tests."""

from __future__ import annotations

from app.minit_mobile_operators import MobileOperatorSeed, ResolvedMobileOperator
from app.minit_mobile_routing import normalize_suburb_name
from app.minit_mobile_territory import (
    OperatorHub,
    PostcodeLocality,
    assign_territories,
    build_operator_hubs,
)
from app.minit_shops import MinitShopRow


def _operator(
    shop_number: str,
    label: str,
    *,
    area: str,
    region: str,
    slug: str | None = None,
) -> ResolvedMobileOperator:
    seed = MobileOperatorSeed(shop_number=shop_number, operator_label=label, dispatch_phone="0400000000")
    tss = MinitShopRow(shop_number=shop_number, name=label, area=area, region=region)
    return ResolvedMobileOperator(
        seed=seed,
        tss=tss,
        tenant_name=f"Mobile Services {label}",
        tenant_slug=slug or f"minit-mobile-{shop_number}",
        dispatch_phone="0400000000",
    )


def test_build_operator_hubs_matches_postcode_locality() -> None:
    localities = [
        PostcodeLocality(name="Burwood", state_code="NSW", lat=-33.878, lng=151.104),
        PostcodeLocality(name="Kotara", state_code="NSW", lat=-32.942, lng=151.711),
    ]
    operators = [
        _operator("2243", "Burwood", area="NSW REGIONAL", region="NSW"),
        _operator("2258", "Kotara", area="NSW NORTH", region="NSW"),
    ]
    hubs, skipped = build_operator_hubs(operators, localities)
    assert skipped == []
    assert len(hubs) == 2


def test_assign_territories_nearest_hub_wins() -> None:
    hubs = [
        OperatorHub(
            shop_number="2243",
            operator_label="Burwood",
            tenant_slug="minit-mobile-2243",
            state_code="NSW",
            hub_locality="Burwood",
            lat=-33.878,
            lng=151.104,
        ),
        OperatorHub(
            shop_number="2258",
            operator_label="Kotara",
            tenant_slug="minit-mobile-2258",
            state_code="NSW",
            hub_locality="Kotara",
            lat=-32.942,
            lng=151.711,
        ),
    ]
    localities = [
        PostcodeLocality(name="Burwood", state_code="NSW", lat=-33.878, lng=151.104),
        PostcodeLocality(name="Kotara", state_code="NSW", lat=-32.942, lng=151.711),
        PostcodeLocality(name="Strathfield", state_code="NSW", lat=-33.873, lng=151.089),
    ]
    result = assign_territories(hubs, localities, max_radius_km=30, conflict_gap_km=2)
    by_suburb = {route.suburb_normalized: route for route in result.routes}
    assert by_suburb["burwood"].shop_number == "2243"
    assert by_suburb["kotara"].shop_number == "2258"
    assert by_suburb["strathfield"].shop_number == "2243"


def test_normalize_suburb_name_collapses_whitespace() -> None:
    assert normalize_suburb_name("  Sunnybank   Hills ") == "sunnybank hills"
