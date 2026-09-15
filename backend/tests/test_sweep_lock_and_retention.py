"""Background sweeps must not double-run, and the new tables must not grow forever.

Both of these are latent today — there is one replica, so nothing can run a sweep
twice, and the tables are young. The lock matters the moment batch 5 extracts the
workers to their own service; the retention matters continuously.
"""
from datetime import datetime, timedelta, timezone
from uuid import uuid4

from sqlmodel import Session, select

from app.advisory_lock import _lock_key, sweep_lock
from app.database import engine
from app.idempotency import STATE_COMPLETED, STATE_IN_PROGRESS
from app.models import EmailLog, MutationIdempotencyKey, Tenant
from app.services.idempotency_retention import (
    purge_expired_idempotency_keys,
    purge_stale_email_payloads,
)


def _tenant(session: Session) -> Tenant:
    tenant = Tenant(name="Retention", slug=f"retention-{uuid4().hex[:8]}")
    session.add(tenant)
    session.commit()
    session.refresh(tenant)
    return tenant


def test_lock_key_stays_in_postgres_bigint_range():
    """pg_try_advisory_lock takes a signed bigint; an unfolded digest overflows it."""
    for name in ("quote_reminders", "retention", "notification_redelivery", ""):
        key = _lock_key(name)
        assert -(2**63) <= key < 2**63
    assert _lock_key("a") == _lock_key("a")
    assert _lock_key("a") != _lock_key("b")


def test_sweep_lock_is_a_no_op_off_postgres():
    """Tests and local dev run one process on SQLite; the lock must not block them."""
    with sweep_lock("test-sweep") as owned:
        assert owned is True
        with sweep_lock("test-sweep") as nested:
            assert nested is True


def test_completed_idempotency_keys_are_purged_past_the_window():
    with Session(engine) as session:
        tenant = _tenant(session)
        old = MutationIdempotencyKey(
            tenant_id=tenant.id, key=f"old-{uuid4().hex}", method="POST", path="/v1/x",
            request_hash="h", state=STATE_COMPLETED, status_code=200,
            created_at=datetime.now(timezone.utc) - timedelta(days=90),
        )
        fresh = MutationIdempotencyKey(
            tenant_id=tenant.id, key=f"fresh-{uuid4().hex}", method="POST", path="/v1/x",
            request_hash="h", state=STATE_COMPLETED, status_code=200,
            created_at=datetime.now(timezone.utc),
        )
        session.add(old)
        session.add(fresh)
        session.commit()
        old_key, fresh_key = old.key, fresh.key

        purge_expired_idempotency_keys(session)

        remaining = {
            r.key for r in session.exec(select(MutationIdempotencyKey)).all()
        }
        assert old_key not in remaining
        assert fresh_key in remaining


def test_abandoned_reservations_are_cleared_so_a_key_is_not_blocked_forever():
    """A process killed mid-request leaves a reservation that would 409 every replay."""
    with Session(engine) as session:
        tenant = _tenant(session)
        stuck = MutationIdempotencyKey(
            tenant_id=tenant.id, key=f"stuck-{uuid4().hex}", method="POST", path="/v1/x",
            request_hash="h", state=STATE_IN_PROGRESS, status_code=0,
            created_at=datetime.now(timezone.utc) - timedelta(hours=3),
        )
        live = MutationIdempotencyKey(
            tenant_id=tenant.id, key=f"live-{uuid4().hex}", method="POST", path="/v1/x",
            request_hash="h", state=STATE_IN_PROGRESS, status_code=0,
            created_at=datetime.now(timezone.utc),
        )
        session.add(stuck)
        session.add(live)
        session.commit()
        stuck_key, live_key = stuck.key, live.key

        purge_expired_idempotency_keys(session)

        remaining = {r.key for r in session.exec(select(MutationIdempotencyKey)).all()}
        assert stuck_key not in remaining, "an abandoned reservation blocks that key forever"
        assert live_key in remaining, "a request still in flight must not be cleared"


def test_email_payload_is_kept_while_still_redeliverable_and_cleared_after():
    with Session(engine) as session:
        tenant = _tenant(session)
        old_ts = datetime.now(timezone.utc) - timedelta(days=365)

        redeliverable = EmailLog(
            tenant_id=tenant.id, to_email="a@example.com", event="quote_sent",
            status="failed", attempt_count=0, payload_json='{"subject":"x"}',
            created_at=old_ts,
        )
        exhausted = EmailLog(
            tenant_id=tenant.id, to_email="b@example.com", event="quote_sent",
            status="failed", attempt_count=99, payload_json='{"subject":"x"}',
            created_at=old_ts,
        )
        delivered = EmailLog(
            tenant_id=tenant.id, to_email="c@example.com", event="quote_sent",
            status="sent", attempt_count=1, payload_json='{"subject":"x"}',
            created_at=old_ts,
        )
        for row in (redeliverable, exhausted, delivered):
            session.add(row)
        session.commit()
        ids = (redeliverable.id, exhausted.id, delivered.id)

        purge_stale_email_payloads(session)
        session.expire_all()

        kept, spent, done = (session.get(EmailLog, i) for i in ids)
        assert kept.payload_json is not None, "still under the attempt cap — keep it"
        assert spent.payload_json is None, "attempts exhausted — the body is inert"
        assert done.payload_json is None, "already delivered — the body is inert"
        # The audit trail itself is never deleted, only the stored body.
        assert done.to_email == "c@example.com"
        assert done.event == "quote_sent"
