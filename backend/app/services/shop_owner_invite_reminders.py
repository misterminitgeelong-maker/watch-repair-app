"""Nudge shops that haven't accepted their owner invite before the link expires.

Invites last SHOP_OWNER_INVITE_EXPIRY_DAYS. Most that go unanswered were simply
missed, so once an invite is within the reminder window of expiring we re-send
the same link once, by whichever of email and SMS the shop has on file.
"""
from __future__ import annotations

import math
from datetime import datetime, timedelta, timezone

from sqlmodel import Session, col, select

from ..config import settings
from ..models import ShopOwnerInvite, Tenant, User


def send_due_shop_owner_invite_reminders(session: Session) -> dict:
    from ..routes.parent_accounts import _send_shop_owner_invite_notifications

    now = datetime.now(timezone.utc)
    window_end = now + timedelta(hours=settings.shop_owner_invite_reminder_hours_before_expiry)
    due = session.exec(
        select(ShopOwnerInvite)
        .where(ShopOwnerInvite.status == "pending")
        .where(col(ShopOwnerInvite.reminder_sent_at).is_(None))
        .where(col(ShopOwnerInvite.expires_at) > now)
        .where(col(ShopOwnerInvite.expires_at) <= window_end)
    ).all()

    sent = 0
    unreachable = 0
    for invite in due:
        tenant = session.get(Tenant, invite.tenant_id)
        owner = session.get(User, invite.owner_user_id)
        # Mark it either way: one attempt per invite, never a daily nag.
        invite.reminder_sent_at = now
        session.add(invite)
        if tenant is None or owner is None:
            session.commit()
            continue
        expires_at = invite.expires_at if invite.expires_at.tzinfo else invite.expires_at.replace(tzinfo=timezone.utc)
        days_left = max(1, math.ceil((expires_at - now).total_seconds() / 86400))
        email_sent, sms_sent = _send_shop_owner_invite_notifications(
            session, invite=invite, tenant=tenant, owner=owner, is_reminder=True, expiry_days=days_left
        )
        session.commit()
        if email_sent or sms_sent:
            sent += 1
        else:
            unreachable += 1
    return {"due": len(due), "sent": sent, "unreachable": unreachable}
