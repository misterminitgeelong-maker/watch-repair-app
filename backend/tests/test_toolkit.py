import os
from pathlib import Path
from uuid import uuid4

_TEST_DB = Path(__file__).with_name(f"test_toolkit_{uuid4().hex}.db")
os.environ["DATABASE_URL"] = f"sqlite:///{_TEST_DB.as_posix()}"

from fastapi.testclient import TestClient

from app.database import create_db_and_tables
from app.main import app

create_db_and_tables()
client = TestClient(app)


def _bootstrap_auto_key() -> str:
    suffix = uuid4().hex[:8]
    slug = f"tk-{suffix}"
    assert client.post(
        "/v1/auth/bootstrap",
        json={
            "tenant_name": "Toolkit Tenant",
            "tenant_slug": slug,
            "owner_email": f"o{suffix}@tk.test",
            "owner_full_name": "Owner",
            "owner_password": "pass123456",
            "plan_code": "basic_auto_key",
        },
    ).status_code == 200
    login = client.post(
        "/v1/auth/login",
        json={"tenant_slug": slug, "email": f"o{suffix}@tk.test", "password": "pass123456"},
    )
    assert login.status_code == 200
    return login.json()["access_token"]


def test_toolkit_catalog_requires_auto_key_plan():
    token = _bootstrap_auto_key()
    headers = {"Authorization": f"Bearer {token}"}
    r = client.get("/v1/toolkit/catalog", headers=headers)
    assert r.status_code == 200
    data = r.json()
    assert "groups" in data
    assert len(data["groups"]) >= 1
    assert any(s["id"] == "add_key_blade_remote_head" for s in data["scenarios"])


def test_toolkit_selection_and_recommend():
    token = _bootstrap_auto_key()
    headers = {"Authorization": f"Bearer {token}"}

    r0 = client.get("/v1/toolkit/my-selection", headers=headers)
    assert r0.status_code == 200
    assert r0.json()["tool_keys"] == []

    r1 = client.put(
        "/v1/toolkit/my-selection",
        headers=headers,
        json={"tool_keys": ["keyline_ninja_total", "abrites_avdi", "unknown_x"]},
    )
    assert r1.status_code == 400

    r2 = client.put(
        "/v1/toolkit/my-selection",
        headers=headers,
        json={"tool_keys": ["keyline_ninja_total", "abrites_avdi"]},
    )
    assert r2.status_code == 200
    assert r2.json()["tool_keys"] == ["keyline_ninja_total", "abrites_avdi"]

    r3 = client.get("/v1/toolkit/my-selection", headers=headers)
    assert r3.json()["tool_keys"] == ["keyline_ninja_total", "abrites_avdi"]

    rec = client.post(
        "/v1/toolkit/recommend",
        headers=headers,
        json={"scenario_id": "add_key_blade_remote_head"},
    )
    assert rec.status_code == 200
    body = rec.json()
    assert body["scenario_id"] == "add_key_blade_remote_head"
    assert body["ready_for_required"] is True
    assert len(body["missing_required"]) == 0

    client.put("/v1/toolkit/my-selection", headers=headers, json={"tool_keys": ["keyline_ninja_total"]})
    rec2 = client.post("/v1/toolkit/recommend", headers=headers, json={"scenario_id": "add_key_blade_remote_head"})
    assert rec2.json()["ready_for_required"] is False
    missing = {x["key"] for x in rec2.json()["missing_required"]}
    assert "abrites_avdi" in missing

    # Substitute cutter satisfies key-cutting slot (canonical is Keyline Ninja Total in seed)
    client.put(
        "/v1/toolkit/my-selection",
        headers=headers,
        json={"tool_keys": ["silca_futura_m600", "abrites_avdi"]},
    )
    rec3 = client.post("/v1/toolkit/recommend", headers=headers, json={"scenario_id": "add_key_blade_remote_head"})
    assert rec3.status_code == 200
    assert rec3.json()["ready_for_required"] is True


def test_toolkit_unknown_scenario():
    token = _bootstrap_auto_key()
    headers = {"Authorization": f"Bearer {token}"}
    r = client.post("/v1/toolkit/recommend", headers=headers, json={"scenario_id": "nope"})
    assert r.status_code == 404
