from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import Session, select

from ..database import get_session
from ..dependencies import AuthContext, get_auth_context, require_manager_or_above
from ..loyalty_utils import adjust_points, build_loyalty_read, get_or_create_loyalty
from ..models import (
    Customer,
    CustomerLoyalty,
    LoyaltyProfileResponse,
    LoyaltyTier,
    PointsAdjustRequest,
    PointsLedger,
    PointsLedgerRead,
)

router = APIRouter(prefix="/v1/loyalty", tags=["loyalty"])


def _get_tier(session: Session, tier_id: int) -> LoyaltyTier:
    tier = session.get(LoyaltyTier, tier_id)
    if not tier:
        raise HTTPException(status_code=500, detail="Loyalty tier data missing — run migration")
    return tier


@router.get("/customers/{customer_id}", response_model=LoyaltyProfileResponse)
def get_loyalty_profile(
    customer_id: UUID,
    auth: AuthContext = Depends(get_auth_context),
    session: Session = Depends(get_session),
):
    customer = session.get(Customer, customer_id)
    if not customer or customer.tenant_id != auth.tenant_id:
        raise HTTPException(status_code=404, detail="Customer not found")

    loyalty = get_or_create_loyalty(session, auth.tenant_id, customer_id)
    session.commit()
    session.refresh(loyalty)

    tier = _get_tier(session, loyalty.tier_id)
    loyalty_read = build_loyalty_read(session, loyalty, tier)

    ledger_rows = session.exec(
        select(PointsLedger)
        .where(PointsLedger.customer_loyalty_id == loyalty.id)
        .order_by(PointsLedger.occurred_at.desc())  # type: ignore[attr-defined]
        .limit(20)
    ).all()

    return LoyaltyProfileResponse(
        loyalty=loyalty_read,
        recent_ledger=[
            PointsLedgerRead(
                id=row.id,
                entry_type=row.entry_type,
                points_delta=row.points_delta,
                source_invoice_id=row.source_invoice_id,
                note=row.note,
                occurred_at=row.occurred_at,
            )
            for row in ledger_rows
        ],
    )


@router.post("/customers/{customer_id}/adjust", response_model=LoyaltyProfileResponse)
def adjust_customer_points(
    customer_id: UUID,
    payload: PointsAdjustRequest,
    auth: AuthContext = Depends(require_manager_or_above),
    session: Session = Depends(get_session),
):
    customer = session.get(Customer, customer_id)
    if not customer or customer.tenant_id != auth.tenant_id:
        raise HTTPException(status_code=404, detail="Customer not found")
    if payload.points_delta == 0:
        raise HTTPException(status_code=400, detail="points_delta cannot be zero")

    loyalty = session.exec(
        select(CustomerLoyalty)
        .where(CustomerLoyalty.tenant_id == auth.tenant_id)
        .where(CustomerLoyalty.customer_id == customer_id)
    ).first()
    if loyalty and (loyalty.points_balance + payload.points_delta) < 0:
        raise HTTPException(status_code=400, detail="Adjustment would make balance negative")

    adjust_points(
        session,
        tenant_id=auth.tenant_id,
        customer_id=customer_id,
        delta=payload.points_delta,
        note=payload.note,
        actor_user_id=auth.user_id,
    )
    session.commit()

    loyalty = session.exec(
        select(CustomerLoyalty)
        .where(CustomerLoyalty.tenant_id == auth.tenant_id)
        .where(CustomerLoyalty.customer_id == customer_id)
    ).first()
    tier = _get_tier(session, loyalty.tier_id)
    loyalty_read = build_loyalty_read(session, loyalty, tier)

    ledger_rows = session.exec(
        select(PointsLedger)
        .where(PointsLedger.customer_loyalty_id == loyalty.id)
        .order_by(PointsLedger.occurred_at.desc())  # type: ignore[attr-defined]
        .limit(20)
    ).all()

    return LoyaltyProfileResponse(
        loyalty=loyalty_read,
        recent_ledger=[
            PointsLedgerRead(
                id=row.id,
                entry_type=row.entry_type,
                points_delta=row.points_delta,
                source_invoice_id=row.source_invoice_id,
                note=row.note,
                occurred_at=row.occurred_at,
            )
            for row in ledger_rows
        ],
    )
