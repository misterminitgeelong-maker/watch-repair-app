"""DELETE /v1/users/{id} — owner-only, FK detachment, business rules."""
import os
from uuid import uuid4
from pathlib import Path

_TEST_DB = Path(__file__).with_name(f"test_ud_{uuid4().hex}.db")
os.environ["DATABASE_URL"] = f"sqlite:///{_TEST_DB.as_posix()}"

from fastapi.testclient import TestClient  # noqa: E402

from app.database import create_db_and_tables  # noqa: E402
from app.main import app  # noqa: E402

create_db_and_tables()
client = TestClient(app)


def _bootstrap() -> tuple[str, str]:
    suffix = uuid4().hex[:8]
    slug = f"ud-{suffix}"
    assert client.post(
        "/v1/auth/bootstrap",
        json={
            "tenant_name": "UD Test",
            "tenant_slug": slug,
            "owner_email": f"owner-{suffix}@test.com",
            "owner_full_name": "Owner",
            "owner_password": "pass123456",
            "plan_code": "pro",
        },
    ).status_code == 200
    login = client.post(
        "/v1/auth/login",
        json={"tenant_slug": slug, "email": f"owner-{suffix}@test.com", "password": "pass123456"},
    )
    assert login.status_code == 200
    return login.json()["access_token"], slug


def _session_user_id(token: str) -> str:
    r = client.get("/v1/auth/session", headers={"Authorization": f"Bearer {token}"})
    assert r.status_code == 200
    return r.json()["user"]["id"]


def test_delete_self_rejected():
    token, _ = _bootstrap()
    h = {"Authorization": f"Bearer {token}"}
    uid = _session_user_id(token)
    r = client.delete(f"/v1/users/{uid}", headers=h)
    assert r.status_code == 400
    assert "own" in r.json()["detail"].lower()


def test_manager_cannot_delete_user():
    token, slug = _bootstrap()
    h_owner = {"Authorization": f"Bearer {token}"}
    suffix = uuid4().hex[:8]
    mr = client.post(
        "/v1/users",
        headers=h_owner,
        json={
            "full_name": "Manager",
            "email": f"mgr-{suffix}@test.com",
            "password": "pass123456",
            "role": "manager",
        },
    )
    assert mr.status_code == 201
    tr = client.post(
        "/v1/users",
        headers=h_owner,
        json={
            "full_name": "Tech",
            "email": f"tech-{suffix}@test.com",
            "password": "pass123456",
            "role": "tech",
        },
    )
    assert tr.status_code == 201
    tech_id = tr.json()["id"]
    login_m = client.post(
        "/v1/auth/login",
        json={"tenant_slug": slug, "email": f"mgr-{suffix}@test.com", "password": "pass123456"},
    )
    assert login_m.status_code == 200
    mgr_token = login_m.json()["access_token"]
    dr = client.delete(f"/v1/users/{tech_id}", headers={"Authorization": f"Bearer {mgr_token}"})
    assert dr.status_code == 403


def test_delete_second_owner_succeeds():
    token, _ = _bootstrap()
    h = {"Authorization": f"Bearer {token}"}
    suffix = uuid4().hex[:8]
    r = client.post(
        "/v1/users",
        headers=h,
        json={
            "full_name": "Co-owner",
            "email": f"co-{suffix}@test.com",
            "password": "pass123456",
            "role": "owner",
        },
    )
    assert r.status_code == 201
    co_id = r.json()["id"]
    r2 = client.delete(f"/v1/users/{co_id}", headers=h)
    assert r2.status_code == 204


def test_delete_tech_unassigns_auto_key_job():
    token, _ = _bootstrap()
    h = {"Authorization": f"Bearer {token}"}
    suffix = uuid4().hex[:8]
    tr = client.post(
        "/v1/users",
        headers=h,
        json={
            "full_name": "Tech",
            "email": f"tech-{suffix}@test.com",
            "password": "pass123456",
            "role": "tech",
        },
    )
    assert tr.status_code == 201, tr.text
    tech_id = tr.json()["id"]
    cr = client.post("/v1/customers", headers=h, json={"full_name": "C", "phone": "0411000222"})
    assert cr.status_code == 201
    cid = cr.json()["id"]
    jr = client.post(
        "/v1/auto-key-jobs",
        headers=h,
        json={
            "customer_id": cid,
            "title": "Job",
            "assigned_user_id": tech_id,
            "key_quantity": 1,
            "priority": "normal",
            "status": "awaiting_quote",
            "programming_status": "pending",
            "deposit_cents": 0,
            "cost_cents": 0,
        },
    )
    assert jr.status_code == 201, jr.text
    job_id = jr.json()["id"]
    assert jr.json()["assigned_user_id"] == tech_id
    dr = client.delete(f"/v1/users/{tech_id}", headers=h)
    assert dr.status_code == 204
    gr = client.get(f"/v1/auto-key-jobs/{job_id}", headers=h)
    assert gr.status_code == 200
    assert gr.json().get("assigned_user_id") in (None, "")


def test_delete_unknown_user_404():
    token, _ = _bootstrap()
    h = {"Authorization": f"Bearer {token}"}
    fake = "00000000-0000-4000-8000-000000000001"
    r = client.delete(f"/v1/users/{fake}", headers=h)
    assert r.status_code == 404
