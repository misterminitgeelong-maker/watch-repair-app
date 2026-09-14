"""Offline-queue replay: duplicate POST rejection and stale-write 409."""
from datetime import datetime, timedelta, timezone

from sqlmodel import Session, select

from app.database import engine
from app.models import AutoKeyJob, MutationIdempotencyKey


def _headers(token: str, extra: dict | None = None) -> dict[str, str]:
    headers = {"Authorization": f"Bearer {token}"}
    if extra:
        headers.update(extra)
    return headers


def _create_job(client, headers: dict[str, str]) -> str:
    customer = client.post(
        "/v1/customers",
        headers=headers,
        json={"full_name": "Offline Tech", "phone": "0400000000"},
    )
    assert customer.status_code == 201, customer.text
    job = client.post(
        "/v1/auto-key-jobs",
        headers=headers,
        json={
            "customer_id": customer.json()["id"],
            "title": "Van lockout",
            "key_quantity": 1,
            "priority": "normal",
            "status": "awaiting_quote",
            "programming_status": "pending",
            "deposit_cents": 0,
            "cost_cents": 0,
        },
    )
    assert job.status_code == 201, job.text
    return job.json()["id"]


def test_duplicate_replay_rejected_by_idempotency_key(client, bootstrap_and_login):
    token = bootstrap_and_login(password="supersecret123", plan_code="enterprise")
    headers = _headers(token)
    customer = client.post(
        "/v1/customers",
        headers=headers,
        json={"full_name": "Dup Customer", "phone": "0400111222"},
    )
    assert customer.status_code == 201, customer.text
    payload = {
        "customer_id": customer.json()["id"],
        "title": "Duplicate replay",
        "key_quantity": 1,
        "priority": "normal",
        "status": "awaiting_quote",
        "programming_status": "pending",
        "deposit_cents": 0,
        "cost_cents": 0,
    }
    keyed = _headers(token, {"Idempotency-Key": "offline-key-1"})
    first = client.post("/v1/auto-key-jobs", headers=keyed, json=payload)
    assert first.status_code == 201, first.text
    second = client.post("/v1/auto-key-jobs", headers=keyed, json=payload)
    assert second.status_code == 201, second.text
    assert second.json()["id"] == first.json()["id"]
    with Session(engine) as session:
        jobs = session.exec(select(AutoKeyJob).where(AutoKeyJob.title == "Duplicate replay")).all()
        assert len(jobs) == 1
        keys = session.exec(select(MutationIdempotencyKey)).all()
        assert len(keys) == 1


def test_idempotency_key_reuse_with_different_body_is_conflict(client, bootstrap_and_login):
    token = bootstrap_and_login(password="supersecret123", plan_code="enterprise")
    headers = _headers(token, {"Idempotency-Key": "offline-key-2"})
    customer = client.post(
        "/v1/customers",
        headers={"Authorization": f"Bearer {token}"},
        json={"full_name": "Other", "phone": "0400333444"},
    )
    assert customer.status_code == 201
    payload = {
        "customer_id": customer.json()["id"],
        "title": "First body",
        "key_quantity": 1,
        "priority": "normal",
        "status": "awaiting_quote",
        "programming_status": "pending",
        "deposit_cents": 0,
        "cost_cents": 0,
    }
    first = client.post("/v1/auto-key-jobs", headers=headers, json=payload)
    assert first.status_code == 201, first.text
    payload["title"] = "Second body"
    reused = client.post("/v1/auto-key-jobs", headers=headers, json=payload)
    assert reused.status_code == 409


def test_stale_write_rejected_on_auto_key_status(client, bootstrap_and_login):
    token = bootstrap_and_login(password="supersecret123", plan_code="enterprise")
    headers = _headers(token)
    job_id = _create_job(client, headers)
    later_write = client.post(
        f"/v1/auto-key-jobs/{job_id}/status",
        headers=headers,
        json={"status": "en_route"},
    )
    assert later_write.status_code == 200, later_write.text
    queued_at = (datetime.now(timezone.utc) - timedelta(hours=8)).isoformat()
    stale = client.post(
        f"/v1/auto-key-jobs/{job_id}/status",
        headers=_headers(token, {"X-Queued-At": queued_at}),
        json={"status": "awaiting_quote"},
    )
    assert stale.status_code == 409, stale.text
    assert stale.json()["detail"] == "stale_write"
    current = client.get(f"/v1/auto-key-jobs/{job_id}", headers=headers)
    assert current.status_code == 200
    assert current.json()["status"] == "en_route"
