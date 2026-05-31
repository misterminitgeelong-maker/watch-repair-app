"""Minit product plan normalization and session features."""

import os
from pathlib import Path
from uuid import uuid4

_TEST_DB = Path(__file__).with_name(f"test_minit_{uuid4().hex}.db")
os.environ["DATABASE_URL"] = f"sqlite:///{_TEST_DB.as_posix()}"
os.environ.setdefault("JWT_SECRET", "test-secret-not-for-production")
os.environ.setdefault("APP_ENV", "test")

from fastapi.testclient import TestClient
from sqlmodel import Session, select

from app.database import create_db_and_tables, engine
from app.main import app
from app.minit_branding import effective_plan_code, ensure_minit_tenant_plan, is_minit_hq_ui, tenant_product
from app.models import Tenant

create_db_and_tables()
client = TestClient(app)


def _bootstrap(tenant_slug: str, email: str, password: str, plan_code: str = "pro") -> str:
    res = client.post(
        "/v1/auth/bootstrap",
        json={
            "tenant_name": f"Tenant {tenant_slug}",
            "tenant_slug": tenant_slug,
            "owner_email": email,
            "owner_full_name": "Owner",
            "owner_password": password,
            "plan_code": plan_code,
        },
    )
    assert res.status_code == 200, res.text
    login = client.post(
        "/v1/auth/login",
        json={"tenant_slug": tenant_slug, "email": email, "password": password},
    )
    assert login.status_code == 200, login.text
    return login.json()["access_token"]


def test_minit_hq_effective_plan_and_product():
    tenant = Tenant(name="HQ", slug="mmsupport", plan_code="enterprise")
    assert effective_plan_code(tenant) == "minit_hq"
    assert tenant_product("mmsupport") == "minit"
    assert tenant_product("minit-3269") == "minit"
    assert tenant_product("timekeepers") == "mainspring"


def test_ensure_minit_hq_persists_plan():
    with Session(engine) as session:
        tenant = session.exec(select(Tenant).where(Tenant.slug == "mmsupport")).first()
        if not tenant:
            tenant = Tenant(name="Test HQ", slug="mmsupport", plan_code="enterprise")
            session.add(tenant)
            session.commit()
        session.refresh(tenant)
        ensure_minit_tenant_plan(session, tenant)
        session.commit()
        session.refresh(tenant)
        assert tenant.plan_code == "minit_hq"


def test_minit_hq_session_flag():
    from app.models import User
    from app.routes.auth import _build_auth_session_response
    from app.security import hash_password

    with Session(engine) as session:
        tenant = session.exec(select(Tenant).where(Tenant.slug == "mmsupport")).first()
        if not tenant:
            tenant = Tenant(name="Minit HQ", slug="mmsupport", plan_code="enterprise")
            session.add(tenant)
            session.commit()
            session.refresh(tenant)
        user = User(
            tenant_id=tenant.id,
            email=f"hq-{uuid4().hex[:8]}@minit.test",
            full_name="HQ",
            role="owner",
            password_hash=hash_password("password12345"),
            is_active=True,
        )
        session.add(user)
        session.commit()
        session.refresh(user)
        payload = _build_auth_session_response(session, tenant, user)
    assert payload.is_minit_hq_ui is True
    assert payload.plan_code == "minit_hq"
    assert payload.tenant_slug == "mmsupport"


def test_minit_hq_ui_helper():
    assert is_minit_hq_ui(Tenant(name="HQ", slug="mmsupport", plan_code="enterprise")) is True
    assert is_minit_hq_ui(Tenant(name="Shop", slug="minit-3269", plan_code="booking_only")) is False


def test_minit_retail_session_strips_repair_features():
    suffix = uuid4().hex[:8]
    slug = f"minit-{suffix}"
    email = f"shop-{suffix}@minit.test"
    token = _bootstrap(slug, email, "password12345", plan_code="enterprise")
    session = client.get("/v1/auth/session", headers={"Authorization": f"Bearer {token}"})
    assert session.status_code == 200
    body = session.json()
    assert body["product"] == "minit"
    assert body["plan_code"] == "booking_only"
    assert "watch" not in body["enabled_features"]
    assert "shoe" not in body["enabled_features"]
    assert "shop_mobile_booking" in body["enabled_features"]
