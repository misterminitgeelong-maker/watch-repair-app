"""Standalone entrypoint for the background sweeps.

    python -m app.worker              # run every enabled sweep on its interval
    python -m app.worker --once       # one pass of each, then exit
    python -m app.worker --once quote_reminders retention
    python -m app.worker --list

Run this as its own service so the sweeps stop competing with HTTP requests for
the web process. The sweeps do real work — rendering and sending email, SMS,
report queries over a whole tenant — on threads inside a single-worker uvicorn
process, so a slow sweep and a slow request contend for the same GIL and the
same connection pool.

Nothing here has to be deployed for the web process to keep working. The web
process still runs the sweeps itself unless RUN_SWEEPS_IN_WEB_PROCESS=false, so
the split is: deploy this service, then flip that flag. The advisory locks mean
the overlap in between is safe rather than a window where everything fires twice.

The worker deliberately does **not** run the optional startup seed. That is
bootstrap for a deployment, not recurring work, and running it from two places
is how you get two seed attempts racing on boot.
"""
from __future__ import annotations

import argparse
import logging
import signal
import sys
import threading

from sqlalchemy import text
from sqlalchemy.exc import OperationalError

from .config import settings, validate_runtime_config
from .database import engine
from .sweeps import Sweep, all_sweeps, enabled_sweeps, run_sweep_once, start_sweep_threads

logger = logging.getLogger("mainspring.worker")


def _configure_logging() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
    )


def _check_schema() -> None:
    """Fail fast rather than logging one exception per sweep per interval."""
    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1 FROM alembic_version LIMIT 1"))
    except OperationalError as exc:
        raise RuntimeError(
            "Database schema is missing or out of date. Run 'alembic upgrade head' "
            "in backend/ before starting the worker."
        ) from exc


def _select(names: list[str]) -> list[Sweep]:
    """Resolve sweep names, rejecting unknown ones rather than silently doing nothing."""
    if not names:
        return enabled_sweeps()
    by_name = {s.name: s for s in all_sweeps()}
    unknown = [n for n in names if n not in by_name]
    if unknown:
        raise SystemExit(
            f"Unknown sweep(s): {', '.join(unknown)}. "
            f"Known: {', '.join(sorted(by_name))}"
        )
    return [by_name[n] for n in names]


def run_once(names: list[str]) -> int:
    """One pass of each named sweep. Returns a process exit code."""
    failures = 0
    for sweep in _select(names):
        try:
            summary = run_sweep_once(sweep)
        except Exception:
            logger.exception("%s failed.", sweep.name)
            failures += 1
            continue
        if summary is None:
            logger.info("%s skipped: another instance holds the lock.", sweep.name)
        else:
            logger.info("%s: %s", sweep.name, summary)
    return 1 if failures else 0


def run_forever() -> int:
    sweeps = enabled_sweeps()
    if not sweeps:
        # Exiting would crash-loop under a process supervisor; idling is the
        # honest response to "every sweep is disabled".
        logger.warning("No sweeps are enabled; worker has nothing to do.")

    stop = threading.Event()

    def _handle(signum, _frame) -> None:
        logger.info("Signal %s received; stopping sweeps.", signal.Signals(signum).name)
        stop.set()

    signal.signal(signal.SIGTERM, _handle)
    signal.signal(signal.SIGINT, _handle)

    logger.info(
        "Worker starting with %d sweep(s): %s",
        len(sweeps),
        ", ".join(f"{s.name}@{s.interval_minutes}m" for s in sweeps),
    )
    threads = start_sweep_threads(sweeps, stop)

    # Block until a signal arrives. Waiting on the event rather than joining the
    # threads keeps the handler responsive.
    while not stop.wait(1.0):
        pass

    logger.info("Waiting for in-flight sweeps to finish.")
    deadline = settings.worker_shutdown_grace_seconds
    for thread in threads:
        thread.join(timeout=deadline)
    still_running = [t.name for t in threads if t.is_alive()]
    if still_running:
        # Daemon threads, so the process exits regardless; say so rather than
        # letting a truncated sweep look like a clean shutdown.
        logger.warning("Exiting with sweeps still in flight: %s", ", ".join(still_running))
    logger.info("Worker stopped.")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="app.worker", description=__doc__)
    parser.add_argument(
        "--once",
        action="store_true",
        help="Run one pass of each selected sweep and exit.",
    )
    parser.add_argument(
        "--list", action="store_true", help="List the sweeps and their intervals."
    )
    parser.add_argument(
        "names",
        nargs="*",
        help="Sweep names to run. Defaults to every enabled sweep.",
    )
    args = parser.parse_args(argv)

    _configure_logging()

    if args.list:
        for sweep in all_sweeps():
            state = "enabled" if sweep.enabled else "disabled"
            print(f"{sweep.name:28} {state:8} every {sweep.interval_minutes}m")
        return 0

    # Validate the invocation before touching config or the database, so a
    # mistyped command answers with usage rather than a schema error.
    if args.names and not args.once:
        parser.error("sweep names are only meaningful with --once")

    validate_runtime_config()
    _check_schema()

    if args.once:
        return run_once(args.names)
    return run_forever()


if __name__ == "__main__":
    sys.exit(main())
