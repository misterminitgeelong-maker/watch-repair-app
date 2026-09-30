"""HQ admins helping accounts in their own network: reset links, email fixes,
account status and message logs."""

import os
from datetime import datetime, timezone
from pathlib import Path
from uuid import UUID, uuid4

_TEST_DB = Path(__file__).with_name(f"test_hq_account_support_{uuid4().hex}.db")
os.environ.setdefault("DATABASE_URL", f"sqlite:///{_TEST_DB.as_posix()}")
os.environ.setdefault("JWT_SECRET", "test-secret-not-for-production")
os.environ.setdefault("APP_ENV", "test")

from fastapi.testclient import TestClient
from sqlmodel import Session, select

from app.database import create_db_and_tables, engine
from app.main import app
from app.models import ParentAccountEventLog, RefreshSession, ShopOwnerInvite, User

from tests.test_shop_owner_invites import _headers, _login, _setup_shop

create_db_and_tables()
client = TestClient(app)


def _claimed_shop(suffix: str) -> dict:
    """A shop whose owner has taken over their own login."""
    ctx = _setup_shop(suffix)
    invite = client.post(f"/v1/parent-accounts/me/sites/{ctx['tenant_id']}/invite", headers=ctx["hq"]).json()
    token = invite["invite_url"].rsplit("/", 1)[-1]
    email = f"owner-{suffix}@test.local"
    res = client.post(
        f"/v1/public/shop-invite/{token}/complete",
        json={"full_name": "Real Owner", "email": email, "password": "brandnewpass1!"},
    )
    assert res.status_code == 200, res.text
    with Session(engine) as session:
        owner = session.exec(select(User).where(User.email == email)).one()
        ctx["owner_id"] = str(owner.id)
    ctx["owner_email"] = email
    return ctx


def _base(ctx: dict) -> str:
    return f"/v1/parent-accounts/me/sites/{ctx['tenant_id']}/accounts"


def test_reset_link_is_sent_and_lets_owner_choose_new_password_and_is_audited():
    ctx = _claimed_shop(uuid4().hex[:8])
    res = client.post(f"{_base(ctx)}/{ctx['owner_id']}/reset-link", headers=ctx["hq"])
    assert res.status_code == 200, res.text
    body = res.json()
    assert "invite_url" not in body and "token" not in body  # HQ never sees the link

    with Session(engine) as session:
        invite = session.exec(
            select(ShopOwnerInvite).where(ShopOwnerInvite.owner_user_id == UUID(ctx["owner_id"])).order_by(ShopOwnerInvite.created_at.desc())
        ).first()
        assert invite.status == "pending"
        token = invite.token
        events = session.exec(
            select(ParentAccountEventLog).where(ParentAccountEventLog.event_type == "account_reset_link_sent")
        ).all()
        assert any(ctx["owner_email"] in e.event_summary for e in events)

    done = client.post(
        f"/v1/public/shop-invite/{token}/complete",
        json={"full_name": "Real Owner", "email": ctx["owner_email"], "password": "anotherpass22!"},
    )
    assert done.status_code == 200, done.text
    assert _login(ctx["shop_slug"], ctx["owner_email"], "anotherpass22!")


def test_change_email_revokes_sessions_blocks_duplicates_and_is_audited():
    ctx = _claimed_shop(uuid4().hex[:8])
    _login(ctx["shop_slug"], ctx["owner_email"], "brandnewpass1!")
    after_login = datetime.now(timezone.utc).replace(tzinfo=None)
    new_email = f"fixed-{uuid4().hex[:6]}@test.local"
    res = client.patch(f"{_base(ctx)}/{ctx['owner_id']}/email", headers=ctx["hq"], json={"email": new_email})
    assert res.status_code == 200, res.text
    assert res.json()["email"] == new_email
    assert _login(ctx["shop_slug"], new_email, "brandnewpass1!")

    with Session(engine) as session:
        sessions = session.exec(select(RefreshSession).where(RefreshSession.user_id == UUID(ctx["owner_id"]))).all()
        assert sessions and all(r.revoked_at is not None for r in sessions if r.created_at < after_login)
        events = session.exec(
            select(ParentAccountEventLog).where(ParentAccountEventLog.event_type == "account_email_changed")
        ).all()
        assert any(new_email in e.event_summary for e in events)

    blank = client.patch(f"{_base(ctx)}/{ctx['owner_id']}/email", headers=ctx["hq"], json={"email": "nope"})
    assert blank.status_code == 400


def test_hq_login_copy_is_refused():
    ctx = _setup_shop(uuid4().hex[:8])  # shop still shares HQ's login
    accounts = client.get(_base(ctx), headers=ctx["hq"])
    assert accounts.status_code == 200, accounts.text
    hq_copy = next(a for a in accounts.json() if a["is_hq_login"])
    assert client.post(f"{_base(ctx)}/{hq_copy['user_id']}/reset-link", headers=ctx["hq"]).status_code == 409
    assert (
        client.patch(f"{_base(ctx)}/{hq_copy['user_id']}/email", headers=ctx["hq"], json={"email": "x@test.local"}).status_code
        == 409
    )


def test_unlinked_site_and_non_hq_are_refused():
    ctx = _claimed_shop(uuid4().hex[:8])
    other = _claimed_shop(uuid4().hex[:8])
    # HQ A cannot touch HQ B's site.
    res = client.post(
        f"/v1/parent-accounts/me/sites/{other['tenant_id']}/accounts/{other['owner_id']}/reset-link", headers=ctx["hq"]
    )
    assert res.status_code == 404
    # The shop owner is not HQ.
    owner_h = _headers(_login(ctx["shop_slug"], ctx["owner_email"], "brandnewpass1!"))
    res = client.get(_base(ctx), headers=owner_h)
    assert res.status_code in (403, 404)


def test_status_and_message_logs():
    ctx = _claimed_shop(uuid4().hex[:8])
    client.post(f"{_base(ctx)}/{ctx['owner_id']}/reset-link", headers=ctx["hq"])
    accounts = client.get(_base(ctx), headers=ctx["hq"]).json()
    owner = next(a for a in accounts if a["user_id"] == ctx["owner_id"])
    assert owner["latest_link_status"] == "pending"
    assert owner["is_hq_login"] is False
    logs = client.get(f"/v1/parent-accounts/me/sites/{ctx['tenant_id']}/message-logs", headers=ctx["hq"])
    assert logs.status_code == 200, logs.text
    assert all("body" not in row for row in logs.json())
