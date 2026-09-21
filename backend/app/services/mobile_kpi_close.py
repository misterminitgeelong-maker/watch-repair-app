"""Close-of-trade compile for Minit HQ mobile KPIs.

Live numbers are queried on demand. This sweep freezes a trade day at 21:00
Australia/Sydney and the operating week at Saturday 23:05, then emails the
weekly CSV to allocated HQ workers. ``emailed_at`` is set only after SendGrid
accepts the send — a dry-run or provider failure leaves the snapshot in place
for the HQ page and retries on the next tick.
"""

from __future__ import annotations

import hashlib
import json
import logging
from datetime import datetime, timedelta, timezone
from uuid import UUID

from sqlmodel import Session, select

from .. import email_client
from ..mobile_network_kpis import (
    NETWORK_TIMEZONE_NAME,
    build_network_kpis,
    csv_bytes_for_report,
    daily_trade_dates_due,
    last_completed_operating_week,
    prior_operating_week_window,
    report_to_payload,
    trade_day_snapshot_window,
    weekly_compile_due,
)
from ..models import (
    MobileKpiDailySnapshot,
    MobileKpiWeeklySnapshot,
    ParentAccount,
    ParentAccountUser,
    User,
)
from ..parent_network import grant_parent_role, parent_role_for_user, parent_users

logger = logging.getLogger(__name__)


def _now() -> datetime:
    return datetime.now(timezone.utc)


def compile_daily_snapshot(
    session: Session,
    parent: ParentAccount,
    trade_date,
    *,
    now: datetime | None = None,
) -> list[MobileKpiDailySnapshot]:
    """Idempotent: skip operators that already have a row for this trade date."""
    existing = {
        row.operator_tenant_id
        for row in session.exec(
            select(MobileKpiDailySnapshot)
            .where(MobileKpiDailySnapshot.parent_account_id == parent.id)
            .where(MobileKpiDailySnapshot.trade_date == trade_date)
        ).all()
    }
    start, end = trade_day_snapshot_window(trade_date)
    prior_start, prior_end = trade_day_snapshot_window(trade_date - timedelta(days=7))

    report = build_network_kpis(
        session,
        parent,
        start,
        end,
        prior_start=prior_start,
        prior_end=prior_end,
        generated_at=now or _now(),
    )
    compiled_at = now or _now()
    written: list[MobileKpiDailySnapshot] = []
    for row in report.operators:
        if row.operator_tenant_id in existing:
            continue
        snap = MobileKpiDailySnapshot(
            parent_account_id=parent.id,
            operator_tenant_id=row.operator_tenant_id,
            trade_date=trade_date,
            payload_json=json.dumps(row.to_dict()),
            compiled_at=compiled_at,
        )
        session.add(snap)
        written.append(snap)
    if written:
        session.commit()
    return written


def _weekly_snapshot_for(
    session: Session, parent_id: UUID, week_start_ymd: str
) -> MobileKpiWeeklySnapshot | None:
    return session.exec(
        select(MobileKpiWeeklySnapshot)
        .where(MobileKpiWeeklySnapshot.parent_account_id == parent_id)
        .where(MobileKpiWeeklySnapshot.week_start_ymd == week_start_ymd)
    ).first()


def compile_weekly_snapshot(
    session: Session,
    parent: ParentAccount,
    *,
    at: datetime | None = None,
    force: bool = False,
) -> MobileKpiWeeklySnapshot:
    now = at or _now()
    start, end, start_ymd, end_ymd = last_completed_operating_week(now)
    existing = _weekly_snapshot_for(session, parent.id, start_ymd)
    if existing is not None and not force:
        return existing

    prior_start, prior_end, _ps, _pe = prior_operating_week_window(start)
    report = build_network_kpis(
        session,
        parent,
        start,
        end,
        prior_start=prior_start,
        prior_end=prior_end,
        generated_at=now,
    )
    csv_bytes = csv_bytes_for_report(report)
    digest = hashlib.sha256(csv_bytes).hexdigest()
    payload = json.dumps(report_to_payload(report))
    if existing is not None:
        existing.week_end_ymd = end_ymd
        existing.payload_json = payload
        existing.csv_sha256 = digest
        existing.compiled_at = now
        if force:
            existing.emailed_at = None
        session.add(existing)
        session.commit()
        session.refresh(existing)
        return existing

    snap = MobileKpiWeeklySnapshot(
        parent_account_id=parent.id,
        week_start_ymd=start_ymd,
        week_end_ymd=end_ymd,
        payload_json=payload,
        csv_sha256=digest,
        compiled_at=now,
    )
    session.add(snap)
    session.commit()
    session.refresh(snap)
    return snap


def allocated_recipient_emails(session: Session, parent: ParentAccount) -> list[str]:
    """HQ workers flagged for the Saturday CSV. Falls back to owner_email when none allocated and opt-in is on."""
    emails: list[str] = []
    seen: set[str] = set()
    for grant in parent_users(session, parent.id):
        if not grant.email_mobile_kpi_report:
            continue
        user = session.get(User, grant.user_id)
        if user is None or not user.is_active:
            continue
        email = (user.email or "").strip()
        if email and email.lower() not in seen:
            seen.add(email.lower())
            emails.append(email)
    if emails:
        return emails
    owner = (parent.owner_email or "").strip()
    if parent.mobile_weekly_report_opt_in and owner:
        return [owner]
    return []


def set_recipient_flag(
    session: Session,
    parent: ParentAccount,
    user: User,
    enabled: bool,
) -> ParentAccountUser:
    role = parent_role_for_user(session, parent, user) or "hq_viewer"
    row = grant_parent_role(session, parent_id=parent.id, user_id=user.id, role=role)
    row.email_mobile_kpi_report = enabled
    session.add(row)
    session.commit()
    session.refresh(row)
    return row


def email_weekly_snapshot(
    session: Session,
    parent: ParentAccount,
    snap: MobileKpiWeeklySnapshot,
    *,
    stamp_parent_last_sent: bool = False,
) -> bool:
    """Send the stored weekly CSV. Returns True only when every recipient send was accepted."""
    recipients = allocated_recipient_emails(session, parent)
    if not recipients:
        if stamp_parent_last_sent:
            parent.last_mobile_weekly_report_sent_at = _now()
            session.add(parent)
            session.commit()
        return False

    payload = json.loads(snap.payload_json)
    operators = payload.get("operators") or []
    csv_bytes = csv_bytes_for_report_payload(payload, snap)
    filename = f"minit-mobile-weekly-{snap.week_start_ymd}_{snap.week_end_ymd}.csv"
    tenant_id = parent.mobile_lead_escalation_tenant_id or parent.mobile_lead_default_tenant_id
    rows_for_email = [
        {
            "operator_name": r.get("operator_name"),
            "customers_count": r.get("customers_count", 0),
            "jobs_count": r.get("jobs_created", 0),
            "sales_cents": r.get("sales_cents", 0),
            "prior_week_sales_cents": r.get("prior_sales_cents", 0),
            "enquiries_not_actioned": r.get("enquiries_not_actioned", 0),
        }
        for r in operators
    ]

    any_failed = False
    any_sent = False
    for to_email in recipients:
        sent, _err = email_client.send_mobile_weekly_report_email(
            to_email=to_email,
            period_start=snap.week_start_ymd,
            period_end=snap.week_end_ymd,
            rows=rows_for_email,
            csv_bytes=csv_bytes,
            csv_filename=filename,
            session=session,
            tenant_id=tenant_id,
        )
        if sent:
            any_sent = True
        else:
            any_failed = True
            logger.warning(
                "mobile_kpi_close.email_failed parent=%s to=%s week=%s",
                parent.id,
                to_email,
                snap.week_start_ymd,
            )

    if stamp_parent_last_sent:
        parent.last_mobile_weekly_report_sent_at = _now()
        session.add(parent)

    if any_sent and not any_failed:
        snap.emailed_at = _now()
        session.add(snap)
        session.commit()
        return True
    session.commit()
    return False


def csv_bytes_for_report_payload(payload: dict, snap: MobileKpiWeeklySnapshot) -> bytes:
    from ..mobile_network_kpis import (
        NetworkKpiReport,
        csv_bytes_for_report,
        operator_row_from_dict,
        rollup_operators,
    )
    from datetime import datetime as dt

    operators = [operator_row_from_dict(r) for r in (payload.get("operators") or [])]
    network = operator_row_from_dict(payload["network"]) if payload.get("network") else rollup_operators(operators)
    start = dt.fromisoformat(payload["start"].replace("Z", "+00:00"))
    end = dt.fromisoformat(payload["end"].replace("Z", "+00:00"))
    generated = dt.fromisoformat(payload.get("generated_at", snap.compiled_at.isoformat()).replace("Z", "+00:00"))
    report = NetworkKpiReport(
        start=start,
        end=end,
        start_ymd=payload.get("start_ymd") or snap.week_start_ymd,
        end_ymd=payload.get("end_ymd") or snap.week_end_ymd,
        timezone=payload.get("timezone") or NETWORK_TIMEZONE_NAME,
        generated_at=generated,
        network=network,
        operators=operators,
    )
    return csv_bytes_for_report(report)


def send_weekly_now(session: Session, parent: ParentAccount) -> MobileKpiWeeklySnapshot:
    """Compile the last completed week and attempt email. Always writes the snapshot.

    ``last_mobile_weekly_report_sent_at`` is stamped on this explicit send-now
    so the settings UI has a timestamp; ``emailed_at`` still requires SendGrid.
    """
    snap = compile_weekly_snapshot(session, parent, force=True)
    email_weekly_snapshot(session, parent, snap, stamp_parent_last_sent=True)
    session.refresh(snap)
    session.refresh(parent)
    return snap


def run_mobile_kpi_close(session: Session, parent_id: UUID | None = None) -> dict[str, int]:
    """Sweep entry: freeze due daily rows and Saturday weekly CSV/email."""
    now = _now()
    summary = {"daily_compiled": 0, "weekly_compiled": 0, "sent": 0, "skipped": 0}
    query = select(ParentAccount)
    if parent_id:
        query = query.where(ParentAccount.id == parent_id)
    parents = session.exec(query).all()

    for parent in parents:
        try:
            for trade_date in daily_trade_dates_due(now):
                written = compile_daily_snapshot(session, parent, trade_date, now=now)
                summary["daily_compiled"] += len(written)
        except Exception:
            logger.exception("mobile_kpi_close.daily_failed parent=%s", parent.id)

        if not weekly_compile_due(now):
            continue
        try:
            snap = compile_weekly_snapshot(session, parent, at=now)
            summary["weekly_compiled"] += 1
            if snap.emailed_at is not None:
                summary["skipped"] += 1
                continue
            recipients = allocated_recipient_emails(session, parent)
            if not recipients:
                summary["skipped"] += 1
                continue
            if email_weekly_snapshot(session, parent, snap):
                summary["sent"] += 1
            else:
                summary["skipped"] += 1
        except Exception:
            logger.exception("mobile_kpi_close.weekly_failed parent=%s", parent.id)
            summary["skipped"] += 1

    return summary
