"""Serialize migrations and verified asset publishing across release containers."""
from contextlib import contextmanager
import subprocess
import sys
import time

from sqlalchemy import text
from .database import engine
from .frontend_assets import publish_build

LOCK_ID = 717391240


@contextmanager
def release_lock(connection, timeout=300):
    locked = False
    try:
        deadline = time.monotonic() + timeout
        while not locked:
            locked = bool(connection.execute(text("SELECT pg_try_advisory_lock(:key)"),
                                             {"key": LOCK_ID}).scalar())
            connection.commit()
            if not locked:
                if time.monotonic() >= deadline:
                    raise RuntimeError("Another release is publishing; deployment lock timed out")
                time.sleep(1)
        yield
    finally:
        if locked:
            connection.execute(text("SELECT pg_advisory_unlock(:key)"), {"key": LOCK_ID})
            connection.commit()


def run_release():
    subprocess.run([sys.executable, "-m", "alembic", "upgrade", "head"], check=True)
    count = publish_build()
    print(f"Frontend retention ready: {count} current assets archived and verified", flush=True)


def main():
    if engine.dialect.name == "postgresql":
        with engine.connect() as connection, release_lock(connection):
            run_release()
    else:
        run_release()


if __name__ == "__main__":
    main()
