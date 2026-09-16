"""Minit shop / operator number validation and display helpers."""

import re
from uuid import UUID

from fastapi import HTTPException
from sqlmodel import Session

from .parent_network import linked_tenant_ids_for_parent, linked_tenants_for_parent

__all__ = [
    "assert_shop_number_unique_in_parent",
    "format_tenant_label",
    "linked_tenant_ids_for_parent",
    "linked_tenants_for_parent",
    "normalize_shop_number",
    "validate_shop_number_format",
]

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
