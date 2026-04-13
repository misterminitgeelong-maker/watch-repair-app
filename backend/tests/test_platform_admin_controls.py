import os
from pathlib import Path
from uuid import UUID
from uuid import uuid4

from fastapi.testclient import TestClient
from sqlmodel import Session, select

_TEST_DB = Path(__file__).with_name(f"test_platform_admin_{uuid4().hex}.db")
os.environ["DATABASE_URL"] = f"sqlite:///{_TEST_DB.as_posix()}"
os.environ.setdefault("APP_ENV", "test")

from app.database import create_db_and_tables, engine  # noqa: E402
from app.main import app  # noqa: E402
from app.models import TenantEventLog, User  # noqa: E402

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
