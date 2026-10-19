"""SMS safety controls: opt-out suppression and soft fair-use metering.

Suppression is global (keyed on the normalised phone, not a tenant) because every
operator sends from the same Twilio number: a STOP is addressed to the number, and
the carrier blocks all further traffic from it whichever shop sent it.

Fair-use metering never blocks a send. It counts SmsLog rows per tenant per
calendar month in Australia/Melbourne and, once per month per threshold, records a
TenantEventLog row and a warning (also sent to Sentry when it is initialised).
"""
from __future__ import annotations

import logging
import math
from dataclasses import dataclass
from datetime import datetime, timezone
from uuid import UUID
from zoneinfo import ZoneInfo

from sqlmodel import Session, func, select

from .config import settings
from .models import SmsLog, SmsSuppression, TenantEventLog
from .phone_utils import normalize_phone

logger = logging.getLogger(__name__)

STOP_KEYWORDS = frozenset({"stop", "stopall", "unsubscribe", "cancel", "end", "quit"})
START_KEYWORDS = frozenset({"start", "unstop", "yes"})

#: Statuses that count as an outbound message for fair use (a real or dry-run send).
COUNTED_STATUSES = ("sent", "dry_run")
FAIR_USE_TZ = ZoneInfo("Australia/Melbourne")
FAIR_USE_THRESHOLDS = (80, 100)


def classify_keyword(body: str) -> str | None:
    """'stop' / 'start' when the whole message is a Twilio opt-out/in keyword."""
    word = "".join(ch for ch in (body or "").lower() if ch.isalnum())
    if word in STOP_KEYWORDS:
        return "stop"
    if word in START_KEYWORDS:
        return "start"
    return None


def is_suppressed(session: Session, phone: str | None) -> bool:
    normalized = normalize_phone(phone or "")
    if not normalized:
        return False
    row = session.exec(
        select(SmsSuppression.id)
        .where(SmsSuppression.phone_normalized == normalized)
        .where(SmsSuppression.active == True)  # noqa: E712
    ).first()
    return row is not None


def set_suppression(
    session: Session,
    phone: str,
    *,
    active: bool,
    keyword: str | None,
    source_tenant_id: UUID | None = None,
) -> bool:
    """Create/update the suppression row (no commit). Returns True if the state changed."""
    normalized = normalize_phone(phone or "")
    if not normalized:
        return False
    row = session.exec(
        select(SmsSuppression).where(SmsSuppression.phone_normalized == normalized)
    ).first()
    if row is None:
        if not active:
            return False
        session.add(SmsSuppression(
            phone_normalized=normalized, active=True, keyword=keyword,
            source_tenant_id=source_tenant_id,
        ))
        return True
    changed = row.active != active
    row.active = active
    row.keyword = keyword
    row.updated_at = datetime.now(timezone.utc)
    if active and source_tenant_id:
        row.source_tenant_id = source_tenant_id
    session.add(row)
    return changed


# ── Fair-use metering ────────────────────────────────────────────────────────

def month_bounds_utc(now: datetime | None = None) -> tuple[datetime, datetime]:
    """[start, end) of the current Melbourne calendar month, expressed in UTC."""
    now = now or datetime.now(timezone.utc)
    local = now.astimezone(FAIR_USE_TZ)
    start_local = local.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    if start_local.month == 12:
        end_local = start_local.replace(year=start_local.year + 1, month=1)
    else:
        end_local = start_local.replace(month=start_local.month + 1)
    return start_local.astimezone(timezone.utc), end_local.astimezone(timezone.utc)


@dataclass
class SmsUsage:
    tenant_id: UUID
    period_start: datetime
    period_end: datetime
    sent: int
    suppressed: int
    limit: int


def usage_for_tenant(session: Session, tenant_id: UUID, now: datetime | None = None) -> SmsUsage:
    start, end = month_bounds_utc(now)
    base = (
        select(func.count(SmsLog.id))
        .where(SmsLog.tenant_id == tenant_id)
        .where(SmsLog.created_at >= start)
        .where(SmsLog.created_at < end)
    )
    sent = session.exec(base.where(SmsLog.status.in_(COUNTED_STATUSES))).one()
    suppressed = session.exec(base.where(SmsLog.status == "suppressed")).one()
    return SmsUsage(
        tenant_id=tenant_id, period_start=start, period_end=end,
        sent=int(sent or 0), suppressed=int(suppressed or 0),
        limit=max(0, int(settings.sms_monthly_fair_use_limit or 0)),
    )


def check_fair_use(session: Session, tenant_id: UUID, now: datetime | None = None) -> None:
    """After a counted send: record 80%/100% crossings once per month. Never raises."""
    try:
        limit = int(settings.sms_monthly_fair_use_limit or 0)
        if limit <= 0:
            return
        usage = usage_for_tenant(session, tenant_id, now)
        for pct in FAIR_USE_THRESHOLDS:
            if usage.sent < math.ceil(limit * pct / 100):
                continue
            event_type = f"sms_fair_use_{pct}"
            already = session.exec(
                select(TenantEventLog.id)
                .where(TenantEventLog.tenant_id == tenant_id)
                .where(TenantEventLog.event_type == event_type)
                .where(TenantEventLog.created_at >= usage.period_start)
                .where(TenantEventLog.created_at < usage.period_end)
            ).first()
            if already:
                continue
            session.add(TenantEventLog(
                tenant_id=tenant_id,
                entity_type="sms_usage",
                event_type=event_type,
                event_summary=(
                    f"SMS fair-use: {usage.sent} of {limit} monthly messages used "
                    f"({pct}% threshold crossed). Sending is not blocked."
                ),
            ))
            logger.warning(
                "sms.fair_use threshold=%s%% tenant=%s sent=%s limit=%s", pct, tenant_id, usage.sent, limit,
            )
            try:
                import sentry_sdk

                if sentry_sdk.is_initialized():
                    sentry_sdk.set_tag("sms_fair_use_threshold", str(pct))
                    sentry_sdk.capture_message(
                        f"sms fair-use {pct}% crossed for tenant {tenant_id}", level="warning",
                    )
            except Exception:  # noqa: BLE001 - telemetry must never affect a send
                pass
    except Exception:  # noqa: BLE001
        logger.exception("sms.fair_use check failed tenant=%s", tenant_id)
