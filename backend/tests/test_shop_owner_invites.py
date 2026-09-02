"""Shop-owner invite claim flow: HQ sends a one-time link, the franchisee sets
their own email/password (replacing the shared HQ credentials), and lands
signed in."""

import os
from pathlib import Path
from uuid import uuid4

_TEST_DB = Path(__file__).with_name(f"test_shop_owner_invites_{uuid4().hex}.db")
os.environ["DATABASE_URL"] = f"sqlite:///{_TEST_DB.as_posix()}"
os.environ.setdefault("JWT_SECRET", "test-secret-not-for-production")
os.environ.setdefault("APP_ENV", "test")

from fastapi.testclient import TestClient
from sqlmodel import Session, select

from app.database import create_db_and_tables, engine
from app.main import app
from app.models import ShopOwnerInvite, User

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


def _login(slug: str, email: str, password: str = "pass123456") -> str:
    res = client.post(
        "/v1/auth/login",
        json={"tenant_slug": slug, "email": email, "password": password},
    )
    assert res.status_code == 200, res.text
    return res.json()["access_token"]


def _headers(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def _setup_shop(suffix: str) -> dict:
    """HQ tenant, plus a retail shop provisioned via create-tenant (shares HQ creds)."""
    hq_slug = f"hq-{suffix}"
    hq_email = f"hq-{suffix}@test.local"
    shop_slug = f"shop-{suffix}"
    _bootstrap(hq_slug, hq_email, "pro")
    hq_h = _headers(_login(hq_slug, hq_email))

    created = client.post(
        "/v1/parent-accounts/me/create-tenant",
        headers=hq_h,
        json={"tenant_name": f"Retail {suffix}", "tenant_slug": shop_slug, "plan_code": "booking_only"},
    )
    assert created.status_code == 200, created.text
    sites = client.get("/v1/parent-accounts/me/sites", headers=hq_h, params={"plan_kind": "all"}).json()
    site = next(s for s in sites["sites"] if s["tenant_slug"] == shop_slug)
    return {"hq": hq_h, "hq_email": hq_email, "shop_slug": shop_slug, "tenant_id": site["tenant_id"]}


def test_create_invite_requires_linked_site():
    suffix = uuid4().hex[:8]
    ctx = _setup_shop(suffix)
    res = client.post(f"/v1/parent-accounts/me/sites/{uuid4()}/invite", headers=ctx["hq"])
    assert res.status_code == 404


def test_create_and_complete_invite_replaces_owner_credentials():
    suffix = uuid4().hex[:8]
    ctx = _setup_shop(suffix)

    created = client.post(f"/v1/parent-accounts/me/sites/{ctx['tenant_id']}/invite", headers=ctx["hq"])
    assert created.status_code == 200, created.text
    invite = created.json()
    assert invite["status"] == "pending"
    assert invite["owner_email"] == ctx["hq_email"]  # shop was provisioned sharing HQ's login
    token = invite["invite_url"].rsplit("/", 1)[-1]

    public = client.get(f"/v1/public/shop-invite/{token}")
    assert public.status_code == 200, public.text
    assert public.json()["status"] == "pending"

    new_email = f"franchisee-{suffix}@test.local"
    complete = client.post(
        f"/v1/public/shop-invite/{token}/complete",
        json={"full_name": "Real Owner", "email": new_email, "password": "brandnewpass1!"},
    )
    assert complete.status_code == 200, complete.text
    body = complete.json()
    assert body["access_token"]

    # The invite is now spent.
    replay = client.get(f"/v1/public/shop-invite/{token}")
    assert replay.status_code == 410

    complete_again = client.post(
        f"/v1/public/shop-invite/{token}/complete",
        json={"full_name": "Someone Else", "email": "x@test.local", "password": "brandnewpass1!"},
    )
    assert complete_again.status_code == 410

    # Login now works with the new credentials, on the same owner row (not a new user).
    new_token = _login(ctx["shop_slug"], new_email, "brandnewpass1!")
    assert new_token

    with Session(engine) as session:
        row = session.exec(select(ShopOwnerInvite).where(ShopOwnerInvite.token == token)).first()
        assert row.status == "completed"
        assert row.completed_at is not None
        owner = session.get(User, row.owner_user_id)
        assert owner.email == new_email
        assert owner.full_name == "Real Owner"


def test_reissuing_invite_revokes_the_previous_one():
    suffix = uuid4().hex[:8]
    ctx = _setup_shop(suffix)

    first = client.post(f"/v1/parent-accounts/me/sites/{ctx['tenant_id']}/invite", headers=ctx["hq"]).json()
    second = client.post(f"/v1/parent-accounts/me/sites/{ctx['tenant_id']}/invite", headers=ctx["hq"]).json()
    assert first["id"] != second["id"]

    first_token = first["invite_url"].rsplit("/", 1)[-1]
    res = client.get(f"/v1/public/shop-invite/{first_token}")
    assert res.status_code == 410

    latest = client.get(f"/v1/parent-accounts/me/sites/{ctx['tenant_id']}/invite", headers=ctx["hq"])
    assert latest.status_code == 200
    assert latest.json()["id"] == second["id"]


def test_complete_invite_rejects_weak_password():
    suffix = uuid4().hex[:8]
    ctx = _setup_shop(suffix)
    invite = client.post(f"/v1/parent-accounts/me/sites/{ctx['tenant_id']}/invite", headers=ctx["hq"]).json()
    token = invite["invite_url"].rsplit("/", 1)[-1]

    res = client.post(
        f"/v1/public/shop-invite/{token}/complete",
        json={"full_name": "Real Owner", "email": f"weak-{suffix}@test.local", "password": "short"},
    )
    assert res.status_code == 400


def test_unknown_invite_token_is_404():
    res = client.get("/v1/public/shop-invite/does-not-exist")
    assert res.status_code == 404


def test_create_invite_can_set_plan_level():
    from uuid import UUID as _UUID

    from app.models import Tenant as _Tenant

    suffix = uuid4().hex[:8]
    ctx = _setup_shop(suffix)  # provisioned as booking_only

    created = client.post(
        f"/v1/parent-accounts/me/sites/{ctx['tenant_id']}/invite",
        headers=ctx["hq"],
        json={"plan_code": "basic_auto_key"},
    )
    assert created.status_code == 200, created.text
    assert created.json()["plan_code"] == "basic_auto_key"

    with Session(engine) as session:
        tenant = session.get(_Tenant, _UUID(ctx["tenant_id"]))
        assert tenant.plan_code == "basic_auto_key"


def test_create_invite_rejects_plan_outside_curated_set():
    suffix = uuid4().hex[:8]
    ctx = _setup_shop(suffix)
    res = client.post(
        f"/v1/parent-accounts/me/sites/{ctx['tenant_id']}/invite",
        headers=ctx["hq"],
        json={"plan_code": "basic_watch"},  # not a mobile-services plan
    )
    assert res.status_code == 400


def test_create_invite_without_plan_code_keeps_current_plan():
    suffix = uuid4().hex[:8]
    ctx = _setup_shop(suffix)
    created = client.post(f"/v1/parent-accounts/me/sites/{ctx['tenant_id']}/invite", headers=ctx["hq"])
    assert created.status_code == 200, created.text
    assert created.json()["plan_code"] == "booking_only"
