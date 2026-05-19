"""Minit shop / operator number validation and display helpers."""

import re
from uuid import UUID

from fastapi import HTTPException
from sqlmodel import Session, col, select

from .models import ParentAccountMembership, Tenant

_SHOP_NUMBER_RE = re.compile(r"^\d{1,10}$")


def normalize_shop_number(value: str | None) -> str | None:
    if value is None:
        return None
    stripped = value.strip()
    return stripped if stripped else None


def validate_shop_number_format(shop_number: str | None) -> str | None:
    """Return normalized shop number or None; raise 400 if invalid when provided."""
    normalized = normalize_shop_number(shop_number)
    if normalized is None:
        return None
    if not _SHOP_NUMBER_RE.match(normalized):
        raise HTTPException(
            status_code=400,
            detail="shop_number must be digits only, up to 10 characters",
        )
    return normalized


def format_tenant_label(name: str, shop_number: str | None) -> str:
    base = (name or "").strip() or "Unknown"
    if shop_number:
        return f"{base} (#{shop_number})"
    return base


def linked_tenant_ids_for_parent(session: Session, parent_id: UUID) -> list[UUID]:
    rows = session.exec(
        select(ParentAccountMembership.tenant_id).where(
            ParentAccountMembership.parent_account_id == parent_id
        )
    ).all()
    return list(dict.fromkeys(rows))


def linked_tenants_for_parent(session: Session, parent_id: UUID) -> list[Tenant]:
    """Load all linked tenants in one query (avoids N+1 session.get loops)."""
    ids = linked_tenant_ids_for_parent(session, parent_id)
    if not ids:
        return []
    tenants = session.exec(select(Tenant).where(col(Tenant.id).in_(ids))).all()
    by_id = {t.id: t for t in tenants}
    return [by_id[tid] for tid in ids if tid in by_id]


def assert_shop_number_unique_in_parent(
    session: Session,
    *,
    parent_id: UUID,
    shop_number: str,
    exclude_tenant_id: UUID | None = None,
) -> None:
    for other in linked_tenants_for_parent(session, parent_id):
        if exclude_tenant_id is not None and other.id == exclude_tenant_id:
            continue
        if other.shop_number == shop_number:
            raise HTTPException(
                status_code=409,
                detail=f"shop_number '{shop_number}' is already used by another site in this account",
            )
