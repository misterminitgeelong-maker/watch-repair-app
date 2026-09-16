"""The recurring background sweeps, described once instead of seven times.

Every sweep had its own near-identical loop function in main.py: read an interval
from settings, take the advisory lock, open a session, call one service function,
log the summary if something happened, sleep, repeat. Seven copies of twenty lines,
which is seven places to fix whenever the shape needs to change — and it did change,
twice, when the lock went in and when shutdown handling went in.

Here each sweep is data (name, setting names, the function to call, which summary
keys are worth logging) and the loop exists once.

Sleeping on an Event rather than time.sleep is what makes the worker process
stoppable. The retention sweep runs every six hours; with time.sleep, SIGTERM
would leave the container waiting up to six hours for a thread that is doing
nothing, and the platform would eventually kill it instead.
"""
from __future__ import annotations

import logging
import threading
from dataclasses import dataclass, field
from typing import Callable, Iterable

from sqlmodel import Session

from .advisory_lock import sweep_lock
from .config import settings
from .database import engine

logger = logging.getLogger(__name__)

SweepFn = Callable[[Session], dict]


@dataclass(frozen=True)
class Sweep:
    """One recurring background job.

    ``name`` is the single source of the advisory-lock key, the thread name and the
    logger name, so a sweep cannot end up locking under one name and logging under
    another.

    ``load`` is a callable returning the work function rather than the function
    itself: the service modules import models and routes, so importing them at
    module scope here would create an import cycle. The original code deferred
    these imports inside each loop body for the same reason.
    """

    name: str
    enabled: bool
    interval_minutes: int
    load: Callable[[], SweepFn]
    notable_keys: tuple[str, ...] = field(default=())

    @property
    def interval_seconds(self) -> int:
        # A zero or negative interval from config would spin this thread hot.
        return max(self.interval_minutes, 1) * 60

    @property
    def logger(self) -> logging.Logger:
        return logging.getLogger(f"mainspring.{self.name}")


def all_sweeps() -> list[Sweep]:
    """Every sweep, including disabled ones — filter with ``enabled_sweeps``."""

    def _quote_reminders() -> SweepFn:
        from .services.quote_reminders import send_due_quote_reminders

        return send_due_quote_reminders

    def _shop_mobile_booking_pool() -> SweepFn:
        from .routes.shop_mobile_bookings import process_due_shop_mobile_bookings

        return process_due_shop_mobile_bookings

    def _pool_alerts() -> SweepFn:
        from .services.pool_alerts import process_stale_pool_jobs

        return process_stale_pool_jobs

    def _sales_report_email() -> SweepFn:
        from .services.sales_report_email import send_due_sales_report_emails

        return send_due_sales_report_emails

    def _regional_report_email() -> SweepFn:
        from .services.regional_report_email import send_due_regional_report_emails

        return send_due_regional_report_emails

    def _mobile_weekly_report() -> SweepFn:
        from .services.mobile_weekly_report import send_due_mobile_weekly_reports

        return send_due_mobile_weekly_reports

    def _notification_redelivery() -> SweepFn:
        from .services.notification_redelivery import redeliver_failed_notifications

        return redeliver_failed_notifications

    def _retention() -> SweepFn:
        from .services.idempotency_retention import run_retention

        return run_retention

    return [
        Sweep(
            name="quote_reminders",
            enabled=settings.quote_reminder_enabled,
            interval_minutes=settings.quote_reminder_check_interval_minutes,
            load=_quote_reminders,
            notable_keys=("watch_sent", "mobile_sent"),
        ),
        Sweep(
            name="shop_mobile_booking_pool",
            enabled=settings.shop_mobile_booking_pool_enabled,
            interval_minutes=settings.shop_mobile_booking_check_interval_minutes,
            load=_shop_mobile_booking_pool,
            notable_keys=("moved_to_pool", "expired"),
        ),
        Sweep(
            name="pool_alerts",
            enabled=settings.pool_alert_enabled,
            interval_minutes=settings.pool_alert_check_interval_minutes,
            load=_pool_alerts,
            notable_keys=("stale_jobs",),
        ),
        Sweep(
            name="sales_report_email",
            enabled=settings.sales_report_email_enabled,
            interval_minutes=settings.sales_report_check_interval_minutes,
            load=_sales_report_email,
            notable_keys=("weekly_sent", "monthly_sent"),
        ),
        Sweep(
            name="regional_report_email",
            enabled=settings.regional_report_email_enabled,
            interval_minutes=settings.regional_report_check_interval_minutes,
            load=_regional_report_email,
            notable_keys=("sent",),
        ),
        Sweep(
            name="mobile_weekly_report",
            enabled=settings.mobile_weekly_report_email_enabled,
            interval_minutes=settings.mobile_weekly_report_check_interval_minutes,
            load=_mobile_weekly_report,
            notable_keys=("sent",),
        ),
        Sweep(
            name="notification_redelivery",
            enabled=settings.notification_redelivery_enabled,
            interval_minutes=settings.notification_redelivery_check_interval_minutes,
            load=_notification_redelivery,
            notable_keys=("email_sent", "sms_sent"),
        ),
        Sweep(
            name="retention",
            enabled=settings.retention_sweep_enabled,
            interval_minutes=settings.retention_sweep_check_interval_minutes,
            load=_retention,
            notable_keys=("idempotency_keys_removed", "email_payloads_cleared"),
        ),
    ]


def enabled_sweeps() -> list[Sweep]:
    return [s for s in all_sweeps() if s.enabled]


def run_sweep_once(sweep: Sweep) -> dict | None:
    """Run one pass. Returns None when another instance held the lock.

    Exceptions propagate: the caller decides whether one bad pass should stop the
    loop (it should not) or fail a manual invocation (it should).
    """
    with sweep_lock(sweep.name) as owned:
        if not owned:
            return None
        work = sweep.load()
        with Session(engine) as session:
            return work(session)


def run_sweep_forever(sweep: Sweep, stop: threading.Event) -> None:
    """Run ``sweep`` on its interval until ``stop`` is set.

    A failing pass is logged and retried on the next tick rather than killing the
    thread — one bad row must not silently end quote reminders for everyone until
    the next deploy.
    """
    log = sweep.logger
    interval = sweep.interval_seconds
    while not stop.is_set():
        try:
            summary = run_sweep_once(sweep)
            if summary and any(summary.get(k) for k in sweep.notable_keys):
                log.info("%s: %s", sweep.name, summary)
        except Exception:
            log.exception("%s run failed.", sweep.name)
        # Interruptible sleep: returns immediately once stop is set.
        stop.wait(interval)


def start_sweep_threads(
    sweeps: Iterable[Sweep], stop: threading.Event
) -> list[threading.Thread]:
    """Start one daemon thread per sweep and return them."""
    threads: list[threading.Thread] = []
    for sweep in sweeps:
        thread = threading.Thread(
            target=run_sweep_forever,
            args=(sweep, stop),
            name=f"mainspring-{sweep.name}",
            daemon=True,
        )
        thread.start()
        threads.append(thread)
    return threads
