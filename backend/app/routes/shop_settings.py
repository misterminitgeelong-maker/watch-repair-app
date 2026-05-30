"""Shop identity settings — payee name, ABN, phone, email, payment instructions, branding."""

import re
from typing import Optional

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field
from sqlmodel import Session

from ..database import get_session
from ..dependencies import AuthContext, require_manager_or_above
from ..models import Tenant

router = APIRouter(prefix="/v1/settings/shop-identity", tags=["shop-settings"])

# Lenient hex colour: #RGB, #RRGGBB or #RRGGBBAA.
_HEX_COLOR_RE = re.compile(r"^#(?:[0-9a-fA-F]{3}|[0-9a-fA-F]{6}|[0-9a-fA-F]{8})$")


def normalize_brand_color(value: Optional[str]) -> Optional[str]:
    """Return a cleaned uppercase hex colour, or None when blank/invalid."""
    cleaned = (value or "").strip()
    if not cleaned:
        return None
    if not _HEX_COLOR_RE.match(cleaned):
        return None
    return "#" + cleaned[1:].upper()


class ShopIdentityRead(BaseModel):
    name: str
    abn: Optional[str] = None
    shop_phone: Optional[str] = None
    shop_email: Optional[str] = None
    payment_instructions: Optional[str] = None
    business_address: Optional[str] = None
    logo_url: Optional[str] = None
    brand_color: Optional[str] = None


class ShopIdentityUpdate(BaseModel):
    abn: Optional[str] = Field(default=None, max_length=20)
    shop_phone: Optional[str] = Field(default=None, max_length=40)
    shop_email: Optional[str] = Field(default=None, max_length=200)
    payment_instructions: Optional[str] = Field(default=None, max_length=500)
    logo_url: Optional[str] = Field(default=None, max_length=1000)
    brand_color: Optional[str] = Field(default=None, max_length=9)


def _read(tenant: Optional[Tenant]) -> ShopIdentityRead:
    return ShopIdentityRead(
        name=tenant.name if tenant else "",
        abn=tenant.abn if tenant else None,
        shop_phone=tenant.shop_phone if tenant else None,
        shop_email=tenant.shop_email if tenant else None,
        payment_instructions=tenant.payment_instructions if tenant else None,
        business_address=tenant.business_address if tenant else None,
        logo_url=tenant.logo_url if tenant else None,
        brand_color=tenant.brand_color if tenant else None,
    )


@router.get("", response_model=ShopIdentityRead)
def get_shop_identity(
    auth: AuthContext = Depends(require_manager_or_above),
    session: Session = Depends(get_session),
):
    tenant = session.get(Tenant, auth.tenant_id)
    return _read(tenant)


@router.patch("", response_model=ShopIdentityRead)
def update_shop_identity(
    payload: ShopIdentityUpdate,
    auth: AuthContext = Depends(require_manager_or_above),
    session: Session = Depends(get_session),
):
    tenant = session.get(Tenant, auth.tenant_id)
    if not tenant:
        from fastapi import HTTPException
        raise HTTPException(status_code=404, detail="Tenant not found")

    if payload.abn is not None:
        tenant.abn = payload.abn.strip() or None
    if payload.shop_phone is not None:
        tenant.shop_phone = payload.shop_phone.strip() or None
    if payload.shop_email is not None:
        tenant.shop_email = payload.shop_email.strip() or None
    if payload.payment_instructions is not None:
        tenant.payment_instructions = payload.payment_instructions.strip() or None
    if payload.logo_url is not None:
        tenant.logo_url = payload.logo_url.strip() or None
    if payload.brand_color is not None:
        # Lenient: blank or invalid hex clears the brand colour rather than erroring.
        tenant.brand_color = normalize_brand_color(payload.brand_color)

    session.add(tenant)
    session.commit()
    session.refresh(tenant)

    return _read(tenant)
