"""Loyalty program business logic — earn points, recalc tier, get-or-create profile."""
from datetime import datetime, timedelta, timezone
from uuid import UUID, uuid4

from sqlmodel import Session, func, select

from .models import (
    CustomerLoyalty,
    CustomerLoyaltyRead,
    Invoice,
    LoyaltyTier,
    PointsLedger,
    PointsLedgerRead,
    RepairJob,
    Watch,
)

SIGNUP_BONUS_POINTS = 50
POINTS_PER_DOLLAR = 1  # 1 pt per AUD $1 (100 cents)


def _get_tiers(session: Session) -> list[LoyaltyTier]:
    return session.exec(select(LoyaltyTier).order_by(LoyaltyTier.id)).all()  # type: ignore[return-value]


def _rolling_12m_spend(session: Session, loyalty_id: UUID) -> int:
    cutoff = datetime.now(timezone.utc) - timedelta(days=365)
    result = session.exec(
        select(func.coalesce(func.sum(PointsLedger.source_amount_cents), 0))
        .where(PointsLedger.customer_loyalty_id == loyalty_id)
        .where(PointsLedger.entry_type == "earn")
        .where(PointsLedger.occurred_at >= cutoff)
    ).one()
    return int(result)


def _resolve_tier(tiers: list[LoyaltyTier], rolling_spend_cents: int) -> LoyaltyTier:
    best = tiers[0]
    for tier in tiers:
        if rolling_spend_cents >= tier.min_spend_cents:
            best = tier
    return best


def get_or_create_loyalty(
    session: Session,
    tenant_id: UUID,
    customer_id: UUID,
) -> CustomerLoyalty:
    loyalty = session.exec(
        select(CustomerLoyalty)
        .where(CustomerLoyalty.tenant_id == tenant_id)
        .where(CustomerLoyalty.customer_id == customer_id)
    ).first()
    if loyalty:
        return loyalty

    loyalty = CustomerLoyalty(
        tenant_id=tenant_id,
        customer_id=customer_id,
        tier_id=1,
        points_balance=SIGNUP_BONUS_POINTS,
    )
    session.add(loyalty)
    session.flush()

    session.add(
        PointsLedger(
            tenant_id=tenant_id,
            customer_loyalty_id=loyalty.id,
            entry_type="signup_bonus",
            points_delta=SIGNUP_BONUS_POINTS,
            note="Welcome bonus",
            idempotency_key=f"signup:{customer_id}",
        )
    )
    session.flush()
    return loyalty


def earn_points_for_invoice(
    session: Session,
    tenant_id: UUID,
    invoice: Invoice,
) -> int:
    """
    Award points when an invoice is paid. Returns points awarded (0 if skipped).
    Idempotent — duplicate calls for the same invoice are no-ops.
    """
    idempotency_key = f"invoice_earn:{invoice.id}"
    existing = session.exec(
        select(PointsLedger)
        .where(PointsLedger.tenant_id == tenant_id)
        .where(PointsLedger.idempotency_key == idempotency_key)
    ).first()
    if existing:
        return 0

    # Resolve customer: Invoice → RepairJob → Watch → customer_id
    job = session.get(RepairJob, invoice.repair_job_id)
    if not job:
        return 0
    watch = session.get(Watch, job.watch_id)
    if not watch:
        return 0
    customer_id = watch.customer_id

    loyalty = get_or_create_loyalty(session, tenant_id, customer_id)

    tiers = _get_tiers(session)
    rolling_spend = _rolling_12m_spend(session, loyalty.id)
    current_tier = _resolve_tier(tiers, rolling_spend)

    base_points = invoice.total_cents // 100
    multiplier = current_tier.earn_multiplier_x100
    awarded = (base_points * multiplier) // 100

    if awarded <= 0:
        return 0

    session.add(
        PointsLedger(
            tenant_id=tenant_id,
            customer_loyalty_id=loyalty.id,
            entry_type="earn",
            points_delta=awarded,
            source_invoice_id=invoice.id,
            source_amount_cents=invoice.total_cents,
            note=f"Invoice {invoice.invoice_number}",
            idempotency_key=idempotency_key,
        )
    )

    loyalty.points_balance += awarded

    # Recalc tier after this earn
    new_rolling = rolling_spend + invoice.total_cents
    new_tier = _resolve_tier(tiers, new_rolling)
    loyalty.tier_id = new_tier.id

    session.add(loyalty)
    session.flush()
    return awarded


def adjust_points(
    session: Session,
    tenant_id: UUID,
    customer_id: UUID,
    delta: int,
    note: str,
    actor_user_id: UUID,
) -> int:
    """Manual points adjustment by a manager. Returns new balance."""
    loyalty = get_or_create_loyalty(session, tenant_id, customer_id)

    new_balance = loyalty.points_balance + delta
    session.add(
        PointsLedger(
            tenant_id=tenant_id,
            customer_loyalty_id=loyalty.id,
            entry_type="adjust",
            points_delta=delta,
            note=note,
            idempotency_key=f"adjust:{uuid4()}",
        )
    )
    loyalty.points_balance = new_balance
    session.add(loyalty)
    session.flush()
    return new_balance


def build_loyalty_read(
    session: Session,
    loyalty: CustomerLoyalty,
    tier: LoyaltyTier,
) -> CustomerLoyaltyRead:
    rolling = _rolling_12m_spend(session, loyalty.id)
    return CustomerLoyaltyRead(
        customer_id=loyalty.customer_id,
        tier_id=tier.id,
        tier_name=tier.name,
        tier_label=tier.label,
        points_balance=loyalty.points_balance,
        points_dollar_value=round(loyalty.points_balance / 100, 2),
        rolling_12m_spend_cents=rolling,
        joined_at=loyalty.joined_at,
    )
