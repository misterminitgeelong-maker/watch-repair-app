"""Shared mobile operator suburb routing for Minit parent accounts."""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from functools import lru_cache
from uuid import UUID

from sqlmodel import Session, select

from .dispatch_utils import haversine_km
from .minit_provision import _is_operator_plan
from .shop_number import linked_tenants_for_parent
from .models import MobileSuburbRoute, ParentAccount, ParentAccountMembership, Tenant

logger = logging.getLogger(__name__)

AU_STATES = frozenset({"ACT", "NSW", "NT", "QLD", "SA", "TAS", "VIC", "WA"})


def normalize_suburb_name(name: str) -> str:
    return " ".join(name.strip().lower().split())


@dataclass(frozen=True)
class MobileRoutingResolution:
    suburb: str
    state_code: str
    suburb_normalized: str
    routing_rule: str
    operator_tenant_id: UUID | None = None
    operator_slug: str | None = None
    operator_name: str | None = None
    operator_shop_number: str | None = None
    message: str | None = None


def _tenant_is_bookable_operator(tenant: Tenant) -> bool:
    return _is_operator_plan(tenant.plan_code)


def lookup_mobile_suburb_route(
    session: Session,
    *,
    parent_id: UUID,
    suburb: str,
    state_code: str,
) -> MobileSuburbRoute | None:
    """Return the territory route row when suburb is inside the operator map."""
    st = state_code.strip().upper()
    sub_norm = normalize_suburb_name(suburb)
    if st not in AU_STATES or not sub_norm:
        return None
    return session.exec(
        select(MobileSuburbRoute)
        .where(MobileSuburbRoute.parent_account_id == parent_id)
        .where(MobileSuburbRoute.state_code == st)
        .where(MobileSuburbRoute.suburb_normalized == sub_norm)
    ).first()


def suburb_in_operator_territory(
    session: Session,
    *,
    parent_id: UUID,
    suburb: str,
    state_code: str,
) -> bool:
    """True when suburb is on the imported operator territory map (within ~100km of a hub)."""
    return lookup_mobile_suburb_route(
        session,
        parent_id=parent_id,
        suburb=suburb,
        state_code=state_code,
    ) is not None


def _resolution_for_outside_territory(
    session: Session,
    *,
    parent_id: UUID,
    suburb: str,
    state_code: str,
    suburb_normalized: str,
) -> MobileRoutingResolution:
    parent = session.get(ParentAccount, parent_id)
    hq_tid = parent.mobile_lead_escalation_tenant_id if parent else None
    if hq_tid:
        tenant = session.get(Tenant, hq_tid)
        if tenant:
            return MobileRoutingResolution(
                suburb=suburb.strip(),
                state_code=state_code,
                suburb_normalized=suburb_normalized,
                routing_rule="outside_operator_territory",
                operator_tenant_id=tenant.id,
                operator_slug=tenant.slug,
                operator_name=tenant.name,
                operator_shop_number=tenant.shop_number,
                message=(
                    "Outside the mobile operator map (~100km from nearest hub). "
                    "Lead goes to HQ for manual dispatch."
                ),
            )
    return MobileRoutingResolution(
        suburb=suburb.strip(),
        state_code=state_code,
        suburb_normalized=suburb_normalized,
        routing_rule="unmapped",
        message="Outside operator territory and no HQ escalation site configured",
    )


def resolve_mobile_operator_route(
    session: Session,
    *,
    parent_id: UUID,
    suburb: str,
    state_code: str,
) -> MobileRoutingResolution:
    """Resolve suburb + state to an operator using the territory map, else HQ."""
    st = state_code.strip().upper()
    sub_norm = normalize_suburb_name(suburb)
    if st not in AU_STATES:
        return MobileRoutingResolution(
            suburb=suburb.strip(),
            state_code=st,
            suburb_normalized=sub_norm,
            routing_rule="invalid_state",
            message=f"state_code must be one of: {', '.join(sorted(AU_STATES))}",
        )
    if not sub_norm:
        return MobileRoutingResolution(
            suburb=suburb.strip(),
            state_code=st,
            suburb_normalized=sub_norm,
            routing_rule="invalid_suburb",
            message="suburb is required",
        )

    route = lookup_mobile_suburb_route(
        session,
        parent_id=parent_id,
        suburb=suburb,
        state_code=st,
    )
    if route:
        tenant = session.get(Tenant, route.target_tenant_id)
        if tenant and _tenant_is_bookable_operator(tenant):
            return MobileRoutingResolution(
                suburb=suburb.strip(),
                state_code=st,
                suburb_normalized=sub_norm,
                routing_rule="suburb_route",
                operator_tenant_id=tenant.id,
                operator_slug=tenant.slug,
                operator_name=tenant.name,
                operator_shop_number=tenant.shop_number,
            )

    return _resolution_for_outside_territory(
        session,
        parent_id=parent_id,
        suburb=suburb,
        state_code=st,
        suburb_normalized=sub_norm,
    )


def _tenant_linked_to_parent(session: Session, parent_id: UUID, tenant_id: UUID) -> bool:
    row = session.exec(
        select(ParentAccountMembership)
        .where(ParentAccountMembership.parent_account_id == parent_id)
        .where(ParentAccountMembership.tenant_id == tenant_id)
    ).first()
    return row is not None


def _bookable_operators_for_parent(session: Session, parent_id: UUID) -> list[Tenant]:
    return [
        t
        for t in linked_tenants_for_parent(session, parent_id)
        if _tenant_is_bookable_operator(t)
    ]


@lru_cache(maxsize=1)
def _suburb_coord_index() -> dict[tuple[str, str], tuple[float, float]]:
    """Lazy AU suburb coordinates for distance ranking (optional)."""
    try:
        from .minit_mobile_territory import load_postcode_localities

        localities = load_postcode_localities()
        return {(loc.normalized, loc.state_code): (loc.lat, loc.lng) for loc in localities}
    except Exception:
        logger.warning("Could not load postcode localities for mobile lead ranking", exc_info=True)
        return {}


def rank_mobile_operator_candidates(
    session: Session,
    *,
    parent_id: UUID,
    suburb: str,
    state_code: str,
    max_candidates: int = 3,
) -> list[UUID]:
    """Return operator tenant ids ordered nearest-first for cascade quoting."""
    if not suburb_in_operator_territory(
        session,
        parent_id=parent_id,
        suburb=suburb,
        state_code=state_code,
    ):
        return []

    route = lookup_mobile_suburb_route(
        session,
        parent_id=parent_id,
        suburb=suburb,
        state_code=state_code,
    )
    if not route:
        return []

    st = state_code.strip().upper()
    sub_norm = normalize_suburb_name(suburb)
    operators = _bookable_operators_for_parent(session, parent_id)
    if not operators:
        return []

    coords = _suburb_coord_index().get((sub_norm, st))
    primary_id = route.target_tenant_id

    def _distance_km(tenant: Tenant) -> float:
        if coords and tenant.base_lat is not None and tenant.base_lng is not None:
            return haversine_km(coords[0], coords[1], tenant.base_lat, tenant.base_lng)
        region = (tenant.minit_region or "").strip().upper()
        state_penalty = 0.0 if region == st else 5000.0
        return state_penalty

    ranked = sorted(operators, key=lambda t: (_distance_km(t), t.name.lower()))
    ordered: list[UUID] = []
    seen: set[UUID] = set()

    tenant = session.get(Tenant, primary_id)
    if tenant and _tenant_is_bookable_operator(tenant) and _tenant_linked_to_parent(session, parent_id, primary_id):
        ordered.append(primary_id)
        seen.add(primary_id)

    for op in ranked:
        if op.id in seen:
            continue
        seen.add(op.id)
        ordered.append(op.id)

    return ordered[: max(1, max_candidates)]


def candidate_operator_ids_json(operator_ids: list[UUID]) -> str:
    return json.dumps([str(tid) for tid in operator_ids])


def parse_candidate_operator_ids(raw: str) -> list[UUID]:
    try:
        data = json.loads(raw or "[]")
    except json.JSONDecodeError:
        return []
    out: list[UUID] = []
    for item in data:
        try:
            out.append(UUID(str(item)))
        except (ValueError, TypeError):
            continue
    return out
