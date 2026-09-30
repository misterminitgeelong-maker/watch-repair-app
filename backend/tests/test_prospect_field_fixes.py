"""Regression coverage for the prospect/kit failures reproduced in field QA."""
from uuid import UUID, uuid4

import httpx
import pytest
from sqlmodel import Session, select

from app.database import engine
from app.models import CustomerAccount, ProspectBusiness
from app.routes import prospects


@pytest.fixture
def mobile_headers(bootstrap_and_login):
    return {"Authorization": f"Bearer {bootstrap_and_login(plan_code='basic_auto_key')}"}


def new_lead(client, headers):
    result = client.post('/v1/prospect-leads', headers=headers, json={"name": "Field QA", "place_id": uuid4().hex})
    assert result.status_code == 200, result.text
    return result.json()


def test_clear_fields_and_omitted_fields(client, mobile_headers):
    lead = new_lead(client, mobile_headers)
    path = f"/v1/prospect-leads/{lead['id']}"
    values = {"contact_name": "Original", "contact_email": "qa@example.test", "notes": "Visit", "visit_scheduled_at": "2026-10-02T00:00:00Z"}
    assert client.patch(path, headers=mobile_headers, json=values).status_code == 200
    omitted = client.patch(path, headers=mobile_headers, json={"notes": "Updated"}).json()
    assert omitted['contact_name'] == 'Original'
    cleared = client.patch(path, headers=mobile_headers, json={k: None for k in values})
    assert cleared.status_code == 200, cleared.text
    persisted = next(l for l in client.get('/v1/prospect-leads', headers=mobile_headers).json() if l['id'] == lead['id'])
    assert all(persisted[k] is None for k in values)


def test_advance_saves_draft_and_repeat_conversion_reuses_account(client, mobile_headers):
    lead = new_lead(client, mobile_headers)
    path = f"/v1/prospect-leads/{lead['id']}/advance"
    assert client.post(path, headers=mobile_headers).json()['status'] == 'contacted'
    assert client.post(path, headers=mobile_headers).json()['status'] == 'visited'
    converted = client.post(path, headers=mobile_headers, json={"contact_name": "Visible draft", "notes": "Latest notes"})
    assert converted.status_code == 200, converted.text
    account_id = converted.json()['customer_account_id']
    assert account_id
    assert client.post(path, headers=mobile_headers).json()['customer_account_id'] == account_id
    with Session(engine) as session:
        account = session.get(CustomerAccount, UUID(account_id))
        assert account.contact_name == 'Visible draft'
        assert account.notes == 'Latest notes'


def test_patch_onboarded_creates_account(client, mobile_headers):
    lead = new_lead(client, mobile_headers)
    result = client.patch(f"/v1/prospect-leads/{lead['id']}", headers=mobile_headers, json={"status": "onboarded", "contact_name": "Draft"})
    assert result.status_code == 200
    assert result.json()['customer_account_id']


def test_inbox_stages_can_be_advanced_without_resetting(client, mobile_headers):
    created = client.post('/v1/prospects/leads', headers=mobile_headers, json={"name": "Quote lead", "status": "quote_needed"}).json()
    listed = client.get('/v1/prospect-leads', headers=mobile_headers).json()
    assert any(l['id'] == created['id'] and l['status'] == 'quote_needed' for l in listed)
    result = client.post(f"/v1/prospect-leads/{created['id']}/advance", headers=mobile_headers)
    assert result.json()['status'] == 'contacted'


def test_stored_empty_search_never_calls_google(client, mobile_headers, monkeypatch):
    def unexpected(*args, **kwargs):
        raise AssertionError('Stored search called Google')
    monkeypatch.setattr(prospects.httpx, 'AsyncClient', unexpected)
    response = client.get('/v1/prospects/search', headers=mobile_headers, params={"category": "insurance", "state": "NT"})
    assert response.status_code == 200, response.text
    assert response.json() == {"results": [], "total": 0, "category": "insurance", "source": "stored"}


def test_stored_search_does_not_drop_suburbs_after_twenty(client, mobile_headers):
    suburbs = [f"QA suburb {i}" for i in range(21)]
    with Session(engine) as session:
        session.add(ProspectBusiness(place_id=uuid4().hex, name='Last suburb business', category='mechanics', state_code='VIC', suburb_name=suburbs[-1]))
        session.commit()
    response = client.get('/v1/prospects/search', headers=mobile_headers, params={"category": "mechanics", "state": "VIC", "suburbs": ','.join(suburbs)})
    assert response.status_code == 200
    assert any(p['name'] == 'Last suburb business' for p in response.json()['results'])
    limited = client.get('/v1/prospects/search', headers=mobile_headers, params={"category": "mechanics", "state": "VIC", "suburbs": ','.join(suburbs), "live": 'true'})
    assert limited.status_code == 400
    assert 'five' in limited.json()['detail']


def test_contact_details_enrich_saved_business(client, mobile_headers, monkeypatch):
    lead = new_lead(client, mobile_headers)
    calls = []
    class DetailsClient:
        def __init__(self, **kwargs):
            pass
        async def __aenter__(self):
            return self
        async def __aexit__(self, *args):
            pass
        async def get(self, url, params):
            calls.append((url, params))
            return httpx.Response(200, json={"status": "OK", "result": {"formatted_phone_number": "03 9000 1111", "website": "https://example.test"}})
    monkeypatch.setattr(prospects.httpx, 'AsyncClient', DetailsClient)
    monkeypatch.setattr(prospects.settings, 'google_places_api_key', 'unit-test')
    result = client.get('/v1/prospects/contact-details', headers=mobile_headers, params={"place_id": lead['place_id']})
    assert result.status_code == 200, result.text
    assert result.json()['phone'] == '03 9000 1111'
    assert calls[0][0] == prospects.PLACE_DETAILS_URL
    assert calls[0][1]['fields'] == 'formatted_phone_number,website'
    saved = next(l for l in client.get('/v1/prospect-leads', headers=mobile_headers).json() if l['id'] == lead['id'])
    assert saved['website'] == 'https://example.test'


def test_draft_kit_check_does_not_change_saved_selection(client, mobile_headers):
    response = client.post('/v1/toolkit/recommend', headers=mobile_headers, json={"scenario_id": "add_key_blade_remote_head", "tool_keys": ["keyline_ninja_total", "abrites_avdi"]})
    assert response.status_code == 200, response.text
    assert response.json()['ready_for_required'] is True
    assert client.get('/v1/toolkit/my-selection', headers=mobile_headers).json()['tool_keys'] == []
    empty = client.post('/v1/toolkit/recommend', headers=mobile_headers, json={"scenario_id": "add_key_blade_remote_head", "tool_keys": []})
    assert empty.json()['ready_for_required'] is False
