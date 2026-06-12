"""Verify the alembic chain builds a fresh database that matches the models.

Builds two throwaway SQLite databases:
  A) `alembic upgrade head` from empty
  B) `SQLModel.metadata.create_all` from the current models

then diffs tables and columns in both directions. Exits non-zero on drift,
so CI fails whenever someone adds a model field without a migration (or a
migration the models don't know about).

Run from backend/:  python scripts/check_migrations.py
"""

from __future__ import annotations

import os
import subprocess
import sys
import tempfile
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parents[1]

# Tables that intentionally exist on one side only.
IGNORE_TABLES = {"alembic_version"}


def build_from_migrations(db_path: Path) -> None:
    env = os.environ.copy()
    env["DATABASE_URL"] = f"sqlite:///{db_path.as_posix()}"
    env.setdefault("APP_ENV", "test")
    env.setdefault("JWT_SECRET", "check-migrations-secret")
    result = subprocess.run(
        [sys.executable, "-m", "alembic", "upgrade", "head"],
        cwd=BACKEND_DIR,
        env=env,
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        print(result.stdout[-4000:])
        print(result.stderr[-4000:])
        raise SystemExit("FAIL: alembic upgrade head failed on an empty database")


def build_from_models(db_path: Path) -> None:
    os.environ["DATABASE_URL"] = f"sqlite:///{db_path.as_posix()}"
    os.environ.setdefault("APP_ENV", "test")
    os.environ.setdefault("JWT_SECRET", "check-migrations-secret")
    sys.path.insert(0, str(BACKEND_DIR))
    from sqlalchemy import create_engine
    from sqlmodel import SQLModel
    import app.models  # noqa: F401 - registers all tables on the metadata

    engine = create_engine(f"sqlite:///{db_path.as_posix()}")
    SQLModel.metadata.create_all(engine)
    engine.dispose()


def schema_map(db_path: Path) -> dict[str, set[str]]:
    from sqlalchemy import create_engine, inspect

    engine = create_engine(f"sqlite:///{db_path.as_posix()}")
    insp = inspect(engine)
    out: dict[str, set[str]] = {}
    for table in insp.get_table_names():
        if table in IGNORE_TABLES:
            continue
        out[table] = {c["name"] for c in insp.get_columns(table)}
    engine.dispose()
    return out


def main() -> int:
    with tempfile.TemporaryDirectory() as tmp:
        mig_db = Path(tmp) / "from_migrations.db"
        mdl_db = Path(tmp) / "from_models.db"

        print("Building database from migrations (alembic upgrade head)...")
        build_from_migrations(mig_db)
        print("Building database from models (create_all)...")
        build_from_models(mdl_db)

        mig = schema_map(mig_db)
        mdl = schema_map(mdl_db)

    problems: list[str] = []

    for table in sorted(set(mdl) - set(mig)):
        problems.append(f"table missing from migrations: {table}")
    for table in sorted(set(mig) - set(mdl)):
        problems.append(f"table in migrations but not in models: {table}")
    for table in sorted(set(mdl) & set(mig)):
        missing_cols = mdl[table] - mig[table]
        extra_cols = mig[table] - mdl[table]
        for col in sorted(missing_cols):
            problems.append(f"column missing from migrations: {table}.{col}")
        for col in sorted(extra_cols):
            problems.append(f"column in migrations but not in models: {table}.{col}")

    if problems:
        print(f"\nFAIL: {len(problems)} schema difference(s) between migrations and models:")
        for p in problems:
            print(f"  - {p}")
        return 1

    print(f"\nOK: migrations and models agree ({len(mdl)} tables).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
