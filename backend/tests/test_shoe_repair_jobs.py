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
