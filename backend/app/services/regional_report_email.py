"""Scheduled weekly VSWT comparison-cockpit emails."""
from __future__ import annotations

import csv
import io
import logging
from datetime import datetime, timezone
from uuid import UUID

from sqlmodel import Session, select

from .. import email_client
from ..dependencies import AuthContext
from ..models import Tenant, User, UserNotificationPreference
from ..routes.vswt_reports import _build_cockpit_data

logger = logging.getLogger(__name__)


def _is_due(last_sent_at: datetime | None, today) -> bool:
    if last_sent_at is None:
        return True
    last_date = last_sent_at.astimezone(timezone.utc).date() if last_sent_at.tzinfo else last_sent_at.date()
    return last_date.isocalendar()[:2] != today.isocalendar()[:2]


def _csv_bytes(data: dict) -> bytes:
    buf = io.StringIO()
    writer = csv.writer(buf)
    writer.writerow([
        "KPI", "Group", "Current", "Previous", "Change", "Change %", "4-week avg",
        "13-week avg", "52-week avg", "Last year", "Target", "Region avg", "Peer avg", "Rank",
    ])
    for row in data.get("rows", []):
        writer.writerow([
            row.get("label"), row.get("group"), row.get("current"), row.get("previous"),
            row.get("delta"), row.get("delta_pct"), row.get("rolling_4"), row.get("rolling_13"),
            row.get("rolling_52"), row.get("last_year"), row.get("target"), row.get("region_avg"),
            row.get("peer_avg"), row.get("rank"),
        ])
    return buf.getvalue().encode("utf-8")


def send_regional_report_for_user(session: Session, *, tenant_id: UUID, user_id: UUID) -> bool:
    tenant = session.get(Tenant, tenant_id)
    user = session.get(User, user_id)
    if not tenant or not tenant.shop_number or not user or not user.is_active or not (user.email or "").strip():
        return False
    data = _build_cockpit_data(
        session,
        auth=AuthContext(tenant_id=tenant_id, user_id=user_id, role=user.role),
        target_shop_number=tenant.shop_number,
        comparison="previous",
    )
    if not data.get("available"):
        return False
    by_key = {row["key"]: row for row in data["rows"]}
    sales = by_key.get("sales_ty", {})
    customers = by_key.get("customer_ty", {})
    jobs = by_key.get("jobs_ty", {})
    sent, _error = email_client.send_vswt_management_report_email(
        to_email=user.email,
        shop_name=tenant.name,
        week=data["week"],
        sales=sales.get("current"),
        sales_delta_pct=sales.get("delta_pct"),
        customers=customers.get("current"),
        jobs=jobs.get("current"),
        sales_rank=sales.get("rank"),
        region_size=data["region_size"],
        alerts=data.get("alerts", []),
        csv_bytes=_csv_bytes(data),
        csv_filename=f"regional-performance-week-{data['week']}.csv",
    )
    # Mark the attempt so a missing external email configuration cannot make the scheduler retry
    # every few minutes. This matches the existing sales-report scheduler's idempotency behaviour.
    pref = session.exec(
        select(UserNotificationPreference)
        .where(UserNotificationPreference.tenant_id == tenant_id)
        .where(UserNotificationPreference.user_id == user_id)
    ).first()
    if pref:
        pref.last_weekly_regional_report_sent_at = datetime.now(timezone.utc)
        session.add(pref)
        session.commit()
    return sent


def send_due_regional_report_emails(session: Session, tenant_id: UUID | None = None) -> dict[str, int]:
    today = datetime.now(timezone.utc).date()
    summary = {"sent": 0, "skipped": 0}
    query = select(UserNotificationPreference).where(UserNotificationPreference.email_weekly_regional_report.is_(True))
    if tenant_id:
        query = query.where(UserNotificationPreference.tenant_id == tenant_id)
    for pref in session.exec(query).all():
        if not _is_due(pref.last_weekly_regional_report_sent_at, today):
            summary["skipped"] += 1
            continue
        try:
            if send_regional_report_for_user(session, tenant_id=pref.tenant_id, user_id=pref.user_id):
                summary["sent"] += 1
            else:
                summary["skipped"] += 1
        except Exception:
            logger.exception("regional_report_email.send_failed tenant=%s user=%s", pref.tenant_id, pref.user_id)
            summary["skipped"] += 1
    return summary
