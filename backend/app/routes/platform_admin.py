from datetime import datetime, timedelta, timezone
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import text
from sqlmodel import Session, func, select

from ..database import get_session
from ..dependencies import AuthContext, require_platform_admin
from ..models import (
    AutoKeyJob,
    Invoice,
    PlatformEnterShopResponse,
    PlatformTenantForceLogoutRequest,
    PlatformTenantPlanUpdateRequest,
    PlatformTenantStatusUpdateRequest,
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
            is_active=t.is_active,
            signup_payment_pending=t.signup_payment_pending,
            user_count=user_counts.get(t.id, 0),
            created_at=t.created_at,
        )
        for t in tenants
    ]


@router.post("/enter-shop/{tenant_id}", response_model=PlatformEnterShopResponse)
def enter_shop(
    tenant_id: UUID,
    auth: AuthContext = Depends(require_platform_admin),
    session: Session = Depends(get_session),
):
    """Issue a platform_admin-scoped token for any tenant, allowing the admin to
    view and manage that shop's data as if they were the owner."""
    tenant = session.get(Tenant, tenant_id)
    if not tenant:
        raise HTTPException(status_code=404, detail="Shop not found.")
    admin = session.get(User, auth.user_id)
    admin_email = admin.email if admin else "platform_admin"

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

    session.add(
        TenantEventLog(
            tenant_id=tenant_id,
            actor_user_id=auth.user_id,
            actor_email=admin_email,
            entity_type="session",
            entity_id=owner.id,
            event_type="platform_admin_enter_shop",
            event_summary=f"Platform admin entered shop '{tenant.slug}'",
        )
    )
    session.commit()

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


@router.patch("/tenants/{tenant_id}/status", response_model=PlatformTenantRead)
def set_tenant_status(
    tenant_id: UUID,
    payload: PlatformTenantStatusUpdateRequest,
    auth: AuthContext = Depends(require_platform_admin),
    session: Session = Depends(get_session),
):
    tenant = session.get(Tenant, tenant_id)
    if not tenant:
        raise HTTPException(status_code=404, detail="Shop not found.")
    admin = session.get(User, auth.user_id)
    admin_email = admin.email if admin else "platform_admin"
    reason = (payload.reason or "").strip()

    tenant.is_active = bool(payload.is_active)
    if not tenant.is_active:
        tenant.auth_revoked_at = datetime.now(timezone.utc)
    session.add(tenant)
    session.add(
        TenantEventLog(
            tenant_id=tenant_id,
            actor_user_id=auth.user_id,
            actor_email=admin_email,
            entity_type="tenant",
            entity_id=tenant_id,
            event_type="platform_admin_tenant_status",
            event_summary=f"Platform admin set tenant active={tenant.is_active}. Reason: {reason or 'n/a'}",
        )
    )
    session.commit()

    user_count = int(session.exec(select(func.count(User.id)).where(User.tenant_id == tenant.id)).one())
    return PlatformTenantRead(
        id=tenant.id,
        slug=tenant.slug,
        name=tenant.name,
        plan_code=tenant.plan_code,
        is_active=tenant.is_active,
        signup_payment_pending=tenant.signup_payment_pending,
        user_count=user_count,
        created_at=tenant.created_at,
    )


@router.patch("/tenants/{tenant_id}/plan", response_model=PlatformTenantRead)
def set_tenant_plan(
    tenant_id: UUID,
    payload: PlatformTenantPlanUpdateRequest,
    auth: AuthContext = Depends(require_platform_admin),
    session: Session = Depends(get_session),
):
    tenant = session.get(Tenant, tenant_id)
    if not tenant:
        raise HTTPException(status_code=404, detail="Shop not found.")
    admin = session.get(User, auth.user_id)
    admin_email = admin.email if admin else "platform_admin"
    old_plan = tenant.plan_code
    tenant.plan_code = payload.plan_code.strip()
    session.add(tenant)
    session.add(
        TenantEventLog(
            tenant_id=tenant_id,
            actor_user_id=auth.user_id,
            actor_email=admin_email,
            entity_type="tenant",
            entity_id=tenant_id,
            event_type="platform_admin_plan_changed",
            event_summary=f"Platform admin changed plan from '{old_plan}' to '{tenant.plan_code}'. Reason: {(payload.reason or '').strip() or 'n/a'}",
        )
    )
    session.commit()
    user_count = int(session.exec(select(func.count(User.id)).where(User.tenant_id == tenant.id)).one())
    return PlatformTenantRead(
        id=tenant.id,
        slug=tenant.slug,
        name=tenant.name,
        plan_code=tenant.plan_code,
        is_active=tenant.is_active,
        signup_payment_pending=tenant.signup_payment_pending,
        user_count=user_count,
        created_at=tenant.created_at,
    )


@router.post("/tenants/{tenant_id}/mark-paid", response_model=PlatformTenantRead)
def mark_tenant_paid(
    tenant_id: UUID,
    auth: AuthContext = Depends(require_platform_admin),
    session: Session = Depends(get_session),
):
    """Clear signup_payment_pending — use for testers/accounts paid outside Stripe."""
    tenant = session.get(Tenant, tenant_id)
    if not tenant:
        raise HTTPException(status_code=404, detail="Shop not found.")
    admin = session.get(User, auth.user_id)
    admin_email = admin.email if admin else "platform_admin"
    tenant.signup_payment_pending = False
    if not tenant.subscription_status:
        tenant.subscription_status = "active"
    session.add(tenant)
    session.add(
        TenantEventLog(
            tenant_id=tenant_id,
            actor_user_id=auth.user_id,
            actor_email=admin_email,
            entity_type="tenant",
            entity_id=tenant_id,
            event_type="platform_admin_marked_paid",
            event_summary="Platform admin manually marked account as paid.",
        )
    )
    session.commit()
    user_count = int(session.exec(select(func.count(User.id)).where(User.tenant_id == tenant.id)).one())
    return PlatformTenantRead(
        id=tenant.id,
        slug=tenant.slug,
        name=tenant.name,
        plan_code=tenant.plan_code,
        is_active=tenant.is_active,
        signup_payment_pending=tenant.signup_payment_pending,
        user_count=user_count,
        created_at=tenant.created_at,
    )


@router.post("/tenants/{tenant_id}/force-logout")
def force_tenant_logout(
    tenant_id: UUID,
    payload: PlatformTenantForceLogoutRequest,
    auth: AuthContext = Depends(require_platform_admin),
    session: Session = Depends(get_session),
):
    tenant = session.get(Tenant, tenant_id)
    if not tenant:
        raise HTTPException(status_code=404, detail="Shop not found.")
    admin = session.get(User, auth.user_id)
    admin_email = admin.email if admin else "platform_admin"
    reason = (payload.reason or "").strip()

    tenant.auth_revoked_at = datetime.now(timezone.utc)
    session.add(tenant)
    session.add(
        TenantEventLog(
            tenant_id=tenant_id,
            actor_user_id=auth.user_id,
            actor_email=admin_email,
            entity_type="session",
            entity_id=tenant_id,
            event_type="platform_admin_force_logout",
            event_summary=f"Platform admin forced logout for tenant users. Reason: {reason or 'n/a'}",
        )
    )
    session.commit()
    return {"ok": True, "tenant_id": str(tenant_id), "auth_revoked_at": tenant.auth_revoked_at}


@router.delete("/tenants/{tenant_id}", status_code=204)
def delete_platform_tenant(
    tenant_id: UUID,
    auth: AuthContext = Depends(require_platform_admin),
    session: Session = Depends(get_session),
):
    tenant = session.get(Tenant, tenant_id)
    if not tenant:
        raise HTTPException(status_code=404, detail="Shop not found.")

    tid = str(tenant_id)
    try:
        # Null out optional cross-tenant references on shared tables
        session.execute(text("UPDATE intakejob SET claimed_by_tenant_id = NULL WHERE claimed_by_tenant_id = :tid"), {"tid": tid})
        session.execute(text("UPDATE intakejob SET resulting_job_id = NULL WHERE resulting_job_id IN (SELECT id FROM autokeyjob WHERE tenant_id = :tid)"), {"tid": tid})
        session.execute(text("UPDATE parentaccounteventlog SET tenant_id = NULL WHERE tenant_id = :tid"), {"tid": tid})

        # Delete tables that have no tenant_id but FK into tenant-owned tables
        session.execute(text("DELETE FROM importlogdetail WHERE import_log_id IN (SELECT id FROM importlog WHERE tenant_id = :tid)"), {"tid": tid})
        session.execute(text("DELETE FROM shoerepairjobshoe WHERE shoe_repair_job_id IN (SELECT id FROM shoerepairjob WHERE tenant_id = :tid)"), {"tid": tid})
        session.execute(text("DELETE FROM shoerepairjobitem WHERE shoe_repair_job_id IN (SELECT id FROM shoerepairjob WHERE tenant_id = :tid)"), {"tid": tid})
        session.execute(text("DELETE FROM shoejobstatushistory WHERE shoe_repair_job_id IN (SELECT id FROM shoerepairjob WHERE tenant_id = :tid)"), {"tid": tid})

        # Delete tenant-owned tables in reverse FK dependency order
        for tbl in [
            "pointsledger",              # → customerloyalty, invoice
            "autokeyquotelineitem",      # → autokeyquote
            "stocktakeline",             # → stocktakesession, stockitem
            "stockadjustment",           # → stockitem, stocktakesession
            "customeraccountinvoiceline",# → customeraccountinvoice
            "payment",                   # → invoice
            "quotelineitem",             # → quote
            "approval",                  # → quote
            "autokeyinvoice",            # → autokeyjob, autokeyquote
            "autokeyquote",              # → autokeyjob
            "invoice",                   # → repairjob, quote
            "invoicenumbercounter",
            "quote",                     # → repairjob
            "jobstatushistory",          # → repairjob
            "worklog",                   # → repairjob
            "attachment",                # → repairjob, watch, shoerepairjob, autokeyjob
            "repairqueuedaystate",
            "repairjobnumbercounter",
            "smslog",
            "autokeyjob",
            "repairjob",                 # → watch, customeraccount
            "shoerepairjob",             # → shoe
            "shoe",
            "watch",                     # → customer
            "customerloyalty",           # → customer
            "customeraccountinvoice",    # → customeraccount
            "customeraccountmembership",
            "customeraccount",
            "stocktakesession",
            "stockitem",
            "customerorder",
            "importlog",
            "customservice",
            "tenanteventlog",
            "parentaccountmembership",
            "customer",
            "user",
        ]:
            session.execute(text(f"DELETE FROM {tbl} WHERE tenant_id = :tid"), {"tid": tid})  # noqa: S608

        # MobileSuburbRoute uses target_tenant_id instead of tenant_id
        session.execute(text("DELETE FROM mobilesuburbroute WHERE target_tenant_id = :tid"), {"tid": tid})

        session.execute(text("DELETE FROM tenant WHERE id = :tid"), {"tid": tid})
        session.commit()
    except Exception as exc:
        session.rollback()
        raise HTTPException(status_code=500, detail=f"Delete failed — {exc}")


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
        "health": {
            "active_tenants": 0,
            "suspended_tenants": 0,
            "tenants_no_activity_7_days": 0,
            "tenants_no_jobs_30_days": 0,
            "tenants_no_active_users": 0,
        },
    }
    seven_days_ago = datetime.now(timezone.utc) - timedelta(days=7)

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
        logins_last_7_days = int(
            session.exec(
                select(func.count(TenantEventLog.id))
                .where(TenantEventLog.tenant_id == tenant.id)
                .where(TenantEventLog.event_type == "login")
                .where(TenantEventLog.created_at >= seven_days_ago)
            ).one()
        )
        days_since_activity = None
        if isinstance(last_activity_at, datetime):
            normalized_last_activity = (
                last_activity_at
                if last_activity_at.tzinfo is not None
                else last_activity_at.replace(tzinfo=timezone.utc)
            )
            days_since_activity = max(0, int((datetime.now(timezone.utc) - normalized_last_activity).days))
        health_status = "healthy"
        if not tenant.is_active:
            health_status = "suspended"
        elif active_users == 0 or jobs_last_30_days == 0 or (days_since_activity is not None and days_since_activity > 7):
            health_status = "attention"

        rows.append({
            "tenant_id": str(tenant.id),
            "tenant_name": tenant.name,
            "tenant_slug": tenant.slug,
            "plan_code": tenant.plan_code,
            "is_active": tenant.is_active,
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
            "logins_last_7_days": logins_last_7_days,
            "days_since_activity": days_since_activity,
            "health_status": health_status,
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
        if tenant.is_active:
            totals["health"]["active_tenants"] += 1
        else:
            totals["health"]["suspended_tenants"] += 1
        if active_users == 0:
            totals["health"]["tenants_no_active_users"] += 1
        if jobs_last_30_days == 0:
            totals["health"]["tenants_no_jobs_30_days"] += 1
        if days_since_activity is None or days_since_activity > 7:
            totals["health"]["tenants_no_activity_7_days"] += 1

    rows.sort(key=lambda r: r["jobs_total"], reverse=True)

    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "totals": totals,
        "tenants": rows,
    }
