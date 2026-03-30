import os
from pathlib import Path
from uuid import UUID, uuid4

_TEST_DB = Path(__file__).with_name(f"test_ak_intake_{uuid4().hex}.db")
os.environ["DATABASE_URL"] = f"sqlite:///{_TEST_DB.as_posix()}"

from fastapi.testclient import TestClient
from sqlmodel import Session

from app.database import create_db_and_tables, engine
from app.main import app
from app.models import AutoKeyJob

create_db_and_tables()
client = TestClient(app)


def _bootstrap_token():
    suffix = uuid4().hex[:8]
    slug = f"akin-{suffix}"
    assert (
        client.post(
            "/v1/auth/bootstrap",
            json={
                "tenant_name": "AK Intake",
                "tenant_slug": slug,
                "owner_email": f"o{suffix}@in.test",
                "owner_full_name": "Owner",
                "owner_password": "pass123456",
                "plan_code": "enterprise",
            },
        ).status_code
        == 200
    )
    login = client.post(
        "/v1/auth/login",
        json={"tenant_slug": slug, "email": f"o{suffix}@in.test", "password": "pass123456"},
    )
    assert login.status_code == 200
    return {"Authorization": f"Bearer {login.json()['access_token']}"}


def test_quick_intake_public_flow():
    h = _bootstrap_token()
    r = client.post(
        "/v1/auto-key-jobs/quick-intake",
        headers=h,
        json={"full_name": "Sam Taylor", "phone": "0412777999"},
    )
    assert r.status_code == 201
    job = r.json()
    assert job["status"] == "awaiting_customer_details"
    assert job["title"].startswith("Pending")

    with Session(engine) as s:
        row = s.get(AutoKeyJob, UUID(job["id"]))
        assert row is not None
        assert row.customer_intake_token
        tok = row.customer_intake_token

    pub = client.get(f"/v1/public/auto-key-intake/{tok}")
    assert pub.status_code == 200
    body = pub.json()
    assert body["job_number"] == job["job_number"]
    assert body["customer_first_name_hint"] == "Sam"

    sub = client.post(
        f"/v1/public/auto-key-intake/{tok}/submit",
        json={
            "vehicle_make": "Toyota",
            "vehicle_model": "Hilux",
            "vehicle_year": 2020,
            "job_type": "Key cut – basic",
            "additional_services": [{"custom": "Spare remote"}],
            "key_quantity": 2,
        },
    )
    assert sub.status_code == 200
    assert sub.json()["ok"] is True

    job2 = client.get(f"/v1/auto-key-jobs/{job['id']}", headers=h)
    assert job2.status_code == 200
    j2 = job2.json()
    assert j2["status"] == "awaiting_quote"
    assert "Sam" in j2["title"] and "Toyota" in j2["title"]
    assert j2["vehicle_year"] == 2020
    assert j2["key_quantity"] == 2
    assert j2.get("additional_services_json")

    with Session(engine) as s:
        row = s.get(AutoKeyJob, UUID(job["id"]))
        assert row is not None
        assert row.customer_intake_token is None


def test_public_intake_requires_details():
    h = _bootstrap_token()
    r = client.post(
        "/v1/auto-key-jobs/quick-intake",
        headers=h,
        json={"full_name": "Pat Lee", "phone": "0499000111"},
    )
    assert r.status_code == 201
    jid = r.json()["id"]
    with Session(engine) as s:
        row = s.get(AutoKeyJob, UUID(jid))
        assert row is not None
        tok = row.customer_intake_token
    bad = client.post(
        f"/v1/public/auto-key-intake/{tok}/submit",
        json={"key_quantity": 1},
    )
    assert bad.status_code == 400
