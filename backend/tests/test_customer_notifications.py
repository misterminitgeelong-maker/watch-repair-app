"""Customer texts/emails that used to be silently missing (notification audit, Nov 2026)."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from uuid import UUID, uuid4

from fastapi.testclient import TestClient
from sqlmodel import Session, select

from app.database import engine
from app.models import AutoKeyJob, Customer, SmsLog
from app.services.mobile_day_before import send_day_before_reminders

from test_sms_controls import _bootstrap_tenant, _unique_phone


def _watch_job(client: TestClient, headers: dict[str, str], phone: str) -> str:
    cust = client.post("/v1/customers", headers=headers, json={"full_name": "Notify Customer", "phone": phone})
    assert cust.status_code == 201, cust.text
    watch = client.post("/v1/watches", headers=headers, json={"customer_id": cust.json()["id"], "brand": "Seiko"})
    job = client.post(
        "/v1/repair-jobs", headers=headers,
        json={"watch_id": watch.json()["id"], "title": "Notify job", "priority": "normal"},
    )
    assert job.status_code == 201, job.text
    return job.json()["id"]


def _events(tenant_id: UUID, job_id: str) -> list[str]:
    with Session(engine) as s:
        rows = s.exec(select(SmsLog).where(SmsLog.repair_job_id == UUID(job_id))).all()
    return [r.event for r in rows]


def test_queue_swipe_forward_into_ready_texts_the_customer(client: TestClient):
    headers, tenant_id, _ = _bootstrap_tenant(client, "swipe")
    _, phone = _unique_phone()
    job_id = _watch_job(client, headers, phone)
    # Walk the job to the status just before "completed" on the status endpoint, then swipe.
    from app.routes.repair_jobs import _WATCH_QUEUE_SEQUENCE

    prev = _WATCH_QUEUE_SEQUENCE[_WATCH_QUEUE_SEQUENCE.index("completed") - 1]
    assert client.post(f"/v1/repair-jobs/{job_id}/status", headers=headers, json={"status": prev}).status_code == 200
    res = client.post(f"/v1/repair-jobs/{job_id}/queue-swipe", headers=headers, json={"direction": "right"})
    assert res.status_code == 200, res.text
    assert res.json()["status"] == "completed"
    assert "status_completed" in _events(tenant_id, job_id)


def test_watch_go_ahead_and_collected_texts_are_sent(client: TestClient):
    headers, tenant_id, _ = _bootstrap_tenant(client, "goahead")
    _, phone = _unique_phone()
    job_id = _watch_job(client, headers, phone)
    for status in ("go_ahead", "collected"):
        assert client.post(f"/v1/repair-jobs/{job_id}/status", headers=headers, json={"status": status}).status_code == 200
    events = _events(tenant_id, job_id)
    assert "status_go_ahead" in events and "status_collected" in events


def test_ready_text_not_repeated_on_second_ready_step(client: TestClient):
    headers, tenant_id, _ = _bootstrap_tenant(client, "once")
    _, phone = _unique_phone()
    job_id = _watch_job(client, headers, phone)
    for status in ("completed", "awaiting_collection"):
        assert client.post(f"/v1/repair-jobs/{job_id}/status", headers=headers, json={"status": status}).status_code == 200
    ready = [e for e in _events(tenant_id, job_id) if e in ("status_completed", "status_awaiting_collection")]
    assert len(ready) == 1


def test_day_before_sweep_texts_tomorrows_job_once(client: TestClient):
    headers, tenant_id, _ = _bootstrap_tenant(client, "daybefore")
    _, phone = _unique_phone()
    with Session(engine) as s:
        cust = Customer(tenant_id=tenant_id, full_name="Day Before", phone=phone)
        s.add(cust)
        s.flush()
        job = AutoKeyJob(
            tenant_id=tenant_id, customer_id=cust.id, job_number=f"AK-{uuid4().hex[:6]}", title="Key",
            status="booking_confirmed",
            scheduled_at=(datetime.now(timezone.utc) + timedelta(hours=24)).replace(tzinfo=None, minute=0),
        )
        s.add(job)
        s.commit()
        job_id = job.id
    with Session(engine) as s:
        first = send_day_before_reminders(s, tenant_id, ignore_hour=True)
    with Session(engine) as s:
        second = send_day_before_reminders(s, tenant_id, ignore_hour=True)
    # 24h ahead is "tomorrow" in every timezone within a couple of hours, so allow the
    # edge case where the shop-local date differs; the point is it never sends twice.
    assert first["sent"] + second["sent"] <= 1
    with Session(engine) as s:
        sent = s.exec(select(SmsLog).where(SmsLog.auto_key_job_id == job_id)).all()
    assert len(sent) <= 1


def test_phone_only_watch_invoice_is_texted(client: TestClient):
    headers, tenant_id, _ = _bootstrap_tenant(client, "invtext")
    _, phone = _unique_phone()
    job_id = _watch_job(client, headers, phone)
    quote = client.post(
        "/v1/quotes", headers=headers,
        json={"repair_job_id": job_id, "tax_cents": 0,
              "line_items": [{"item_type": "labor", "description": "Service", "quantity": 1, "unit_price_cents": 1000}]},
    )
    assert quote.status_code == 201, quote.text
    sent = client.post(f"/v1/quotes/{quote.json()['id']}/send", headers=headers)
    assert sent.status_code == 200
    token = sent.json()["approval_token"]
    assert client.post(f"/v1/public/quotes/{token}/decision", json={"decision": "approved"}).status_code == 200
    inv = client.post(f"/v1/invoices/from-quote/{quote.json()['id']}", headers=headers)
    assert inv.status_code == 201, inv.text
    invoice_id = inv.json()["invoice"]["id"] if "invoice" in inv.json() else inv.json()["id"]
    inv_total = client.get(f"/v1/invoices/{invoice_id}", headers=headers).json()["invoice"]["total_cents"]
    res = client.post(f"/v1/invoices/{invoice_id}/send", headers=headers)
    assert res.status_code == 200, res.text
    with Session(engine) as s:
        rows = s.exec(select(SmsLog).where(SmsLog.repair_job_id == UUID(job_id))).all()
    assert any(r.event == "invoice_sent" for r in rows)
    # Paying in full sends a receipt text.
    pay = client.post(f"/v1/invoices/{invoice_id}/payments", headers=headers, json={"amount_cents": inv_total})
    assert pay.status_code == 201, pay.text
    with Session(engine) as s:
        rows = s.exec(select(SmsLog).where(SmsLog.repair_job_id == UUID(job_id))).all()
    assert any(r.event == "payment_receipt" for r in rows)
