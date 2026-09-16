import os
from datetime import datetime
from pathlib import Path
from uuid import uuid4

_TEST_DB = Path(__file__).with_name(f"test_ak_ops_{uuid4().hex}.db")
os.environ["DATABASE_URL"] = f"sqlite:///{_TEST_DB.as_posix()}"

from fastapi.testclient import TestClient

from app.database import create_db_and_tables
from app.main import app

create_db_and_tables()
client = TestClient(app)


def _setup() -> tuple[dict[str, str], str]:
    suffix = uuid4().hex[:8]
    slug = f"akops-{suffix}"
    bootstrap = client.post(
        "/v1/auth/bootstrap",
        json={
            "tenant_name": "AK Operations",
            "tenant_slug": slug,
            "owner_email": f"owner-{suffix}@test.com",
            "owner_full_name": "Operations Owner",
            "owner_password": "pass123456",
            "plan_code": "enterprise",
        },
    )
    assert bootstrap.status_code == 200, bootstrap.text
    login = client.post(
        "/v1/auth/login",
        json={"tenant_slug": slug, "email": f"owner-{suffix}@test.com", "password": "pass123456"},
    )
    assert login.status_code == 200, login.text
    headers = {"Authorization": f"Bearer {login.json()['access_token']}"}
    customer = client.post(
        "/v1/customers",
        headers=headers,
        json={"full_name": "Paged Customer", "phone": "0411000111"},
    )
    assert customer.status_code == 201, customer.text
    return headers, customer.json()["id"]


def _job(headers: dict[str, str], customer_id: str, title: str, status: str = "awaiting_quote") -> dict:
    response = client.post(
        "/v1/auto-key-jobs",
        headers=headers,
        json={
            "customer_id": customer_id,
            "title": title,
            "key_quantity": 1,
            "priority": "normal",
            "status": status,
            "programming_status": "pending",
            "deposit_cents": 0,
            "cost_cents": 0,
        },
    )
    assert response.status_code == 201, response.text
    return response.json()


def test_paginated_directory_search_and_closed_no_go():
    headers, customer_id = _setup()
    first = _job(headers, customer_id, "Alpha lockout")
    second = _job(headers, customer_id, "Beta duplicate")
    closed = client.post(
        f"/v1/auto-key-jobs/{second['id']}/status",
        headers=headers,
        json={"status": "no_go", "note": "Customer cancelled"},
    )
    assert closed.status_code == 200, closed.text
    legacy_closed = _job(headers, customer_id, "Imported completed job", status="completed")

    active = client.get("/v1/auto-key-jobs/page", headers=headers, params={"directory": "active", "limit": 1})
    assert active.status_code == 200, active.text
    assert active.json()["total"] == 1
    assert active.json()["items"][0]["id"] == first["id"]

    completed = client.get("/v1/auto-key-jobs/page", headers=headers, params={"directory": "completed"})
    assert completed.status_code == 200, completed.text
    assert completed.json()["total"] == 2
    assert {item["status"] for item in completed.json()["items"]} == {"no_go", "completed"}

    searched = client.get("/v1/auto-key-jobs/page", headers=headers, params={"directory": "all", "q": "Paged Customer"})
    assert searched.status_code == 200, searched.text
    assert searched.json()["total"] == 3
    assert legacy_closed["status"] == "completed"


def test_job_activity_records_creation_updates_and_status():
    headers, customer_id = _setup()
    job = _job(headers, customer_id, "Timeline job")
    update = client.patch(
        f"/v1/auto-key-jobs/{job['id']}",
        headers=headers,
        json={"priority": "urgent", "job_address": "10 Test Street"},
    )
    assert update.status_code == 200, update.text
    status = client.post(
        f"/v1/auto-key-jobs/{job['id']}/status",
        headers=headers,
        json={"status": "booking_confirmed", "note": "Customer approved"},
    )
    assert status.status_code == 200, status.text

    activity = client.get(f"/v1/auto-key-jobs/{job['id']}/activity", headers=headers)
    assert activity.status_code == 200, activity.text
    event_types = [row["event_type"] for row in activity.json()]
    assert "auto_key_job_created" in event_types
    assert "auto_key_job_updated" in event_types
    assert "auto_key_status_changed" in event_types
    assert any("Customer approved" in row["event_summary"] for row in activity.json())
    serialized_created_at = activity.json()[0]["created_at"].replace("Z", "+00:00")
    assert datetime.fromisoformat(serialized_created_at).utcoffset() is not None
