from datetime import datetime, timedelta, timezone
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import text
from sqlmodel import Session, func, select

from ..database import get_session
from ..dependencies import AuthContext, invalidate_auth_cache, require_platform_admin
from ..models import (
    AutoKeyJob,
    Invoice,
    PlatformEnterShopResponse,
    PlatformTenantBillingExemptRequest,
    PlatformTenantForceLogoutRequest,
    PlatformTenantPlanUpdateRequest,
    PlatformTenantStatusUpdateRequest,
    PlatformTenantUpdateRequest,
    PlatformTenantRead,
    PlatformUserRead,
    RepairJob,
    ShoeRepairJob,
    Tenant,
    TenantEventLog,
    TenantEventLogRead,
    User,
)
from ..security import create_access_token, create_refresh_token, hash_password

router = APIRouter(prefix="/v1/platform-admin", tags=["platform-admin"])


def _tenant_read(session: Session, tenant: Tenant) -> PlatformTenantRead:
    user_count = int(session.exec(select(func.count(User.id)).where(User.tenant_id == tenant.id)).one())
    return PlatformTenantRead(
        id=tenant.id,
        slug=tenant.slug,
        name=tenant.name,
        plan_code=tenant.plan_code,
        is_active=tenant.is_active,
        signup_payment_pending=tenant.signup_payment_pending,
        billing_exempt=tenant.billing_exempt,
        subscription_status=tenant.subscription_status,
        user_count=user_count,
        created_at=tenant.created_at,
    )


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

    # Count users per tenant in a single grouped query. This list can have hundreds
    # of shops (the Minit network alone is ~379), so a per-tenant COUNT query here
    # meant one DB round trip per shop — on a cold Postgres connection that was slow
    # enough to blow past the frontend's request timeout and leave the Shops tab
    # stuck with nothing loaded.
    count_rows = session.exec(
        select(User.tenant_id, func.count(User.id)).group_by(User.tenant_id)
    ).all()
    user_counts: dict[UUID, int] = dict(count_rows)

    return [
        PlatformTenantRead(
            id=t.id,
            slug=t.slug,
            name=t.name,
            plan_code=t.plan_code,
            is_active=t.is_active,
            signup_payment_pending=t.signup_payment_pending,
            billing_exempt=t.billing_exempt,
            subscription_status=t.subscription_status,
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
    invalidate_auth_cache()

    return _tenant_read(session, tenant)


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
    return _tenant_read(session, tenant)


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
    return _tenant_read(session, tenant)


@router.post("/tenants/{tenant_id}/billing-exempt", response_model=PlatformTenantRead)
def set_tenant_billing_exempt(
    tenant_id: UUID,
    payload: PlatformTenantBillingExemptRequest,
    auth: AuthContext = Depends(require_platform_admin),
    session: Session = Depends(get_session),
):
    """Comp a shop: stop billing it while keeping full access.

    Unlike mark-paid (a one-time nudge past the signup gate), this is a durable
    flag — it keeps working even after a Stripe webhook later re-flags
    signup_payment_pending (e.g. once the subscription this clears is canceled).
    Turning exemption on cancels any live Stripe subscription by default so the
    shop actually stops being charged, not just stops being gated in-app.
    """
    tenant = session.get(Tenant, tenant_id)
    if not tenant:
        raise HTTPException(status_code=404, detail="Shop not found.")
    admin = session.get(User, auth.user_id)
    admin_email = admin.email if admin else "platform_admin"
    reason = (payload.reason or "").strip()

    stripe_note = ""
    if payload.billing_exempt:
        tenant.billing_exempt = True
        tenant.signup_payment_pending = False
        tenant.subscription_status = None
        tenant.trial_end = None

        if payload.cancel_stripe_subscription and tenant.stripe_subscription_id:
            from .billing import _get_stripe, _stripe_configured

            if _stripe_configured():
                try:
                    stripe = _get_stripe()
                    stripe.Subscription.cancel(tenant.stripe_subscription_id)
                    stripe_note = f" Canceled Stripe subscription {tenant.stripe_subscription_id}."
                except Exception as exc:  # noqa: BLE001 — surface but don't block the local exemption
                    stripe_note = f" Could not cancel Stripe subscription: {exc}"
                tenant.stripe_subscription_id = None
    else:
        tenant.billing_exempt = False
        # No active subscription remains after an exemption (we cancel it above),
        # so re-requiring payment means flagging it pending again — only if
        # billing is actually configured, otherwise this is a no-op gate anyway.
        if not tenant.stripe_subscription_id:
            tenant.signup_payment_pending = True

    session.add(tenant)
    session.add(
        TenantEventLog(
            tenant_id=tenant_id,
            actor_user_id=auth.user_id,
            actor_email=admin_email,
            entity_type="tenant",
            entity_id=tenant_id,
            event_type="platform_admin_billing_exempt_changed",
            event_summary=(
                f"Platform admin set billing_exempt={tenant.billing_exempt}. "
                f"Reason: {reason or 'n/a'}.{stripe_note}"
            ),
        )
    )
    session.commit()
    invalidate_auth_cache()
    return _tenant_read(session, tenant)


@router.patch("/tenants/{tenant_id}", response_model=PlatformTenantRead)
def update_tenant(
    tenant_id: UUID,
    payload: PlatformTenantUpdateRequest,
    auth: AuthContext = Depends(require_platform_admin),
    session: Session = Depends(get_session),
):
    """Edit shop name, slug, owner email, or reset owner password."""
    tenant = session.get(Tenant, tenant_id)
    if not tenant:
        raise HTTPException(status_code=404, detail="Shop not found.")
    admin = session.get(User, auth.user_id)
    admin_email = admin.email if admin else "platform_admin"

    changes: list[str] = []

    if payload.name is not None:
        new_name = payload.name.strip()
        if not new_name:
            raise HTTPException(status_code=422, detail="Shop name cannot be empty.")
        old_name = tenant.name
        tenant.name = new_name
        changes.append(f"name: '{old_name}' → '{new_name}'")

    if payload.slug is not None:
        new_slug = payload.slug.strip().lower()
        if not new_slug:
            raise HTTPException(status_code=422, detail="Shop slug cannot be empty.")
        existing = session.exec(
            select(Tenant).where(Tenant.slug == new_slug).where(Tenant.id != tenant_id)
        ).first()
        if existing:
            raise HTTPException(status_code=409, detail=f"Slug '{new_slug}' is already in use.")
        old_slug = tenant.slug
        tenant.slug = new_slug
        changes.append(f"slug: '{old_slug}' → '{new_slug}'")

    session.add(tenant)

    owner = session.exec(
        select(User)
        .where(User.tenant_id == tenant_id)
        .where(User.role == "owner")
        .order_by(User.created_at)
    ).first()

    if payload.owner_email is not None and owner:
        new_email = payload.owner_email.strip().lower()
        if new_email:
            old_email = owner.email
            owner.email = new_email
            changes.append(f"owner email: '{old_email}' → '{new_email}'")
            session.add(owner)

    if payload.new_password is not None and owner:
        pwd = payload.new_password.strip()
        if len(pwd) < 8:
            raise HTTPException(status_code=422, detail="Password must be at least 8 characters.")
        owner.hashed_password = hash_password(pwd)
        changes.append("owner password reset")
        session.add(owner)

    if changes:
        session.add(
            TenantEventLog(
                tenant_id=tenant_id,
                actor_user_id=auth.user_id,
                actor_email=admin_email,
                entity_type="tenant",
                entity_id=tenant_id,
                event_type="platform_admin_tenant_updated",
                event_summary=f"Platform admin updated shop: {'; '.join(changes)}",
            )
        )
        session.commit()

    return _tenant_read(session, tenant)


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
    invalidate_auth_cache()
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

    # SQLite stores UUID as 32-char hex; Postgres uuid accepts hyphenated strings.
    tid = tenant_id.hex if session.get_bind().dialect.name == "sqlite" else str(tenant_id)
    try:
        # Null out optional cross-tenant references on shared tables
        session.execute(text("DELETE FROM intakejob WHERE claimed_by_tenant_id = :tid"), {"tid": tid})
        session.execute(text("UPDATE intakejob SET resulting_job_id = NULL WHERE resulting_job_id IN (SELECT id FROM autokeyjob WHERE tenant_id = :tid)"), {"tid": tid})
        session.execute(text("UPDATE parentaccounteventlog SET tenant_id = NULL WHERE tenant_id = :tid"), {"tid": tid})
        session.execute(text("UPDATE parentaccounteventlog SET actor_user_id = NULL WHERE actor_user_id IN (SELECT id FROM \"user\" WHERE tenant_id = :tid)"), {"tid": tid})
        session.execute(text("UPDATE parentaccount SET mobile_lead_default_tenant_id = NULL WHERE mobile_lead_default_tenant_id = :tid"), {"tid": tid})
        session.execute(text("UPDATE parentaccount SET mobile_lead_escalation_tenant_id = NULL WHERE mobile_lead_escalation_tenant_id = :tid"), {"tid": tid})
        session.execute(text("UPDATE autokeyjob SET referring_shop_tenant_id = NULL WHERE referring_shop_tenant_id = :tid"), {"tid": tid})
        session.execute(text("UPDATE autokeyjob SET shop_mobile_booking_request_id = NULL WHERE tenant_id = :tid"), {"tid": tid})

        # Delete tables that have no tenant_id but FK into tenant-owned tables
        session.execute(text("DELETE FROM importlogdetail WHERE import_log_id IN (SELECT id FROM importlog WHERE tenant_id = :tid)"), {"tid": tid})
        session.execute(text("DELETE FROM shoerepairjobshoe WHERE shoe_repair_job_id IN (SELECT id FROM shoerepairjob WHERE tenant_id = :tid)"), {"tid": tid})
        session.execute(text("DELETE FROM shoerepairjobitem WHERE shoe_repair_job_id IN (SELECT id FROM shoerepairjob WHERE tenant_id = :tid)"), {"tid": tid})
        session.execute(text("DELETE FROM shoejobstatushistory WHERE shoe_repair_job_id IN (SELECT id FROM shoerepairjob WHERE tenant_id = :tid)"), {"tid": tid})
        session.execute(text("DELETE FROM inboundemail WHERE auto_key_job_id IN (SELECT id FROM autokeyjob WHERE tenant_id = :tid)"), {"tid": tid})
        session.execute(text("DELETE FROM shopmobilebookingrequest WHERE requesting_tenant_id = :tid OR target_operator_tenant_id = :tid"), {"tid": tid})
        session.execute(text("DELETE FROM mobileleaddispatch WHERE current_operator_tenant_id = :tid OR auto_key_job_id IN (SELECT id FROM autokeyjob WHERE tenant_id = :tid)"), {"tid": tid})
        session.execute(text("DELETE FROM portalsession WHERE lower(email) IN (SELECT lower(email) FROM \"user\" WHERE tenant_id = :tid)"), {"tid": tid})

        # Delete tenant-owned tables in reverse FK dependency order
        for tbl in [
            "jobmessage",                # → repairjob / shoerepairjob / autokeyjob
            "usernotificationpreference",
            "tenantapikey",
            "tenantwebhooksubscription",
            "refreshsession",
            "customerportalsession",
            "prospectlead",
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
            quoted = f'"{tbl}"' if tbl == "user" else tbl
            session.execute(text(f"DELETE FROM {quoted} WHERE tenant_id = :tid"), {"tid": tid})  # noqa: S608

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


def _counts_by_tenant(session: Session, model, *filters) -> dict[UUID, int]:
    stmt = select(model.tenant_id, func.count(model.id)).group_by(model.tenant_id)
    for extra in filters:
        stmt = stmt.where(extra)
    return {tid: int(n) for tid, n in session.exec(stmt).all() if tid is not None}


def _sums_by_tenant(session: Session, model, column, *filters) -> dict[UUID, int]:
    stmt = select(model.tenant_id, func.coalesce(func.sum(column), 0)).group_by(model.tenant_id)
    for extra in filters:
        stmt = stmt.where(extra)
    return {tid: int(n) for tid, n in session.exec(stmt).all() if tid is not None}


def _build_platform_reports(session: Session) -> dict:
    """Grouped aggregates — one query per metric, not per tenant."""
    tenants = session.exec(select(Tenant).order_by(Tenant.name)).all()
    thirty_days_ago = datetime.now(timezone.utc) - timedelta(days=30)
    seven_days_ago = datetime.now(timezone.utc) - timedelta(days=7)

    users = _counts_by_tenant(session, User)
    active_users = _counts_by_tenant(session, User, User.is_active == True)  # noqa: E712
    repair_jobs = _counts_by_tenant(session, RepairJob)
    shoe_jobs = _counts_by_tenant(session, ShoeRepairJob)
    auto_key_jobs = _counts_by_tenant(session, AutoKeyJob)
    invoices = _counts_by_tenant(session, Invoice)
    paid_invoices = _counts_by_tenant(session, Invoice, Invoice.status == "paid")
    billed_totals = _sums_by_tenant(session, Invoice, Invoice.total_cents)
    paid_totals = _sums_by_tenant(session, Invoice, Invoice.total_cents, Invoice.status == "paid")
    repair_last_30 = _counts_by_tenant(session, RepairJob, RepairJob.created_at >= thirty_days_ago)
    shoe_last_30 = _counts_by_tenant(session, ShoeRepairJob, ShoeRepairJob.created_at >= thirty_days_ago)
    auto_last_30 = _counts_by_tenant(session, AutoKeyJob, AutoKeyJob.created_at >= thirty_days_ago)
    invoices_last_30 = _counts_by_tenant(session, Invoice, Invoice.created_at >= thirty_days_ago)
    last_activity = {
        tid: ts
        for tid, ts in session.exec(
            select(TenantEventLog.tenant_id, func.max(TenantEventLog.created_at)).group_by(TenantEventLog.tenant_id)
        ).all()
        if tid is not None
    }
    logins_last_7 = _counts_by_tenant(
        session,
        TenantEventLog,
        TenantEventLog.event_type == "login",
        TenantEventLog.created_at >= seven_days_ago,
    )

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

    for tenant in tenants:
        u = users.get(tenant.id, 0)
        au = active_users.get(tenant.id, 0)
        rj = repair_jobs.get(tenant.id, 0)
        sj = shoe_jobs.get(tenant.id, 0)
        ak = auto_key_jobs.get(tenant.id, 0)
        inv = invoices.get(tenant.id, 0)
        paid = paid_invoices.get(tenant.id, 0)
        billed = billed_totals.get(tenant.id, 0)
        paid_cents = paid_totals.get(tenant.id, 0)
        jobs_last_30_days = repair_last_30.get(tenant.id, 0) + shoe_last_30.get(tenant.id, 0) + auto_last_30.get(tenant.id, 0)
        inv_last_30 = invoices_last_30.get(tenant.id, 0)
        last_activity_at = last_activity.get(tenant.id)
        logins = logins_last_7.get(tenant.id, 0)
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
        elif au == 0 or jobs_last_30_days == 0 or (days_since_activity is not None and days_since_activity > 7):
            health_status = "attention"

        rows.append({
            "tenant_id": str(tenant.id),
            "tenant_name": tenant.name,
            "tenant_slug": tenant.slug,
            "plan_code": tenant.plan_code,
            "is_active": tenant.is_active,
            "users": u,
            "active_users": au,
            "repair_jobs": rj,
            "shoe_jobs": sj,
            "auto_key_jobs": ak,
            "jobs_total": rj + sj + ak,
            "jobs_last_30_days": jobs_last_30_days,
            "invoices": inv,
            "paid_invoices": paid,
            "invoices_last_30_days": inv_last_30,
            "billed_total_cents": billed,
            "paid_total_cents": paid_cents,
            "last_activity_at": last_activity_at,
            "logins_last_7_days": logins,
            "days_since_activity": days_since_activity,
            "health_status": health_status,
        })

        totals["users"] += u
        totals["active_users"] += au
        totals["repair_jobs"] += rj
        totals["shoe_jobs"] += sj
        totals["auto_key_jobs"] += ak
        totals["invoices"] += inv
        totals["paid_invoices"] += paid
        totals["billed_total_cents"] += billed
        totals["paid_total_cents"] += paid_cents
        totals["jobs_last_30_days"] += jobs_last_30_days
        totals["invoices_last_30_days"] += inv_last_30
        if tenant.is_active:
            totals["health"]["active_tenants"] += 1
        else:
            totals["health"]["suspended_tenants"] += 1
        if au == 0:
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


@router.get("/reports")
def get_platform_reports(
    _: object = Depends(require_platform_admin),
    session: Session = Depends(get_session),
):
    return _build_platform_reports(session)
