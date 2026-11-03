import os
from pathlib import Path
from unittest.mock import patch
from uuid import uuid4

_TEST_DB = Path(__file__).with_name(f"test_places_{uuid4().hex}.db")
os.environ.setdefault("DATABASE_URL", f"sqlite:///{_TEST_DB.as_posix()}")

from fastapi.testclient import TestClient

from app.config import settings
from app.database import create_db_and_tables
from app.main import app
from app.routes.places import normalize_state, parse_components

create_db_and_tables()
client = TestClient(app)


def _login_token() -> str:
    suffix = uuid4().hex[:8]
    slug = f"places-{suffix}"
    r = client.post(
        "/v1/auth/bootstrap",
        json={
            "tenant_name": "Places Test",
            "tenant_slug": slug,
            "owner_email": f"o{suffix}@test.com",
            "owner_full_name": "O",
            "owner_password": "pass123456",
            "plan_code": "enterprise",
        },
    )
    assert r.status_code == 200
    r2 = client.post("/v1/auth/login", json={"tenant_slug": slug, "email": f"o{suffix}@test.com", "password": "pass123456"})
    assert r2.status_code == 200
    return r2.json()["access_token"]


class _FakeGoogle:
    """Stands in for httpx.AsyncClient; records each call and returns the queued payload."""

    payload: dict = {}
    status_code = 200
    calls: list[tuple[str, dict]] = []

    def __init__(self, *a, **k):
        pass

    async def __aenter__(self):
        return self

    async def __aexit__(self, *a):
        return None

    async def get(self, url: str, params: dict | None = None):
        _FakeGoogle.calls.append((url, dict(params or {})))

        class _R:
            status_code = _FakeGoogle.status_code

            def json(self_inner):
                return _FakeGoogle.payload

        return _R()


def _auth(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


def test_normalize_state_handles_codes_and_names():
    assert normalize_state("VIC") == "VIC"
    assert normalize_state("Victoria") == "VIC"
    assert normalize_state(" western australia ") == "WA"
    assert normalize_state("Auckland") is None
    assert normalize_state(None) is None


def test_parse_components_picks_suburb_state_and_postcode():
    components = [
        {"long_name": "14", "short_name": "14", "types": ["street_number"]},
        {"long_name": "Malvern East", "short_name": "Malvern East", "types": ["locality", "political"]},
        {"long_name": "Victoria", "short_name": "VIC", "types": ["administrative_area_level_1", "political"]},
        {"long_name": "3145", "short_name": "3145", "types": ["postal_code"]},
    ]
    assert parse_components(components) == ("Malvern East", "VIC", "3145")


def test_parse_components_falls_back_to_sublocality():
    components = [{"long_name": "Fitzroy", "short_name": "Fitzroy", "types": ["sublocality_level_1"]}]
    assert parse_components(components) == ("Fitzroy", None, None)


def test_requires_login():
    assert client.get("/v1/places/autocomplete", params={"q": "14 Burke"}).status_code in (401, 403)
    assert client.get("/v1/places/details", params={"place_id": "ChIJabcdefghij"}).status_code in (401, 403)


def test_503_when_no_key_is_configured(monkeypatch):
    monkeypatch.setattr(settings, "google_places_api_key", "")
    monkeypatch.setattr(settings, "google_maps_web_services_key", "")
    token = _login_token()
    res = client.get("/v1/places/autocomplete", params={"q": "14 Burke Rd"}, headers=_auth(token))
    assert res.status_code == 503


def test_short_queries_never_call_google(monkeypatch):
    monkeypatch.setattr(settings, "google_places_api_key", "test-key")
    token = _login_token()
    _FakeGoogle.calls = []
    with patch("app.routes.places.httpx.AsyncClient", _FakeGoogle):
        res = client.get("/v1/places/autocomplete", params={"q": " 14 "}, headers=_auth(token))
    assert res.status_code == 200
    assert res.json() == {"suggestions": []}
    assert _FakeGoogle.calls == []


def test_autocomplete_returns_suggestions_restricted_to_au_nz(monkeypatch):
    monkeypatch.setattr(settings, "google_places_api_key", "test-key")
    token = _login_token()
    _FakeGoogle.calls = []
    _FakeGoogle.status_code = 200
    _FakeGoogle.payload = {
        "status": "OK",
        "predictions": [
            {"place_id": "ChIJabcdefghij1", "description": "14 Burke Rd, Malvern East VIC, Australia",
             "structured_formatting": {"main_text": "14 Burke Rd", "secondary_text": "Malvern East VIC, Australia"}},
            {"place_id": "", "description": "ignored: no place id"},
        ],
    }
    with patch("app.routes.places.httpx.AsyncClient", _FakeGoogle):
        res = client.get("/v1/places/autocomplete", params={"q": "14  Burke   Rd", "session": "abc12345-session"}, headers=_auth(token))
    assert res.status_code == 200
    body = res.json()["suggestions"]
    assert len(body) == 1
    assert body[0]["description"].startswith("14 Burke Rd")
    assert body[0]["primary_text"] == "14 Burke Rd"
    url, params = _FakeGoogle.calls[0]
    assert "autocomplete" in url
    assert params["input"] == "14 Burke Rd"  # whitespace collapsed
    assert params["components"] == "country:au|country:nz"
    assert params["types"] == "address"
    assert params["sessiontoken"] == "abc12345-session"
    assert params["key"] == "test-key"


def test_autocomplete_zero_results_is_an_empty_list(monkeypatch):
    monkeypatch.setattr(settings, "google_places_api_key", "test-key")
    token = _login_token()
    _FakeGoogle.payload = {"status": "ZERO_RESULTS", "predictions": []}
    with patch("app.routes.places.httpx.AsyncClient", _FakeGoogle):
        res = client.get("/v1/places/autocomplete", params={"q": "zzzzzz nowhere"}, headers=_auth(token))
    assert res.status_code == 200 and res.json()["suggestions"] == []


def test_autocomplete_google_error_is_a_502_without_leaking_the_key(monkeypatch):
    monkeypatch.setattr(settings, "google_places_api_key", "secret-test-key")
    token = _login_token()
    _FakeGoogle.payload = {"status": "REQUEST_DENIED", "error_message": "The provided API key is invalid."}
    with patch("app.routes.places.httpx.AsyncClient", _FakeGoogle):
        res = client.get("/v1/places/autocomplete", params={"q": "14 Burke Rd"}, headers=_auth(token))
    assert res.status_code == 502
    assert "secret-test-key" not in res.text and "invalid" not in res.text.lower()


def test_details_resolves_suburb_state_and_position(monkeypatch):
    monkeypatch.setattr(settings, "google_places_api_key", "test-key")
    token = _login_token()
    _FakeGoogle.calls = []
    _FakeGoogle.payload = {
        "status": "OK",
        "result": {
            "formatted_address": "14 Burke Rd, Malvern East VIC 3145, Australia",
            "address_components": [
                {"long_name": "Malvern East", "short_name": "Malvern East", "types": ["locality"]},
                {"long_name": "Victoria", "short_name": "VIC", "types": ["administrative_area_level_1"]},
                {"long_name": "3145", "short_name": "3145", "types": ["postal_code"]},
            ],
            "geometry": {"location": {"lat": -37.88, "lng": 145.05}},
        },
    }
    with patch("app.routes.places.httpx.AsyncClient", _FakeGoogle):
        res = client.get("/v1/places/details", params={"place_id": "ChIJabcdefghij1"}, headers=_auth(token))
    assert res.status_code == 200
    assert res.json() == {
        "formatted_address": "14 Burke Rd, Malvern East VIC 3145, Australia",
        "suburb": "Malvern East", "state_code": "VIC", "postcode": "3145", "lat": -37.88, "lng": 145.05,
    }
    assert "details" in _FakeGoogle.calls[0][0]


def test_details_rejects_a_malformed_place_id_before_calling_google(monkeypatch):
    monkeypatch.setattr(settings, "google_places_api_key", "test-key")
    token = _login_token()
    _FakeGoogle.calls = []
    with patch("app.routes.places.httpx.AsyncClient", _FakeGoogle):
        res = client.get("/v1/places/details", params={"place_id": "bad id&key=evil"}, headers=_auth(token))
    assert res.status_code == 422
    assert _FakeGoogle.calls == []


def test_details_not_found_is_a_404(monkeypatch):
    monkeypatch.setattr(settings, "google_places_api_key", "test-key")
    token = _login_token()
    _FakeGoogle.payload = {"status": "NOT_FOUND"}
    with patch("app.routes.places.httpx.AsyncClient", _FakeGoogle):
        res = client.get("/v1/places/details", params={"place_id": "ChIJabcdefghij1"}, headers=_auth(token))
    assert res.status_code == 404
