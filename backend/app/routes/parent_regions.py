"""The regional manager's view of the network: one region's week rolled up,
ranked against the other regions, with the shops underneath it.

Cross-tenant by design — a region spans its shops — so every endpoint takes
``unscoped_session``. Access is by network role: any HQ role may read any
region; a regional manager (an hq_viewer grant pinned to a region_id) may
read and annotate only theirs.
"""

from __future__ import annotations

from datetime import datetime, timezone
from statistics import median
from typing import Any, Literal, Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlmodel import Session, col, select

from ..database import unscoped_session
from ..dependencies import AuthContext, get_auth_context, require_feature
from ..models import (
    ParentAccount,
    Region,
    RegionTargetFillRequest,
    RegionTargetFillResponse,
    RegionWeekAnnotationRead,
    RegionWeekAnnotationUpdateRequest,
    User,
    VswtRegionWeekAnnotation,
    VswtReportTarget,
    VswtWeeklyShopMetric,
)
from ..parent_network import (
    can_write_region,
    region_by_shop_number,
    regions_for_parent,
    require_region_access,
    shop_numbers_for_region,
)
from ..tenant_scope import without_scope
from ..vswt_insights import build_region_narrative
from ..vswt_kpis import KPI_BY_KEY
from ..vswt_regional import (
    HEADLINE_KEYS,
    METRIC_DEFS,
    build_region_rows,
    build_shop_table,
    category_drivers,
    group_rows_by_region,
    movers,
    rank_among,
    region_alerts,
    rollup,
    shop_value,
    target_attainment,
)
from .parent_accounts import _parent_for_scoped_read, _parent_for_write, _record_event
from .vswt_reports import _all_weeks, _week_rows

router = APIRouter(
    prefix="/v1/parent-accounts/me/regions",
    tags=["parent-regions"],
    dependencies=[Depends(require_feature("multi_site"))],
)

_COMPARISON_LABELS = {
    "previous": "previous week",
    "4w": "prior 4-week average",
    "13w": "prior 13-week average",
    "52w": "prior 52-week average",
    "last_year": "same week last year",
}
_ALLOWED_TARGET_KEYS = set(KPI_BY_KEY) | {"avg_sale", "jobs_per_customer"}


# ── access ───────────────────────────────────────────────────────────────────


def _region_for_read(session: Session, auth: AuthContext, region_id: UUID) -> tuple[User, ParentAccount, Region]:
    user, parent, _role, _scope = _parent_for_scoped_read(session, auth)
    region = session.get(Region, region_id)
    if region is None or region.parent_account_id != parent.id:
        raise HTTPException(status_code=404, detail="Region not found")
    require_region_access(session, parent, user, region.id)
    return user, parent, region


def _region_for_annotate(session: Session, auth: AuthContext, region_id: UUID) -> tuple[User, ParentAccount, Region]:
    user, parent, region = _region_for_read(session, auth, region_id)
    if not can_write_region(session, parent, user, region.id):
        raise HTTPException(status_code=403, detail="Only HQ admins or this region's manager can do that")
    return user, parent, region


# ── data ─────────────────────────────────────────────────────────────────────


def _region_history(
    session: Session, shop_numbers: list[str], weeks: list[int]
) -> dict[str, dict[int, VswtWeeklyShopMetric]]:
    """Every region shop's rows for the given weeks — one query, not one per shop-week."""
    if not shop_numbers or not weeks:
        return {}
    rows = session.exec(
        select(VswtWeeklyShopMetric)
        .where(col(VswtWeeklyShopMetric.shop_number).in_(shop_numbers))
        .where(col(VswtWeeklyShopMetric.week_seq).in_(weeks))
    ).all()
    out: dict[str, dict[int, VswtWeeklyShopMetric]] = {sn: {} for sn in shop_numbers}
    for r in rows:
        out.setdefault(r.shop_number, {})[r.week_seq] = r
    return out


def _region_annotation_rows(session: Session, region_id: UUID) -> list[VswtRegionWeekAnnotation]:
    return list(
        session.exec(
            select(VswtRegionWeekAnnotation)
            .where(VswtRegionWeekAnnotation.region_id == region_id)
            .order_by(col(VswtRegionWeekAnnotation.week_seq).desc())
        ).all()
    )


def _annotation_read(row: VswtRegionWeekAnnotation) -> RegionWeekAnnotationRead:
    return RegionWeekAnnotationRead(
        id=row.id,
        region_id=row.region_id,
        week=row.week_seq,
        event_type=row.event_type,
        note=row.note,
        exclude_from_baselines=bool(row.exclude_from_baselines),
        created_at=row.created_at,
        updated_at=row.updated_at,
    )


def _targets_by_shop(session: Session, tenant_by_shop: dict[str, UUID]) -> dict[str, dict[str, float]]:
    if not tenant_by_shop:
        return {}
    with without_scope(session):
        rows = session.exec(
            select(VswtReportTarget).where(col(VswtReportTarget.tenant_id).in_(list(tenant_by_shop.values())))
        ).all()
    out: dict[str, dict[str, float]] = {}
    for row in rows:
        out.setdefault(row.shop_number, {})[row.metric_key] = row.target_value
    return out


def build_region_cockpit(
    session: Session,
    *,
    parent: ParentAccount,
    region: Region,
    selected_week: Optional[int] = None,
    comparison: str = "previous",
) -> dict[str, Any]:
    all_weeks = _all_weeks(session)
    if not all_weeks:
        return {"available": False, "reason": "no_data"}
    tenant_by_shop = shop_numbers_for_region(session, parent.id, region.id)
    shop_numbers = sorted(tenant_by_shop)
    if not shop_numbers:
        return {"available": False, "reason": "no_shops"}

    week = selected_week if selected_week in all_weeks else all_weeks[-1]
    week_index = all_weeks.index(week)
    visible_weeks = all_weeks[: week_index + 1]
    previous_week = visible_weeks[-2] if len(visible_weeks) > 1 else None

    notes = _region_annotation_rows(session, region.id)
    excluded_weeks = {n.week_seq for n in notes if n.exclude_from_baselines}
    prior_weeks_all = visible_weeks[:-1]
    prior_weeks = [w for w in prior_weeks_all if w not in excluded_weeks]

    # Whole network for the selected and previous weeks (region ranking, network averages).
    current_rows = _week_rows(session, week)
    previous_rows = _week_rows(session, previous_week) if previous_week is not None else []
    region_of_shop = region_by_shop_number(session, parent.id)
    current_by_region = group_rows_by_region(current_rows, region_of_shop)
    previous_by_region = group_rows_by_region(previous_rows, region_of_shop)
    region_rollups = {rid: rollup(rows) for rid, rows in current_by_region.items()}
    prev_region_rollups = {rid: rollup(rows) for rid, rows in previous_by_region.items()}
    if region.id not in region_rollups:
        region_rollups[region.id] = rollup([])

    # This region only, back 52 weeks, one query.
    history = _region_history(session, shop_numbers, visible_weeks[-53:])
    weekly_rollups = {
        w: rollup([history[sn][w] for sn in shop_numbers if w in history.get(sn, {})]) for w in visible_weeks[-53:]
    }
    current = region_rollups[region.id]
    previous = prev_region_rollups.get(region.id, rollup([]))

    region_values_by_key = {
        d["key"]: {rid: vals.get(d["key"]) for rid, vals in region_rollups.items()} for d in METRIC_DEFS
    }
    prev_region_values_by_key = {
        d["key"]: {rid: vals.get(d["key"]) for rid, vals in prev_region_rollups.items()} for d in METRIC_DEFS
    }
    network_avg_by_key = {
        d["key"]: (
            (lambda vs: sum(vs) / len(vs) if vs else None)(
                [shop_value(r, d["key"]) for r in current_rows if shop_value(r, d["key"]) is not None]
            )
        )
        for d in METRIC_DEFS
    }
    rows, baselines = build_region_rows(
        current=current,
        previous=previous,
        weekly_rollups=weekly_rollups,
        prior_weeks=prior_weeks,
        comparison=comparison,
        region_values_by_key=region_values_by_key,
        prev_region_values_by_key=prev_region_values_by_key,
        region_id=region.id,
        network_avg_by_key=network_avg_by_key,
    )
    rows_by_key = {r["key"]: r for r in rows}

    current_by_shop = {r.shop_number: r for r in current_rows if r.shop_number in tenant_by_shop}
    previous_by_shop = {r.shop_number: r for r in previous_rows if r.shop_number in tenant_by_shop}
    targets_by_shop = _targets_by_shop(session, tenant_by_shop)
    table = build_shop_table(
        shop_numbers=shop_numbers,
        current_by_shop=current_by_shop,
        previous_by_shop=previous_by_shop,
        history_by_shop=history,
        prior_weeks=prior_weeks,
        network_current_rows=current_rows,
        targets_by_shop=targets_by_shop,
        tenant_by_shop=tenant_by_shop,
    )
    up, down = movers(table)
    attainment = target_attainment(table)
    anomalies = [r for r in table if r["anomaly"]]
    region_count = len(region_rollups)
    alerts = region_alerts(
        rows_by_key=rows_by_key, baselines=baselines, table=table, movers_down=down, region_count=region_count
    )

    # Every region's headline for the "vs other regions" strip.
    regions_by_id = {r.id: r for r in regions_for_parent(session, parent.id)}
    sales_by_region = region_values_by_key.get("sales_ty", {})
    leaderboard = sorted(
        (
            {
                "region_id": str(rid),
                "region_name": regions_by_id[rid].name if rid in regions_by_id else "Unknown",
                "sales": vals.get("sales_ty"),
                "customers": vals.get("customer_ty"),
                "shops": len(current_by_region.get(rid, [])),
                "rank": rank_among(sales_by_region, rid),
                "is_me": rid == region.id,
                "delta_pct": (
                    (vals.get("sales_ty") - prev_region_rollups.get(rid, {}).get("sales_ty"))
                    / abs(prev_region_rollups.get(rid, {}).get("sales_ty"))
                    if vals.get("sales_ty") is not None and prev_region_rollups.get(rid, {}).get("sales_ty")
                    else None
                ),
            }
            for rid, vals in region_rollups.items()
        ),
        key=lambda r: (r["rank"] is None, r["rank"] or 0),
    )

    narrative = build_region_narrative(
        region_name=region.name,
        week=week,
        comparison_label=_COMPARISON_LABELS.get(comparison, "previous week"),
        sales=rows_by_key["sales_ty"],
        customers=rows_by_key["customer_ty"],
        shop_count=len([r for r in table if r["reported"]]),
        region_rank=rows_by_key["sales_ty"]["rank"],
        region_count=region_count,
        movers_up=up,
        movers_down=down,
        anomalies=[r for r in anomalies if r["anomaly"] == "low"],
        target_attainment=attainment,
    )

    return {
        "available": True,
        "region": {
            "id": str(region.id),
            "code": region.code,
            "name": region.name,
            "manager_name": region.manager_name,
            "manager_email": region.manager_email,
            "weekly_report_opt_in": bool(region.weekly_report_opt_in),
            "last_weekly_report_sent_at": region.last_weekly_report_sent_at,
        },
        "week": week,
        "previous_week": previous_week,
        "weeks": all_weeks,
        "comparison": comparison,
        "shop_count": len(shop_numbers),
        "shops_reported": len([r for r in table if r["reported"]]),
        "region_count": region_count,
        "rows": rows,
        "headline": [rows_by_key[k] for k in HEADLINE_KEYS if k in rows_by_key],
        "drivers": {"category_sales": category_drivers(current, previous)},
        "shops": table,
        "movers": {"up": up, "down": down},
        "anomalies": anomalies,
        "alerts": alerts,
        "narrative": narrative,
        "target_attainment": attainment,
        "leaderboard": leaderboard,
        "annotations": [_annotation_read(n).model_dump() for n in notes],
        "excluded_weeks": sorted(excluded_weeks),
    }


# ── routes ───────────────────────────────────────────────────────────────────


@router.get("/{region_id}/cockpit")
def get_region_cockpit(
    region_id: UUID,
    week: Optional[int] = Query(None),
    comparison: Literal["previous", "4w", "13w", "52w", "last_year"] = Query("previous"),
    auth: AuthContext = Depends(get_auth_context),
    session: Session = Depends(unscoped_session),
):
    _user, parent, region = _region_for_read(session, auth, region_id)
    return build_region_cockpit(session, parent=parent, region=region, selected_week=week, comparison=comparison)


@router.get("/{region_id}/annotations", response_model=list[RegionWeekAnnotationRead])
def list_region_annotations(
    region_id: UUID,
    auth: AuthContext = Depends(get_auth_context),
    session: Session = Depends(unscoped_session),
):
    _user, _parent, region = _region_for_read(session, auth, region_id)
    return [_annotation_read(r) for r in _region_annotation_rows(session, region.id)]


@router.put("/{region_id}/annotations", response_model=RegionWeekAnnotationRead)
def put_region_annotation(
    region_id: UUID,
    payload: RegionWeekAnnotationUpdateRequest,
    auth: AuthContext = Depends(get_auth_context),
    session: Session = Depends(unscoped_session),
):
    """One note for the whole region's week. It shows on every shop in the
    region, and with ``exclude_from_baselines`` it drops that week out of
    every one of their rolling comparisons."""
    user, parent, region = _region_for_annotate(session, auth, region_id)
    if payload.week not in _all_weeks(session):
        raise HTTPException(status_code=400, detail="That reporting week is not available.")
    note = payload.note.strip()
    if not note:
        raise HTTPException(status_code=400, detail="Week note must be between 1 and 500 characters.")
    event_type = payload.event_type.strip().lower().replace(" ", "_")[:32] or "other"
    now = datetime.now(timezone.utc)
    row = session.exec(
        select(VswtRegionWeekAnnotation)
        .where(VswtRegionWeekAnnotation.region_id == region.id)
        .where(VswtRegionWeekAnnotation.week_seq == payload.week)
    ).first()
    if row:
        row.note, row.event_type = note, event_type
        row.exclude_from_baselines = payload.exclude_from_baselines
        row.updated_at = now
    else:
        row = VswtRegionWeekAnnotation(
            parent_account_id=parent.id,
            region_id=region.id,
            week_seq=payload.week,
            event_type=event_type,
            note=note,
            exclude_from_baselines=payload.exclude_from_baselines,
            created_by_user_id=user.id,
            created_at=now,
            updated_at=now,
        )
    session.add(row)
    _record_event(
        session,
        parent_account_id=parent.id,
        tenant_id=None,
        actor_user_id=user.id,
        actor_email=user.email,
        event_type="region_week_annotated",
        event_summary=(
            f"Noted week {payload.week} for {region.name}: {event_type}"
            + (" (excluded from baselines)" if payload.exclude_from_baselines else "")
        ),
    )
    session.commit()
    session.refresh(row)
    return _annotation_read(row)


@router.delete("/{region_id}/annotations/{annotation_id}")
def delete_region_annotation(
    region_id: UUID,
    annotation_id: UUID,
    auth: AuthContext = Depends(get_auth_context),
    session: Session = Depends(unscoped_session),
):
    _user, _parent, region = _region_for_annotate(session, auth, region_id)
    row = session.get(VswtRegionWeekAnnotation, annotation_id)
    if row is None or row.region_id != region.id:
        raise HTTPException(status_code=404, detail="Week note not found.")
    session.delete(row)
    session.commit()
    return {"deleted": str(annotation_id)}


@router.post("/{region_id}/targets/fill", response_model=RegionTargetFillResponse)
def fill_region_targets(
    region_id: UUID,
    payload: RegionTargetFillRequest,
    auth: AuthContext = Depends(get_auth_context),
    session: Session = Depends(unscoped_session),
):
    """Set every shop in the region's targets from one rule.

    ``last_year_plus_pct`` reads each shop's same-week-last-year figure and
    uplifts it; ``region_median`` gives every shop the region's median for
    the week; ``previous_week`` carries last week's actual forward. Shops with
    no figure for the rule are skipped, never zeroed.
    """
    user, parent = _parent_for_write(session, auth)
    region = session.get(Region, region_id)
    if region is None or region.parent_account_id != parent.id:
        raise HTTPException(status_code=404, detail="Region not found")
    strategy = payload.strategy.strip().lower()
    if strategy not in {"last_year_plus_pct", "region_median", "previous_week"}:
        raise HTTPException(status_code=400, detail="strategy must be last_year_plus_pct, region_median or previous_week")
    keys = [k for k in payload.metric_keys if k in _ALLOWED_TARGET_KEYS]
    if not keys:
        raise HTTPException(status_code=400, detail="No valid metric_keys")
    if payload.pct < -100 or payload.pct > 500:
        raise HTTPException(status_code=400, detail="pct must be between -100 and 500")
    all_weeks = _all_weeks(session)
    if not all_weeks:
        raise HTTPException(status_code=400, detail="No reporting weeks on file")
    week = payload.week if payload.week in all_weeks else all_weeks[-1]

    tenant_by_shop = shop_numbers_for_region(session, parent.id, region.id)
    shop_numbers = sorted(tenant_by_shop)
    if not shop_numbers:
        raise HTTPException(status_code=400, detail="This region has no shops with a shop number")

    week_rows = {r.shop_number: r for r in _week_rows(session, week) if r.shop_number in tenant_by_shop}
    prev_week = all_weeks[all_weeks.index(week) - 1] if all_weeks.index(week) > 0 else None
    prev_rows = (
        {r.shop_number: r for r in _week_rows(session, prev_week) if r.shop_number in tenant_by_shop}
        if prev_week is not None
        else {}
    )
    ly_keys = {"sales_ty": "sales_ly", "customer_ty": "customer_ly", "jobs_ty": "jobs_ly"}

    def value_for(sn: str, key: str) -> Optional[float]:
        if strategy == "previous_week":
            return shop_value(prev_rows.get(sn), key)
        if strategy == "last_year_plus_pct":
            row = week_rows.get(sn)
            base = getattr(row, ly_keys[key], None) if row and key in ly_keys else (
                shop_value(prev_rows.get(sn), key) if key not in ly_keys else None
            )
            return base * (1 + payload.pct / 100) if base is not None else None
        values = [shop_value(r, key) for r in week_rows.values()]
        present = [v for v in values if v is not None]
        return median(present) if present else None

    now = datetime.now(timezone.utc)
    written = 0
    shops_updated: set[str] = set()
    skipped: set[str] = set()
    for sn in shop_numbers:
        tenant_id = tenant_by_shop[sn]
        wrote_any = False
        for key in keys:
            value = value_for(sn, key)
            if value is None or value < 0:
                continue
            value = round(value, 2)
            with without_scope(session):
                existing = session.exec(
                    select(VswtReportTarget)
                    .where(VswtReportTarget.tenant_id == tenant_id)
                    .where(VswtReportTarget.shop_number == sn)
                    .where(VswtReportTarget.metric_key == key)
                ).first()
            if existing:
                existing.target_value = value
                existing.updated_at = now
                session.add(existing)
            else:
                session.add(
                    VswtReportTarget(
                        tenant_id=tenant_id,
                        shop_number=sn,
                        metric_key=key,
                        target_value=value,
                        created_by_user_id=user.id,
                        created_at=now,
                        updated_at=now,
                    )
                )
            written += 1
            wrote_any = True
        (shops_updated if wrote_any else skipped).add(sn)

    _record_event(
        session,
        parent_account_id=parent.id,
        tenant_id=None,
        actor_user_id=user.id,
        actor_email=user.email,
        event_type="region_targets_filled",
        event_summary=(
            f"Set {', '.join(keys)} targets for {len(shops_updated)} shops in {region.name} "
            f"from {strategy.replace('_', ' ')}"
            + (f" ({payload.pct:+.0f}%)" if strategy == "last_year_plus_pct" else "")
            + f", week {week}"
        ),
    )
    session.commit()
    return RegionTargetFillResponse(
        strategy=strategy,
        week=week,
        shops_updated=len(shops_updated),
        targets_written=written,
        shops_skipped_no_data=len(skipped),
    )


@router.post("/{region_id}/report/send-now")
def send_region_report_now(
    region_id: UUID,
    auth: AuthContext = Depends(get_auth_context),
    session: Session = Depends(unscoped_session),
):
    """Email the region's week to its manager right now, regardless of opt-in."""
    from ..services.regional_manager_report import send_region_report

    user, parent, region = _region_for_annotate(session, auth, region_id)
    if not (region.manager_email or "").strip():
        raise HTTPException(status_code=400, detail="This region has no manager email set")
    sent = send_region_report(session, parent=parent, region=region)
    return {"sent": sent, "to": region.manager_email}


__all__ = ["router", "build_region_cockpit"]
