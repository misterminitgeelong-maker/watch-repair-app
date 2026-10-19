"""Dedupe for unauthenticated lead creators (website leads, key enquiries, pool intake).

The authenticated idempotency middleware (``idempotency.py``) keys on a tenant taken from
a Bearer token, so it never applies to public forms. Those get the same guarantee here:

* A client ``Idempotency-Key`` header scopes to the HQ (``k:<parent>:<sha>``): the same key
  always maps to the original record.
* With no header, a fingerprint of the normalised payload (phone digits, lower-cased email,
  trimmed strings) identifies the same submission inside ``DEDUPE_WINDOW``.

The ref is stored in a unique column on the created row, so two truly concurrent
submissions cannot both insert: the loser gets an IntegrityError and returns the winner.
"""
from __future__ import annotations

import hashlib
import json
from datetime import datetime, timedelta, timezone
from typing import Any, Type
from uuid import UUID

from sqlmodel import Session, col, select

from .phone_utils import normalize_phone

IDEMPOTENCY_HEADER = "Idempotency-Key"
DEDUPE_WINDOW = timedelta(minutes=10)
_BUCKET_SECONDS = int(DEDUPE_WINDOW.total_seconds())


def _norm_value(key: str, value: Any) -> Any:
    if isinstance(value, str):
        v = value.strip()
        if key in ("phone", "customer_phone"):
            return normalize_phone(v) or v
        if key in ("email", "customer_email"):
            return v.lower()
        return " ".join(v.lower().split())
    return value


def payload_fingerprint(payload: dict[str, Any], *, ignore: tuple[str, ...] = ("website",)) -> str:
    canon = {k: _norm_value(k, v) for k, v in payload.items() if k not in ignore and v not in (None, "")}
    return hashlib.sha256(json.dumps(canon, sort_keys=True, default=str).encode()).hexdigest()[:40]


def make_ref(scope: UUID | str | None, idempotency_key: str | None, payload: dict[str, Any]) -> tuple[str, bool]:
    """Return ``(ref, is_client_key)``.

    Fingerprint refs end in a window bucket so a legitimate repeat after the window is a
    new submission; ``find_existing`` also checks the neighbouring-bucket case by prefix.
    """
    scope_s = str(scope) if scope else "-"
    key = (idempotency_key or "").strip()
    if key:
        return f"k:{scope_s}:{hashlib.sha256(key.encode()).hexdigest()[:40]}", True
    bucket = int(datetime.now(timezone.utc).timestamp() // _BUCKET_SECONDS)
    return f"f:{scope_s}:{payload_fingerprint(payload)}:{bucket}", False


def find_existing(session: Session, model: Type, ref: str, *, is_client_key: bool):
    """The original row for this submission, or None."""
    ref_col = model.external_ref
    if is_client_key:
        return session.exec(select(model).where(ref_col == ref)).first()
    prefix = ref.rsplit(":", 1)[0] + ":"
    cutoff = datetime.now(timezone.utc) - DEDUPE_WINDOW
    # created_at is naive-UTC on SQLite and aware on Postgres; compare naive-safe.
    rows = session.exec(
        select(model).where(col(ref_col).like(prefix + "%")).order_by(col(model.created_at).desc())
    ).all()
    for row in rows:
        created = row.created_at
        if created.tzinfo is None:
            created = created.replace(tzinfo=timezone.utc)
        if created >= cutoff:
            return row
    return None
