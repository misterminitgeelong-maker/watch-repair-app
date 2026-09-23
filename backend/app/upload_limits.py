"""Bounded reads for uploaded files and request bodies.

``await upload.read()`` pulls a whole file into memory before anyone checks its
size, so a public form could be made to allocate as much as the client sends.
Two layers stop that:

* ``RequestBodyLimitMiddleware`` refuses a request body over
  ``max_request_body_bytes`` — up front from ``Content-Length`` when it's
  declared, otherwise by counting bytes as they stream in — before multipart
  parsing spools any of it.
* ``read_upload_capped`` reads a single file in chunks and stops as soon as it
  passes that file's limit, so at most ``max_bytes + chunk`` is ever held.
"""
from __future__ import annotations

import json

from fastapi import HTTPException, UploadFile

_CHUNK = 64 * 1024


def _too_large(max_bytes: int, what: str, detail: str | None = None) -> HTTPException:
    if detail:
        return HTTPException(status_code=413, detail=detail)
    mb = max_bytes / (1024 * 1024)
    limit = f"{mb:g} MB" if mb >= 1 else f"{max_bytes // 1024} KB"
    return HTTPException(status_code=413, detail=f"{what} exceeds maximum size of {limit}")


async def read_upload_capped(upload: UploadFile, max_bytes: int, *, what: str = "File", detail: str | None = None) -> bytes:
    """Read ``upload`` in chunks, raising 413 once it exceeds ``max_bytes``."""
    buf = bytearray()
    while True:
        chunk = await upload.read(_CHUNK)
        if not chunk:
            break
        buf.extend(chunk)
        if len(buf) > max_bytes:
            raise _too_large(max_bytes, what, detail)
    return bytes(buf)


def read_upload_capped_sync(upload: UploadFile, max_bytes: int, *, what: str = "File", detail: str | None = None) -> bytes:
    """Sync-route variant of ``read_upload_capped`` (reads ``upload.file``)."""
    buf = bytearray()
    while True:
        chunk = upload.file.read(_CHUNK)
        if not chunk:
            break
        buf.extend(chunk)
        if len(buf) > max_bytes:
            raise _too_large(max_bytes, what, detail)
    return bytes(buf)


class RequestBodyLimitMiddleware:
    """Pure ASGI middleware: reject request bodies larger than ``max_bytes`` with 413."""

    def __init__(self, app, max_bytes: int) -> None:
        self.app = app
        self.max_bytes = max_bytes

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http" or self.max_bytes <= 0:
            await self.app(scope, receive, send)
            return

        for name, value in scope.get("headers") or []:
            if name == b"content-length":
                try:
                    declared = int(value)
                except ValueError:
                    declared = 0
                if declared > self.max_bytes:
                    await self._reject(send)
                    return
                break

        received = 0
        exceeded = False
        response_started = False

        async def counting_receive():
            nonlocal received, exceeded
            if exceeded:
                return {"type": "http.disconnect"}
            message = await receive()
            if message["type"] == "http.request":
                received += len(message.get("body", b""))
                if received > self.max_bytes:
                    # Stop feeding the app: to it the client has gone away, so
                    # nothing more is buffered or parsed. We answer 413 below.
                    exceeded = True
                    return {"type": "http.disconnect"}
            return message

        async def guarded_send(message):
            nonlocal response_started
            if exceeded:
                return  # whatever the app says about a truncated body is moot
            if message["type"] == "http.response.start":
                response_started = True
            await send(message)

        try:
            await self.app(scope, counting_receive, guarded_send)
        except Exception:
            if not exceeded:
                raise
        if exceeded and not response_started:
            await self._reject(send)

    async def _reject(self, send) -> None:
        body = json.dumps({"detail": "Request body is too large"}).encode()
        await send(
            {
                "type": "http.response.start",
                "status": 413,
                "headers": [(b"content-type", b"application/json"), (b"content-length", str(len(body)).encode())],
            }
        )
        await send({"type": "http.response.body", "body": body})
