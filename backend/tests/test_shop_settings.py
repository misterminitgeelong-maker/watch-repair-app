"""Shop Identity settings — shop_number field (self-service Minit shop number)."""
from __future__ import annotations


def _bootstrap(client, tenant_slug, email, password="pass123456") -> dict[str, str]:
    res = client.post(
        "/v1/auth/bootstrap",
        json={
            "tenant_name": f"Tenant {tenant_slug}",
            "tenant_slug": tenant_slug,
            "owner_email": email,
            "owner_full_name": "Owner",
            "owner_password": password,
        },
    )
    assert res.status_code == 200, res.text
    login = client.post(
        "/v1/auth/login",
        json={"tenant_slug": tenant_slug, "email": email, "password": password},
    )
    assert login.status_code == 200, login.text
    return {"Authorization": f"Bearer {login.json()['access_token']}"}


def test_shop_number_defaults_to_none(client):
    headers = _bootstrap(client, "shopnum-default", "owner-default@test.com")
    res = client.get("/v1/settings/shop-identity", headers=headers)
    assert res.status_code == 200
    assert res.json()["shop_number"] is None


def test_can_set_and_read_back_shop_number(client):
    headers = _bootstrap(client, "shopnum-set", "owner-set@test.com")
    patch = client.patch("/v1/settings/shop-identity", headers=headers, json={"shop_number": "3269"})
    assert patch.status_code == 200, patch.text
    assert patch.json()["shop_number"] == "3269"

    res = client.get("/v1/settings/shop-identity", headers=headers)
    assert res.json()["shop_number"] == "3269"


def test_shop_number_can_be_cleared(client):
    headers = _bootstrap(client, "shopnum-clear", "owner-clear@test.com")
    client.patch("/v1/settings/shop-identity", headers=headers, json={"shop_number": "3269"})
    patch = client.patch("/v1/settings/shop-identity", headers=headers, json={"shop_number": ""})
    assert patch.status_code == 200
    assert patch.json()["shop_number"] is None


def test_shop_number_rejects_non_digits(client):
    headers = _bootstrap(client, "shopnum-invalid", "owner-invalid@test.com")
    res = client.patch("/v1/settings/shop-identity", headers=headers, json={"shop_number": "ABC123"})
    assert res.status_code == 400


def test_shop_number_must_be_unique_within_same_parent_account(client):
    # Same owner email on both bootstraps -> both tenants land in one parent account/network
    # (see _get_or_create_parent_account), which is exactly the scope shop_number uniqueness
    # is enforced against.
    shared_email = "owner-multisite@test.com"
    headers_a = _bootstrap(client, "shopnum-multisite-a", shared_email)
    headers_b = _bootstrap(client, "shopnum-multisite-b", shared_email)

    ok = client.patch("/v1/settings/shop-identity", headers=headers_a, json={"shop_number": "9001"})
    assert ok.status_code == 200, ok.text

    conflict = client.patch("/v1/settings/shop-identity", headers=headers_b, json={"shop_number": "9001"})
    assert conflict.status_code == 409, conflict.text


def test_shop_number_not_touching_it_leaves_it_unchanged(client):
    headers = _bootstrap(client, "shopnum-untouched", "owner-untouched@test.com")
    client.patch("/v1/settings/shop-identity", headers=headers, json={"shop_number": "4200"})
    # Updating an unrelated field shouldn't clear shop_number.
    patch = client.patch("/v1/settings/shop-identity", headers=headers, json={"abn": "12 345 678 901"})
    assert patch.status_code == 200
    assert patch.json()["shop_number"] == "4200"
    assert patch.json()["abn"] == "12 345 678 901"
