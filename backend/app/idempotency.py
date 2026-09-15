"""HTTP Idempotency-Key handling for offline-queue replays.

The key is **reserved before the mutation runs**, not recorded after it. That
ordering is the whole mechanism: the unique constraint on (tenant_id, key) is
what stops a second request executing, so it has to be taken while the first
request is still in flight.

Recording afterwards only prevents a duplicate *row*; both requests still run.
That is reachable in this app — the axios client times out at 20 seconds, so a
slow mutation aborts client-side, gets queued by the offline interceptor, and is
replayed with the same key while the original is still executing on the server.

Every completed response is recorded, not just 2xx. "The mutation committed but
the caller never saw the response" is the exact failure this exists to cover,
and a 500 after commit is the clearest example of it.
"""
from __future__ import annotations

import hashlib
import logging
from datetime import datetime, timedelta, timezone
from uuid import UUID

from fastapi import Request
from fastapi.responses import JSONResponse, Response
from sqlalchemy.exc import IntegrityError
from sqlmodel import Session, select
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.types import ASGIApp, Message

from .database import engine
from .models import MutationIdempotencyKey
from .security import decode_access_token

logger = logging.getLogger(__name__)

IDEMPOTENCY_HEADER = "Idempotency-Key"
_MUTATING = {"POST", "PATCH", "PUT", "DELETE"}
_MAX_STORED_BODY = 64_000

STATE_IN_PROGRESS = "in_progress"
STATE_COMPLETED = "completed"

# A reservation older than this whose request never completed is treated as
# abandoned (process killed mid-request) and is cleared by the retention sweep
# in services/idempotency_retention.py rather than blocking the key forever.
IN_PROGRESS_ABANDONED_AFTER = timedelta(minutes=10)


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _tenant_id_from_request(request: Request) -> UUID | None:
    auth = request.headers.get("Authorization") or ""
    if not auth.lower().startswith("bearer "):
        return None
    token = auth.split(" ", 1)[1].strip()
    if not token:
        return None
    try:
        return decode_access_token(token).tenant_id
    except ValueError:
        return None


def _lookup(session: Session, tenant_id: UUID, key: str) -> MutationIdempotencyKey | None:
    return session.exec(
        select(MutationIdempotencyKey)
        .where(MutationIdempotencyKey.tenant_id == tenant_id)
        .where(MutationIdempotencyKey.key == key)
    ).first()


def _reserve(
    *, tenant_id: UUID, key: str, method: str, path: str, request_hash: str
) -> tuple[UUID | None, MutationIdempotencyKey | None]:
    """Claim the key before running the mutation.

    Returns ``(reservation_id, None)`` when this request won the key, or
    ``(None, existing_row)`` when someone else already holds it.
    """
    with Session(engine) as session:
        row = MutationIdempotencyKey(
            tenant_id=tenant_id,
            key=key,
            method=method,
            path=path,
            request_hash=request_hash,
            state=STATE_IN_PROGRESS,
            status_code=0,
            response_body="",
        )
        session.add(row)
        try:
            session.commit()
        except IntegrityError:
            session.rollback()
            return None, _lookup(session, tenant_id, key)
        return row.id, None


def _complete(reservation_id: UUID, *, status_code: int, response_body: str) -> None:
    with Session(engine) as session:
        row = session.get(MutationIdempotencyKey, reservation_id)
        if row is None:
            return
        row.state = STATE_COMPLETED
        row.status_code = status_code
        row.response_body = response_body[:_MAX_STORED_BODY]
        row.completed_at = _utcnow()
        session.add(row)
        session.commit()


def _replay_body(request: Request, body: bytes) -> None:
    """BaseHTTPMiddleware consumes the body; restore it for the route."""

    async def receive() -> Message:
        return {"type": "http.request", "body": body, "more_body": False}

    request._receive = receive  # type: ignore[method-assign]
    request._stream_consumed = False
    request._body = body


def _mismatch(row: MutationIdempotencyKey, method: str, path: str, request_hash: str) -> bool:
    return row.method != method or row.path != path or row.request_hash != request_hash


class MutationIdempotencyMiddleware(BaseHTTPMiddleware):
    def __init__(self, app: ASGIApp) -> None:
        super().__init__(app)

    async def dispatch(self, request: Request, call_next):
        if request.method not in _MUTATING:
            return await call_next(request)
        key = (request.headers.get(IDEMPOTENCY_HEADER) or "").strip()
        if not key or len(key) > 128:
            return await call_next(request)
        tenant_id = _tenant_id_from_request(request)
        if tenant_id is None:
            return await call_next(request)

        body = await request.body()
        _replay_body(request, body)
        request_hash = hashlib.sha256(body).hexdigest()
        path = request.url.path
        method = request.method

        reservation_id, existing = _reserve(
            tenant_id=tenant_id, key=key, method=method, path=path, request_hash=request_hash
        )

        if reservation_id is None:
            if existing is None:
                # Lost the insert race and then could not read the winner back;
                # treat as in-flight rather than executing a possible duplicate.
                return JSONResponse({"detail": "idempotent_request_in_progress"}, status_code=409)
            if _mismatch(existing, method, path, request_hash):
                return JSONResponse(
                    {"detail": "Idempotency-Key reused with a different request"},
                    status_code=409,
                )
            if existing.state == STATE_COMPLETED:
                return Response(
                    content=existing.response_body,
                    status_code=existing.status_code,
                    media_type="application/json",
                )
            # The original request is still running. Refusing here is the point:
            # executing now is exactly the duplicate this middleware prevents.
            return JSONResponse({"detail": "idempotent_request_in_progress"}, status_code=409)

        try:
            response = await call_next(request)
        except Exception:
            # The route raised, so the caller never saw a response — but the work
            # may already have committed. Record a 500 rather than releasing the
            # key, so a replay returns this instead of running the mutation again.
            _complete(
                reservation_id,
                status_code=500,
                response_body='{"detail":"Internal Server Error"}',
            )
            raise

        resp_body = getattr(response, "body", None)
        headers = dict(response.headers)
        headers.pop("content-length", None)
        if resp_body is None:
            chunks: list[bytes] = []
            async for chunk in response.body_iterator:
                chunks.append(chunk if isinstance(chunk, bytes) else chunk.encode())
            resp_body = b"".join(chunks)
        new_response = Response(
            content=resp_body,
            status_code=response.status_code,
            headers=headers,
            media_type=response.media_type,
        )

        try:
            text = resp_body.decode("utf-8") if isinstance(resp_body, (bytes, bytearray)) else str(resp_body)
        except Exception:
            text = ""
        _complete(reservation_id, status_code=response.status_code, response_body=text)
        return new_response
