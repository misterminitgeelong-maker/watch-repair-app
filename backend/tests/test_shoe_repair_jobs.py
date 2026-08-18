"""Shoe repair job list and related helpers."""
from uuid import uuid4

from fastapi.testclient import TestClient

_SHOE_ITEM = {
    "catalogue_key": "soles__half_sole_leather",
    "catalogue_group": "soles",
    "item_name": "Half sole leather",
    "pricing_type": "fixed",
    "quantity": 1,
    "unit_price_cents": 5000,
}


def _bootstrap(client: TestClient) -> dict[str, str]:
    suffix = uuid4().hex[:8]
    slug = f"shoe-{suffix}"
    email = f"owner-{suffix}@shoe.test"
    boot = client.post(
        "/v1/auth/bootstrap",
        json={
            "tenant_name": f"Shoe {suffix}",
            "tenant_slug": slug,
            "owner_email": email,
            "owner_full_name": "Owner",
            "owner_password": "pass123456",
            "plan_code": "enterprise",
        },
    )
    assert boot.status_code == 200, boot.text
    login = client.post(
        "/v1/auth/login",
        json={"tenant_slug": slug, "email": email, "password": "pass123456"},
    )
    assert login.status_code == 200, login.text
    return {"Authorization": f"Bearer {login.json()['access_token']}"}


def test_list_shoe_jobs_includes_nested_shoes_and_items(client: TestClient):
    headers = _bootstrap(client)
    customer = client.post(
        "/v1/customers",
        headers=headers,
        json={"full_name": "Shoe Customer", "email": f"c-{uuid4().hex[:8]}@shoe.test"},
    )
    assert customer.status_code == 201, customer.text
    cid = customer.json()["id"]

    jobs = []
    for i in range(2):
        shoe = client.post(
            "/v1/shoe-repair-jobs/shoes",
            headers=headers,
            json={"customer_id": cid, "shoe_type": "Boot", "brand": f"Brand{i}"},
        )
        assert shoe.status_code == 201, shoe.text
        created = client.post(
            "/v1/shoe-repair-jobs",
            headers=headers,
            json={
                "shoe_id": shoe.json()["id"],
                "title": f"Resole {i}",
                "priority": "normal",
                "items": [_SHOE_ITEM],
            },
        )
        assert created.status_code == 201, created.text
        jobs.append(created.json())

    listed = client.get("/v1/shoe-repair-jobs", headers=headers)
    assert listed.status_code == 200, listed.text
    body = listed.json()
    assert len(body) >= 2
    by_id = {row["id"]: row for row in body}
    for created in jobs:
        row = by_id[created["id"]]
        assert row["shoe"] is not None
        assert row["shoe"]["brand"]
        assert row["items"]
        assert row["items"][0]["item_name"] == "Half sole leather"
        assert row["extra_shoes"] == []


def test_shoe_job_numbers_use_compare_and_set_counter(client: TestClient):
    headers = _bootstrap(client)
    customer = client.post(
        "/v1/customers",
        headers=headers,
        json={"full_name": "Shoe Customer", "email": f"c-{uuid4().hex[:8]}@shoe.test"},
    )
    cid = customer.json()["id"]
    numbers = []
    for i in range(2):
        shoe = client.post(
            "/v1/shoe-repair-jobs/shoes",
            headers=headers,
            json={"customer_id": cid, "shoe_type": "Boot", "brand": f"Brand{i}"},
        )
        created = client.post(
            "/v1/shoe-repair-jobs",
            headers=headers,
            json={"shoe_id": shoe.json()["id"], "title": f"Job {i}", "priority": "normal", "items": [_SHOE_ITEM]},
        )
        assert created.status_code == 201, created.text
        numbers.append(created.json()["job_number"])
    assert numbers == ["SHO-00001", "SHO-00002"]


def test_intake_cannot_change_shoe_status_and_invalid_status_rejected(client: TestClient):
    suffix = uuid4().hex[:8]
    slug = f"shoe-status-{suffix}"
    email = f"owner-{suffix}@shoe.test"
    boot = client.post(
        "/v1/auth/bootstrap",
        json={
            "tenant_name": f"Shoe {suffix}",
            "tenant_slug": slug,
            "owner_email": email,
            "owner_full_name": "Owner",
            "owner_password": "pass123456",
            "plan_code": "enterprise",
        },
    )
    assert boot.status_code == 200, boot.text
    login = client.post("/v1/auth/login", json={"tenant_slug": slug, "email": email, "password": "pass123456"})
    owner_h = {"Authorization": f"Bearer {login.json()['access_token']}"}

    created_user = client.post(
        "/v1/users",
        headers=owner_h,
        json={
            "full_name": "Intake",
            "email": f"intake-{suffix}@shoe.test",
            "password": "pass123456",
            "role": "intake",
        },
    )
    assert created_user.status_code == 201, created_user.text
    intake_login = client.post(
        "/v1/auth/login",
        json={"tenant_slug": slug, "email": f"intake-{suffix}@shoe.test", "password": "pass123456"},
    )
    intake_h = {"Authorization": f"Bearer {intake_login.json()['access_token']}"}

    customer = client.post(
        "/v1/customers",
        headers=owner_h,
        json={"full_name": "Shoe Customer", "email": f"c-{suffix}@shoe.test"},
    )
    shoe = client.post(
        "/v1/shoe-repair-jobs/shoes",
        headers=owner_h,
        json={"customer_id": customer.json()["id"], "shoe_type": "Boot", "brand": "RM"},
    )
    job = client.post(
        "/v1/shoe-repair-jobs",
        headers=owner_h,
        json={"shoe_id": shoe.json()["id"], "title": "Heels", "priority": "normal", "items": [_SHOE_ITEM]},
    )
    job_id = job.json()["id"]

    denied = client.post(f"/v1/shoe-repair-jobs/{job_id}/status", headers=intake_h, json={"status": "working_on"})
    assert denied.status_code == 403, denied.text

    bad = client.post(f"/v1/shoe-repair-jobs/{job_id}/status", headers=owner_h, json={"status": "not_a_real_status"})
    assert bad.status_code == 422, bad.text

    ok = client.post(f"/v1/shoe-repair-jobs/{job_id}/status", headers=owner_h, json={"status": "working_on"})
    assert ok.status_code == 200, ok.text
    assert ok.json()["status"] == "working_on"
