import pytest
from app import predeploy


class Connection:
    def __init__(self, results):
        self.results = iter(results)
        self.calls = []

    def execute(self, query, values):
        self.calls.append(str(query))
        return self

    def scalar(self):
        return next(self.results)

    def commit(self):
        pass


def test_release_waits_for_lock_and_releases_on_failure(monkeypatch):
    connection = Connection([False, True])
    monkeypatch.setattr(predeploy.time, "sleep", lambda _: None)
    with pytest.raises(ValueError):
        with predeploy.release_lock(connection):
            raise ValueError("publisher failed")
    assert len(connection.calls) == 3
    assert "pg_advisory_unlock" in connection.calls[-1]


def test_release_lock_timeout_never_runs_or_unlocks_another_release():
    connection = Connection([False])
    with pytest.raises(RuntimeError, match="lock timed out"):
        with predeploy.release_lock(connection, timeout=0):
            pytest.fail("Release must not run without its lock")
    assert len(connection.calls) == 1


def test_failed_migration_never_publishes_assets(monkeypatch):
    def failed(*args, **kwargs):
        raise predeploy.subprocess.CalledProcessError(1, args[0])
    monkeypatch.setattr(predeploy.subprocess, "run", failed)
    monkeypatch.setattr(predeploy, "publish_build", lambda: pytest.fail("Migration failed"))
    with pytest.raises(predeploy.subprocess.CalledProcessError):
        predeploy.run_release()


@pytest.mark.skipif(predeploy.engine.dialect.name != "postgresql", reason="Requires PostgreSQL session locks")
def test_postgres_release_lock_excludes_second_connection():
    with predeploy.engine.connect() as first, predeploy.engine.connect() as second:
        with predeploy.release_lock(first):
            acquired = second.execute(predeploy.text("SELECT pg_try_advisory_lock(:key)"),
                                      {"key": predeploy.LOCK_ID}).scalar()
            second.commit()
            if acquired:
                second.execute(predeploy.text("SELECT pg_advisory_unlock(:key)"), {"key": predeploy.LOCK_ID})
                second.commit()
            assert acquired is False
        with predeploy.release_lock(second, timeout=0):
            pass
