"""Minit HQ parent-account operations: dashboard, cross-network reports, troubleshooting."""

from __future__ import annotations

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
    ParentMobileJobNetworkRead,
    ParentMobileJobsReport,
    ParentOperationsOverview,
    ParentShopBookingVolume,
    ParentShopBookingsReport,
    ParentTroubleshootingItem,
    ParentTroubleshootingResponse,
    ShopMobileBookingRead,
    ShopMobileBookingRequest,
    Tenant,
    User,
)
from ..shop_number import format_tenant_label, linked_tenants_for_parent
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
    tenants = _linked_tenants(session, parent.id)
    retail = [t for t in tenants if _is_retail_shop(t.plan_code)]
    operators = [t for t in tenants if _is_operator(t.plan_code)]
    retail_ids = [t.id for t in retail]
    operator_ids = [t.id for t in operators]

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

    cutoff = datetime.now(timezone.utc) - timedelta(days=30)
    shops_without_recent = 0
    for shop in retail:
        recent = session.exec(
            select(func.count())
            .select_from(ShopMobileBookingRequest)
            .where(ShopMobileBookingRequest.parent_account_id == parent.id)
            .where(ShopMobileBookingRequest.requesting_tenant_id == shop.id)
            .where(col(ShopMobileBookingRequest.created_at) >= cutoff)
        ).one()
        if int(recent) == 0:
            shops_without_recent += 1

    week_ago = datetime.now(timezone.utc) - timedelta(days=7)
    problem_bookings = int(
        session.exec(
            select(func.count())
            .select_from(ShopMobileBookingRequest)
            .where(ShopMobileBookingRequest.parent_account_id == parent.id)
            .where(ShopMobileBookingRequest.status.in_(_PROBLEM_BOOKING_STATUSES))  # type: ignore[attr-defined]
            .where(col(ShopMobileBookingRequest.created_at) >= week_ago)
        ).one()
    )

    missing_dispatch = sum(
        1 for op in operators if not (getattr(op, "mobile_dispatch_phone", None) or "").strip()
    )

    return ParentOperationsOverview(
        retail_shop_count=len(retail),
        operator_count=len(operators),
        pending_bookings=pending,
        active_mobile_jobs=active_jobs,
        shops_without_recent_booking=shops_without_recent,
        problem_bookings_7d=problem_bookings,
        operators_missing_dispatch_phone=missing_dispatch,
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
    items: list[ParentTroubleshootingItem] = []

    for op in operators:
        if not (getattr(op, "mobile_dispatch_phone", None) or "").strip():
            items.append(
                ParentTroubleshootingItem(
                    kind="operator_missing_dispatch_phone",
                    severity="warning",
                    title=f"Operator missing dispatch SMS number",
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
                title=f"Pending booking older than 7 days",
                detail=f"{row.customer_name} — {format_tenant_label(shop.name, shop.shop_number) if shop else 'Shop'}",
                tenant_id=row.requesting_tenant_id,
                tenant_slug=shop.slug if shop else None,
                related_id=row.id,
                created_at=row.created_at,
            )
        )

    cutoff = datetime.now(timezone.utc) - timedelta(days=30)
    for shop in retail:
        recent = session.exec(
            select(func.count())
            .select_from(ShopMobileBookingRequest)
            .where(ShopMobileBookingRequest.parent_account_id == parent.id)
            .where(ShopMobileBookingRequest.requesting_tenant_id == shop.id)
            .where(col(ShopMobileBookingRequest.created_at) >= cutoff)
        ).one()
        if int(recent) == 0:
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

    return ParentTroubleshootingResponse(items=items[:limit])
