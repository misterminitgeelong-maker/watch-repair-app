"""The Idempotency-Key must be claimed before the mutation runs, not after.

Recording the key after the response only prevents a duplicate row — both
requests still execute. This is reachable in production: the axios client times
out at 20 seconds, so a slow mutation aborts client-side, is queued by the
offline interceptor, and replays with the same key while the original is still
running on the server.
"""
import threading
import time
import uuid

import pytest
from fastapi import APIRouter
from fastapi.testclient import TestClient
from sqlmodel import Session, select

from app.database import engine
from app.idempotency import STATE_COMPLETED, STATE_IN_PROGRESS
from app.main import app
from app.models import MutationIdempotencyKey

# Counts how many times the route body actually executed.
_executions: list[str] = []

_probe = APIRouter()


@_probe.post("/v1/_test/idempotency-probe")
def _probe_route(delay_ms: int = 0):
    _executions.append("ran")
    if delay_ms:
        time.sleep(delay_ms / 1000)
    return {"ok": True, "executions": len(_executions)}


@_probe.post("/v1/_test/idempotency-boom")
def _boom_route():
    _executions.append("ran")
    raise RuntimeError("route exploded after doing its work")


app.include_router(_probe)


@pytest.fixture(autouse=True)
def _reset():
    _executions.clear()
    yield
    _executions.clear()


def _headers(auth_headers: dict[str, str], key: str) -> dict[str, str]:
    return {**auth_headers, "Idempotency-Key": key}


def test_replay_returns_cached_response_without_re_executing(client: TestClient, auth_headers):
    key = f"probe-{uuid.uuid4().hex}"
    first = client.post("/v1/_test/idempotency-probe", headers=_headers(auth_headers, key))
    assert first.status_code == 200
    assert len(_executions) == 1

    second = client.post("/v1/_test/idempotency-probe", headers=_headers(auth_headers, key))
    assert second.status_code == 200
    assert second.json() == first.json()
    assert len(_executions) == 1, "replay re-executed the mutation"


def test_concurrent_same_key_executes_once(client: TestClient, auth_headers):
    """The regression: before reserving up front, both requests ran the body."""
    key = f"race-{uuid.uuid4().hex}"
    statuses: list[int] = []
    lock = threading.Lock()

    def fire():
        r = client.post(
            "/v1/_test/idempotency-probe?delay_ms=300", headers=_headers(auth_headers, key)
        )
        with lock:
            statuses.append(r.status_code)

    threads = [threading.Thread(target=fire) for _ in range(2)]
    for t in threads:
        t.start()
    for t in threads:
        t.join(timeout=15)

    assert len(_executions) == 1, f"mutation ran {len(_executions)} times for one key"
    assert sorted(statuses) == [200, 409], f"expected one success and one in-progress, got {statuses}"


def test_failed_response_is_recorded_so_replay_does_not_re_execute(client: TestClient, auth_headers):
    """A route that commits and then raises is exactly what the key exists for."""
    key = f"boom-{uuid.uuid4().hex}"
    with pytest.raises(RuntimeError):
        client.post("/v1/_test/idempotency-boom", headers=_headers(auth_headers, key))
    assert len(_executions) == 1

    second = client.post("/v1/_test/idempotency-boom", headers=_headers(auth_headers, key))
    assert second.status_code == 500
    assert len(_executions) == 1, "replay re-ran a mutation that had already committed"

    with Session(engine) as session:
        row = session.exec(
            select(MutationIdempotencyKey).where(MutationIdempotencyKey.key == key)
        ).first()
        assert row is not None
        assert row.state == STATE_COMPLETED
        assert row.status_code == 500


def test_same_key_different_body_is_rejected(client: TestClient, auth_headers):
    key = f"mismatch-{uuid.uuid4().hex}"
    first = client.post(
        "/v1/_test/idempotency-probe", headers=_headers(auth_headers, key), json={"a": 1}
    )
    assert first.status_code == 200
    second = client.post(
        "/v1/_test/idempotency-probe", headers=_headers(auth_headers, key), json={"a": 2}
    )
    assert second.status_code == 409
    assert "different request" in second.json()["detail"]
    assert len(_executions) == 1


def test_reservation_is_written_before_the_response_is_known(client: TestClient, auth_headers):
    """Guard the ordering directly: a completed row must carry completed_at."""
    key = f"state-{uuid.uuid4().hex}"
    client.post("/v1/_test/idempotency-probe", headers=_headers(auth_headers, key))
    with Session(engine) as session:
        row = session.exec(
            select(MutationIdempotencyKey).where(MutationIdempotencyKey.key == key)
        ).first()
        assert row is not None
        assert row.state == STATE_COMPLETED
        assert row.completed_at is not None
        assert row.created_at is not None
        assert row.state != STATE_IN_PROGRESS
