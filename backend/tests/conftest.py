"""Shared pytest fixtures for the backend test suite.

Existing test modules predate this file and each set up their own sqlite DB,
``TestClient`` and ``_bootstrap_and_login`` / ``_create_customer`` helpers. This
conftest centralises that boilerplate so new tests can reuse it via fixtures,
while leaving the older modules working unchanged.

Database selection
------------------
``DATABASE_URL`` is honoured when set (CI points it at Postgres); otherwise a
throwaway sqlite file is used so local iteration needs no services. It must be
set before ``app.database`` is imported, and pytest loads conftest before any
test module, so the engine every module ends up using is the one chosen here.

Schema bootstrap
----------------
``TEST_SCHEMA_BOOTSTRAP`` picks how the schema is built at session start:

* ``alembic``    -- ``alembic upgrade head`` in a subprocess, exactly as the
                    Railway pre-deploy step does. Default for Postgres.
* ``create_all`` -- ``SQLModel.metadata.create_all``. Default for sqlite
                    (fast local path).

Isolation
---------
Every test module starts from an empty database: an autouse module-scoped
fixture truncates every model table (``DELETE FROM`` on sqlite) before the
module's first test, keeping only migration-seeded reference rows
(``_REFERENCE_TABLES``). That restores the "one throwaway DB per module"
semantics the older modules were written against, on both backends.

On Postgres the whole ``public`` schema is dropped and rebuilt at session
start, so the same database can be reused across pytest invocations. As a
guard against pointing the suite at a real database, non-sqlite database
names must contain ``test``.
"""
import os
import subprocess
import sys
from pathlib import Path
from urllib.parse import urlsplit
from uuid import uuid4

# Fresh sqlite file per test session; must be set before importing app.database.
_TEST_DB = Path(__file__).with_name(f"conftest_{uuid4().hex}.db")
os.environ.setdefault("DATABASE_URL", f"sqlite:///{_TEST_DB.as_posix()}")
os.environ.setdefault("JWT_SECRET", "test-secret-not-for-production")
os.environ.setdefault("APP_ENV", "test")

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import event, text
from sqlmodel import SQLModel

from app.database import create_db_and_tables, database_url, engine
from app.main import app

BACKEND_DIR = Path(__file__).resolve().parents[1]
IS_SQLITE = database_url.startswith("sqlite")

if not IS_SQLITE:

    @event.listens_for(engine, "connect")
    def _pin_session_timezone_to_utc(dbapi_connection, _record):
        """The app stores naive-UTC timestamps but writes tz-aware values into them;
        Postgres converts those through the session TimeZone. Production (Railway) and
        CI (postgres:16-alpine) run UTC, so pin it rather than inherit the developer's
        server default -- otherwise every expiry comparison is off by the local offset."""
        cursor = dbapi_connection.cursor()
        cursor.execute("SET TIME ZONE 'UTC'")
        cursor.close()


SCHEMA_BOOTSTRAP = os.environ.get("TEST_SCHEMA_BOOTSTRAP") or ("create_all" if IS_SQLITE else "alembic")
if SCHEMA_BOOTSTRAP not in {"alembic", "create_all"}:
    raise RuntimeError(f"TEST_SCHEMA_BOOTSTRAP must be 'alembic' or 'create_all', got {SCHEMA_BOOTSTRAP!r}")


def _redacted_database_url() -> str:
    parts = urlsplit(database_url)
    if parts.password:
        netloc = parts.netloc.replace(f":{parts.password}@", ":***@", 1)
        return parts._replace(netloc=netloc).geturl()
    return database_url


def _guard_against_real_database() -> None:
    if IS_SQLITE:
        return
    db_name = urlsplit(database_url).path.lstrip("/")
    if "test" not in db_name.lower():
        raise RuntimeError(
            "Refusing to run the test suite against a database whose name does not contain "
            f"'test' (got {db_name!r}): the suite drops and truncates every table. "
            "Point DATABASE_URL at a dedicated test database."
        )


def _reset_postgres_schema() -> None:
    """Drop everything (tables, alembic_version, ...) so the run starts empty."""
    with engine.begin() as conn:
        conn.execute(text("DROP SCHEMA public CASCADE"))
        conn.execute(text("CREATE SCHEMA public"))


def _alembic_upgrade_head() -> None:
    result = subprocess.run(
        [sys.executable, "-m", "alembic", "upgrade", "head"],
        cwd=BACKEND_DIR,
        env=os.environ.copy(),
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        raise RuntimeError(
            "alembic upgrade head failed while bootstrapping the test schema:\n"
            f"{result.stdout[-4000:]}\n{result.stderr[-4000:]}"
        )


def _bootstrap_schema() -> None:
    if SCHEMA_BOOTSTRAP == "alembic":
        _alembic_upgrade_head()
    else:
        create_db_and_tables()


# Static reference rows seeded by migrations that application code hard-codes
# ids for (loyalty_utils uses tier_id=1). Never wiped between modules. Catalogue
# tables such as oem_key_pricing are content, not reference data: tests seed
# their own rows and assert on exactly those, so they are wiped like the rest.
_REFERENCE_TABLES = {"loyaltytier"}

# Order is irrelevant: Postgres truncates with CASCADE, and sqlite never enforces
# foreign keys here (no PRAGMA foreign_keys). Not sorted_tables -- the
# autokeyjob/intakejob/shopmobilebookingrequest FK cycle makes it warn.
_MODEL_TABLES = sorted(set(SQLModel.metadata.tables) - _REFERENCE_TABLES)


def _wipe_all_tables() -> None:
    quoted = [f'"{name}"' for name in _MODEL_TABLES]
    with engine.begin() as conn:
        if IS_SQLITE:
            for name in quoted:
                conn.execute(text(f"DELETE FROM {name}"))
            has_sequence_table = conn.execute(
                text("SELECT 1 FROM sqlite_master WHERE type = 'table' AND name = 'sqlite_sequence'")
            ).first()
            if has_sequence_table:
                conn.execute(text("DELETE FROM sqlite_sequence"))
        else:
            conn.execute(text(f"TRUNCATE TABLE {', '.join(quoted)} RESTART IDENTITY CASCADE"))


def pytest_report_header(config):
    # The dialect line is the one to check in CI: GitHub masks the URL's
    # credential prefix (scheme included), the dialect name cannot be masked.
    return [
        f"database dialect: {engine.dialect.name} ({engine.dialect.driver})",
        f"database: {_redacted_database_url()}",
        f"schema bootstrap: {SCHEMA_BOOTSTRAP}",
    ]


def pytest_sessionstart(session):
    """Build the schema before collection: many modules call create_db_and_tables() at import."""
    _guard_against_real_database()
    if not IS_SQLITE:
        _reset_postgres_schema()
    _bootstrap_schema()


def pytest_sessionfinish(session, exitstatus):
    """Release pooled connections, then drop the throwaway sqlite file.

    A hook rather than a session fixture so it also runs for --collect-only
    (module imports create the sqlite file during collection).
    """
    engine.dispose()
    if IS_SQLITE:
        try:
            _TEST_DB.unlink(missing_ok=True)
        except OSError:
            pass


@pytest.fixture(scope="module", autouse=True)
def _isolate_module_state():
    """Each module starts from an empty database, as if it had its own throwaway DB."""
    _wipe_all_tables()
    yield


@pytest.fixture(scope="session")
def client() -> TestClient:
    """Shared FastAPI TestClient for the session."""
    return TestClient(app)


@pytest.fixture
def bootstrap_and_login(client: TestClient):
    """Return a helper that bootstraps a tenant and returns its owner access token.

    Slug/email are auto-generated to be unique when not supplied, so tests can be
    called repeatedly within a shared database without collisions.
    """

    def _bootstrap(
        tenant_slug: str | None = None,
        email: str | None = None,
        password: str = "supersecret123",
        owner_full_name: str = "Main Owner",
    ) -> str:
        suffix = uuid4().hex[:8]
        tenant_slug = tenant_slug or f"tenant-{suffix}"
        email = email or f"owner-{suffix}@example.test"

        bootstrap_res = client.post(
            "/v1/auth/bootstrap",
            json={
                "tenant_name": f"Tenant {tenant_slug}",
                "tenant_slug": tenant_slug,
                "owner_email": email,
                "owner_full_name": owner_full_name,
                "owner_password": password,
            },
        )
        assert bootstrap_res.status_code == 200, bootstrap_res.text

        login_res = client.post(
            "/v1/auth/login",
            json={"tenant_slug": tenant_slug, "email": email, "password": password},
        )
        assert login_res.status_code == 200, login_res.text
        return login_res.json()["access_token"]

    return _bootstrap


@pytest.fixture
def auth_headers(bootstrap_and_login) -> dict[str, str]:
    """Authorization headers for a freshly bootstrapped tenant owner."""
    token = bootstrap_and_login()
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
def make_customer(client: TestClient):
    """Return a helper that creates a customer and returns its id."""

    def _make(
        headers: dict[str, str],
        full_name: str = "Alice Watch Owner",
        email: str = "alice@example.com",
        **extra,
    ) -> str:
        res = client.post(
            "/v1/customers",
            headers=headers,
            json={"full_name": full_name, "email": email, **extra},
        )
        assert res.status_code == 201, res.text
        return res.json()["id"]

    return _make


@pytest.fixture
def make_watch(client: TestClient):
    """Return a helper that creates a watch for a customer and returns its id."""

    def _make(
        headers: dict[str, str],
        customer_id: str,
        brand: str = "Omega",
        model: str = "Seamaster",
        **extra,
    ) -> str:
        res = client.post(
            "/v1/watches",
            headers=headers,
            json={"customer_id": customer_id, "brand": brand, "model": model, **extra},
        )
        assert res.status_code == 201, res.text
        return res.json()["id"]

    return _make
