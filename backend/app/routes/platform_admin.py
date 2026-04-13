from datetime import datetime, timedelta, timezone
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlmodel import Session, func, select

from ..database import get_session
from ..dependencies import require_platform_admin
from ..models import (
    AutoKeyJob,
    Invoice,
    PlatformEnterShopResponse,
    PlatformTenantRead,
    PlatformUserRead,
    RepairJob,
    ShoeRepairJob,
    Tenant,
    TenantEventLog,
    TenantEventLogRead,
    User,
)
from ..security import create_access_token, create_refresh_token

router = APIRouter(prefix="/v1/platform-admin", tags=["platform-admin"])


@router.get("/users", response_model=list[PlatformUserRead])
def list_all_users(
    _: object = Depends(require_platform_admin),
    session: Session = Depends(get_session),
):
    rows = session.exec(
        select(User, Tenant)
        .join(Tenant, Tenant.id == User.tenant_id)
        .order_by(Tenant.slug, User.created_at)
    ).all()

    return [
        PlatformUserRead(
            id=user.id,
            tenant_id=user.tenant_id,
            tenant_slug=tenant.slug,
            tenant_name=tenant.name,
            email=user.email,
            full_name=user.full_name,
            role=user.role,
            is_active=user.is_active,
        )
        for user, tenant in rows
    ]


@router.get("/tenants", response_model=list[PlatformTenantRead])
def list_all_tenants(
    _: object = Depends(require_platform_admin),
    session: Session = Depends(get_session),
):
    tenants = session.exec(select(Tenant).order_by(Tenant.name)).all()

    # Count users per tenant with a simple per-tenant query to avoid SQLModel aggregation issues
    user_counts: dict[UUID, int] = {}
    for t in tenants:
        user_counts[t.id] = session.exec(
            select(func.count(User.id)).where(User.tenant_id == t.id)
        ).one()

    return [
        PlatformTenantRead(
            id=t.id,
            slug=t.slug,
            name=t.name,
            plan_code=t.plan_code,
            user_count=user_counts.get(t.id, 0),
            created_at=t.created_at,
        )
        for t in tenants
    ]


@router.post("/enter-shop/{tenant_id}", response_model=PlatformEnterShopResponse)
def enter_shop(
    tenant_id: UUID,
    auth: object = Depends(require_platform_admin),
    session: Session = Depends(get_session),
):
    """Issue a platform_admin-scoped token for any tenant, allowing the admin to
    view and manage that shop's data as if they were the owner."""
    tenant = session.get(Tenant, tenant_id)
    if not tenant:
        raise HTTPException(status_code=404, detail="Shop not found.")

    # Find first active owner in the target tenant to anchor the user_id
    owner = session.exec(
        select(User)
        .where(User.tenant_id == tenant_id)
        .where(User.role == "owner")
        .where(User.is_active == True)  # noqa: E712
        .order_by(User.created_at)
    ).first()
    if not owner:
        raise HTTPException(status_code=400, detail="This shop has no active owner account.")

    # Issue tokens with platform_admin role but scoped to the target tenant
    access_token, expires = create_access_token(tenant_id, owner.id, "platform_admin")
    refresh_token, refresh_expires = create_refresh_token(tenant_id, owner.id, "platform_admin")

    return PlatformEnterShopResponse(
        access_token=access_token,
        refresh_token=refresh_token,
        expires_in_seconds=expires,
        refresh_expires_in_seconds=refresh_expires,
        tenant_id=tenant_id,
        tenant_name=tenant.name,
    )


@router.get("/activity", response_model=list[TenantEventLogRead])
def list_platform_activity(
    limit: int = Query(default=100, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
    _: object = Depends(require_platform_admin),
    session: Session = Depends(get_session),
):
    rows = session.exec(
        select(TenantEventLog)
        .order_by(TenantEventLog.created_at.desc())
        .offset(offset)
        .limit(limit)
    ).all()
    return [
        TenantEventLogRead(
            id=row.id,
            tenant_id=row.tenant_id,
            actor_user_id=row.actor_user_id,
            actor_email=row.actor_email,
            entity_type=row.entity_type,
            entity_id=row.entity_id,
            event_type=row.event_type,
            event_summary=row.event_summary,
            created_at=row.created_at,
        )
        for row in rows
    ]


@router.get("/reports")
def get_platform_reports(
    _: object = Depends(require_platform_admin),
    session: Session = Depends(get_session),
):
    tenants = session.exec(select(Tenant).order_by(Tenant.name)).all()
    thirty_days_ago = datetime.now(timezone.utc) - timedelta(days=30)

    rows: list[dict] = []
    totals = {
        "tenants": len(tenants),
        "users": 0,
        "active_users": 0,
        "repair_jobs": 0,
        "shoe_jobs": 0,
        "auto_key_jobs": 0,
        "invoices": 0,
        "paid_invoices": 0,
        "billed_total_cents": 0,
        "paid_total_cents": 0,
        "jobs_last_30_days": 0,
        "invoices_last_30_days": 0,
    }

    for tenant in tenants:
        users = int(session.exec(select(func.count(User.id)).where(User.tenant_id == tenant.id)).one())
        active_users = int(
            session.exec(
                select(func.count(User.id))
                .where(User.tenant_id == tenant.id)
                .where(User.is_active == True)  # noqa: E712
            ).one()
        )
        repair_jobs = int(session.exec(select(func.count(RepairJob.id)).where(RepairJob.tenant_id == tenant.id)).one())
        shoe_jobs = int(session.exec(select(func.count(ShoeRepairJob.id)).where(ShoeRepairJob.tenant_id == tenant.id)).one())
        auto_key_jobs = int(session.exec(select(func.count(AutoKeyJob.id)).where(AutoKeyJob.tenant_id == tenant.id)).one())
        invoices = int(session.exec(select(func.count(Invoice.id)).where(Invoice.tenant_id == tenant.id)).one())
        paid_invoices = int(
            session.exec(
                select(func.count(Invoice.id))
                .where(Invoice.tenant_id == tenant.id)
                .where(Invoice.status == "paid")
            ).one()
        )
        billed_total_cents = int(
            session.exec(
                select(func.coalesce(func.sum(Invoice.total_cents), 0))
                .where(Invoice.tenant_id == tenant.id)
            ).one()
        )
        paid_total_cents = int(
            session.exec(
                select(func.coalesce(func.sum(Invoice.total_cents), 0))
                .where(Invoice.tenant_id == tenant.id)
                .where(Invoice.status == "paid")
            ).one()
        )
        # Count last-30 jobs separately to avoid cross-join inflation.
        jobs_last_30_days = int(session.exec(select(func.count(RepairJob.id)).where(RepairJob.tenant_id == tenant.id).where(RepairJob.created_at >= thirty_days_ago)).one()) \
            + int(session.exec(select(func.count(ShoeRepairJob.id)).where(ShoeRepairJob.tenant_id == tenant.id).where(ShoeRepairJob.created_at >= thirty_days_ago)).one()) \
            + int(session.exec(select(func.count(AutoKeyJob.id)).where(AutoKeyJob.tenant_id == tenant.id).where(AutoKeyJob.created_at >= thirty_days_ago)).one())
        invoices_last_30_days = int(
            session.exec(
                select(func.count(Invoice.id))
                .where(Invoice.tenant_id == tenant.id)
                .where(Invoice.created_at >= thirty_days_ago)
            ).one()
        )
        last_activity_at = session.exec(
            select(TenantEventLog.created_at)
            .where(TenantEventLog.tenant_id == tenant.id)
            .order_by(TenantEventLog.created_at.desc())
            .limit(1)
        ).first()

        rows.append({
            "tenant_id": str(tenant.id),
            "tenant_name": tenant.name,
            "tenant_slug": tenant.slug,
            "plan_code": tenant.plan_code,
            "users": users,
            "active_users": active_users,
            "repair_jobs": repair_jobs,
            "shoe_jobs": shoe_jobs,
            "auto_key_jobs": auto_key_jobs,
            "jobs_total": repair_jobs + shoe_jobs + auto_key_jobs,
            "jobs_last_30_days": jobs_last_30_days,
            "invoices": invoices,
            "paid_invoices": paid_invoices,
            "invoices_last_30_days": invoices_last_30_days,
            "billed_total_cents": billed_total_cents,
            "paid_total_cents": paid_total_cents,
            "last_activity_at": last_activity_at,
        })

        totals["users"] += users
        totals["active_users"] += active_users
        totals["repair_jobs"] += repair_jobs
        totals["shoe_jobs"] += shoe_jobs
        totals["auto_key_jobs"] += auto_key_jobs
        totals["invoices"] += invoices
        totals["paid_invoices"] += paid_invoices
        totals["billed_total_cents"] += billed_total_cents
        totals["paid_total_cents"] += paid_total_cents
        totals["jobs_last_30_days"] += jobs_last_30_days
        totals["invoices_last_30_days"] += invoices_last_30_days

    rows.sort(key=lambda r: r["jobs_total"], reverse=True)

    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "totals": totals,
        "tenants": rows,
    }
