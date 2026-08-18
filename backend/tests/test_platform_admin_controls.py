import os
from datetime import datetime, timedelta, timezone
from pathlib import Path
from uuid import UUID
from uuid import uuid4

from fastapi.testclient import TestClient
from sqlmodel import Session, select

_TEST_DB = Path(__file__).with_name(f"test_platform_admin_{uuid4().hex}.db")
os.environ["DATABASE_URL"] = f"sqlite:///{_TEST_DB.as_posix()}"
os.environ.setdefault("APP_ENV", "test")

from app.config import settings  # noqa: E402
from app.database import create_db_and_tables, engine  # noqa: E402
from app.main import app  # noqa: E402
from app.models import (
    AutoKeyJob,
    Customer,
    CustomerPortalSession,
    InboundEmail,
    IntakeJob,
    JobMessage,
    MobileLeadDispatch,
    ParentAccount,
    ParentAccountMembership,
    PortalSession,
    ProspectLead,
    RefreshSession,
    ShopMobileBookingRequest,
    Tenant,
    TenantApiKey,
    TenantEventLog,
    TenantWebhookSubscription,
    User,
    UserNotificationPreference,
)  # noqa: E402

create_db_and_tables()
client = TestClient(app)


def _bootstrap_and_login(slug: str, email: str, password: str = "pass123456") -> tuple[str, str]:
    bootstrap = client.post(
        "/v1/auth/bootstrap",
        json={
            "tenant_name": f"Tenant {slug}",
            "tenant_slug": slug,
            "owner_email": email,
            "owner_full_name": "Owner",
            "owner_password": password,
            "plan_code": "pro",
        },
    )
    assert bootstrap.status_code == 200
    login = client.post(
        "/v1/auth/login",
        json={"tenant_slug": slug, "email": email, "password": password},
    )
    assert login.status_code == 200
    token = login.json()["access_token"]
    session_res = client.get("/v1/auth/session", headers={"Authorization": f"Bearer {token}"})
    assert session_res.status_code == 200
    return token, session_res.json()["tenant_id"]


def _promote_to_platform_admin(email: str) -> None:
    with Session(engine) as db:
        user = db.exec(select(User).where(User.email == email)).first()
        assert user is not None
        user.role = "platform_admin"
        db.add(user)
        db.commit()


def test_enter_shop_logs_event():
    suffix = uuid4().hex[:8]
    _, target_tenant_id = _bootstrap_and_login(f"target-{suffix}", f"target-{suffix}@test.com")
    _bootstrap_and_login(f"admin-{suffix}", f"admin-{suffix}@test.com")
    _promote_to_platform_admin(f"admin-{suffix}@test.com")
    admin_login = client.post(
        "/v1/auth/login",
        json={"tenant_slug": f"admin-{suffix}", "email": f"admin-{suffix}@test.com", "password": "pass123456"},
    )
    admin_token = admin_login.json()["access_token"]
    admin_headers = {"Authorization": f"Bearer {admin_token}"}

    ok = client.post(
        f"/v1/platform-admin/enter-shop/{target_tenant_id}",
        headers=admin_headers,
    )
    assert ok.status_code == 200

    with Session(engine) as db:
        event = db.exec(
            select(TenantEventLog)
            .where(TenantEventLog.tenant_id == UUID(target_tenant_id))
            .where(TenantEventLog.event_type == "platform_admin_enter_shop")
        ).first()
        assert event is not None


def test_suspend_reactivate_and_force_logout():
    suffix = uuid4().hex[:8]
    target_email = f"target2-{suffix}@test.com"
    target_slug = f"target2-{suffix}"
    target_token, target_tenant_id = _bootstrap_and_login(target_slug, target_email)
    _bootstrap_and_login(f"admin2-{suffix}", f"admin2-{suffix}@test.com")
    _promote_to_platform_admin(f"admin2-{suffix}@test.com")
    admin_login = client.post(
        "/v1/auth/login",
        json={"tenant_slug": f"admin2-{suffix}", "email": f"admin2-{suffix}@test.com", "password": "pass123456"},
    )
    admin_headers = {"Authorization": f"Bearer {admin_login.json()['access_token']}"}

    suspend = client.patch(
        f"/v1/platform-admin/tenants/{target_tenant_id}/status",
        headers=admin_headers,
        json={"is_active": False, "reason": "Compliance hold"},
    )
    assert suspend.status_code == 200
    assert suspend.json()["is_active"] is False

    old_token_session = client.get("/v1/auth/session", headers={"Authorization": f"Bearer {target_token}"})
    assert old_token_session.status_code in (401, 403)

    blocked_login = client.post(
        "/v1/auth/login",
        json={"tenant_slug": target_slug, "email": target_email, "password": "pass123456"},
    )
    assert blocked_login.status_code == 403

    reactivate = client.patch(
        f"/v1/platform-admin/tenants/{target_tenant_id}/status",
        headers=admin_headers,
        json={"is_active": True, "reason": "Issue resolved"},
    )
    assert reactivate.status_code == 200
    assert reactivate.json()["is_active"] is True

    relogin = client.post(
        "/v1/auth/login",
        json={"tenant_slug": target_slug, "email": target_email, "password": "pass123456"},
    )
    assert relogin.status_code == 200
    active_token = relogin.json()["access_token"]
    ok_session = client.get("/v1/auth/session", headers={"Authorization": f"Bearer {active_token}"})
    assert ok_session.status_code == 200

    force = client.post(
        f"/v1/platform-admin/tenants/{target_tenant_id}/force-logout",
        headers=admin_headers,
        json={"reason": "Credential rotation"},
    )
    assert force.status_code == 200

    after_force = client.get("/v1/auth/session", headers={"Authorization": f"Bearer {active_token}"})
    assert after_force.status_code == 401


def test_list_tenants_does_not_scale_query_count_with_shop_count():
    """The Shops tab lists every tenant on the platform (~379 shops in production
    for the Minit network). If listing tenants issues a separate user-count query
    per tenant, that many DB round trips can blow past the frontend request
    timeout on a slow connection and leave the tab stuck with nothing loaded.
    Assert the query count stays flat as the number of shops grows."""
    from sqlalchemy import event

    suffix = uuid4().hex[:8]
    _bootstrap_and_login(f"admin3-{suffix}", f"admin3-{suffix}@test.com")
    _promote_to_platform_admin(f"admin3-{suffix}@test.com")
    admin_login = client.post(
        "/v1/auth/login",
        json={"tenant_slug": f"admin3-{suffix}", "email": f"admin3-{suffix}@test.com", "password": "pass123456"},
    )
    admin_headers = {"Authorization": f"Bearer {admin_login.json()['access_token']}"}

    for i in range(20):
        _bootstrap_and_login(f"scale{i}-{suffix}", f"scale{i}-{suffix}@test.com")

    queries: list[str] = []

    def _count(conn, cursor, statement, parameters, context, executemany):
        queries.append(statement)

    event.listen(engine, "before_cursor_execute", _count)
    try:
        resp = client.get("/v1/platform-admin/tenants", headers=admin_headers)
    finally:
        event.remove(engine, "before_cursor_execute", _count)

    assert resp.status_code == 200
    assert len(resp.json()) >= 21
    # A couple of queries for auth-context lookup plus one for tenants and one
    # grouped count query — a small constant, not one-per-tenant.
    assert len(queries) <= 6, f"expected a constant, small number of queries, got {len(queries)}"


def test_billing_exempt_keeps_access_through_a_later_payment_pending_flag():
    """A shop marked billing_exempt must stay accessible even if something later
    re-flags signup_payment_pending (e.g. a Stripe subscription.deleted webhook),
    which is exactly the case mark-paid does not survive."""
    suffix = uuid4().hex[:8]
    target_slug = f"exempt-{suffix}"
    target_email = f"exempt-{suffix}@test.com"
    target_token, target_tenant_id = _bootstrap_and_login(target_slug, target_email)
    _bootstrap_and_login(f"admin4-{suffix}", f"admin4-{suffix}@test.com")
    _promote_to_platform_admin(f"admin4-{suffix}@test.com")
    admin_login = client.post(
        "/v1/auth/login",
        json={"tenant_slug": f"admin4-{suffix}", "email": f"admin4-{suffix}@test.com", "password": "pass123456"},
    )
    admin_headers = {"Authorization": f"Bearer {admin_login.json()['access_token']}"}
    target_headers = {"Authorization": f"Bearer {target_token}"}

    original_stripe_key = settings.stripe_secret_key
    settings.stripe_secret_key = "sk_test_dummy"  # pretend Stripe is configured
    try:
        exempt = client.post(
            f"/v1/platform-admin/tenants/{target_tenant_id}/billing-exempt",
            headers=admin_headers,
            json={"billing_exempt": True, "reason": "Franchise HQ covers this shop", "cancel_stripe_subscription": True},
        )
        assert exempt.status_code == 200
        body = exempt.json()
        assert body["billing_exempt"] is True
        assert body["signup_payment_pending"] is False

        # Simulate what a later Stripe subscription.deleted webhook does: re-flag
        # signup_payment_pending. Exemption must still keep the shop accessible.
        with Session(engine) as db:
            tenant = db.get(Tenant, UUID(target_tenant_id))
            tenant.signup_payment_pending = True
            db.add(tenant)
            db.commit()

        # /v1/auth/session is always allowed even when payment-pending (so the SPA
        # can render the "subscription required" page), so exercise the gate
        # against an ordinary tenant-data route instead.
        still_ok = client.get("/v1/customers", headers=target_headers)
        assert still_ok.status_code == 200

        # Turning exemption back off re-requires payment (no subscription remains).
        unexempt = client.post(
            f"/v1/platform-admin/tenants/{target_tenant_id}/billing-exempt",
            headers=admin_headers,
            json={"billing_exempt": False},
        )
        assert unexempt.status_code == 200
        assert unexempt.json()["billing_exempt"] is False
        assert unexempt.json()["signup_payment_pending"] is True

        blocked = client.get("/v1/customers", headers=target_headers)
        assert blocked.status_code == 403
    finally:
        settings.stripe_secret_key = original_stripe_key


def test_delete_tenant_clears_new_fk_tables():
    suffix = uuid4().hex[:8]
    token, tenant_id_str = _bootstrap_and_login(f"del-{suffix}", f"del-{suffix}@test.com")
    _bootstrap_and_login(f"adm-{suffix}", f"adm-{suffix}@test.com")
    _promote_to_platform_admin(f"adm-{suffix}@test.com")
    admin_login = client.post(
        "/v1/auth/login",
        json={"tenant_slug": f"adm-{suffix}", "email": f"adm-{suffix}@test.com", "password": "pass123456"},
    )
    admin_headers = {"Authorization": f"Bearer {admin_login.json()['access_token']}"}
    tenant_id = UUID(tenant_id_str)

    with Session(engine) as db:
        user = db.exec(select(User).where(User.tenant_id == tenant_id)).first()
        assert user is not None
        customer = Customer(tenant_id=tenant_id, full_name="Delete Me", phone="0400111222")
        db.add(customer)
        db.flush()
        job = AutoKeyJob(
            tenant_id=tenant_id,
            customer_id=customer.id,
            job_number=f"AK-{suffix}",
            title="Delete job",
        )
        db.add(job)
        db.flush()
        parent = ParentAccount(name="Delete parent", owner_email=f"parent-{suffix}@test.com")
        db.add(parent)
        db.flush()
        db.add(ParentAccountMembership(parent_account_id=parent.id, tenant_id=tenant_id, user_id=user.id))
        db.add(
            JobMessage(
                tenant_id=tenant_id,
                auto_key_job_id=job.id,
                direction="inbound",
                body="hi",
                from_phone="+61400111222",
            )
        )
        db.add(
            ShopMobileBookingRequest(
                parent_account_id=parent.id,
                requesting_tenant_id=tenant_id,
                target_operator_tenant_id=tenant_id,
                created_by_user_id=user.id,
                customer_name="Booker",
                job_address="1 Test St",
            )
        )
        db.add(
            MobileLeadDispatch(
                parent_account_id=parent.id,
                suburb="Sydney",
                state_code="NSW",
                suburb_normalized="sydney",
                    payload_json="{}",
                    candidate_operator_ids_json="[]",
                    current_operator_tenant_id=tenant_id,
                auto_key_job_id=job.id,
            )
        )
        db.add(
            IntakeJob(
                customer_name="Intake",
                job_address="2 Test St",
                job_lat=-33.8,
                job_lng=151.2,
                claimed_by_tenant_id=tenant_id,
                resulting_job_id=job.id,
            )
        )
        db.add(
            InboundEmail(
                parent_account_id=parent.id,
                subject="lead",
                auto_key_job_id=job.id,
            )
        )
        now = datetime.now(timezone.utc)
        db.add(
            PortalSession(
                email=user.email,
                token=uuid4().hex,
                expires_at=now + timedelta(hours=1),
            )
        )
        db.add(
            CustomerPortalSession(
                tenant_id=tenant_id,
                customer_id=customer.id,
                token=uuid4().hex,
                expires_at=now + timedelta(hours=1),
            )
        )
        db.add(
            UserNotificationPreference(tenant_id=tenant_id, user_id=user.id)
        )
        db.add(
            TenantApiKey(
                tenant_id=tenant_id,
                name="test",
                key_prefix="msk_test",
                key_hash="abc",
            )
        )
        db.add(
            TenantWebhookSubscription(
                tenant_id=tenant_id,
                url="https://example.test/hook",
                event_types="quote_approved",
                secret="s" * 32,
            )
        )
        db.add(
            RefreshSession(
                tenant_id=tenant_id,
                user_id=user.id,
                jti=uuid4().hex,
                expires_at=now + timedelta(days=7),
            )
        )
        db.add(ProspectLead(tenant_id=tenant_id, name="Prospect shop"))
        job_id = job.id
        owner_email = user.email
        db.commit()

    res = client.delete(f"/v1/platform-admin/tenants/{tenant_id}", headers=admin_headers)
    assert res.status_code == 204, res.text

    with Session(engine) as db:
        assert db.get(Tenant, tenant_id) is None
        assert db.exec(select(JobMessage).where(JobMessage.tenant_id == tenant_id)).first() is None
        assert db.exec(select(ShopMobileBookingRequest).where(ShopMobileBookingRequest.requesting_tenant_id == tenant_id)).first() is None
        assert db.exec(select(MobileLeadDispatch).where(MobileLeadDispatch.current_operator_tenant_id == tenant_id)).first() is None
        assert db.exec(select(IntakeJob).where(IntakeJob.claimed_by_tenant_id == tenant_id)).first() is None
        assert db.exec(select(InboundEmail).where(InboundEmail.auto_key_job_id == job_id)).first() is None
        assert db.exec(select(PortalSession).where(PortalSession.email == owner_email)).first() is None
        assert db.exec(select(CustomerPortalSession).where(CustomerPortalSession.tenant_id == tenant_id)).first() is None
        assert db.exec(select(UserNotificationPreference).where(UserNotificationPreference.tenant_id == tenant_id)).first() is None
        assert db.exec(select(TenantApiKey).where(TenantApiKey.tenant_id == tenant_id)).first() is None
        assert db.exec(select(TenantWebhookSubscription).where(TenantWebhookSubscription.tenant_id == tenant_id)).first() is None
        assert db.exec(select(RefreshSession).where(RefreshSession.tenant_id == tenant_id)).first() is None
        assert db.exec(select(ProspectLead).where(ProspectLead.tenant_id == tenant_id)).first() is None
        assert db.exec(select(ParentAccountMembership).where(ParentAccountMembership.tenant_id == tenant_id)).first() is None
        assert db.exec(select(AutoKeyJob).where(AutoKeyJob.tenant_id == tenant_id)).first() is None
        assert db.exec(select(User).where(User.tenant_id == tenant_id)).first() is None


def _naive_platform_reports(session: Session) -> dict:
    """Pre-aggregation loop — used only to lock the new grouped query to the old contract."""
    from app.models import Invoice, RepairJob, ShoeRepairJob
    from sqlalchemy.sql.functions import coalesce
    from sqlmodel import func as smfunc

    tenants = session.exec(select(Tenant).order_by(Tenant.name)).all()
    thirty_days_ago = datetime.now(timezone.utc) - timedelta(days=30)
    seven_days_ago = datetime.now(timezone.utc) - timedelta(days=7)
    rows = []
    for tenant in tenants:
        users = int(session.exec(select(smfunc.count(User.id)).where(User.tenant_id == tenant.id)).one())
        active_users = int(session.exec(select(smfunc.count(User.id)).where(User.tenant_id == tenant.id).where(User.is_active == True)).one())  # noqa: E712
        repair_jobs = int(session.exec(select(smfunc.count(RepairJob.id)).where(RepairJob.tenant_id == tenant.id)).one())
        shoe_jobs = int(session.exec(select(smfunc.count(ShoeRepairJob.id)).where(ShoeRepairJob.tenant_id == tenant.id)).one())
        auto_key_jobs = int(session.exec(select(smfunc.count(AutoKeyJob.id)).where(AutoKeyJob.tenant_id == tenant.id)).one())
        invoices = int(session.exec(select(smfunc.count(Invoice.id)).where(Invoice.tenant_id == tenant.id)).one())
        paid_invoices = int(session.exec(select(smfunc.count(Invoice.id)).where(Invoice.tenant_id == tenant.id).where(Invoice.status == "paid")).one())
        billed_total_cents = int(session.exec(select(coalesce(smfunc.sum(Invoice.total_cents), 0)).where(Invoice.tenant_id == tenant.id)).one())
        paid_total_cents = int(session.exec(select(coalesce(smfunc.sum(Invoice.total_cents), 0)).where(Invoice.tenant_id == tenant.id).where(Invoice.status == "paid")).one())
        jobs_last_30_days = (
            int(session.exec(select(smfunc.count(RepairJob.id)).where(RepairJob.tenant_id == tenant.id).where(RepairJob.created_at >= thirty_days_ago)).one())
            + int(session.exec(select(smfunc.count(ShoeRepairJob.id)).where(ShoeRepairJob.tenant_id == tenant.id).where(ShoeRepairJob.created_at >= thirty_days_ago)).one())
            + int(session.exec(select(smfunc.count(AutoKeyJob.id)).where(AutoKeyJob.tenant_id == tenant.id).where(AutoKeyJob.created_at >= thirty_days_ago)).one())
        )
        invoices_last_30_days = int(session.exec(select(smfunc.count(Invoice.id)).where(Invoice.tenant_id == tenant.id).where(Invoice.created_at >= thirty_days_ago)).one())
        last_activity_at = session.exec(select(TenantEventLog.created_at).where(TenantEventLog.tenant_id == tenant.id).order_by(TenantEventLog.created_at.desc()).limit(1)).first()
        logins_last_7_days = int(session.exec(select(smfunc.count(TenantEventLog.id)).where(TenantEventLog.tenant_id == tenant.id).where(TenantEventLog.event_type == "login").where(TenantEventLog.created_at >= seven_days_ago)).one())
        days_since_activity = None
        if isinstance(last_activity_at, datetime):
            normalized = last_activity_at if last_activity_at.tzinfo else last_activity_at.replace(tzinfo=timezone.utc)
            days_since_activity = max(0, int((datetime.now(timezone.utc) - normalized).days))
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
    rows.sort(key=lambda r: r["jobs_total"], reverse=True)
    return {"tenants": rows}


def test_platform_reports_match_naive_loop_on_three_tenants():
    from app.models import Invoice, RepairJob, Watch
    from app.routes.platform_admin import _build_platform_reports

    suffix = uuid4().hex[:8]
    tokens = []
    for i in range(3):
        token, tid = _bootstrap_and_login(f"rpt{i}-{suffix}", f"rpt{i}-{suffix}@test.com")
        tokens.append((token, UUID(tid), i))
    _promote_to_platform_admin(f"rpt0-{suffix}@test.com")
    admin_login = client.post(
        "/v1/auth/login",
        json={"tenant_slug": f"rpt0-{suffix}", "email": f"rpt0-{suffix}@test.com", "password": "pass123456"},
    )
    admin_headers = {"Authorization": f"Bearer {admin_login.json()['access_token']}"}

    with Session(engine) as db:
        for token, tid, i in tokens:
            if i == 0:
                continue
            cust = Customer(tenant_id=tid, full_name=f"C{i}")
            db.add(cust)
            db.flush()
            watch = Watch(tenant_id=tid, customer_id=cust.id, brand="Omega")
            db.add(watch)
            db.flush()
            repair = RepairJob(tenant_id=tid, watch_id=watch.id, job_number=f"JOB-{i}", title="svc")
            db.add(repair)
            db.flush()
            db.add(AutoKeyJob(tenant_id=tid, customer_id=cust.id, job_number=f"AK-{i}", title="key"))
            db.add(Invoice(tenant_id=tid, repair_job_id=repair.id, invoice_number=f"INV-{i}", status="paid" if i == 1 else "unpaid", total_cents=1000 * i, subtotal_cents=1000 * i, tax_cents=0))
        db.commit()
        grouped = _build_platform_reports(db)
        naive = _naive_platform_reports(db)

    def _strip(rows):
        return [{k: v for k, v in r.items() if k != "last_activity_at"} for r in rows]

    assert _strip(grouped["tenants"]) == _strip(naive["tenants"])

    res = client.get("/v1/platform-admin/reports", headers=admin_headers)
    assert res.status_code == 200, res.text
    body = res.json()
    assert "totals" in body and "tenants" in body
    assert body["totals"]["tenants"] >= 3
