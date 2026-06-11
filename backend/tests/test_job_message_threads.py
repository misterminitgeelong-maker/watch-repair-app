"""Per-ticket message threads include every message exchanged with the customer's
phone, not only rows linked to that job id."""
from datetime import datetime, timezone
from uuid import UUID, uuid4

from fastapi.testclient import TestClient
from sqlmodel import Session

from app.database import engine
from app.models import SmsLog

_WEBHOOK = "/v1/webhook/sms/incoming"


def _bootstrap_tenant(client: TestClient) -> dict[str, str]:
    suffix = uuid4().hex[:8]
    slug = f"threads-{suffix}"
    email = f"owner-{suffix}@threads.test"
    boot = client.post(
        "/v1/auth/bootstrap",
        json={
            "tenant_name": f"Threads {suffix}",
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


def _customer(client: TestClient, headers: dict[str, str], phone: str) -> tuple[str, UUID]:
    res = client.post(
        "/v1/customers",
        headers=headers,
        json={"full_name": "Thread Customer", "phone": phone},
    )
    assert res.status_code == 201, res.text
    body = res.json()
    return body["id"], UUID(body["tenant_id"])


def _watch_job(client: TestClient, headers: dict[str, str], customer_id: str, title: str) -> str:
    watch = client.post(
        "/v1/watches",
        headers=headers,
        json={"customer_id": customer_id, "brand": "Seiko", "model": "5"},
    )
    assert watch.status_code == 201, watch.text
    job = client.post(
        "/v1/repair-jobs",
        headers=headers,
        json={"watch_id": watch.json()["id"], "title": title, "priority": "normal"},
    )
    assert job.status_code == 201, job.text
    return job.json()["id"]


def test_inbound_routed_to_other_job_still_visible_on_each_ticket(client: TestClient):
    headers = _bootstrap_tenant(client)
    phone = "0400111222"
    customer_id, _tenant_id = _customer(client, headers, phone)

    older_job = _watch_job(client, headers, customer_id, "Older ticket")
    newer_job = _watch_job(client, headers, customer_id, "Newer ticket")

    # Inbound reply routes to the most recent open job (the newer ticket).
    res = client.post(_WEBHOOK, data={"From": "+61400111222", "Body": "Running late, sorry!"})
    assert res.status_code == 200

    for job_id in (older_job, newer_job):
        thread = client.get(f"/v1/repair-jobs/{job_id}/messages", headers=headers)
        assert thread.status_code == 200, thread.text
        inbound = [m for m in thread.json() if m["direction"] == "inbound"]
        assert any("Running late" in m["body"] for m in inbound), f"missing inbound on job {job_id}"


def test_inbound_without_open_job_visible_on_later_ticket(client: TestClient):
    headers = _bootstrap_tenant(client)
    phone = "0400333444"
    customer_id, _tenant_id = _customer(client, headers, phone)

    # Customer texts before any job exists — message is saved without a job link.
    res = client.post(_WEBHOOK, data={"From": "+61400333444", "Body": "Do you fix Tissot watches?"})
    assert res.status_code == 200

    job_id = _watch_job(client, headers, customer_id, "Tissot service")
    thread = client.get(f"/v1/repair-jobs/{job_id}/messages", headers=headers)
    assert thread.status_code == 200, thread.text
    inbound = [m for m in thread.json() if m["direction"] == "inbound"]
    assert any("Tissot" in m["body"] for m in inbound)


def test_unlinked_system_sms_visible_in_auto_key_thread(client: TestClient):
    headers = _bootstrap_tenant(client)
    phone = "0400555666"
    customer_id, tenant_id = _customer(client, headers, phone)

    job = client.post(
        "/v1/auto-key-jobs",
        headers=headers,
        json={
            "customer_id": customer_id,
            "title": "Lockout",
            "vehicle_make": "Mazda",
            "vehicle_model": "3",
        },
    )
    assert job.status_code == 201, job.text
    job_id = job.json()["id"]

    # Several automated mobile services SMS persist without any job link
    # (en route, arrival window, day-before). Simulate one.
    with Session(engine) as session:
        session.add(SmsLog(
            tenant_id=tenant_id,
            to_phone=phone,
            body="Hi, your technician is now on the way to you.",
            event="auto_key_en_route",
            status="sent",
            created_at=datetime.now(timezone.utc),
        ))
        session.commit()

    thread = client.get(f"/v1/auto-key-jobs/{job_id}/messages", headers=headers)
    assert thread.status_code == 200, thread.text
    system = [m for m in thread.json() if m["direction"] == "system"]
    assert any(m["event"] == "auto_key_en_route" for m in system)


def test_thread_merges_mixed_tz_aware_and_naive_timestamps(client: TestClient):
    """Production Postgres returns jobmessage.created_at tz-aware (timestamptz) but
    smslog.created_at naive (timestamp). The merged sort must not TypeError."""
    from datetime import timedelta
    from uuid import UUID
    from app.models import JobMessage
    from app.services.message_threads import build_job_thread

    headers = _bootstrap_tenant(client)
    phone = "0400777888"
    customer_id, tenant_id = _customer(client, headers, phone)
    job_id = _watch_job(client, headers, customer_id, "Mixed tz")

    now = datetime.now(timezone.utc)
    with Session(engine) as session:
        session.add(SmsLog(
            tenant_id=tenant_id,
            repair_job_id=UUID(job_id),
            to_phone=phone,
            body="Quote sent",
            event="quote_sent",
            status="sent",
            created_at=now.replace(tzinfo=None),  # naive, like prod smslog
        ))
        session.add(JobMessage(
            tenant_id=tenant_id,
            repair_job_id=UUID(job_id),
            direction="inbound",
            body="Sounds good",
            from_phone=phone,
            created_at=now + timedelta(minutes=5),  # aware, like prod jobmessage
        ))
        session.flush()

        thread = build_job_thread(
            session,
            tenant_id=tenant_id,
            customer_phone=phone,
            repair_job_id=UUID(job_id),
        )
        bodies = [m.body for m in thread]
        assert "Quote sent" in bodies
        assert "Sounds good" in bodies
        assert all(m.created_at.tzinfo is not None for m in thread)
        assert bodies.index("Quote sent") < bodies.index("Sounds good")
