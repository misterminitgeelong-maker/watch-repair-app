"""Inbound Twilio SMS webhook routing — open-job preference over stale SmsLog."""
from datetime import datetime, timedelta, timezone
from uuid import UUID, uuid4

import pytest
from fastapi.testclient import TestClient
from sqlmodel import Session, select

from app.database import engine
from app.models import AutoKeyJob, Customer, JobMessage, RepairJob, Shoe, ShoeRepairJob, SmsLog, TenantEventLog

_WEBHOOK = "/v1/webhook/sms/incoming"


def _phone_pair(n: int) -> tuple[str, str]:
    """Twilio From (E.164) and stored customer phone for suffix n."""
    local = f"040000{n:04d}"
    return f"+61{local[1:]}", local


def _post_inbound(client: TestClient, phone: str, body: str = "Thanks, see you soon") -> None:
    res = client.post(_WEBHOOK, data={"From": phone, "Body": body})
    assert res.status_code == 200, res.text
    assert "Response" in res.text


def _bootstrap_tenant(client: TestClient, suffix: str | None = None) -> tuple[dict[str, str], UUID]:
    suffix = suffix or uuid4().hex[:8]
    slug = f"sms-route-{suffix}"
    email = f"owner-{suffix}@sms.test"
    boot = client.post(
        "/v1/auth/bootstrap",
        json={
            "tenant_name": f"SMS Route {suffix}",
            "tenant_slug": slug,
            "owner_email": email,
            "owner_full_name": "Owner",
            "owner_password": "pass123456",
            "plan_code": "enterprise",
        },
    )
    assert boot.status_code == 200, boot.text
    tenant_id = UUID(boot.json()["tenant_id"])
    login = client.post(
        "/v1/auth/login",
        json={"tenant_slug": slug, "email": email, "password": "pass123456"},
    )
    assert login.status_code == 200, login.text
    return {"Authorization": f"Bearer {login.json()['access_token']}"}, tenant_id


def _customer_with_phone(client: TestClient, headers: dict[str, str], local_phone: str) -> str:
    res = client.post(
        "/v1/customers",
        headers=headers,
        json={
            "full_name": "SMS Customer",
            "phone": local_phone,
            "email": f"sms-{local_phone}@example.test",
        },
    )
    assert res.status_code == 201, res.text
    return res.json()["id"]


def _watch_job(client: TestClient, headers: dict[str, str], customer_id: str, title: str) -> RepairJob:
    watch = client.post(
        "/v1/watches",
        headers=headers,
        json={"customer_id": customer_id, "brand": "Omega", "model": "Seamaster"},
    )
    assert watch.status_code == 201, watch.text
    job = client.post(
        "/v1/repair-jobs",
        headers=headers,
        json={"watch_id": watch.json()["id"], "title": title, "priority": "normal"},
    )
    assert job.status_code == 201, job.text
    with Session(engine) as session:
        return session.get(RepairJob, UUID(job.json()["id"]))


def _auto_key_job(client: TestClient, headers: dict[str, str], customer_id: str, title: str) -> AutoKeyJob:
    job = client.post(
        "/v1/auto-key-jobs",
        headers=headers,
        json={
            "customer_id": customer_id,
            "title": title,
            "vehicle_make": "Toyota",
            "vehicle_model": "Camry",
        },
    )
    assert job.status_code == 201, job.text
    with Session(engine) as session:
        return session.get(AutoKeyJob, UUID(job.json()["id"]))


def _shoe_job(client: TestClient, headers: dict[str, str], customer_id: str, tenant_id: UUID, title: str) -> ShoeRepairJob:
    """Insert shoe job directly — avoids shoe create API SMS path in tests."""
    with Session(engine) as session:
        shoe = Shoe(
            tenant_id=tenant_id,
            customer_id=UUID(customer_id),
            shoe_type="Boot",
            brand="RM",
        )
        session.add(shoe)
        session.flush()
        job = ShoeRepairJob(
            tenant_id=tenant_id,
            shoe_id=shoe.id,
            job_number=f"SHOE-{uuid4().hex[:5]}",
            title=title,
            priority="normal",
            status="awaiting_go_ahead",
        )
        session.add(job)
        session.commit()
        session.refresh(job)
        return job


def _add_sms_log(
    session: Session,
    *,
    tenant_id: UUID,
    to_phone: str,
    repair_job_id: UUID | None = None,
    shoe_repair_job_id: UUID | None = None,
    auto_key_job_id: UUID | None = None,
    created_at: datetime | None = None,
) -> SmsLog:
    log = SmsLog(
        tenant_id=tenant_id,
        repair_job_id=repair_job_id,
        shoe_repair_job_id=shoe_repair_job_id,
        auto_key_job_id=auto_key_job_id,
        to_phone=to_phone,
        body="Outbound test",
        event="quote_sent",
        status="sent",
        created_at=created_at or datetime.now(timezone.utc),
    )
    session.add(log)
    session.commit()
    return log


def test_inbound_prefers_open_job_over_stale_sms_log(client: TestClient):
    from_phone, stored_phone = _phone_pair(1)
    headers, tenant_id = _bootstrap_tenant(client)
    customer_id = _customer_with_phone(client, headers, stored_phone)

    closed_watch = _watch_job(client, headers, customer_id, "Old watch repair")
    open_auto = _auto_key_job(client, headers, customer_id, "Active mobile key")

    with Session(engine) as session:
        closed = session.get(RepairJob, closed_watch.id)
        assert closed is not None
        closed.status = "collected"
        session.add(closed)
        _add_sms_log(
            session,
            tenant_id=tenant_id,
            to_phone=from_phone,
            repair_job_id=closed_watch.id,
            created_at=datetime.now(timezone.utc) - timedelta(hours=1),
        )

    _post_inbound(client, from_phone, body="On my way")

    with Session(engine) as session:
        msg = session.exec(
            select(JobMessage)
            .where(JobMessage.direction == "inbound")
            .where(JobMessage.from_phone == from_phone)
        ).first()
        assert msg is not None
        assert msg.auto_key_job_id == open_auto.id
        assert msg.repair_job_id is None

        event = session.exec(
            select(TenantEventLog)
            .where(TenantEventLog.event_type == "customer_sms_reply")
            .where(TenantEventLog.event_summary.contains(from_phone))
        ).first()
        assert event is not None
        assert event.entity_type == "auto_key_job"
        assert event.entity_id == open_auto.id


def test_inbound_fallback_to_most_recent_sms_log(client: TestClient):
    from_phone, stored_phone = _phone_pair(2)
    headers, tenant_id = _bootstrap_tenant(client)
    customer_id = _customer_with_phone(client, headers, stored_phone)
    watch = _watch_job(client, headers, customer_id, "Only watch job")

    with Session(engine) as session:
        job = session.get(RepairJob, watch.id)
        assert job is not None
        job.status = "collected"
        session.add(job)
        _add_sms_log(
            session,
            tenant_id=tenant_id,
            to_phone=stored_phone,
            repair_job_id=watch.id,
        )

    _post_inbound(client, from_phone)

    with Session(engine) as session:
        msg = session.exec(
            select(JobMessage)
            .where(JobMessage.direction == "inbound")
            .where(JobMessage.from_phone == from_phone)
        ).first()
        assert msg is not None
        assert msg.repair_job_id == watch.id


def test_inbound_routes_to_open_shoe_job(client: TestClient):
    from_phone, stored_phone = _phone_pair(3)
    headers, tenant_id = _bootstrap_tenant(client)
    customer_id = _customer_with_phone(client, headers, stored_phone)
    shoe = _shoe_job(client, headers, customer_id, tenant_id, "Heel repair")

    _post_inbound(client, from_phone, body="Can I pick up Friday?")

    with Session(engine) as session:
        msg = session.exec(
            select(JobMessage)
            .where(JobMessage.direction == "inbound")
            .where(JobMessage.from_phone == from_phone)
        ).first()
        assert msg is not None
        assert msg.shoe_repair_job_id == shoe.id

        event = session.exec(
            select(TenantEventLog)
            .where(TenantEventLog.event_type == "customer_sms_reply")
            .where(TenantEventLog.event_summary.contains(from_phone))
        ).first()
        assert event is not None
        assert event.entity_type == "shoe_repair_job"
        assert event.entity_id == shoe.id


def test_inbound_known_customer_without_job_logs_inbox_only(client: TestClient):
    from_phone, stored_phone = _phone_pair(4)
    headers, tenant_id = _bootstrap_tenant(client)
    customer_id = _customer_with_phone(client, headers, stored_phone)

    _post_inbound(client, from_phone, body="Hello?")

    with Session(engine) as session:
        assert session.exec(
            select(JobMessage)
            .where(JobMessage.direction == "inbound")
            .where(JobMessage.from_phone == from_phone)
        ).first() is None

        event = session.exec(
            select(TenantEventLog)
            .where(TenantEventLog.event_type == "customer_sms_reply")
            .where(TenantEventLog.event_summary.contains(from_phone))
        ).first()
        assert event is not None
        assert event.tenant_id == tenant_id
        assert event.entity_type == "customer"
        assert event.entity_id == UUID(customer_id)


def test_inbound_unknown_sender_is_silent(client: TestClient):
    _bootstrap_tenant(client)
    unknown = "+61499998888"
    _post_inbound(client, unknown, body="Wrong number")

    with Session(engine) as session:
        assert session.exec(
            select(JobMessage).where(JobMessage.from_phone == unknown)
        ).first() is None
        assert session.exec(
            select(TenantEventLog)
            .where(TenantEventLog.event_type == "customer_sms_reply")
            .where(TenantEventLog.event_summary.contains(unknown))
        ).first() is None
