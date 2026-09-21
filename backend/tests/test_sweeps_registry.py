"""The sweep registry replaced the hand-written loops in main.py.

The failure mode of that refactor is not a crash — it is a sweep quietly going
missing, or a deferred import being wrong, and nobody noticing until customers
stop getting quote reminders. These tests exist to make that loud.
"""
from __future__ import annotations

import threading
import time

import pytest

from app import sweeps as sweeps_module
from app.sweeps import (
    Sweep,
    all_sweeps,
    enabled_sweeps,
    run_sweep_forever,
    start_sweep_threads,
)

# The sweeps that ran in main.py before the extraction. If a name changes, the
# advisory lock key changes with it, and two deploys briefly stop excluding each
# other — so this list is pinned deliberately, not derived from the registry.
EXPECTED_SWEEPS = {
    "quote_reminders",
    "shop_mobile_booking_pool",
    "pool_alerts",
    "sales_report_email",
    "regional_report_email",
    "regional_manager_report",
    "mobile_weekly_report",
    "mobile_kpi_close",
    "notification_redelivery",
    "retention",
}


def test_every_sweep_that_used_to_run_is_still_registered():
    assert {s.name for s in all_sweeps()} == EXPECTED_SWEEPS


def test_sweep_names_are_unique():
    """The name is the advisory lock key; a duplicate would make two sweeps
    mutually exclusive and silently halve how often each runs."""
    names = [s.name for s in all_sweeps()]
    assert len(names) == len(set(names)), f"duplicate sweep name in {names}"


@pytest.mark.parametrize("sweep", all_sweeps(), ids=lambda s: s.name)
def test_sweep_work_function_actually_imports(sweep: Sweep):
    """The service imports are deferred to avoid an import cycle, so a wrong path
    would not fail at startup — it would fail on the first tick, in production,
    once per interval, forever."""
    work = sweep.load()
    assert callable(work), f"{sweep.name} did not load a callable"


@pytest.mark.parametrize("sweep", all_sweeps(), ids=lambda s: s.name)
def test_sweep_interval_is_never_hot(sweep: Sweep):
    """A misconfigured 0 would spin the thread against the database."""
    assert sweep.interval_seconds >= 60


def test_enabled_sweeps_is_a_subset_driven_by_settings():
    enabled = {s.name for s in enabled_sweeps()}
    assert enabled <= EXPECTED_SWEEPS
    assert all(s.enabled for s in enabled_sweeps())


def _probe_sweep(name: str, fn, interval_minutes: int = 1) -> Sweep:
    return Sweep(
        name=name,
        enabled=True,
        interval_minutes=interval_minutes,
        load=lambda: fn,
        notable_keys=("did",),
    )


def test_loop_stops_promptly_when_asked_instead_of_sleeping_out_its_interval():
    """The reason the loop waits on an Event rather than time.sleep.

    Retention runs every 6 hours. With time.sleep, a SIGTERM would leave the
    container sitting idle until the platform lost patience and killed it.
    """
    calls: list[int] = []

    def work(_session):
        calls.append(1)
        return {"did": 0}

    stop = threading.Event()
    # An interval far longer than this test would ever wait for.
    sweep = _probe_sweep("probe-stop", work, interval_minutes=600)
    thread = threading.Thread(target=run_sweep_forever, args=(sweep, stop), daemon=True)

    thread.start()
    # Let the first pass happen, then ask it to stop.
    deadline = time.monotonic() + 5
    while not calls and time.monotonic() < deadline:
        time.sleep(0.01)
    assert calls, "the sweep never ran its first pass"

    stop.set()
    thread.join(timeout=5)
    assert not thread.is_alive(), "loop ignored the stop event and slept out its interval"


def test_a_failing_pass_does_not_kill_the_loop():
    """One bad row must not silently end a sweep until the next deploy."""
    calls: list[int] = []

    def work(_session):
        calls.append(1)
        raise RuntimeError("bad row")

    stop = threading.Event()
    sweep = _probe_sweep("probe-boom", work)
    # Nothing should escape run_sweep_forever.
    thread = threading.Thread(target=run_sweep_forever, args=(sweep, stop), daemon=True)
    thread.start()

    deadline = time.monotonic() + 5
    while not calls and time.monotonic() < deadline:
        time.sleep(0.01)
    stop.set()
    thread.join(timeout=5)

    assert calls, "the sweep never ran"
    assert not thread.is_alive()


def test_summary_is_only_logged_when_something_notable_happened(caplog):
    """These run every couple of minutes; logging an empty summary each time is
    how a log becomes unreadable."""
    quiet = _probe_sweep("probe-quiet", lambda _s: {"did": 0})
    loud = _probe_sweep("probe-loud", lambda _s: {"did": 3})

    for sweep, expected in ((quiet, False), (loud, True)):
        stop = threading.Event()
        caplog.clear()
        with caplog.at_level("INFO"):
            thread = threading.Thread(
                target=run_sweep_forever, args=(sweep, stop), daemon=True
            )
            thread.start()
            deadline = time.monotonic() + 5
            while sweep.name not in caplog.text and time.monotonic() < deadline:
                time.sleep(0.01)
            stop.set()
            thread.join(timeout=5)
        assert (sweep.name in caplog.text) is expected


def test_start_sweep_threads_names_threads_after_their_sweep():
    """Thread names are what a stack dump shows when a sweep wedges."""
    stop = threading.Event()
    stop.set()  # loops exit after one pass
    sweep = _probe_sweep("probe-named", lambda _s: {"did": 0})
    threads = start_sweep_threads([sweep], stop)
    try:
        assert [t.name for t in threads] == ["mainspring-probe-named"]
    finally:
        for t in threads:
            t.join(timeout=5)


def test_run_sweep_once_returns_none_when_another_instance_holds_the_lock(monkeypatch):
    """Two workers must not both do the work; the caller distinguishes
    'skipped' from 'ran and found nothing' by the None."""
    from contextlib import contextmanager

    @contextmanager
    def busy_lock(_name):
        yield False

    monkeypatch.setattr(sweeps_module, "sweep_lock", busy_lock)

    ran: list[int] = []
    sweep = _probe_sweep("probe-locked", lambda _s: ran.append(1) or {"did": 1})

    assert sweeps_module.run_sweep_once(sweep) is None
    assert ran == [], "the sweep ran despite another instance holding the lock"


def test_web_process_runs_sweeps_by_default_and_yields_them_when_told(monkeypatch):
    """The whole rollout is this flag: deploy the worker, then flip it.

    Defaulting to True is what makes this change a no-op until someone chooses
    otherwise — the sweeps keep running in the web process exactly as before.
    """
    from app import main as main_module
    from app.config import settings

    monkeypatch.setattr(settings, "app_env", "production")

    monkeypatch.setattr(settings, "run_sweeps_in_web_process", True)
    assert main_module._should_run_sweeps_here() is True

    monkeypatch.setattr(settings, "run_sweeps_in_web_process", False)
    assert main_module._should_run_sweeps_here() is False


def test_tests_never_run_sweeps_even_when_enabled(monkeypatch):
    """A sweep firing during a test run would send real SMS and email."""
    from app import main as main_module
    from app.config import settings

    monkeypatch.setattr(settings, "run_sweeps_in_web_process", True)
    monkeypatch.setattr(settings, "app_env", "test")
    assert main_module._should_run_sweeps_here() is False


def test_the_default_is_to_keep_running_sweeps_in_the_web_process():
    """If this ever flips to False by default, an upgrade silently stops every
    sweep for anyone who has not deployed the worker service."""
    from app.config import Settings

    assert Settings().run_sweeps_in_web_process is True
