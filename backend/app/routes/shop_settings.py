"""Shop identity settings — payee name, ABN, phone, email, payment instructions."""

from typing import Optional

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field
from sqlmodel import Session

from ..database import get_session
from ..dependencies import AuthContext, require_manager_or_above
from ..models import Tenant

router = APIRouter(prefix="/v1/settings/shop-identity", tags=["shop-settings"])


class ShopIdentityRead(BaseModel):
    name: str
    abn: Optional[str] = None
    shop_phone: Optional[str] = None
    shop_email: Optional[str] = None
    payment_instructions: Optional[str] = None
    business_address: Optional[str] = None


class ShopIdentityUpdate(BaseModel):
    abn: Optional[str] = Field(default=None, max_length=20)
    shop_phone: Optional[str] = Field(default=None, max_length=40)
    shop_email: Optional[str] = Field(default=None, max_length=200)
    payment_instructions: Optional[str] = Field(default=None, max_length=500)


@router.get("", response_model=ShopIdentityRead)
def get_shop_identity(
    auth: AuthContext = Depends(require_manager_or_above),
    session: Session = Depends(get_session),
):
    tenant = session.get(Tenant, auth.tenant_id)
    return ShopIdentityRead(
        name=tenant.name if tenant else "",
        abn=tenant.abn if tenant else None,
        shop_phone=tenant.shop_phone if tenant else None,
        shop_email=tenant.shop_email if tenant else None,
        payment_instructions=tenant.payment_instructions if tenant else None,
        business_address=tenant.business_address if tenant else None,
    )


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

    session.add(tenant)
    session.commit()
    session.refresh(tenant)

    return ShopIdentityRead(
        name=tenant.name,
        abn=tenant.abn,
        shop_phone=tenant.shop_phone,
        shop_email=tenant.shop_email,
        payment_instructions=tenant.payment_instructions,
        business_address=tenant.business_address,
    )
