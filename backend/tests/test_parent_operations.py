"""Parent-account HQ operations APIs (Minit network dashboard)."""

import os
from pathlib import Path
from uuid import uuid4

_TEST_DB = Path(__file__).with_name(f"test_parent_ops_{uuid4().hex}.db")
os.environ["DATABASE_URL"] = f"sqlite:///{_TEST_DB.as_posix()}"
os.environ.setdefault("JWT_SECRET", "test-secret-not-for-production")
os.environ.setdefault("APP_ENV", "test")

from fastapi.testclient import TestClient
from sqlmodel import Session, select

from app.database import create_db_and_tables, engine
from app.main import app
from app.minit_branding import MINIT_HQ_SLUG
from app.models import Tenant, User
from app.security import hash_password

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
    assert boot.status_code in (200, 409), boot.text
    if boot.status_code == 409:
        # Another test may have created the HQ tenant without bootstrap side effects.
        from app.minit_branding import ensure_minit_tenant_plan
        from app.routes.auth import _ensure_parent_membership, _get_or_create_parent_account

        with Session(engine) as session:
            tenant = session.exec(select(Tenant).where(Tenant.slug == hq_slug)).first()
            assert tenant is not None, f"HQ tenant {hq_slug} missing after 409"
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
            parent = _get_or_create_parent_account(session, hq_email, "HQ Owner")
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

    link = client.post(
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
    assert "items" in trouble.json()


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
