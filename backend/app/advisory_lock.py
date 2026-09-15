"""Cross-process mutual exclusion for background sweeps.

The recurring sweeps in main.py run as threads inside the single web process, so
today nothing can run one twice. That stops being true the moment the workers are
extracted to their own service (batch 5, item 5.1) — two instances would each pick
up the same due rows and send the same SMS or email twice.

Postgres advisory locks are the right primitive here: session-scoped, released
automatically if the holder dies, and needing no table of their own. On SQLite
(tests, local dev) there is only ever one process, so this is a no-op.
"""
from __future__ import annotations

import hashlib
import logging
from contextlib import contextmanager
from typing import Iterator

from sqlalchemy import text
from sqlmodel import Session

from .database import engine

logger = logging.getLogger(__name__)


def _lock_key(name: str) -> int:
    """Stable signed 64-bit key for a sweep name.

    pg_try_advisory_lock takes a bigint, so fold the digest down and re-centre it
    into the signed range rather than letting Postgres reject an out-of-range value.
    """
    digest = hashlib.sha256(name.encode("utf-8")).digest()
    unsigned = int.from_bytes(digest[:8], "big", signed=False)
    return unsigned - (1 << 63)


@contextmanager
def sweep_lock(name: str) -> Iterator[bool]:
    """Hold an exclusive lock for ``name`` for the duration of the block.

    Yields True when this process holds the lock and should do the work, False
    when another instance already holds it and this run should be skipped.

    Uses its own connection so the lock's lifetime is the block, independent of
    whatever session the sweep itself uses.
    """
    if engine.dialect.name != "postgresql":
        yield True
        return

    key = _lock_key(name)
    with Session(engine) as lock_session:
        acquired = bool(
            lock_session.exec(text("SELECT pg_try_advisory_lock(:k)").bindparams(k=key)).one()[0]
        )
        if not acquired:
            logger.info("Sweep %s skipped: another instance holds the lock.", name)
            yield False
            return
        try:
            yield True
        finally:
            try:
                lock_session.exec(text("SELECT pg_advisory_unlock(:k)").bindparams(k=key)).one()
            except Exception:
                # Losing the connection releases the lock anyway; never let unlock
                # failure mask an error raised inside the block.
                logger.warning("Sweep %s: advisory unlock failed.", name, exc_info=True)
