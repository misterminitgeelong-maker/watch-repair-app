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
