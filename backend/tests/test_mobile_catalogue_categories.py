"""Owner-controlled POS catalogue categories for Mobile Services."""
import os
from pathlib import Path
from uuid import uuid4

_TEST_DB = Path(__file__).with_name(f"test_mobile_catalogue_{uuid4().hex}.db")
os.environ["DATABASE_URL"] = f"sqlite:///{_TEST_DB.as_posix()}"

from fastapi.testclient import TestClient

from app.database import create_db_and_tables
from app.main import app
from app.mobile_catalogue import (
    DEFAULT_CATALOGUE_CATEGORIES,
    normalise_catalogue_categories,
    parse_catalogue_categories,
    serialise_catalogue_categories,
)

create_db_and_tables()
client = TestClient(app)


def _tenant() -> tuple[dict[str, str], str, str]:
    suffix = uuid4().hex[:8]
    slug = f"cat-{suffix}"
    owner_email = f"owner-{suffix}@test.com"
    assert client.post(
        "/v1/auth/bootstrap",
        json={
            "tenant_name": "Catalogue Shop",
            "tenant_slug": slug,
            "owner_email": owner_email,
            "owner_full_name": "Owner",
            "owner_password": "pass123456",
            "plan_code": "enterprise",
        },
    ).status_code == 200
    login = client.post("/v1/auth/login", json={"tenant_slug": slug, "email": owner_email, "password": "pass123456"})
    assert login.status_code == 200, login.text
    return {"Authorization": f"Bearer {login.json()['access_token']}"}, slug, owner_email


def _tech_headers(owner_headers: dict[str, str], slug: str) -> dict[str, str]:
    email = f"tech-{uuid4().hex[:6]}@test.com"
    created = client.post(
        "/v1/users",
        headers=owner_headers,
        json={"email": email, "full_name": "Field Tech", "password": "pass123456", "role": "tech"},
    )
    assert created.status_code in (200, 201), created.text
    login = client.post("/v1/auth/login", json={"tenant_slug": slug, "email": email, "password": "pass123456"})
    assert login.status_code == 200, login.text
    return {"Authorization": f"Bearer {login.json()['access_token']}"}


def test_default_catalogue_is_vehicle_keys_and_general_services_only():
    headers, _slug, _ = _tenant()
    res = client.get("/v1/toolkit/mobile-catalogue", headers=headers)
    assert res.status_code == 200, res.text
    body = res.json()
    assert body["enabled_categories"] == ["vehicle_key", "general_service"]
    assert [c["key"] for c in body["available_categories"]] == ["vehicle_key", "general_service", "garage_door"]
    # The pricing meta the POS reads carries the same answer.
    meta = client.get("/v1/mobile-services-pricing/meta", headers=headers)
    assert meta.status_code == 200, meta.text
    assert meta.json()["enabled_categories"] == ["vehicle_key", "general_service"]


def test_owner_can_enable_garage_door_and_the_catalogue_rows_are_untouched():
    headers, _slug, _ = _tenant()
    before = client.get("/v1/mobile-services-pricing/meta", headers=headers).json()
    res = client.patch(
        "/v1/toolkit/mobile-catalogue",
        headers=headers,
        json={"enabled_categories": ["garage_door", "vehicle_key", "general_service"]},
    )
    assert res.status_code == 200, res.text
    # Stored in canonical order regardless of click order.
    assert res.json()["enabled_categories"] == ["vehicle_key", "general_service", "garage_door"]
    after = client.get("/v1/mobile-services-pricing/meta", headers=headers).json()
    assert after["enabled_categories"] == ["vehicle_key", "general_service", "garage_door"]
    for count in ("oem_row_count", "service_row_count", "garage_row_count"):
        assert after[count] == before[count]
    # Garage rows are still served by the read endpoints either way (data is never hidden server-side).
    assert client.get("/v1/mobile-services-pricing/garage", headers=headers).status_code == 200


def test_technicians_cannot_change_the_catalogue_but_can_read_it():
    owner, slug, _ = _tenant()
    tech = _tech_headers(owner, slug)
    assert client.get("/v1/toolkit/mobile-catalogue", headers=tech).status_code == 200
    res = client.patch("/v1/toolkit/mobile-catalogue", headers=tech, json={"enabled_categories": ["garage_door"]})
    assert res.status_code == 403


def test_selection_must_be_known_and_non_empty():
    headers, _slug, _ = _tenant()
    assert client.patch("/v1/toolkit/mobile-catalogue", headers=headers, json={"enabled_categories": ["plumbing"]}).status_code == 422
    assert client.patch("/v1/toolkit/mobile-catalogue", headers=headers, json={"enabled_categories": []}).status_code == 422


def test_catalogue_is_per_tenant():
    a, _, _ = _tenant()
    b, _, _ = _tenant()
    assert client.patch("/v1/toolkit/mobile-catalogue", headers=a, json={"enabled_categories": ["garage_door"]}).status_code == 200
    assert client.get("/v1/toolkit/mobile-catalogue", headers=a).json()["enabled_categories"] == ["garage_door"]
    assert client.get("/v1/toolkit/mobile-catalogue", headers=b).json()["enabled_categories"] == list(DEFAULT_CATALOGUE_CATEGORIES)


def test_stored_value_round_trips_and_tolerates_bad_data():
    assert parse_catalogue_categories(None) == ["vehicle_key", "general_service"]
    assert parse_catalogue_categories("not json") == ["vehicle_key", "general_service"]
    assert parse_catalogue_categories('["garage_door", "bogus", "garage_door"]') == ["garage_door"]
    assert parse_catalogue_categories("[]") == ["vehicle_key", "general_service"]
    assert serialise_catalogue_categories(["vehicle_key", "general_service"]) is None  # default stays NULL
    assert serialise_catalogue_categories(["garage_door"]) == '["garage_door"]'
    assert normalise_catalogue_categories(["general_service", "vehicle_key", "vehicle_key"]) == ["vehicle_key", "general_service"]
