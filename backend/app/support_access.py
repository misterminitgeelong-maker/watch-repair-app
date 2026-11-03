"""Franchisee consent for HQ support access.

An HQ admin may only open a shop that has taken its own login while the shop
owner has an active, time-boxed grant (`Tenant.support_access_until`). A shop
still on the HQ-provisioned shared login has nothing to consent to yet, so the
gate does not apply to it.
"""
from __future__ import annotations

from datetime import datetime, timezone

from fastapi import HTTPException
from sqlmodel import Session, select

from .models import ParentAccountUser, Tenant, User

SUPPORT_ACCESS_MAX_HOURS = 24 * 7
SUPPORT_ACCESS_DEFAULT_HOURS = 24
MIN_REASON_CHARS = 5


def _aware(dt: datetime) -> datetime:
    return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)


def grant_active(tenant: Tenant, now: datetime | None = None) -> bool:
    until = tenant.support_access_until
    if until is None:
        return False
    return _aware(until) > (now or datetime.now(timezone.utc))


def owner_has_own_login(session: Session, owner: User) -> bool:
    """False while the owner row is still a copy of an HQ login."""
    return session.exec(
        select(ParentAccountUser.id).where(ParentAccountUser.user_id == owner.id).limit(1)
    ).first() is None


def require_support_access(session: Session, tenant: Tenant, owner: User) -> None:
    """403 unless the shop's owner has granted support access (or has no own login yet)."""
    if not owner_has_own_login(session, owner):
        return
    if not grant_active(tenant):
        raise HTTPException(
            status_code=403,
            detail=(
                "This shop hasn't allowed support access. Ask the shop owner to turn on "
                "'Allow support access' in their settings, then try again."
            ),
        )


def clean_reason(reason: str | None) -> str:
    return " ".join((reason or "").split())[:300]
