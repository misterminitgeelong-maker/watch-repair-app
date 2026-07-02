"""Minit HQ parent-account operations: dashboard, cross-network reports, troubleshooting."""

from __future__ import annotations

from collections import defaultdict
from datetime import datetime, timedelta, timezone
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import or_
from sqlmodel import Session, col, func, select

from ..database import get_session
from ..dependencies import (
    AuthContext,
    PLAN_FEATURES,
    get_auth_context,
    normalize_plan_code,
    require_feature,
    require_owner,
)
from ..minit_branding import MINIT_HQ_PLAN, tenant_product
from ..minit_shops import tenant_slug_for_shop
from ..models import (
    AutoKeyJob,
    ParentAccount,
    ParentDashboardBookingSnippet,
    ParentMobileJobNetworkRead,
    ParentMobileJobsReport,
    ParentOperationsOverview,
    ParentRegionDashboardStat,
    ParentShopBookingVolume,
    ParentShopBookingsReport,
    ParentTroubleshootingItem,
    ParentTroubleshootingResponse,
    ShopMobileBookingRead,
    ShopMobileBookingRequest,
    Tenant,
    User,
)
from ..shop_number import format_tenant_label, linked_tenant_ids_for_parent, linked_tenants_for_parent
from .parent_accounts import _get_parent_account_for_user, _record_event
from .shop_mobile_bookings import (
    BOOKABLE_OPERATOR_PLAN_CODES,
    _maybe_expire_pending,
    _to_read,
)

router = APIRouter(
    prefix="/v1/parent-accounts",
    tags=["parent-operations"],
    dependencies=[Depends(require_feature("multi_site"))],
)

_AUTO_KEY_ACTIVE_STATUSES = frozenset(
    {
        "awaiting_quote",
        "awaiting_customer_details",
        "quote_sent",
        "quote_approved",
        "scheduled",
        "en_route",
        "on_site",
        "in_progress",
    }
)
_PROBLEM_BOOKING_STATUSES = frozenset({"declined", "cancelled", "expired"})
_REGION_ORDER = ("VIC", "NSW", "QLD", "SW", "NZ", "SEA")
_UNASSIGNED_REGION = "Unassigned"


def _require_minit_hq(auth: AuthContext, session: Session) -> Tenant:
    tenant = session.get(Tenant, auth.tenant_id)
    if not tenant:
        raise HTTPException(status_code=401, detail="Invalid token")
    if normalize_plan_code(auth.plan_code) != MINIT_HQ_PLAN:
        raise HTTPException(status_code=403, detail="Minit HQ plan required")
    if tenant_product(tenant.slug) != "minit":
        raise HTTPException(status_code=403, detail="Minit product required")
    return tenant


def _resolve_parent(session: Session, user: User) -> ParentAccount:
    return _get_parent_account_for_user(session, user)


def _linked_tenants(session: Session, parent_id: UUID) -> list[Tenant]:
    return linked_tenants_for_parent(session, parent_id)


def _is_retail_shop(plan_code: str) -> bool:
    plan = normalize_plan_code(plan_code)
    if plan == "booking_only":
        return True
    return "shop_mobile_booking" in PLAN_FEATURES.get(plan, set()) and plan not in BOOKABLE_OPERATOR_PLAN_CODES


def _is_operator(plan_code: str) -> bool:
    return normalize_plan_code(plan_code) in BOOKABLE_OPERATOR_PLAN_CODES


def _parse_date_range(
    from_date: str | None,
    to_date: str | None,
) -> tuple[datetime | None, datetime | None]:
    start: datetime | None = None
    end: datetime | None = None
    if from_date:
        try:
            start = datetime.fromisoformat(from_date.replace("Z", "+00:00"))
            if start.tzinfo is None:
                start = start.replace(tzinfo=timezone.utc)
        except ValueError as exc:
            raise HTTPException(status_code=400, detail="from_date must be ISO-8601") from exc
    if to_date:
        try:
            end = datetime.fromisoformat(to_date.replace("Z", "+00:00"))
            if end.tzinfo is None:
                end = end.replace(tzinfo=timezone.utc)
        except ValueError as exc:
            raise HTTPException(status_code=400, detail="to_date must be ISO-8601") from exc
    return start, end


def _region_sort_key(region: str) -> tuple[int, str]:
    try:
        idx = _REGION_ORDER.index(region)
    except ValueError:
        idx = len(_REGION_ORDER)
    return (idx, region)


def _booking_status_counts(
    session: Session,
    parent_id: UUID,
    since: datetime,
) -> dict[str, int]:
    rows = session.exec(
        select(ShopMobileBookingRequest.status, func.count())
        .where(ShopMobileBookingRequest.parent_account_id == parent_id)
        .where(col(ShopMobileBookingRequest.created_at) >= since)
        .group_by(ShopMobileBookingRequest.status)
    ).all()
    return {str(status): int(count) for status, count in rows}


def _collect_troubleshooting_items(
    session: Session,
    parent: ParentAccount,
    retail: list[Tenant],
    operators: list[Tenant],
    *,
    limit: int = 50,
    max_quiet_shops: int = 25,
) -> list[ParentTroubleshootingItem]:
    items: list[ParentTroubleshootingItem] = []

    for op in operators:
        if not (getattr(op, "mobile_dispatch_phone", None) or "").strip():
            items.append(
                ParentTroubleshootingItem(
                    kind="operator_missing_dispatch_phone",
                    severity="error",
                    title="Operator missing dispatch SMS number",
                    detail=format_tenant_label(op.name, op.shop_number),
                    tenant_id=op.id,
                    tenant_slug=op.slug,
                )
            )

    problem_rows = session.exec(
        select(ShopMobileBookingRequest)
        .where(ShopMobileBookingRequest.parent_account_id == parent.id)
        .where(ShopMobileBookingRequest.status.in_(_PROBLEM_BOOKING_STATUSES))  # type: ignore[attr-defined]
        .order_by(ShopMobileBookingRequest.created_at.desc())
        .limit(limit)
    ).all()
    for row in problem_rows:
        shop = session.get(Tenant, row.requesting_tenant_id)
        op = session.get(Tenant, row.target_operator_tenant_id)
        items.append(
            ParentTroubleshootingItem(
                kind=f"booking_{row.status}",
                severity="warning" if row.status == "declined" else "info",
                title=f"Booking {row.status}: {row.customer_name}",
                detail=(
                    f"{format_tenant_label(shop.name, shop.shop_number) if shop else 'Shop'} → "
                    f"{format_tenant_label(op.name, op.shop_number) if op else 'Operator'}"
                    + (f" — {row.decline_reason}" if row.decline_reason else "")
                ),
                tenant_id=row.requesting_tenant_id,
                tenant_slug=shop.slug if shop else None,
                related_id=row.id,
                created_at=row.created_at,
            )
        )

    week_ago = datetime.now(timezone.utc) - timedelta(days=7)
    for row in session.exec(
        select(ShopMobileBookingRequest)
        .where(ShopMobileBookingRequest.parent_account_id == parent.id)
        .where(ShopMobileBookingRequest.status == "pending")
        .where(col(ShopMobileBookingRequest.created_at) < week_ago)
        .order_by(ShopMobileBookingRequest.created_at.asc())
        .limit(20)
    ).all():
        shop = session.get(Tenant, row.requesting_tenant_id)
        items.append(
            ParentTroubleshootingItem(
                kind="booking_stale_pending",
                severity="warning",
                title="Pending booking older than 7 days",
                detail=f"{row.customer_name} — {format_tenant_label(shop.name, shop.shop_number) if shop else 'Shop'}",
                tenant_id=row.requesting_tenant_id,
                tenant_slug=shop.slug if shop else None,
                related_id=row.id,
                created_at=row.created_at,
            )
        )

    cutoff = datetime.now(timezone.utc) - timedelta(days=30)
    active_shop_ids = {
        tid
        for (tid,) in session.exec(
            select(ShopMobileBookingRequest.requesting_tenant_id)
            .where(ShopMobileBookingRequest.parent_account_id == parent.id)
            .where(col(ShopMobileBookingRequest.created_at) >= cutoff)
            .distinct()
        ).all()
    }
    quiet_shops = [shop for shop in retail if shop.id not in active_shop_ids]
    for shop in quiet_shops[:max_quiet_shops]:
        items.append(
            ParentTroubleshootingItem(
                kind="shop_no_recent_bookings",
                severity="info",
                title="No bookings in 30 days",
                detail=format_tenant_label(shop.name, shop.shop_number),
                tenant_id=shop.id,
                tenant_slug=shop.slug,
            )
        )
    if len(quiet_shops) > max_quiet_shops:
        items.append(
            ParentTroubleshootingItem(
                kind="shops_quiet_summary",
                severity="info",
                title=f"{len(quiet_shops)} shops with no bookings in 30 days",
                detail=(
                    f"Showing {max_quiet_shops} examples. "
                    "Use Shop reports or filter Shops to review the full network."
                ),
            )
        )

    operator_ids = [t.id for t in operators]
    if operator_ids:
        stuck = session.exec(
            select(AutoKeyJob)
            .where(AutoKeyJob.tenant_id.in_(operator_ids))  # type: ignore[attr-defined]
            .where(AutoKeyJob.shop_mobile_booking_request_id.isnot(None))  # type: ignore[union-attr]
            .where(AutoKeyJob.status.in_(_AUTO_KEY_ACTIVE_STATUSES))  # type: ignore[attr-defined]
            .where(col(AutoKeyJob.created_at) < datetime.now(timezone.utc) - timedelta(days=14))
            .order_by(AutoKeyJob.created_at.asc())
            .limit(20)
        ).all()
        for job in stuck:
            op = session.get(Tenant, job.tenant_id)
            items.append(
                ParentTroubleshootingItem(
                    kind="job_stuck_active",
                    severity="warning",
                    title=f"Active job open 14+ days: {job.job_number}",
                    detail=f"{job.title} — {format_tenant_label(op.name, op.shop_number) if op else 'Operator'}",
                    tenant_id=job.tenant_id,
                    tenant_slug=op.slug if op else None,
                    related_id=job.id,
                    created_at=job.created_at,
                )
            )

    def _attention_rank(item: ParentTroubleshootingItem) -> tuple[int, float]:
        severity_rank = 0 if item.severity == "warning" else 1
        ts = item.created_at.timestamp() if item.created_at else 0.0
        return (severity_rank, -ts)

    items.sort(key=_attention_rank)
    return items[:limit]


def _classify_linked_tenants(
    session: Session,
    parent_id: UUID,
) -> tuple[list[UUID], list[UUID], dict[str, int], int]:
    """Lightweight plan/region scan — avoids loading full Tenant ORM rows for every shop."""
    ids = linked_tenant_ids_for_parent(session, parent_id)
    if not ids:
        return [], [], {}, 0
    rows = session.exec(
        select(
            Tenant.id,
            Tenant.plan_code,
            Tenant.minit_region,
            Tenant.mobile_dispatch_phone,
        ).where(col(Tenant.id).in_(ids))  # type: ignore[attr-defined]
    ).all()
    retail_ids: list[UUID] = []
    operator_ids: list[UUID] = []
    region_shops: dict[str, int] = defaultdict(int)
    missing_dispatch = 0
    for tid, plan_code, region, phone in rows:
        if _is_retail_shop(plan_code):
            retail_ids.append(tid)
            reg = (region or "").strip() or _UNASSIGNED_REGION
            region_shops[reg] += 1
        elif _is_operator(plan_code):
            operator_ids.append(tid)
            if not (phone or "").strip():
                missing_dispatch += 1
    return retail_ids, operator_ids, dict(region_shops), missing_dispatch


def _region_dashboard_stats(
    session: Session,
    parent_id: UUID,
    region_shops: dict[str, int],
    since_30d: datetime,
) -> list[ParentRegionDashboardStat]:
    booking_rows = session.exec(
        select(
            Tenant.minit_region,
            ShopMobileBookingRequest.status,
            func.count(),
        )
        .join(Tenant, ShopMobileBookingRequest.requesting_tenant_id == Tenant.id)
        .where(ShopMobileBookingRequest.parent_account_id == parent_id)
        .where(col(ShopMobileBookingRequest.created_at) >= since_30d)
        .group_by(Tenant.minit_region, ShopMobileBookingRequest.status)
    ).all()

    active_rows = session.exec(
        select(
            Tenant.minit_region,
            func.count(func.distinct(ShopMobileBookingRequest.requesting_tenant_id)),
        )
        .join(Tenant, ShopMobileBookingRequest.requesting_tenant_id == Tenant.id)
        .where(ShopMobileBookingRequest.parent_account_id == parent_id)
        .where(col(ShopMobileBookingRequest.created_at) >= since_30d)
        .group_by(Tenant.minit_region)
    ).all()

    bookings_30d: dict[str, int] = defaultdict(int)
    pending: dict[str, int] = defaultdict(int)
    active_shops: dict[str, int] = defaultdict(int)

    for region_raw, status, count in booking_rows:
        region = (region_raw or "").strip() or _UNASSIGNED_REGION
        bookings_30d[region] += int(count)
        if status == "pending":
            pending[region] += int(count)

    for region_raw, count in active_rows:
        region = (region_raw or "").strip() or _UNASSIGNED_REGION
        active_shops[region] = int(count)

    regions = set(region_shops) | set(bookings_30d) | set(active_shops)
    stats = [
        ParentRegionDashboardStat(
            region=region,
            shop_count=region_shops.get(region, 0),
            bookings_30d=bookings_30d.get(region, 0),
            pending=pending.get(region, 0),
            active_shops_30d=active_shops.get(region, 0),
        )
        for region in regions
    ]
    stats.sort(key=lambda s: _region_sort_key(s.region))
    return stats


def _recent_booking_snippets(
    session: Session,
    parent_id: UUID,
    *,
    limit: int = 8,
) -> list[ParentDashboardBookingSnippet]:
    rows = session.exec(
        select(ShopMobileBookingRequest)
        .where(ShopMobileBookingRequest.parent_account_id == parent_id)
        .order_by(ShopMobileBookingRequest.created_at.desc())
        .limit(limit)
    ).all()
    if not rows:
        return []
    tenant_ids = list(
        dict.fromkeys(
            [row.requesting_tenant_id for row in rows]
            + [row.target_operator_tenant_id for row in rows]
        )
    )
    tenants_by_id = {
        t.id: t
        for t in session.exec(select(Tenant).where(col(Tenant.id).in_(tenant_ids))).all()
    }
    snippets: list[ParentDashboardBookingSnippet] = []
    for row in rows:
        shop = tenants_by_id.get(row.requesting_tenant_id)
        op = tenants_by_id.get(row.target_operator_tenant_id)
        snippets.append(
            ParentDashboardBookingSnippet(
                id=row.id,
                customer_name=row.customer_name,
                status=row.status,
                requesting_shop_name=shop.name if shop else "Shop",
                requesting_shop_number=shop.shop_number if shop else None,
                target_operator_name=op.name if op else "Operator",
                region=((shop.minit_region or "").strip() or None) if shop else None,
                area=((shop.minit_area or "").strip() or None) if shop else None,
                created_at=row.created_at,
            )
        )
    return snippets


@router.get("/me/operations/overview", response_model=ParentOperationsOverview)
def get_operations_overview(
    auth: AuthContext = Depends(get_auth_context),
    session: Session = Depends(get_session),
):
    _require_minit_hq(auth, session)
    user = session.get(User, auth.user_id)
    if not user or not user.is_active:
        raise HTTPException(status_code=401, detail="Invalid token")
    parent = _resolve_parent(session, user)
    retail_ids, operator_ids, region_shop_counts, missing_dispatch = _classify_linked_tenants(
        session, parent.id
    )
    operators = (
        session.exec(select(Tenant).where(col(Tenant.id).in_(operator_ids))).all()  # type: ignore[attr-defined]
        if operator_ids
        else []
    )

    pending = int(
        session.exec(
            select(func.count())
            .select_from(ShopMobileBookingRequest)
            .where(ShopMobileBookingRequest.parent_account_id == parent.id)
            .where(ShopMobileBookingRequest.status == "pending")
        ).one()
    )

    active_jobs = 0
    if operator_ids:
        active_jobs = int(
            session.exec(
                select(func.count())
                .select_from(AutoKeyJob)
                .where(AutoKeyJob.tenant_id.in_(operator_ids))  # type: ignore[attr-defined]
                .where(
                    or_(
                        AutoKeyJob.referring_shop_tenant_id.in_(retail_ids),  # type: ignore[attr-defined]
                        AutoKeyJob.shop_mobile_booking_request_id.isnot(None),  # type: ignore[union-attr]
                    )
                )
                .where(AutoKeyJob.status.in_(_AUTO_KEY_ACTIVE_STATUSES))  # type: ignore[attr-defined]
            ).one()
        )

    now = datetime.now(timezone.utc)
    cutoff_30d = now - timedelta(days=30)
    week_ago = now - timedelta(days=7)

    active_shop_ids = {
        tid
        for (tid,) in session.exec(
            select(ShopMobileBookingRequest.requesting_tenant_id)
            .where(ShopMobileBookingRequest.parent_account_id == parent.id)
            .where(col(ShopMobileBookingRequest.created_at) >= cutoff_30d)
            .distinct()
        ).all()
    }
    retail_id_set = set(retail_ids)
    active_retail = active_shop_ids & retail_id_set
    shops_without_recent = len(retail_ids) - len(active_retail)

    problem_bookings = int(
        session.exec(
            select(func.count())
            .select_from(ShopMobileBookingRequest)
            .where(ShopMobileBookingRequest.parent_account_id == parent.id)
            .where(ShopMobileBookingRequest.status.in_(_PROBLEM_BOOKING_STATUSES))  # type: ignore[attr-defined]
            .where(col(ShopMobileBookingRequest.created_at) >= week_ago)
        ).one()
    )

    stale_pending = int(
        session.exec(
            select(func.count())
            .select_from(ShopMobileBookingRequest)
            .where(ShopMobileBookingRequest.parent_account_id == parent.id)
            .where(ShopMobileBookingRequest.status == "pending")
            .where(col(ShopMobileBookingRequest.created_at) < week_ago)
        ).one()
    )

    counts_7d = _booking_status_counts(session, parent.id, week_ago)
    counts_30d = _booking_status_counts(session, parent.id, cutoff_30d)
    bookings_7d = sum(counts_7d.values())
    accepted_7d = counts_7d.get("accepted", 0)
    declined_7d = counts_7d.get("declined", 0)
    resolved_7d = accepted_7d + declined_7d + counts_7d.get("cancelled", 0) + counts_7d.get("expired", 0)
    acceptance_rate_7d = round(accepted_7d / resolved_7d * 100, 1) if resolved_7d else None

    attention_items = _collect_troubleshooting_items(
        session, parent, [], operators, limit=12, max_quiet_shops=0
    )
    if shops_without_recent > 0 and not any(i.kind == "shops_quiet_summary" for i in attention_items):
        attention_items.append(
            ParentTroubleshootingItem(
                kind="shops_quiet_summary",
                severity="info",
                title=f"{shops_without_recent} shops with no bookings in 30 days",
                detail="See Shop reports for adoption across the network.",
            )
        )
        attention_items = attention_items[:12]

    return ParentOperationsOverview(
        retail_shop_count=len(retail_ids),
        operator_count=len(operator_ids),
        pending_bookings=pending,
        active_mobile_jobs=active_jobs,
        shops_without_recent_booking=shops_without_recent,
        problem_bookings_7d=problem_bookings,
        operators_missing_dispatch_phone=missing_dispatch,
        bookings_7d=bookings_7d,
        accepted_7d=accepted_7d,
        declined_7d=declined_7d,
        bookings_30d=sum(counts_30d.values()),
        accepted_30d=counts_30d.get("accepted", 0),
        stale_pending_count=stale_pending,
        acceptance_rate_7d=acceptance_rate_7d,
        region_stats=_region_dashboard_stats(session, parent.id, region_shop_counts, cutoff_30d),
        recent_bookings=_recent_booking_snippets(session, parent.id),
        attention_items=attention_items,
    )


@router.get("/me/operations/bookings", response_model=ParentShopBookingsReport)
def get_operations_bookings_report(
    from_date: str | None = Query(default=None, description="ISO-8601 start (inclusive)"),
    to_date: str | None = Query(default=None, description="ISO-8601 end (inclusive)"),
    status: str | None = Query(default=None),
    shop_tenant_id: UUID | None = Query(default=None),
    limit: int = Query(default=100, ge=1, le=500),
    auth: AuthContext = Depends(get_auth_context),
    session: Session = Depends(get_session),
):
    _require_minit_hq(auth, session)
    user = session.get(User, auth.user_id)
    if not user or not user.is_active:
        raise HTTPException(status_code=401, detail="Invalid token")
    parent = _resolve_parent(session, user)
    start, end = _parse_date_range(from_date, to_date)

    stmt = (
        select(ShopMobileBookingRequest)
        .where(ShopMobileBookingRequest.parent_account_id == parent.id)
        .order_by(ShopMobileBookingRequest.created_at.desc())
    )
    if start is not None:
        stmt = stmt.where(col(ShopMobileBookingRequest.created_at) >= start)
    if end is not None:
        stmt = stmt.where(col(ShopMobileBookingRequest.created_at) <= end)
    if status:
        stmt = stmt.where(ShopMobileBookingRequest.status == status.strip().lower())
    if shop_tenant_id is not None:
        stmt = stmt.where(ShopMobileBookingRequest.requesting_tenant_id == shop_tenant_id)

    rows = session.exec(stmt.limit(limit)).all()
    expired_any = False
    reads: list[ShopMobileBookingRead] = []
    for row in rows:
        if _maybe_expire_pending(session, row):
            expired_any = True
        reads.append(_to_read(session, row))
    if expired_any:
        session.commit()

    by_shop: dict[UUID, ParentShopBookingVolume] = {}
    totals = ParentShopBookingVolume(
        tenant_id=parent.id,
        tenant_name="Network total",
        total=0,
        pending=0,
        accepted=0,
        declined=0,
        cancelled=0,
        expired=0,
    )

    def bump(vol: ParentShopBookingVolume, st: str) -> None:
        vol.total += 1
        if st == "pending":
            vol.pending += 1
        elif st == "accepted":
            vol.accepted += 1
        elif st == "declined":
            vol.declined += 1
        elif st == "cancelled":
            vol.cancelled += 1
        elif st == "expired":
            vol.expired += 1

    for row in rows:
        shop = session.get(Tenant, row.requesting_tenant_id)
        if not shop:
            continue
        if row.requesting_tenant_id not in by_shop:
            by_shop[row.requesting_tenant_id] = ParentShopBookingVolume(
                tenant_id=shop.id,
                tenant_name=shop.name,
                shop_number=shop.shop_number,
                area=shop.minit_area,
                region=shop.minit_region,
                total=0,
                pending=0,
                accepted=0,
                declined=0,
                cancelled=0,
                expired=0,
            )
        bump(by_shop[row.requesting_tenant_id], row.status)
        bump(totals, row.status)

    return ParentShopBookingsReport(
        from_date=start,
        to_date=end,
        totals=totals,
        by_shop=sorted(by_shop.values(), key=lambda s: s.tenant_name.lower()),
        bookings=reads,
    )


@router.get("/me/operations/mobile-jobs", response_model=ParentMobileJobsReport)
def get_operations_mobile_jobs_report(
    from_date: str | None = Query(default=None),
    to_date: str | None = Query(default=None),
    status: str | None = Query(default=None),
    operator_tenant_id: UUID | None = Query(default=None),
    limit: int = Query(default=100, ge=1, le=500),
    auth: AuthContext = Depends(get_auth_context),
    session: Session = Depends(get_session),
):
    _require_minit_hq(auth, session)
    user = session.get(User, auth.user_id)
    if not user or not user.is_active:
        raise HTTPException(status_code=401, detail="Invalid token")
    parent = _resolve_parent(session, user)
    tenants = _linked_tenants(session, parent.id)
    retail_ids = [t.id for t in tenants if _is_retail_shop(t.plan_code)]
    operator_ids = [t.id for t in tenants if _is_operator(t.plan_code)]
    if not operator_ids:
        return ParentMobileJobsReport(from_date=None, to_date=None, active_count=0, total_count=0, jobs=[])

    start, end = _parse_date_range(from_date, to_date)
    stmt = (
        select(AutoKeyJob)
        .where(AutoKeyJob.tenant_id.in_(operator_ids))  # type: ignore[attr-defined]
        .where(
            or_(
                AutoKeyJob.referring_shop_tenant_id.in_(retail_ids),  # type: ignore[attr-defined]
                AutoKeyJob.shop_mobile_booking_request_id.isnot(None),  # type: ignore[union-attr]
            )
        )
        .order_by(AutoKeyJob.created_at.desc())
    )
    if start is not None:
        stmt = stmt.where(col(AutoKeyJob.created_at) >= start)
    if end is not None:
        stmt = stmt.where(col(AutoKeyJob.created_at) <= end)
    if status:
        stmt = stmt.where(AutoKeyJob.status == status.strip().lower())
    if operator_tenant_id is not None:
        stmt = stmt.where(AutoKeyJob.tenant_id == operator_tenant_id)

    rows = session.exec(stmt.limit(limit)).all()
    active_count = sum(1 for j in rows if j.status in _AUTO_KEY_ACTIVE_STATUSES)
    jobs: list[ParentMobileJobNetworkRead] = []
    for job in rows:
        op = session.get(Tenant, job.tenant_id)
        ref_shop = (
            session.get(Tenant, job.referring_shop_tenant_id) if job.referring_shop_tenant_id else None
        )
        jobs.append(
            ParentMobileJobNetworkRead(
                id=job.id,
                job_number=job.job_number,
                status=job.status,
                title=job.title,
                operator_tenant_id=job.tenant_id,
                operator_name=op.name if op else "Unknown",
                operator_shop_number=op.shop_number if op else None,
                referring_shop_tenant_id=job.referring_shop_tenant_id,
                referring_shop_name=ref_shop.name if ref_shop else None,
                referring_shop_number=ref_shop.shop_number if ref_shop else None,
                shop_mobile_booking_request_id=job.shop_mobile_booking_request_id,
                scheduled_at=job.scheduled_at,
                created_at=job.created_at,
            )
        )

    return ParentMobileJobsReport(
        from_date=start,
        to_date=end,
        active_count=active_count,
        total_count=len(jobs),
        jobs=jobs,
    )


@router.get("/me/operations/troubleshooting", response_model=ParentTroubleshootingResponse)
def get_operations_troubleshooting(
    limit: int = Query(default=50, ge=1, le=200),
    auth: AuthContext = Depends(get_auth_context),
    session: Session = Depends(get_session),
):
    _require_minit_hq(auth, session)
    user = session.get(User, auth.user_id)
    if not user or not user.is_active:
        raise HTTPException(status_code=401, detail="Invalid token")
    parent = _resolve_parent(session, user)
    tenants = _linked_tenants(session, parent.id)
    retail = [t for t in tenants if _is_retail_shop(t.plan_code)]
    operators = [t for t in tenants if _is_operator(t.plan_code)]
    items = _collect_troubleshooting_items(session, parent, retail, operators, limit=limit)
    return ParentTroubleshootingResponse(items=items)
