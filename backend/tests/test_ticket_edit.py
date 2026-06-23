"""Edit-ticket endpoints: watch/shoe job, item, and customer field updates."""
import os
from pathlib import Path
from uuid import uuid4

from fastapi.testclient import TestClient

_TEST_DB = Path(__file__).with_name(f"test_ticket_edit_{uuid4().hex}.db")
os.environ["DATABASE_URL"] = f"sqlite:///{_TEST_DB.as_posix()}"
os.environ.setdefault("JWT_SECRET", "test-secret-not-for-production")
os.environ.setdefault("APP_ENV", "test")

from app.database import create_db_and_tables  # noqa: E402
from app.main import app  # noqa: E402

create_db_and_tables()
client = TestClient(app)


def _login(slug: str) -> dict[str, str]:
    suffix = uuid4().hex[:8]
    client.post("/v1/auth/bootstrap", json={
        "tenant_name": f"Tenant {slug}",
        "tenant_slug": f"{slug}-{suffix}",
        "owner_email": f"owner-{suffix}@{slug}.test",
        "owner_full_name": "Owner",
        "owner_password": "pass123456",
        "plan_code": "enterprise",
    })
    res = client.post("/v1/auth/login", json={
        "tenant_slug": f"{slug}-{suffix}",
        "email": f"owner-{suffix}@{slug}.test",
        "password": "pass123456",
    })
    assert res.status_code == 200
    return {"Authorization": f"Bearer {res.json()['access_token']}"}


def _customer(headers: dict[str, str]) -> str:
    r = client.post("/v1/customers", headers=headers, json={"full_name": "Jane Doe", "phone": "0400000000"})
    assert r.status_code == 201
    return r.json()["id"]


def _watch(headers: dict[str, str], customer_id: str) -> str:
    r = client.post("/v1/watches", headers=headers, json={"customer_id": customer_id, "brand": "Seiko", "model": "5"})
    assert r.status_code == 201
    return r.json()["id"]


def test_update_watch_job_title_and_fields():
    headers = _login("watchedit")
    customer_id = _customer(headers)
    watch_id = _watch(headers, customer_id)
    job = client.post("/v1/repair-jobs", headers=headers, json={
        "watch_id": watch_id, "title": "Battery", "priority": "normal",
    })
    assert job.status_code == 201
    job_id = job.json()["id"]

    res = client.patch(f"/v1/repair-jobs/{job_id}", headers=headers, json={
        "title": "Full service", "priority": "high", "description": "Runs slow",
    })
    assert res.status_code == 200
    body = res.json()
    assert body["title"] == "Full service"
    assert body["priority"] == "high"
    assert body["description"] == "Runs slow"


def test_update_watch_item():
    headers = _login("watchitem")
    customer_id = _customer(headers)
    watch_id = _watch(headers, customer_id)

    res = client.patch(f"/v1/watches/{watch_id}", headers=headers, json={
        "brand": "Omega", "serial_number": "ABC123", "condition_notes": "Scratched bezel",
    })
    assert res.status_code == 200
    body = res.json()
    assert body["brand"] == "Omega"
    assert body["model"] == "5"  # untouched
    assert body["serial_number"] == "ABC123"
    assert body["condition_notes"] == "Scratched bezel"


def test_update_customer_contact():
    headers = _login("custedit")
    customer_id = _customer(headers)

    res = client.patch(f"/v1/customers/{customer_id}", headers=headers, json={
        "phone": "0411111111", "email": "jane@example.com",
    })
    assert res.status_code == 200
    body = res.json()
    assert body["phone"] == "0411111111"
    assert body["email"] == "jane@example.com"
    assert body["full_name"] == "Jane Doe"  # untouched


def test_update_customer_blank_name_rejected():
    headers = _login("custblank")
    customer_id = _customer(headers)
    res = client.patch(f"/v1/customers/{customer_id}", headers=headers, json={"full_name": "  "})
    assert res.status_code == 400


def test_update_shoe_item():
    headers = _login("shoeedit")
    customer_id = _customer(headers)
    shoe = client.post("/v1/shoe-repair-jobs/shoes", headers=headers, json={
        "customer_id": customer_id, "shoe_type": "boots", "brand": "RM Williams",
    })
    assert shoe.status_code == 201
    shoe_id = shoe.json()["id"]

    res = client.patch(f"/v1/shoe-repair-jobs/shoes/{shoe_id}", headers=headers, json={
        "color": "brown", "description_notes": "Resole both",
    })
    assert res.status_code == 200
    body = res.json()
    assert body["color"] == "brown"
    assert body["description_notes"] == "Resole both"
    assert body["brand"] == "RM Williams"  # untouched


def test_edit_cross_tenant_denied():
    headers_a = _login("tenantA")
    headers_b = _login("tenantB")
    customer_id = _customer(headers_a)
    watch_id = _watch(headers_a, customer_id)

    # Tenant B must not be able to edit tenant A's watch or customer.
    assert client.patch(f"/v1/watches/{watch_id}", headers=headers_b, json={"brand": "X"}).status_code == 404
    assert client.patch(f"/v1/customers/{customer_id}", headers=headers_b, json={"phone": "0"}).status_code == 404
