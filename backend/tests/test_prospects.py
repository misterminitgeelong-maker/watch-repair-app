import os
from pathlib import Path
from uuid import uuid4

_TEST_DB = Path(__file__).with_name(f"test_prospects_{uuid4().hex}.db")
os.environ["DATABASE_URL"] = f"sqlite:///{_TEST_DB.as_posix()}"
os.environ.setdefault("JWT_SECRET", "test-secret-not-for-production")
os.environ.setdefault("APP_ENV", "test")

from fastapi.testclient import TestClient

from app.database import create_db_and_tables
from app.main import app

create_db_and_tables()
client = TestClient(app)


def _bootstrap_and_login(tenant_slug: str, email: str, password: str, plan_code: str = "enterprise") -> str:
    bootstrap_payload = {
        "tenant_name": f"Tenant {tenant_slug}",
        "tenant_slug": tenant_slug,
        "owner_email": email,
        "owner_full_name": "Owner",
        "owner_password": password,
        "plan_code": plan_code,
    }
    bootstrap_res = client.post("/v1/auth/bootstrap", json=bootstrap_payload)
    assert bootstrap_res.status_code == 200

    login_payload = {
        "tenant_slug": tenant_slug,
        "email": email,
        "password": password,
    }
    login_res = client.post("/v1/auth/login", json=login_payload)
    assert login_res.status_code == 200
    return login_res.json()["access_token"]


def test_save_and_update_prospect_lead():
    suffix = uuid4().hex[:8]
    token = _bootstrap_and_login(
        tenant_slug=f"prospects-{suffix}",
        email=f"owner-{suffix}@prospects.test",
        password="pass123456",
    )
    headers = {"Authorization": f"Bearer {token}"}

    create_res = client.post(
        "/v1/prospects/leads",
        headers=headers,
        json={
            "place_id": f"place-{suffix}",
            "name": "Northside Mechanics",
            "address": "12 Service Rd, Geelong VIC",
            "phone": "03 9000 1111",
            "website": "https://northside.example.com",
            "category": "mechanics",
            "state_code": "VIC",
            "suburb_name": "Geelong",
        },
    )
    assert create_res.status_code == 201
    lead = create_res.json()
    assert lead["status"] == "new"
    assert lead["name"] == "Northside Mechanics"

    list_res = client.get("/v1/prospects/leads", headers=headers)
    assert list_res.status_code == 200
    leads = list_res.json()
    assert len(leads) == 1
    assert leads[0]["place_id"] == f"place-{suffix}"

    update_res = client.patch(
        f"/v1/prospects/leads/{lead['id']}",
        headers=headers,
        json={
            "status": "contacted",
            "notes": "Called service desk, send pricing pack next week.",
            "next_follow_up_on": "2026-04-14",
        },
    )
    assert update_res.status_code == 200
    updated = update_res.json()
    assert updated["status"] == "contacted"
    assert updated["notes"] == "Called service desk, send pricing pack next week."
    assert updated["next_follow_up_on"] == "2026-04-14"


def test_convert_prospect_to_customer_account():
    suffix = uuid4().hex[:8]
    token = _bootstrap_and_login(
        tenant_slug=f"prospects-convert-{suffix}",
        email=f"owner-{suffix}@prospects.test",
        password="pass123456",
    )
    headers = {"Authorization": f"Bearer {token}"}

    create_res = client.post(
        "/v1/prospects/leads",
        headers=headers,
        json={
            "place_id": f"convert-{suffix}",
            "name": "Metro Fleet Services",
            "address": "88 Depot Way, Melbourne VIC",
            "phone": "03 9555 2222",
            "website": "https://metrofleet.example.com",
            "category": "fleet_management",
            "state_code": "VIC",
            "suburb_name": "Melbourne",
        },
    )
    assert create_res.status_code == 201
    lead_id = create_res.json()["id"]

    convert_res = client.post(
        f"/v1/prospects/leads/{lead_id}/convert-to-account",
        headers=headers,
        json={
            "account_name": "Metro Fleet Services",
            "contact_name": "Service Desk",
            "contact_phone": "03 9555 2222",
            "contact_email": "service@metrofleet.example.com",
        },
    )
    assert convert_res.status_code == 201
    converted = convert_res.json()
    assert converted["customer_account_id"]
    assert converted["status"] == "won"

    accounts_res = client.get("/v1/customer-accounts", headers=headers)
    assert accounts_res.status_code == 200
    accounts = accounts_res.json()
    assert len(accounts) == 1
    assert accounts[0]["name"] == "Metro Fleet Services"
