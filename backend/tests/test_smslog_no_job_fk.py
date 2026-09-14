"""The SMS audit row must be writable before its job exists, on every backend.

``sms._begin_sms_log`` records the attempt in its own transaction before calling
the provider, so the row survives a caller rollback. That independent commit
cannot see the caller's uncommitted job, so a foreign key from smslog to the job
tables makes every send fail on a database that enforces foreign keys.

This regression test forces SQLite to enforce foreign keys for its duration.
Without that, SQLite silently permits the orphan write and the suite would stay
green while production (Postgres) raised IntegrityError on every SMS — exactly
how this shipped in the first place.
"""
import uuid

import pytest
from sqlalchemy import event, inspect
from sqlmodel import Session, select

from app.database import engine
from app.models import SmsLog, Tenant


@pytest.fixture
def enforce_sqlite_foreign_keys():
    """Turn on SQLite FK enforcement so this test means the same thing on both backends."""
    if engine.dialect.name != "sqlite":
        yield
        return

    def _fk_pragma_on_connect(dbapi_connection, _connection_record):
        dbapi_connection.execute("PRAGMA foreign_keys=ON")

    event.listen(engine, "connect", _fk_pragma_on_connect)
    engine.dispose()  # force fresh connections that carry the pragma
    try:
        yield
    finally:
        event.remove(engine, "connect", _fk_pragma_on_connect)
        engine.dispose()


def test_smslog_has_no_foreign_keys_to_job_tables():
    """Guard the schema itself, so a future model edit cannot quietly reintroduce them."""
    fk_columns = {
        column
        for fk in inspect(engine).get_foreign_keys("smslog")
        for column in (fk.get("constrained_columns") or [])
    }
    assert "repair_job_id" not in fk_columns
    assert "shoe_repair_job_id" not in fk_columns
    assert "auto_key_job_id" not in fk_columns
    # tenant_id keeps its foreign key: a tenant always exists before a send.
    assert "tenant_id" in fk_columns


def test_sms_log_row_can_reference_an_uncommitted_job(enforce_sqlite_foreign_keys):
    """The log-then-send write must succeed while the job is still uncommitted."""
    with Session(engine) as setup:
        tenant = Tenant(name="FK Probe", slug=f"fk-probe-{uuid.uuid4().hex[:8]}")
        setup.add(tenant)
        setup.commit()
        setup.refresh(tenant)
        tenant_id = tenant.id

    # A job id the database has never seen — the same shape as a job the caller
    # has created but not yet committed when the provider call is logged.
    unseen_job_id = uuid.uuid4()

    with Session(engine) as log_session:
        log_session.add(
            SmsLog(
                tenant_id=tenant_id,
                repair_job_id=unseen_job_id,
                to_phone="+61400000000",
                body="quote ready",
                event="quote_sent",
                status="sent",
            )
        )
        log_session.commit()  # raised IntegrityError before the FKs were dropped

    with Session(engine) as check:
        rows = check.exec(
            select(SmsLog).where(SmsLog.repair_job_id == unseen_job_id)
        ).all()
        assert len(rows) == 1
        assert rows[0].event == "quote_sent"
