import os
from pathlib import Path
from uuid import UUID, uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.exc import IntegrityError
from sqlmodel import Session

_TEST_DB = Path(__file__).with_name(f"test_repair_jobs_{uuid4().hex}.db")
os.environ["DATABASE_URL"] = f"sqlite:///{_TEST_DB.as_posix()}"
os.environ.setdefault("JWT_SECRET", "test-secret-not-for-production")
os.environ.setdefault("APP_ENV", "test")

from app.database import create_db_and_tables, engine
from app.main import app
from app.models import RepairJob

create_db_and_tables()
client = TestClient(app)


def _bootstrap_and_login(tenant_slug: str, email: str, password: str) -> str:
    bootstrap_payload = {
        "tenant_name": f"Tenant {tenant_slug}",
        "tenant_slug": tenant_slug,
        "owner_email": email,
        "owner_full_name": "Owner",
        "owner_password": password,
    }
    bootstrap_res = client.post("/v1/auth/bootstrap", json=bootstrap_payload)
    assert bootstrap_res.status_code == 200

    login_payload = {"tenant_slug": tenant_slug, "email": email, "password": password}
    login_res = client.post("/v1/auth/login", json=login_payload)
    assert login_res.status_code == 200
    return login_res.json()["access_token"]


def _create_watch(headers: dict[str, str]) -> str:
    customer_res = client.post(
        "/v1/customers",
        headers=headers,
        json={"full_name": "Repair Customer", "email": "repair@example.com"},
    )
    assert customer_res.status_code == 201
    customer_id = customer_res.json()["id"]
    watch_res = client.post(
        "/v1/watches",
        headers=headers,
        json={"customer_id": customer_id, "brand": "Rolex", "model": "Datejust"},
    )
    assert watch_res.status_code == 201
    return watch_res.json()["id"]


def _create_repair_job(headers: dict[str, str], watch_id: str, title: str = "Service") -> dict:
    res = client.post(
        "/v1/repair-jobs",
        headers=headers,
        json={"watch_id": watch_id, "title": title, "priority": "normal"},
    )
    assert res.status_code == 201
    return res.json()


def test_first_job_number_in_tenant_starts_at_one():
    suffix = uuid4().hex[:8]
    token = _bootstrap_and_login(f"repair-first-{suffix}", f"owner-{suffix}@repair.test", "pass123456")
    headers = {"Authorization": f"Bearer {token}"}
    watch_id = _create_watch(headers)

    job = _create_repair_job(headers, watch_id, "First")
    assert job["job_number"] == "JOB-00001"


def test_multiple_jobs_increment_for_same_tenant():
    suffix = uuid4().hex[:8]
    token = _bootstrap_and_login(f"repair-multi-{suffix}", f"owner-{suffix}@repair.test", "pass123456")
    headers = {"Authorization": f"Bearer {token}"}
    watch_id = _create_watch(headers)

    first = _create_repair_job(headers, watch_id, "First")
    second = _create_repair_job(headers, watch_id, "Second")
    third = _create_repair_job(headers, watch_id, "Third")

    assert first["job_number"] == "JOB-00001"
    assert second["job_number"] == "JOB-00002"
    assert third["job_number"] == "JOB-00003"


def test_different_tenants_have_independent_sequences():
    suffix_a = uuid4().hex[:8]
    suffix_b = uuid4().hex[:8]

    token_a = _bootstrap_and_login(f"repair-a-{suffix_a}", f"owner-{suffix_a}@repair.test", "pass123456")
    token_b = _bootstrap_and_login(f"repair-b-{suffix_b}", f"owner-{suffix_b}@repair.test", "pass123456")
    headers_a = {"Authorization": f"Bearer {token_a}"}
    headers_b = {"Authorization": f"Bearer {token_b}"}
    watch_a = _create_watch(headers_a)
    watch_b = _create_watch(headers_b)

    a_first = _create_repair_job(headers_a, watch_a, "A1")
    b_first = _create_repair_job(headers_b, watch_b, "B1")
    a_second = _create_repair_job(headers_a, watch_a, "A2")

    assert a_first["job_number"] == "JOB-00001"
    assert b_first["job_number"] == "JOB-00001"
    assert a_second["job_number"] == "JOB-00002"


def test_number_not_derived_from_row_count_after_delete():
    suffix = uuid4().hex[:8]
    token = _bootstrap_and_login(f"repair-gap-{suffix}", f"owner-{suffix}@repair.test", "pass123456")
    headers = {"Authorization": f"Bearer {token}"}
    watch_id = _create_watch(headers)

    first = _create_repair_job(headers, watch_id, "First")
    second = _create_repair_job(headers, watch_id, "Second")
    assert first["job_number"] == "JOB-00001"
    assert second["job_number"] == "JOB-00002"

    delete_res = client.delete(f"/v1/repair-jobs/{second['id']}", headers=headers)
    assert delete_res.status_code == 204

    third = _create_repair_job(headers, watch_id, "Third")
    assert third["job_number"] == "JOB-00003"


def test_uniqueness_protection_on_tenant_and_job_number():
    suffix = uuid4().hex[:8]
    token = _bootstrap_and_login(f"repair-unique-{suffix}", f"owner-{suffix}@repair.test", "pass123456")
    headers = {"Authorization": f"Bearer {token}"}
    watch_id = _create_watch(headers)

    created = _create_repair_job(headers, watch_id, "Original")
    tenant_id = UUID(created["tenant_id"])

    with Session(engine) as session:
        duplicate = RepairJob(
            tenant_id=tenant_id,
            watch_id=UUID(watch_id),
            job_number=created["job_number"],
            title="Duplicate",
            priority="normal",
            status="awaiting_go_ahead",
        )
        session.add(duplicate)
        with pytest.raises(IntegrityError):
            session.commit()


def test_queue_swipe_right_advances_along_lane():
    suffix = uuid4().hex[:8]
    token = _bootstrap_and_login(f"repair-qswipe-{suffix}", f"owner-{suffix}@repair.test", "pass123456")
    headers = {"Authorization": f"Bearer {token}"}
    watch_id = _create_watch(headers)
    job = _create_repair_job(headers, watch_id, "Queue test")
    assert job["status"] == "awaiting_go_ahead"

    res = client.post(
        f"/v1/repair-jobs/{job['id']}/queue-swipe",
        headers=headers,
        json={"direction": "right"},
    )
    assert res.status_code == 200
    assert res.json()["status"] == "go_ahead"

    back = client.post(
        f"/v1/repair-jobs/{job['id']}/queue-swipe",
        headers=headers,
        json={"direction": "left"},
    )
    assert back.status_code == 200
    assert back.json()["status"] == "awaiting_go_ahead"


def test_queue_swipe_left_at_first_status_returns_400():
    suffix = uuid4().hex[:8]
    token = _bootstrap_and_login(f"repair-qfirst-{suffix}", f"owner-{suffix}@repair.test", "pass123456")
    headers = {"Authorization": f"Bearer {token}"}
    watch_id = _create_watch(headers)
    job = _create_repair_job(headers, watch_id, "First status")
    with Session(engine) as session:
        row = session.get(RepairJob, UUID(job["id"]))
        assert row is not None
        row.status = "awaiting_quote"
        session.add(row)
        session.commit()

    res = client.post(
        f"/v1/repair-jobs/{job['id']}/queue-swipe",
        headers=headers,
        json={"direction": "left"},
    )
    assert res.status_code == 400
    assert "first" in res.json()["detail"].lower()


def test_queue_swipe_rejects_status_outside_lane():
    suffix = uuid4().hex[:8]
    token = _bootstrap_and_login(f"repair-qofflane-{suffix}", f"owner-{suffix}@repair.test", "pass123456")
    headers = {"Authorization": f"Bearer {token}"}
    watch_id = _create_watch(headers)
    job = _create_repair_job(headers, watch_id, "Off lane")
    with Session(engine) as session:
        row = session.get(RepairJob, UUID(job["id"]))
        assert row is not None
        row.status = "no_go"
        session.add(row)
        session.commit()

    res = client.post(
        f"/v1/repair-jobs/{job['id']}/queue-swipe",
        headers=headers,
        json={"direction": "right"},
    )
    assert res.status_code == 400
    assert "queue" in res.json()["detail"].lower() or "board" in res.json()["detail"].lower()


def test_repair_queue_day_get_put_roundtrip():
    suffix = uuid4().hex[:8]
    token = _bootstrap_and_login(f"repair-qday-{suffix}", f"owner-{suffix}@repair.test", "pass123456")
    headers = {"Authorization": f"Bearer {token}"}

    g = client.get("/v1/me/repair-queue-day", params={"mode": "watch"}, headers=headers)
    assert g.status_code == 200
    body = g.json()
    assert body["mode"] == "watch"
    assert len(body["shop_date"]) == 10
    assert body["done_ids"] == []
    assert body["stats"]["advanced"] == 0

    jid = str(uuid4())
    p = client.put(
        "/v1/me/repair-queue-day",
        headers=headers,
        json={
            "mode": "watch",
            "done_ids": [jid],
            "stats": {"advanced": 2, "checkedIn": 1, "skipped": 0},
        },
    )
    assert p.status_code == 200
    assert p.json()["done_ids"] == [jid]
    assert p.json()["stats"]["advanced"] == 2

    g2 = client.get("/v1/me/repair-queue-day", params={"mode": "watch"}, headers=headers)
    assert g2.status_code == 200
    assert g2.json()["done_ids"] == [jid]

    d = client.delete("/v1/me/repair-queue-day", params={"mode": "watch"}, headers=headers)
    assert d.status_code == 204

    g3 = client.get("/v1/me/repair-queue-day", params={"mode": "watch"}, headers=headers)
    assert g3.json()["done_ids"] == []


def test_repair_queue_day_rejects_bad_uuid():
    suffix = uuid4().hex[:8]
    token = _bootstrap_and_login(f"repair-qdaybad-{suffix}", f"owner-{suffix}@repair.test", "pass123456")
    headers = {"Authorization": f"Bearer {token}"}
    p = client.put(
        "/v1/me/repair-queue-day",
        headers=headers,
        json={"mode": "shoe", "done_ids": ["not-a-uuid"], "stats": {"advanced": 0, "checkedIn": 0, "skipped": 0}},
    )
    assert p.status_code == 422


def test_job_note_appends_to_description_fault_report():
    suffix = uuid4().hex[:8]
    token = _bootstrap_and_login(f"repair-note-{suffix}", f"owner-{suffix}@repair.test", "pass123456")
    headers = {"Authorization": f"Bearer {token}"}
    watch_id = _create_watch(headers)
    job = _create_repair_job(headers, watch_id)
    job_id = job["id"]

    patch = client.patch(
        f"/v1/repair-jobs/{job_id}",
        headers=headers,
        json={"description": "Original fault text"},
    )
    assert patch.status_code == 200

    note_res = client.post(
        f"/v1/repair-jobs/{job_id}/note",
        headers=headers,
        json={"note": "Customer called back"},
    )
    assert note_res.status_code == 204

    got = client.get(f"/v1/repair-jobs/{job_id}", headers=headers)
    assert got.status_code == 200
    desc = got.json()["description"]
    assert "Original fault text" in desc
    assert "Shop note: Customer called back" in desc


def test_status_update_with_note_appends_to_description():
    suffix = uuid4().hex[:8]
    token = _bootstrap_and_login(f"repair-stat-{suffix}", f"owner-{suffix}@repair.test", "pass123456")
    headers = {"Authorization": f"Bearer {token}"}
    watch_id = _create_watch(headers)
    job = _create_repair_job(headers, watch_id)
    job_id = job["id"]

    st = client.post(
        f"/v1/repair-jobs/{job_id}/status",
        headers=headers,
        json={"status": "awaiting_go_ahead", "note": "Quote emailed"},
    )
    assert st.status_code == 200
    desc = st.json()["description"]
    assert "Shop note: Quote emailed" in (desc or "")
