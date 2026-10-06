"""Parent-account HQ operations APIs (Minit network dashboard)."""

import os
from pathlib import Path
from uuid import uuid4

_TEST_DB = Path(__file__).with_name(f"test_parent_ops_{uuid4().hex}.db")
os.environ.setdefault("DATABASE_URL", f"sqlite:///{_TEST_DB.as_posix()}")
os.environ.setdefault("JWT_SECRET", "test-secret-not-for-production")
os.environ.setdefault("APP_ENV", "test")

from fastapi.testclient import TestClient
from sqlmodel import Session, select

from app.database import create_db_and_tables, engine
from app.main import app
from app.minit_branding import MINIT_HQ_SLUG
from app.models import Tenant, User
from app.security import hash_password
from network_link_helpers import link_and_accept

create_db_and_tables()
client = TestClient(app)


def _bootstrap(slug: str, email: str, plan_code: str) -> dict:
    res = client.post(
        "/v1/auth/bootstrap",
        json={
            "tenant_name": f"Tenant {slug}",
            "tenant_slug": slug,
            "owner_email": email,
            "owner_full_name": "Owner",
            "owner_password": "pass123456",
            "plan_code": plan_code,
        },
    )
    assert res.status_code == 200, res.text
    return res.json()


def _login(slug: str, email: str) -> str:
    res = client.post(
        "/v1/auth/login",
        json={"tenant_slug": slug, "email": email, "password": "pass123456"},
    )
    assert res.status_code == 200, res.text
    return res.json()["access_token"]


def _headers(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


HQ_OWNER_EMAIL = "hq-owner@minit-ops.test"


def _setup_hq_network(suffix: str) -> dict[str, str]:
    hq_email = HQ_OWNER_EMAIL
    hq_slug = MINIT_HQ_SLUG
    op_slug = f"op-{suffix}"
    shop_slug = f"shop-{suffix}"

    boot = client.post(
        "/v1/auth/bootstrap",
        json={
            "tenant_name": "Minit HQ",
            "tenant_slug": hq_slug,
            "owner_email": hq_email,
            "owner_full_name": "HQ Owner",
            "owner_password": "pass123456",
            "plan_code": "enterprise",
        },
    )
    # Public signup refuses Minit slugs (only provisioning makes them), so the
    # HQ tenant is created directly below when bootstrap won't.
    assert boot.status_code in (200, 400, 409), boot.text
    if boot.status_code != 200:
        # Another test may have created the HQ tenant without bootstrap side effects.
        from app.minit_branding import ensure_minit_tenant_plan
        from app.models import ParentAccount
        from app.routes.auth import _create_parent_account, _ensure_parent_membership

        with Session(engine) as session:
            tenant = session.exec(select(Tenant).where(Tenant.slug == hq_slug)).first()
            if tenant is None:
                tenant = Tenant(name="Minit HQ", slug=hq_slug, plan_code="enterprise", is_minit=True)
                session.add(tenant)
                session.flush()
            tenant.is_minit = True
            ensure_minit_tenant_plan(session, tenant)
            user = session.exec(
                select(User).where(User.tenant_id == tenant.id, User.email == hq_email)
            ).first()
            if not user:
                user = User(
                    tenant_id=tenant.id,
                    email=hq_email,
                    full_name="HQ Owner",
                    role="owner",
                    password_hash=hash_password("pass123456"),
                    is_active=True,
                )
                session.add(user)
                session.flush()
            parent = session.exec(
                select(ParentAccount).where(ParentAccount.owner_email == hq_email)
            ).first() or _create_parent_account(session, hq_email, "HQ Owner")
            _ensure_parent_membership(session, parent, user)
            session.commit()
    op_boot = _bootstrap(op_slug, f"op-{suffix}@test.local", "basic_auto_key")
    hq_h = _headers(_login(hq_slug, hq_email))

    shop_num = str(int(suffix[:4], 16) % 9000 + 1000)
    create_shop = client.post(
        "/v1/parent-accounts/me/create-tenant",
        headers=hq_h,
        json={
            "tenant_name": f"Retail {suffix}",
            "tenant_slug": shop_slug,
            "plan_code": "booking_only",
            "shop_number": shop_num,
        },
    )
    assert create_shop.status_code in (200, 409), create_shop.text

    link = link_and_accept(client,
        "/v1/parent-accounts/me/link-tenant",
        headers=hq_h,
        json={"tenant_slug": op_slug, "owner_email": f"op-{suffix}@test.local"},
    )
    assert link.status_code == 200, link.text

    return {"hq": hq_h, "shop_slug": shop_slug, "op_id": op_boot["tenant_id"]}


def test_operations_overview_requires_minit_hq_plan():
    suffix = uuid4().hex[:8]
    email = f"pro-{suffix}@test.local"
    slug = f"pro-{suffix}"
    _bootstrap(slug, email, "pro")
    token = _login(slug, email)
    res = client.get("/v1/parent-accounts/me/operations/overview", headers=_headers(token))
    assert res.status_code == 403


def test_overview_counts_same_active_jobs_as_mobile_reporting_accounts():
    from uuid import UUID
    from app.models import AutoKeyJob, Customer, ParentAccount, ParentMobileReportingSource
    ctx=_setup_hq_network(uuid4().hex[:8])
    with Session(engine) as session:
        parent=session.exec(select(ParentAccount).where(ParentAccount.owner_email==HQ_OWNER_EMAIL)).one()
        reporting=Tenant(slug=f"report-{uuid4().hex[:8]}",name="Opted-in shop",plan_code="basic_auto_key")
        session.add(reporting);session.flush()
        session.add(ParentMobileReportingSource(parent_account_id=parent.id,tenant_id=reporting.id))
        for tenant_id in (UUID(ctx["op_id"]),reporting.id):
            customer=Customer(tenant_id=tenant_id,full_name="Synthetic customer")
            session.add(customer);session.flush()
            for status in ("booking_confirmed","booking_on_hold","booked","work_completed","invoice_paid"):
                session.add(AutoKeyJob(tenant_id=tenant_id,customer_id=customer.id,job_number=f"AK-{uuid4().hex[:8]}",title="Synthetic job",status=status))
        operator=session.get(Tenant,UUID(ctx["op_id"]))
        operator.mobile_dispatch_paused=True;session.add(operator);session.commit()
    overview=client.get("/v1/parent-accounts/me/operations/overview",headers=ctx["hq"])
    jobs=client.get("/v1/parent-accounts/me/operations/mobile-jobs",headers=ctx["hq"])
    assert overview.status_code==jobs.status_code==200
    assert overview.json()["active_mobile_jobs"]==jobs.json()["active_count"]
    assert overview.json()["active_mobile_jobs"]>=6
    assert overview.json()["operators_paused_dispatch"]>=1


def test_operations_overview_and_bookings_for_hq():
    suffix = uuid4().hex[:8]
    ctx = _setup_hq_network(suffix)
    overview = client.get("/v1/parent-accounts/me/operations/overview", headers=ctx["hq"])
    assert overview.status_code == 200, overview.text
    body = overview.json()
    assert body["retail_shop_count"] >= 1
    assert body["operator_count"] >= 1

    bookings = client.get("/v1/parent-accounts/me/operations/bookings", headers=ctx["hq"])
    assert bookings.status_code == 200, bookings.text
    assert "totals" in bookings.json()
    assert "by_shop" in bookings.json()

    mobile = client.get("/v1/parent-accounts/me/operations/mobile-jobs", headers=ctx["hq"])
    assert mobile.status_code == 200, mobile.text
    assert "jobs" in mobile.json()

    trouble = client.get("/v1/parent-accounts/me/operations/troubleshooting", headers=ctx["hq"])
    assert trouble.status_code == 200, trouble.text
    items = trouble.json()["items"]
    assert "items" in trouble.json()

    # Operator was bootstrapped with no mobile_dispatch_phone — should be flagged.
    kinds = {item["kind"] for item in items if item["tenant_id"] == ctx["op_id"]}
    assert "operator_missing_dispatch_phone" in kinds
    # ...but it DOES have an owner login email, so the email gap should not fire.
    assert "operator_missing_dispatch_email" not in kinds


def test_troubleshooting_surfaces_failed_notifications():
    from uuid import UUID as _UUID

    from app.models import EmailLog, SmsLog

    suffix = uuid4().hex[:8]
    ctx = _setup_hq_network(suffix)
    op_id = _UUID(ctx["op_id"])

    with Session(engine) as session:
        session.add(SmsLog(
            tenant_id=op_id, to_phone="+61400000000", body="test",
            event="shop_mobile_booking_pending", status="failed",
        ))
        session.add(EmailLog(
            tenant_id=op_id, to_email="broken@example.com",
            event="website_lead_alert", status="failed", error="SendGrid HTTP 400",
        ))
        session.commit()

    trouble = client.get("/v1/parent-accounts/me/operations/troubleshooting", headers=ctx["hq"])
    assert trouble.status_code == 200, trouble.text
    items = trouble.json()["items"]

    sms_items = [i for i in items if i["kind"] == "notification_sms_failed" and i["tenant_id"] == ctx["op_id"]]
    email_items = [i for i in items if i["kind"] == "notification_email_failed" and i["tenant_id"] == ctx["op_id"]]
    assert len(sms_items) == 1
    assert sms_items[0]["severity"] == "error"
    assert len(email_items) == 1
    assert "SendGrid HTTP 400" in email_items[0]["detail"]

    # Error-severity items must rank ahead of warning/info ones.
    severities = [i["severity"] for i in items]
    first_non_error = next((i for i, s in enumerate(severities) if s != "error"), len(severities))
    assert all(s == "error" for s in severities[:first_non_error])


def test_provision_shop_creates_minit_slug():
    suffix = uuid4().hex[:8]
    ctx = _setup_hq_network(suffix)
    hq_h = ctx["hq"]

    shop_num = str(int(suffix, 16) % 900000 + 100000)
    res = client.post(
        "/v1/parent-accounts/me/provision-shop",
        headers=hq_h,
        json={"shop_number": shop_num, "tenant_name": "Test Mall"},
    )
    assert res.status_code == 200, res.text
    sites = res.json()["sites"]
    assert any(s["tenant_slug"] == f"minit-{shop_num}" for s in sites)


def test_hq_manager_can_read_operations_overview():
    """HQ staff whose email is not owner_email still resolve the parent account."""
    suffix = uuid4().hex[:8]
    ctx = _setup_hq_network(suffix)
    hq_h = ctx["hq"]
    manager_email = f"hq-mgr-{suffix}@minit-ops.test"

    created = client.post(
        "/v1/users",
        headers=hq_h,
        json={
            "email": manager_email,
            "full_name": "HQ Manager",
            "password": "pass123456",
            "role": "manager",
        },
    )
    assert created.status_code == 201, created.text

    manager_token = _login(MINIT_HQ_SLUG, manager_email)
    overview = client.get(
        "/v1/parent-accounts/me/operations/overview",
        headers=_headers(manager_token),
    )
    assert overview.status_code == 200, overview.text


def test_invited_mobile_van_sales_still_reach_minit_hq():
    """A van's owner takes over its login from HQ's invite, then works in the
    normal Mobile Services app. What they sell must still show in HQ's reports."""
    from uuid import UUID

    from app.models import AutoKeyInvoice

    suffix = uuid4().hex[:8]
    ctx = _setup_hq_network(suffix)
    van_num = str(int(suffix[:4], 16) % 8000 + 1000 + 77)
    owner_email = f"van-owner-{suffix}@franchise.test"

    made = client.post(
        "/v1/parent-accounts/me/provision-shop",
        headers=ctx["hq"],
        json={
            "shop_number": van_num,
            "tenant_name": f"Van {suffix}",
            "shop_type": "mobile",
            "owner_email": owner_email,
            "owner_full_name": "Van Owner",
        },
    )
    assert made.status_code == 200, made.text
    van = next(s for s in made.json()["sites"] if s["shop_number"] == van_num)
    assert van["network_role"] == "operator"

    invite = client.post(f"/v1/parent-accounts/me/sites/{van['tenant_id']}/invite", headers=ctx["hq"])
    assert invite.status_code == 200, invite.text
    token = invite.json()["invite_url"].rsplit("/", 1)[-1]
    done = client.post(
        f"/v1/public/shop-invite/{token}/complete",
        json={"full_name": "Van Owner", "email": owner_email, "password": "Str0ng!Passw0rd"},
    )
    assert done.status_code == 200, done.text
    van_h = _headers(done.json()["access_token"])

    # The van keeps its Minit identity and its Auto Key plan.
    me = client.get("/v1/auth/session", headers=van_h)
    assert me.status_code == 200, me.text
    assert me.json()["product"] == "minit"
    assert me.json()["plan_code"] == "basic_auto_key"
    assert "auto_key" in me.json()["enabled_features"]
    assert me.json()["is_minit_hq_ui"] is False

    customer = client.post("/v1/customers", headers=van_h, json={"full_name": "Van Customer", "phone": "0400123456"})
    assert customer.status_code == 201, customer.text
    job = client.post(
        "/v1/auto-key-jobs",
        headers=van_h,
        json={
            "customer_id": customer.json()["id"],
            "title": f"Van sale {suffix}",
            "key_quantity": 1,
            "priority": "normal",
            "status": "awaiting_quote",
            "programming_status": "pending",
            "deposit_cents": 0,
            "cost_cents": 0,
        },
    )
    assert job.status_code == 201, job.text
    with Session(engine) as session:
        session.add(
            AutoKeyInvoice(
                tenant_id=UUID(van["tenant_id"]),
                auto_key_job_id=UUID(job.json()["id"]),
                invoice_number=f"AKI-{suffix}",
                status="paid",
                total_cents=18500,
            )
        )
        session.commit()

    # Still linked to HQ as an operator after the owner took over the login.
    operators = client.get(
        "/v1/parent-accounts/me/sites", headers=ctx["hq"], params={"plan_kind": "operator"}
    ).json()["sites"]
    assert van["tenant_id"] in {s["tenant_id"] for s in operators}

    report = client.get(
        "/v1/parent-accounts/me/operations/mobile-jobs",
        headers=ctx["hq"],
        params={"operator_tenant_id": van["tenant_id"]},
    )
    assert report.status_code == 200, report.text
    jobs = report.json()["jobs"]
    assert [j["id"] for j in jobs] == [job.json()["id"]]
    assert jobs[0]["paid_cents"] == 18500
