import os
from pathlib import Path
from unittest.mock import patch
from uuid import uuid4

_TEST_DB = Path(__file__).with_name(f"test_maps_{uuid4().hex}.db")
os.environ["DATABASE_URL"] = f"sqlite:///{_TEST_DB.as_posix()}"

from fastapi.testclient import TestClient

from app.config import settings
from app.database import create_db_and_tables
from app.main import app
from app.routes.maps_routing import visit_order_from_waypoints

create_db_and_tables()
client = TestClient(app)


def test_visit_order_from_waypoints_trivial():
    assert visit_order_from_waypoints(n=1, waypoint_order=None) == [0]
    assert visit_order_from_waypoints(n=2, waypoint_order=None) == [0, 1]


def test_visit_order_from_waypoints_reorders_middle():
    assert visit_order_from_waypoints(n=4, waypoint_order=[1, 0]) == [0, 2, 1, 3]


def test_visit_order_invalid_waypoint_falls_back():
    assert visit_order_from_waypoints(n=4, waypoint_order=[0]) == [0, 1, 2, 3]


def _login_token() -> str:
    suffix = uuid4().hex[:8]
    slug = f"maps-{suffix}"
    r = client.post(
        "/v1/auth/bootstrap",
        json={
            "tenant_name": "Maps Test",
            "tenant_slug": slug,
            "owner_email": f"o{suffix}@test.com",
            "owner_full_name": "O",
            "owner_password": "pass123456",
            "plan_code": "enterprise",
        },
    )
    assert r.status_code == 200
    r2 = client.post(
        "/v1/auth/login",
        json={"tenant_slug": slug, "email": f"o{suffix}@test.com", "password": "pass123456"},
    )
    assert r2.status_code == 200
    return r2.json()["access_token"]


def test_optimize_driving_route_503_without_key(monkeypatch):
    monkeypatch.setattr(settings, "google_maps_web_services_key", "")
    monkeypatch.setattr(settings, "google_places_api_key", "")
    token = _login_token()
    res = client.post(
        "/v1/maps/optimize-driving-route",
        headers={"Authorization": f"Bearer {token}"},
        json={"stops": [{"lat": -37.81, "lng": 144.96}, {"lat": -37.82, "lng": 144.97}]},
    )
    assert res.status_code == 503


class _FakeDirectionsClient:
    def __init__(self, *a, **k):
        pass

    async def __aenter__(self):
        return self

    async def __aexit__(self, *a):
        return None

    async def get(self, url: str):
        class _R:
            status_code = 200

            def json(self):
                return {"status": "OK", "routes": [{"waypoint_order": [1, 0]}]}

        return _R()


def test_optimize_driving_route_uses_directions(monkeypatch):
    monkeypatch.setattr(settings, "google_maps_web_services_key", "test-key")
    token = _login_token()
    with patch("app.routes.maps_routing.httpx.AsyncClient", _FakeDirectionsClient):
        res = client.post(
            "/v1/maps/optimize-driving-route",
            headers={"Authorization": f"Bearer {token}"},
            json={
                "stops": [
                    {"lat": -37.8, "lng": 144.9},
                    {"lat": -37.81, "lng": 144.91},
                    {"lat": -37.82, "lng": 144.92},
                    {"lat": -37.83, "lng": 144.93},
                ],
            },
        )
    assert res.status_code == 200
    data = res.json()
    assert data["source"] == "directions"
    assert data["visit_order"] == [0, 2, 1, 3]


def test_optimize_driving_trivial_two_stops(monkeypatch):
    monkeypatch.setattr(settings, "google_maps_web_services_key", "test-key")
    token = _login_token()
    res = client.post(
        "/v1/maps/optimize-driving-route",
        headers={"Authorization": f"Bearer {token}"},
        json={"stops": [{"lat": -37.8, "lng": 144.9}, {"lat": -37.82, "lng": 144.92}]},
    )
    assert res.status_code == 200
    assert res.json() == {"visit_order": [0, 1], "source": "trivial"}
