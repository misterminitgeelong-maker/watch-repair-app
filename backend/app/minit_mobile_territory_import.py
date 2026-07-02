"""Bulk import generated mobile suburb territory routes for Minit parent accounts."""

from __future__ import annotations

import json
from pathlib import Path
from uuid import UUID

from sqlmodel import Session, select

from .minit_mobile_routing import normalize_suburb_name
from .minit_provision import _is_operator_plan, linked_tenants_for_parent
from .models import MobileSuburbRoute, Tenant

DEFAULT_TERRITORY_ROUTES_SEED = (
    Path(__file__).resolve().parents[1] / "seed" / "minit_mobile_territory_routes_au_2026.json"
)


def load_territory_routes_seed(path: Path | None = None) -> tuple[list[dict[str, object]], list[dict[str, object]]]:
    seed_path = path or DEFAULT_TERRITORY_ROUTES_SEED
    if not seed_path.is_file():
        raise FileNotFoundError(f"Territory seed not found: {seed_path}")
    payload = json.loads(seed_path.read_text(encoding="utf-8"))
    routes = payload.get("routes") or []
    operators = payload.get("operators") or []
    if not isinstance(routes, list):
        raise ValueError("routes must be a list")
    if not isinstance(operators, list):
        raise ValueError("operators must be a list")
    return routes, operators


def _apply_operator_hub_coords(
    session: Session,
    parent_id: UUID,
    operators: list[dict[str, object]],
) -> int:
    """Set tenant.base_lat/lng from territory hub coordinates (improves distance ranking)."""
    by_shop: dict[str, Tenant] = {}
    for tenant in linked_tenants_for_parent(session, parent_id):
        if _is_operator_plan(tenant.plan_code) and tenant.shop_number:
            by_shop[tenant.shop_number] = tenant

    updated = 0
    for raw in operators:
        shop_number = str(raw.get("shop_number") or "").strip()
        lat = raw.get("lat")
        lng = raw.get("lng")
        if not shop_number or lat is None or lng is None:
            continue
        tenant = by_shop.get(shop_number)
        if not tenant:
            continue
        try:
            flat = float(lat)
            flng = float(lng)
        except (TypeError, ValueError):
            continue
        if tenant.base_lat == flat and tenant.base_lng == flng:
            continue
        tenant.base_lat = flat
        tenant.base_lng = flng
        session.add(tenant)
        updated += 1
    return updated


def import_mobile_suburb_routes(
    session: Session,
    *,
    parent_id: UUID,
    routes: list[dict[str, object]],
    operators: list[dict[str, object]] | None = None,
    apply: bool = False,
    replace_existing: bool = False,
    update_operator_coords: bool = True,
) -> dict[str, object]:
    operators_by_shop: dict[str, Tenant] = {}
    for tenant in linked_tenants_for_parent(session, parent_id):
        if not _is_operator_plan(tenant.plan_code):
            continue
        if tenant.shop_number:
            operators_by_shop[tenant.shop_number] = tenant

    existing = session.exec(
        select(MobileSuburbRoute).where(MobileSuburbRoute.parent_account_id == parent_id)
    ).all()
    existing_by_key = {(row.state_code, row.suburb_normalized): row for row in existing}

    would_create = 0
    would_update = 0
    would_skip = 0
    missing_operator: list[str] = []
    pending: list[tuple[str, str, str, UUID]] = []

    for raw in routes:
        state = str(raw.get("state_code") or "").strip().upper()
        suburb_norm = str(raw.get("suburb_normalized") or normalize_suburb_name(str(raw.get("suburb") or "")))
        shop_number = str(raw.get("shop_number") or "").strip()
        if not state or not suburb_norm or not shop_number:
            continue
        tenant = operators_by_shop.get(shop_number)
        if not tenant:
            missing_operator.append(shop_number)
            continue
        key = (state, suburb_norm)
        current = existing_by_key.get(key)
        if current and current.target_tenant_id == tenant.id:
            would_skip += 1
            continue
        if current:
            would_update += 1
        else:
            would_create += 1
        pending.append((state, suburb_norm, shop_number, tenant.id))

    result: dict[str, object] = {
        "route_rows_in_file": len(routes),
        "would_create_count": would_create,
        "would_update_count": would_update,
        "would_skip_count": would_skip,
        "missing_operator_shop_numbers": sorted(set(missing_operator)),
        "pending_apply_count": len(pending),
    }
    if not apply:
        return result

    if replace_existing and existing:
        for row in existing:
            session.delete(row)
        session.flush()
        existing_by_key = {}

    created = 0
    updated = 0
    for state, suburb_norm, _shop_number, tenant_id in pending:
        key = (state, suburb_norm)
        current = existing_by_key.get(key)
        if current:
            if current.target_tenant_id != tenant_id:
                current.target_tenant_id = tenant_id
                session.add(current)
                updated += 1
            continue
        row = MobileSuburbRoute(
            parent_account_id=parent_id,
            state_code=state,
            suburb_normalized=suburb_norm,
            target_tenant_id=tenant_id,
        )
        session.add(row)
        existing_by_key[key] = row
        created += 1

    coords_updated = 0
    if update_operator_coords and operators:
        coords_updated = _apply_operator_hub_coords(session, parent_id, operators)

    session.commit()
    result["created_count"] = created
    result["updated_count"] = updated
    result["skipped_count"] = would_skip
    result["operator_coords_updated"] = coords_updated
    return result
