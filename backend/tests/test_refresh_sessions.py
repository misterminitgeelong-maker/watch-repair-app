"""Tests for persisted refresh-token sessions and per-device revocation.

Covers the hardening-roadmap ``refresh-persist`` item: each login creates a
tracked ``RefreshSession`` (sid shared by access+refresh tokens, jti on the
refresh token), ``/auth/sessions/revoke-others`` revokes every other device,
and a revoked refresh token can no longer mint access tokens.
"""
from uuid import uuid4


def _bootstrap_creds(client):
    """Bootstrap a fresh tenant/owner WITHOUT logging in.

    (The shared ``bootstrap_and_login`` fixture would create an extra session,
    which would skew the per-session counts asserted below.)
    """
    slug = f"sess-{uuid4().hex[:8]}"
    email = f"owner-{uuid4().hex[:8]}@example.test"
    password = "supersecret123"
    res = client.post(
        "/v1/auth/bootstrap",
        json={
            "tenant_name": f"Tenant {slug}",
            "tenant_slug": slug,
            "owner_email": email,
            "owner_full_name": "Session Owner",
            "owner_password": password,
        },
    )
    assert res.status_code == 200, res.text
    return slug, email, password


def _login(client, slug, email, password):
    res = client.post(
        "/v1/auth/login",
        json={"tenant_slug": slug, "email": email, "password": password},
    )
    assert res.status_code == 200, res.text
    return res.json()


def test_login_issues_tracked_session(client):
    slug, email, password = _bootstrap_creds(client)
    tokens = _login(client, slug, email, password)

    headers = {"Authorization": f"Bearer {tokens['access_token']}"}
    res = client.get("/v1/auth/sessions", headers=headers)
    assert res.status_code == 200, res.text
    sessions = res.json()["sessions"]
    assert len(sessions) == 1
    assert sessions[0]["is_current"] is True


def test_revoke_others_kills_other_sessions(client):
    slug, email, password = _bootstrap_creds(client)

    session_a = _login(client, slug, email, password)
    session_b = _login(client, slug, email, password)

    headers_a = {"Authorization": f"Bearer {session_a['access_token']}"}

    # Two active sessions before revocation.
    listed = client.get("/v1/auth/sessions", headers=headers_a).json()["sessions"]
    assert len(listed) == 2

    revoke = client.post("/v1/auth/sessions/revoke-others", headers=headers_a)
    assert revoke.status_code == 200, revoke.text
    assert revoke.json()["revoked"] == 1

    # Session B's refresh token is now dead.
    refresh_b = client.post(
        "/v1/auth/refresh", json={"refresh_token": session_b["refresh_token"]}
    )
    assert refresh_b.status_code == 401, refresh_b.text

    # Session A can still refresh, and the sid stays stable.
    refresh_a = client.post(
        "/v1/auth/refresh", json={"refresh_token": session_a["refresh_token"]}
    )
    assert refresh_a.status_code == 200, refresh_a.text
    new_access = refresh_a.json()["access_token"]

    listed_after = client.get(
        "/v1/auth/sessions", headers={"Authorization": f"Bearer {new_access}"}
    ).json()["sessions"]
    assert len(listed_after) == 1
    assert listed_after[0]["is_current"] is True


def test_refresh_rotates_access_but_keeps_session(client):
    slug, email, password = _bootstrap_creds(client)
    tokens = _login(client, slug, email, password)

    refreshed = client.post(
        "/v1/auth/refresh", json={"refresh_token": tokens["refresh_token"]}
    )
    assert refreshed.status_code == 200, refreshed.text

    headers = {"Authorization": f"Bearer {refreshed.json()['access_token']}"}
    sessions = client.get("/v1/auth/sessions", headers=headers).json()["sessions"]
    # Still exactly one session (refresh keeps the same sid rather than forking).
    assert len(sessions) == 1
    assert sessions[0]["is_current"] is True


# ── L2: refresh tokens rotate on every use; reuse ends the session ───────────

def _age_rotation(refresh_token: str, seconds: int) -> None:
    """Pretend the session's last rotation happened ``seconds`` ago."""
    from datetime import datetime, timedelta, timezone

    from sqlmodel import Session, select

    from app.database import engine
    from app.models import RefreshSession
    from app.security import decode_refresh_token

    jti = decode_refresh_token(refresh_token).jti
    with Session(engine) as s:
        row = s.exec(
            select(RefreshSession).where(
                (RefreshSession.jti == jti) | (RefreshSession.previous_jti == jti)
            )
        ).one()
        row.rotated_at = datetime.now(timezone.utc) - timedelta(seconds=seconds)
        s.add(row)
        s.commit()


def test_refresh_token_is_replaced_on_each_use(client):
    slug, email, password = _bootstrap_creds(client)
    first = _login(client, slug, email, password)["refresh_token"]

    second_res = client.post("/v1/auth/refresh", json={"refresh_token": first})
    assert second_res.status_code == 200, second_res.text
    second = second_res.json()["refresh_token"]
    assert second != first

    third_res = client.post("/v1/auth/refresh", json={"refresh_token": second})
    assert third_res.status_code == 200, third_res.text
    assert third_res.json()["refresh_token"] not in (first, second)


def test_reused_refresh_token_revokes_the_session(client):
    from app.dependencies import invalidate_auth_cache

    slug, email, password = _bootstrap_creds(client)
    stolen = _login(client, slug, email, password)["refresh_token"]

    # The legitimate client refreshes and carries on.
    legit = client.post("/v1/auth/refresh", json={"refresh_token": stolen}).json()
    _age_rotation(stolen, 120)

    # Later, the thief replays the old token: refused, and the session ends.
    replay = client.post("/v1/auth/refresh", json={"refresh_token": stolen})
    assert replay.status_code == 401, replay.text

    # The legitimate client's newer refresh token is dead too…
    after = client.post("/v1/auth/refresh", json={"refresh_token": legit["refresh_token"]})
    assert after.status_code == 401, after.text
    # …and so is its access token (the session it belongs to was revoked).
    invalidate_auth_cache()
    me = client.get("/v1/auth/session", headers={"Authorization": f"Bearer {legit['access_token']}"})
    assert me.status_code == 401, me.text


def test_simultaneous_refresh_from_two_tabs_is_not_reuse(client):
    slug, email, password = _bootstrap_creds(client)
    shared = _login(client, slug, email, password)["refresh_token"]

    tab_a = client.post("/v1/auth/refresh", json={"refresh_token": shared})
    tab_b = client.post("/v1/auth/refresh", json={"refresh_token": shared})
    assert tab_a.status_code == 200, tab_a.text
    assert tab_b.status_code == 200, tab_b.text
    # Both tabs end up holding the same current token, which still works.
    from app.security import decode_refresh_token

    assert (
        decode_refresh_token(tab_a.json()["refresh_token"]).jti
        == decode_refresh_token(tab_b.json()["refresh_token"]).jti
    )
    again = client.post("/v1/auth/refresh", json={"refresh_token": tab_b.json()["refresh_token"]})
    assert again.status_code == 200, again.text


def test_logout_stops_the_access_token_too(client):
    from app.dependencies import invalidate_auth_cache

    slug, email, password = _bootstrap_creds(client)
    tokens = _login(client, slug, email, password)
    headers = {"Authorization": f"Bearer {tokens['access_token']}"}
    assert client.post("/v1/auth/logout", headers=headers).status_code == 200
    invalidate_auth_cache()
    assert client.get("/v1/auth/session", headers=headers).status_code == 401


def test_legacy_untracked_refresh_token_upgrades_once(client):
    from sqlmodel import Session, select

    from app.database import engine
    from app.models import Tenant, User
    from app.security import create_refresh_token

    slug, email, password = _bootstrap_creds(client)
    with Session(engine) as s:
        tenant = s.exec(select(Tenant).where(Tenant.slug == slug)).one()
        user = s.exec(select(User).where(User.tenant_id == tenant.id)).first()
        legacy, _ = create_refresh_token(tenant.id, user.id, user.role)

    upgraded = client.post("/v1/auth/refresh", json={"refresh_token": legacy})
    assert upgraded.status_code == 200, upgraded.text
    from app.security import decode_refresh_token

    assert decode_refresh_token(upgraded.json()["refresh_token"]).jti

    # Presenting the same legacy token again is reuse.
    _age_rotation(upgraded.json()["refresh_token"], 120)
    again = client.post("/v1/auth/refresh", json={"refresh_token": legacy})
    assert again.status_code == 401, again.text
