"""HTTP Idempotency-Key handling for offline-queue replays."""
from __future__ import annotations

import hashlib
import logging
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


def _lookup(tenant_id: UUID, key: str) -> MutationIdempotencyKey | None:
    with Session(engine) as session:
        return session.exec(
            select(MutationIdempotencyKey)
            .where(MutationIdempotencyKey.tenant_id == tenant_id)
            .where(MutationIdempotencyKey.key == key)
        ).first()


def _store(
    *,
    tenant_id: UUID,
    key: str,
    method: str,
    path: str,
    request_hash: str,
    status_code: int,
    response_body: str,
) -> MutationIdempotencyKey | None:
    with Session(engine) as session:
        session.add(
            MutationIdempotencyKey(
                tenant_id=tenant_id,
                key=key,
                method=method,
                path=path,
                request_hash=request_hash,
                status_code=status_code,
                response_body=response_body[:_MAX_STORED_BODY],
            )
        )
        try:
            session.commit()
        except IntegrityError:
            session.rollback()
            return _lookup(tenant_id, key)
    return _lookup(tenant_id, key)


def _replay_body(request: Request, body: bytes) -> None:
    """BaseHTTPMiddleware consumes the body; restore it for the route."""

    async def receive() -> Message:
        return {"type": "http.request", "body": body, "more_body": False}

    request._receive = receive  # type: ignore[method-assign]
    request._stream_consumed = False
    request._body = body


def _cached_response(row: MutationIdempotencyKey) -> Response:
    return Response(
        content=row.response_body,
        status_code=row.status_code,
        media_type="application/json",
    )


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

        existing = _lookup(tenant_id, key)
        if existing is not None:
            if existing.method != method or existing.path != path or existing.request_hash != request_hash:
                return JSONResponse(
                    {"detail": "Idempotency-Key reused with a different request"},
                    status_code=409,
                )
            return _cached_response(existing)

        response = await call_next(request)
        if not (200 <= response.status_code < 300):
            return response

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
        stored = _store(
            tenant_id=tenant_id,
            key=key,
            method=method,
            path=path,
            request_hash=request_hash,
            status_code=response.status_code,
            response_body=text,
        )
        if stored is not None and stored.request_hash != request_hash:
            return JSONResponse(
                {"detail": "Idempotency-Key reused with a different request"},
                status_code=409,
            )
        return new_response
