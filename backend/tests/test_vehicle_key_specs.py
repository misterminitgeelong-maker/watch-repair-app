import os
from pathlib import Path
from uuid import uuid4

_TEST_DB = Path(__file__).with_name(f"test_vehicle_specs_{uuid4().hex}.db")
os.environ["DATABASE_URL"] = f"sqlite:///{_TEST_DB.as_posix()}"

from fastapi.testclient import TestClient

from app.database import create_db_and_tables
from app.main import app

create_db_and_tables()
client = TestClient(app)


def _token() -> str:
    suffix = uuid4().hex[:8]
    slug = f"vs-{suffix}"
    assert client.post(
        "/v1/auth/bootstrap",
        json={
            "tenant_name": "VS Tenant",
            "tenant_slug": slug,
            "owner_email": f"o{suffix}@vs.test",
            "owner_full_name": "Owner",
            "owner_password": "pass123456",
            "plan_code": "basic_auto_key",
        },
    ).status_code == 200
    login = client.post(
        "/v1/auth/login",
        json={"tenant_slug": slug, "email": f"o{suffix}@vs.test", "password": "pass123456"},
    )
    assert login.status_code == 200
    return login.json()["access_token"]


def test_vehicle_key_specs_search_requires_auto_key():
    token = _token()
    h = {"Authorization": f"Bearer {token}"}
    r = client.get("/v1/vehicle-key-specs/search", params={"make": "Toyota", "model": "Hilux", "year": 2010}, headers=h)
    assert r.status_code == 200
    data = r.json()
    assert "matches" in data
    assert len(data["matches"]) >= 1
    first = data["matches"][0]
    assert first["vehicle_make"] == "Toyota"
    assert "Hilux" in first["vehicle_model"]
    assert first.get("key_type") or first.get("chip_type") or first.get("tech_notes")


def test_vehicle_key_specs_short_query_empty():
    token = _token()
    h = {"Authorization": f"Bearer {token}"}
    r = client.get("/v1/vehicle-key-specs/search", params={"make": "T"}, headers=h)
    assert r.status_code == 200
    assert r.json()["matches"] == []
