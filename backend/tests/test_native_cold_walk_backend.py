"""Backend fixes from the native Android cold-walk findings (#1, #2, #3, #5, #10, #15, #21)."""
from uuid import uuid4

import pytest
from sqlmodel import Session

from app.database import engine
from app.models import Invoice, ProspectLead, RepairJob


@pytest.fixture
def headers(bootstrap_and_login):
    return {"Authorization": f"Bearer {bootstrap_and_login(plan_code='enterprise')}"}


def _customer(client, headers, name="Cold Walk Customer", phone="0400111222"):
    res = client.post("/v1/customers", headers=headers, json={"full_name": name, "phone": phone})
    assert res.status_code == 201, res.text
    return res.json()["id"]


def _repair_job(client, headers, **customer_kwargs):
    cid = _customer(client, headers, **customer_kwargs)
    watch = client.post("/v1/watches", headers=headers, json={"customer_id": cid, "brand": "Seiko", "model": "5"})
    assert watch.status_code == 201, watch.text
    job = client.post(
        "/v1/repair-jobs", headers=headers,
        json={"watch_id": watch.json()["id"], "title": "Service", "priority": "normal"},
    )
    assert job.status_code == 201, job.text
    return job.json()


def test_auto_key_single_job_responses_include_customer(client, headers):
    cid = _customer(client, headers, name="Ada Key", phone="0455000111")
    res = client.post(
        "/v1/auto-key-jobs", headers=headers,
        json={"customer_id": cid, "title": "Spare key", "key_quantity": 1, "priority": "normal",
              "status": "awaiting_quote", "programming_status": "pending", "deposit_cents": 0, "cost_cents": 0},
    )
    assert res.status_code == 201, res.text
    job = res.json()
    assert (job["customer_name"], job["customer_phone"]) == ("Ada Key", "0455000111")
    jid = job["id"]
    got = client.get(f"/v1/auto-key-jobs/{jid}", headers=headers).json()
    assert (got["customer_name"], got["customer_phone"]) == ("Ada Key", "0455000111")
    patched = client.patch(f"/v1/auto-key-jobs/{jid}", headers=headers, json={"title": "Spare key 2"}).json()
    assert patched["title"] == "Spare key 2" and patched["customer_name"] == "Ada Key"
    st = client.post(f"/v1/auto-key-jobs/{jid}/status", headers=headers, json={"status": "awaiting_go_ahead"})
    assert st.status_code == 200, st.text
    assert st.json()["customer_name"] == "Ada Key" and st.json()["customer_phone"] == "0455000111"


def test_repair_job_single_responses_include_claimed_by_and_customer(client, headers):
    job = _repair_job(client, headers, name="Wally Watch", phone="0466777888")
    jid = job["id"]
    claimed = client.post(f"/v1/repair-jobs/{jid}/claim", headers=headers)
    assert claimed.status_code == 200
    assert claimed.json()["claimed_by_name"] == "Main Owner"
    assert claimed.json()["customer_name"] == "Wally Watch"
    got = client.get(f"/v1/repair-jobs/{jid}", headers=headers).json()
    assert got["claimed_by_name"] == "Main Owner"
    assert got["customer_name"] == "Wally Watch" and got["customer_phone"] == "0466777888"
    assert got["watch_brand"] == "Seiko"
    patched = client.patch(f"/v1/repair-jobs/{jid}", headers=headers, json={"internal_notes": "x"}).json()
    assert patched["claimed_by_name"] == "Main Owner" and patched["customer_name"] == "Wally Watch"
    released = client.post(f"/v1/repair-jobs/{jid}/release", headers=headers).json()
    assert released["claimed_by_name"] is None and released["customer_name"] == "Wally Watch"


def test_repair_job_list_q_matches_customer_name_and_phone(client, headers):
    a = _repair_job(client, headers, name="Zebediah Quill", phone="0499123456")
    b = _repair_job(client, headers, name="Someone Else", phone="0411000000")

    def ids(q):
        return {j["id"] for j in client.get("/v1/repair-jobs", headers=headers, params={"q": q}).json()}

    assert ids("zebediah") == {a["id"]}
    assert ids("0499123") == {a["id"]}
    assert b["id"] in ids("someone")
    assert ids("service") >= {a["id"], b["id"]}  # title match still works
    assert ids("nomatch-xyz") == set()


def test_invoice_list_repair_job_filter(client, headers):
    j1 = _repair_job(client, headers)
    j2 = _repair_job(client, headers)
    with Session(engine) as s:
        for jid in (j1["id"], j2["id"], j2["id"]):
            row = s.get(RepairJob, __import__("uuid").UUID(jid))
            s.add(Invoice(tenant_id=row.tenant_id, repair_job_id=row.id,
                          invoice_number=f"INV-{uuid4().hex[:6]}", subtotal_cents=100, tax_cents=10, total_cents=110))
        s.commit()
    allres = client.get("/v1/invoices", headers=headers).json()
    assert allres["total"] >= 3
    one = client.get("/v1/invoices", headers=headers, params={"repair_job_id": j1["id"]}).json()
    assert one["total"] == 1 and len(one["items"]) == 1
    two = client.get("/v1/invoices", headers=headers, params={"repair_job_id": j2["id"]}).json()
    assert two["total"] == 2


def test_prospect_visit_time_normalised_and_serialised_utc(client, headers):
    lead = client.post("/v1/prospect-leads", headers=headers, json={"name": "Visit Co", "place_id": uuid4().hex}).json()
    res = client.patch(f"/v1/prospect-leads/{lead['id']}", headers=headers,
                       json={"visit_scheduled_at": "2026-10-02T10:00:00+10:00"})
    assert res.status_code == 200, res.text
    assert res.json()["visit_scheduled_at"].startswith("2026-10-02T00:00:00")
    assert res.json()["visit_scheduled_at"].endswith(("Z", "+00:00"))
    with Session(engine) as s:
        stored = s.get(ProspectLead, __import__("uuid").UUID(lead["id"]))
        from app.datetime_utils import naive_utc_from_any
        # Postgres returns tz-aware UTC, SQLite naive: compare the normalised UTC value
        assert naive_utc_from_any(stored.visit_scheduled_at).hour == 0
    web = client.patch(f"/v1/prospects/leads/{lead['id']}", headers=headers,
                       json={"visit_scheduled_at": "2026-10-02T00:00:00Z"})
    assert web.status_code == 200, web.text
    assert web.json()["visit_scheduled_at"].endswith(("Z", "+00:00"))


def test_prospects_accepts_visited_and_onboarded(client, headers):
    for status in ("visited", "onboarded"):
        res = client.post("/v1/prospects/leads", headers=headers, json={"name": f"L {status}", "status": status})
        assert res.status_code == 201, res.text
        listed = client.get("/v1/prospects/leads", headers=headers, params={"status": status})
        assert listed.status_code == 200 and any(l["status"] == status for l in listed.json())


def test_me_trial_end_is_explicit_utc(client, bootstrap_and_login):
    from datetime import datetime
    from sqlmodel import select
    from app.models import Tenant

    token = bootstrap_and_login(plan_code="enterprise")
    h = {"Authorization": f"Bearer {token}"}
    with Session(engine) as s:
        tenant = s.exec(select(Tenant).order_by(Tenant.created_at.desc())).first()
        tenant.trial_end = datetime(2030, 1, 1, 12, 0, 0)
        s.add(tenant)
        s.commit()
    res = client.get("/v1/auth/session", headers=h)
    assert res.status_code == 200, res.text
    assert res.json()["trial_end"] == "2030-01-01T12:00:00Z"
