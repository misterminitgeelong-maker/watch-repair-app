"""Shop-owner invite claim flow: HQ sends a one-time link, the franchisee sets
their own email/password (replacing the shared HQ credentials), and lands
signed in."""

import os
from pathlib import Path
from uuid import uuid4

_TEST_DB = Path(__file__).with_name(f"test_shop_owner_invites_{uuid4().hex}.db")
os.environ.setdefault("DATABASE_URL", f"sqlite:///{_TEST_DB.as_posix()}")
os.environ.setdefault("JWT_SECRET", "test-secret-not-for-production")
os.environ.setdefault("APP_ENV", "test")

from fastapi.testclient import TestClient
from sqlmodel import Session, select

from app.database import create_db_and_tables, engine
from app.main import app
from app.models import EmailLog, ShopOwnerInvite, SmsLog, Tenant, User

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


def test_create_invite_emails_the_link_and_logs_the_attempt():
    from uuid import UUID as _UUID

    suffix = uuid4().hex[:8]
    ctx = _setup_shop(suffix)

    created = client.post(f"/v1/parent-accounts/me/sites/{ctx['tenant_id']}/invite", headers=ctx["hq"])
    assert created.status_code == 200, created.text
    body = created.json()
    # Twilio/SendGrid aren't configured in tests, so delivery itself is a
    # dry-run — but the send was attempted and logged either way.
    assert "email_sent" in body
    assert "sms_sent" in body
    assert body["sms_sent"] is False  # no mobile on file for this owner yet

    with Session(engine) as session:
        logs = session.exec(
            select(EmailLog)
            .where(EmailLog.tenant_id == _UUID(ctx["tenant_id"]))
            .where(EmailLog.event == "shop_owner_invite")
        ).all()
        assert len(logs) == 1
        assert logs[0].to_email == ctx["hq_email"]


def test_create_invite_texts_the_link_when_owner_has_a_mobile_on_file():
    from uuid import UUID as _UUID

    suffix = uuid4().hex[:8]
    ctx = _setup_shop(suffix)

    with Session(engine) as session:
        tenant_id = _UUID(ctx["tenant_id"])
        owner = session.exec(select(User).where(User.tenant_id == tenant_id)).first()
        owner.mobile = "+61400123456"
        session.add(owner)
        session.commit()

    created = client.post(f"/v1/parent-accounts/me/sites/{ctx['tenant_id']}/invite", headers=ctx["hq"])
    assert created.status_code == 200, created.text
    body = created.json()
    assert body["owner_mobile"] == "+61400123456"

    with Session(engine) as session:
        sms_logs = session.exec(
            select(SmsLog).where(SmsLog.tenant_id == tenant_id).where(SmsLog.event == "shop_owner_invite")
        ).all()
        assert len(sms_logs) == 1
        assert sms_logs[0].to_phone == "+61400123456"


def test_hq_can_set_shop_identity_contact_used_by_invite():
    from uuid import UUID as _UUID

    suffix = uuid4().hex[:8]
    ctx = _setup_shop(suffix)
    shop_email = f"shop-{suffix}@franchise.test"
    shop_phone = "0412 345 678"

    patched = client.patch(
        f"/v1/parent-accounts/me/sites/{ctx['tenant_id']}",
        headers=ctx["hq"],
        json={"shop_email": shop_email, "shop_phone": shop_phone},
    )
    assert patched.status_code == 200, patched.text
    body = patched.json()
    assert body["shop_email"] == shop_email
    assert body["shop_phone"] == shop_phone

    with Session(engine) as session:
        tenant = session.get(Tenant, _UUID(ctx["tenant_id"]))
        assert tenant.shop_email == shop_email
        assert tenant.shop_phone == shop_phone
        owner = session.exec(select(User).where(User.tenant_id == tenant.id)).first()
        assert owner.email == ctx["hq_email"]  # login identity is unchanged

    created = client.post(f"/v1/parent-accounts/me/sites/{ctx['tenant_id']}/invite", headers=ctx["hq"])
    assert created.status_code == 200, created.text
    invite = created.json()
    assert invite["owner_email"] == shop_email
    assert invite["owner_mobile"] == shop_phone

    with Session(engine) as session:
        tenant_id = _UUID(ctx["tenant_id"])
        email_logs = session.exec(
            select(EmailLog)
            .where(EmailLog.tenant_id == tenant_id)
            .where(EmailLog.event == "shop_owner_invite")
        ).all()
        assert len(email_logs) == 1
        assert email_logs[0].to_email == shop_email
        sms_logs = session.exec(
            select(SmsLog).where(SmsLog.tenant_id == tenant_id).where(SmsLog.event == "shop_owner_invite")
        ).all()
        assert len(sms_logs) == 1
        assert sms_logs[0].to_phone == shop_phone


def test_hq_shop_contact_rejects_invalid_email_and_phone():
    suffix = uuid4().hex[:8]
    ctx = _setup_shop(suffix)

    bad_email = client.patch(
        f"/v1/parent-accounts/me/sites/{ctx['tenant_id']}",
        headers=ctx["hq"],
        json={"shop_email": "not-an-email"},
    )
    assert bad_email.status_code == 400

    bad_phone = client.patch(
        f"/v1/parent-accounts/me/sites/{ctx['tenant_id']}",
        headers=ctx["hq"],
        json={"shop_phone": "123"},
    )
    assert bad_phone.status_code == 400


def test_hq_can_clear_shop_contact_and_invite_falls_back_to_owner():
    from uuid import UUID as _UUID

    suffix = uuid4().hex[:8]
    ctx = _setup_shop(suffix)

    client.patch(
        f"/v1/parent-accounts/me/sites/{ctx['tenant_id']}",
        headers=ctx["hq"],
        json={"shop_email": f"shop-{suffix}@franchise.test", "shop_phone": "0412 345 678"},
    )
    cleared = client.patch(
        f"/v1/parent-accounts/me/sites/{ctx['tenant_id']}",
        headers=ctx["hq"],
        json={"shop_email": "", "shop_phone": ""},
    )
    assert cleared.status_code == 200, cleared.text
    assert cleared.json()["shop_email"] is None
    assert cleared.json()["shop_phone"] is None

    created = client.post(f"/v1/parent-accounts/me/sites/{ctx['tenant_id']}/invite", headers=ctx["hq"])
    assert created.status_code == 200, created.text
    assert created.json()["owner_email"] == ctx["hq_email"]
    assert created.json()["owner_mobile"] is None

    with Session(engine) as session:
        tenant = session.get(Tenant, _UUID(ctx["tenant_id"]))
        assert tenant.shop_email is None
        assert tenant.shop_phone is None
