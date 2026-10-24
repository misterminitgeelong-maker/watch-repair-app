import os
from uuid import UUID, uuid4
from pathlib import Path


_TEST_DB = Path(__file__).with_name(f"test_aq_options_{uuid4().hex}.db")
os.environ.setdefault("DATABASE_URL", f"sqlite:///{_TEST_DB.as_posix()}")

from fastapi.testclient import TestClient

from app.database import create_db_and_tables
from app.main import app

create_db_and_tables()
client = TestClient(app)


def _setup():
    suffix = uuid4().hex[:8]
    slug = f"aqo-{suffix}"
    assert client.post("/v1/auth/bootstrap", json={
        "tenant_name": slug, "tenant_slug": slug, "owner_email": f"o-{suffix}@aqo.test",
        "owner_full_name": "Owner", "owner_password": "pass123456", "plan_code": "enterprise",
    }).status_code == 200
    token = client.post("/v1/auth/login", json={
        "tenant_slug": slug, "email": f"o-{suffix}@aqo.test", "password": "pass123456",
    }).json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}
    cust = client.post("/v1/customers", headers=headers, json={"full_name": "A Nguyen", "phone": "0400000000"}).json()["id"]
    job = client.post("/v1/auto-key-jobs", headers=headers, json={
        "customer_id": cust, "title": "BMW all keys lost", "key_quantity": 1, "priority": "normal",
        "status": "awaiting_quote", "programming_status": "pending", "deposit_cents": 0, "cost_cents": 0,
    })
    assert job.status_code == 201
    return headers, job.json()["id"]


def _line(desc, cents):
    return {"description": desc, "quantity": 1, "unit_price_cents": cents}


def _two_option_quote(headers, job_id):
    res = client.post(f"/v1/auto-key-jobs/{job_id}/quotes", headers=headers, json={
        "gst_enabled": True, "gst_inclusive": False,
        "line_items": [_line("Call-out", 9000)],
        "options": [
            {"label": "CAS3 module", "line_items": [_line("Programme CAS3 key", 60000)]},
            {"label": "CAS3++ module", "line_items": [_line("Programme CAS3++ key", 79000)]},
        ],
    })
    assert res.status_code == 201, res.text
    return res.json()


def test_two_option_quote_totals_and_invoice_follow_selected_option():
    headers, job_id = _setup()
    quote = _two_option_quote(headers, job_id)
    totals = {o["key"]: o["total_cents"] for o in quote["options"]}
    assert totals == {"A": 75900, "B": 96800}  # (90 + 600) * 1.1 and (90 + 790) * 1.1
    assert quote["total_cents"] == 96800  # highest until a choice is made
    assert quote["selected_option"] is None

    # Can't invoice or complete before choosing.
    assert client.post(f"/v1/auto-key-jobs/{job_id}/invoices/from-quote/{quote['id']}", headers=headers).status_code == 409
    done = client.post(f"/v1/auto-key-jobs/{job_id}/status", headers=headers, json={"status": "work_completed", "note": "x"})
    assert done.status_code == 409

    picked = client.post(f"/v1/auto-key-jobs/quotes/{quote['id']}/select-option", headers=headers, json={"option": "A"})
    assert picked.status_code == 200, picked.text
    assert picked.json()["selected_option"] == "A"
    assert picked.json()["total_cents"] == 75900

    done = client.post(f"/v1/auto-key-jobs/{job_id}/status", headers=headers, json={"status": "work_completed", "note": "x"})
    assert done.status_code == 200, done.text
    assert done.json()["invoice_created"] is True
    invoices = client.get(f"/v1/auto-key-jobs/{job_id}/invoices", headers=headers).json()
    assert len(invoices) == 1 and invoices[0]["total_cents"] == 75900


def test_public_approval_does_not_invoice_until_option_selected():
    headers, job_id = _setup()
    quote = _two_option_quote(headers, job_id)
    sent = client.post(f"/v1/auto-key-jobs/quotes/{quote['id']}/send", headers=headers)
    assert sent.status_code == 200, sent.text

    from sqlmodel import Session, select
    from app.database import engine
    from app.models import AutoKeyQuote
    with Session(engine) as s:
        token = s.exec(select(AutoKeyQuote).where(AutoKeyQuote.id == UUID(quote["id"]))).one().quote_approval_token

    page = client.get(f"/v1/public/auto-key-quote/{token}")
    assert page.status_code == 200, page.text
    body = page.json()
    assert [o["key"] for o in body["options"]] == ["A", "B"]
    assert {i["option_key"] for i in body["line_items"]} == {None, "A", "B"}

    approved = client.post(f"/v1/public/auto-key-quote/{token}/decision", json={"decision": "approved"})
    assert approved.status_code == 200, approved.text
    assert client.get(f"/v1/auto-key-jobs/{job_id}/invoices", headers=headers).json() == []

    assert client.post(f"/v1/auto-key-jobs/quotes/{quote['id']}/select-option", headers=headers, json={"option": "B"}).status_code == 200
    inv = client.post(f"/v1/auto-key-jobs/{job_id}/invoices/from-quote/{quote['id']}", headers=headers)
    assert inv.status_code == 201, inv.text
    assert inv.json()["total_cents"] == 96800


def test_options_validation_and_plain_quotes_unchanged():
    headers, job_id = _setup()
    bad = client.post(f"/v1/auto-key-jobs/{job_id}/quotes", headers=headers, json={
        "options": [{"label": "Only one", "line_items": [_line("x", 100)]}],
    })
    assert bad.status_code == 400
    plain = client.post(f"/v1/auto-key-jobs/{job_id}/quotes", headers=headers, json={"line_items": [_line("Key", 10000)]})
    assert plain.status_code == 201
    assert plain.json()["options"] == [] and plain.json()["total_cents"] == 11000
    assert client.post(f"/v1/auto-key-jobs/quotes/{plain.json()['id']}/select-option", headers=headers, json={"option": "A"}).status_code == 400
