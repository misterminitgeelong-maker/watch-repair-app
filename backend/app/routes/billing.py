"""Billing, plan limits, and Stripe subscription management."""

from datetime import datetime, timezone
from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Depends, Header, HTTPException, Request
from sqlmodel import Session, func, select

from ..config import settings
from ..database import get_session
from ..dependencies import PLAN_LIMITS, AuthContext, get_auth_context, require_owner
from ..models import (
    AutoKeyJob,
    BillingCheckoutRequest,
    BillingLimitsResponse,
    BillingPlanLimits,
    BillingLimitsUsage,
    RepairJob,
    ShoeRepairJob,
    Tenant,
    TenantEventLog,
    User,
)

router = APIRouter(prefix="/v1/billing", tags=["billing"])


def _stripe_configured() -> bool:
    return bool(settings.stripe_secret_key)


def _get_stripe():
    if not _stripe_configured():
        raise HTTPException(status_code=503, detail="Stripe is not configured on this server")
    try:
        import stripe as _stripe
        _stripe.api_key = settings.stripe_secret_key
        return _stripe
    except ImportError:
        raise HTTPException(status_code=503, detail="Stripe library not installed")


def _plan_code_from_price_id(price_id: str) -> Optional[str]:
    price_map: dict[str, str] = {}
    if settings.stripe_price_watch:
        price_map[settings.stripe_price_watch] = "watch"
    if settings.stripe_price_shoe:
        price_map[settings.stripe_price_shoe] = "shoe"
    if settings.stripe_price_auto_key:
        price_map[settings.stripe_price_auto_key] = "auto_key"
    if settings.stripe_price_enterprise:
        price_map[settings.stripe_price_enterprise] = "enterprise"
    return price_map.get(price_id)


# ── Limits (no Stripe required) ───────────────────────────────────────────────

@router.get("/limits", response_model=BillingLimitsResponse)
def get_billing_limits(
    auth: AuthContext = Depends(get_auth_context),
    session: Session = Depends(get_session),
):
    plan_code = auth.plan_code
    limits = PLAN_LIMITS.get(plan_code, PLAN_LIMITS["enterprise"])

    user_count = int(
        session.exec(
            select(func.count())
            .select_from(User)
            .where(User.tenant_id == auth.tenant_id)
            .where(User.is_active == True)
        ).one()
    )
    repair_job_count = int(
        session.exec(
            select(func.count()).select_from(RepairJob).where(RepairJob.tenant_id == auth.tenant_id)
        ).one()
    )
    shoe_job_count = int(
        session.exec(
            select(func.count()).select_from(ShoeRepairJob).where(ShoeRepairJob.tenant_id == auth.tenant_id)
        ).one()
    )
    auto_key_count = int(
        session.exec(
            select(func.count()).select_from(AutoKeyJob).where(AutoKeyJob.tenant_id == auth.tenant_id)
        ).one()
    )

    tenant = session.get(Tenant, auth.tenant_id)
    stripe_sub_id = tenant.stripe_subscription_id if tenant else None
    stripe_cust_id = tenant.stripe_customer_id if tenant else None

    return BillingLimitsResponse(
        plan_code=plan_code,
        limits=BillingPlanLimits(
            max_users=limits["max_users"],
            max_repair_jobs=limits["max_repair_jobs"],
            max_shoe_jobs=limits["max_shoe_jobs"],
            max_auto_key_jobs=limits["max_auto_key_jobs"],
        ),
        usage=BillingLimitsUsage(
            users=user_count,
            repair_jobs=repair_job_count,
            shoe_jobs=shoe_job_count,
            auto_key_jobs=auto_key_count,
        ),
        stripe_configured=_stripe_configured(),
        stripe_subscription_id=stripe_sub_id,
        stripe_customer_id=stripe_cust_id,
    )


# ── Stripe Checkout ───────────────────────────────────────────────────────────

@router.post("/checkout")
def create_checkout_session(
    payload: BillingCheckoutRequest,
    auth: AuthContext = Depends(require_owner),
    session: Session = Depends(get_session),
):
    stripe = _get_stripe()
    plan_code = _plan_code_from_price_id(payload.price_id)
    if not plan_code:
        raise HTTPException(status_code=400, detail="Unknown price ID — check Stripe price configuration")

    tenant = session.get(Tenant, auth.tenant_id)
    user = session.get(User, auth.user_id)
    if not tenant or not user:
        raise HTTPException(status_code=404, detail="Tenant not found")

    # Ensure Stripe Customer exists
    if not tenant.stripe_customer_id:
        customer = stripe.Customer.create(
            email=user.email,
            name=tenant.name,
            metadata={"tenant_id": str(tenant.id), "tenant_slug": tenant.slug},
        )
        tenant.stripe_customer_id = customer.id
        session.add(tenant)
        session.commit()
        session.refresh(tenant)

    return_url = f"{settings.public_base_url}/accounts"
    checkout_session = stripe.checkout.Session.create(
        customer=tenant.stripe_customer_id,
        mode="subscription",
        line_items=[{"price": payload.price_id, "quantity": 1}],
        success_url=f"{return_url}?billing=success",
        cancel_url=f"{return_url}?billing=cancelled",
        subscription_data={
            "metadata": {"tenant_id": str(tenant.id), "tenant_slug": tenant.slug}
        },
    )
    return {"checkout_url": checkout_session.url}


# ── Stripe Customer Portal ────────────────────────────────────────────────────

@router.get("/portal-url")
def get_portal_url(
    auth: AuthContext = Depends(require_owner),
    session: Session = Depends(get_session),
):
    stripe = _get_stripe()
    tenant = session.get(Tenant, auth.tenant_id)
    if not tenant or not tenant.stripe_customer_id:
        raise HTTPException(
            status_code=400,
            detail="No Stripe customer linked. Subscribe to a plan first.",
        )
    portal = stripe.billing_portal.Session.create(
        customer=tenant.stripe_customer_id,
        return_url=f"{settings.public_base_url}/accounts",
    )
    return {"url": portal.url}


# ── Stripe Webhook ─────────────────────────────────────────────────────────────

@router.post("/webhook")
async def stripe_webhook(
    request: Request,
    stripe_signature: str = Header(alias="stripe-signature", default=""),
    session: Session = Depends(get_session),
):
    if not _stripe_configured():
        raise HTTPException(status_code=400, detail="Stripe not configured")
    if not settings.stripe_webhook_secret:
        raise HTTPException(status_code=503, detail="Stripe webhook secret not configured")

    try:
        import stripe as _stripe
        _stripe.api_key = settings.stripe_secret_key
    except ImportError:
        raise HTTPException(status_code=503, detail="Stripe library not installed")

    body = await request.body()
    try:
        event = _stripe.Webhook.construct_event(body, stripe_signature, settings.stripe_webhook_secret)
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid webhook signature")

    obj = event.data.object

    if event["type"] in ("customer.subscription.created", "customer.subscription.updated"):
        tenant_id_str = obj.get("metadata", {}).get("tenant_id")
        if tenant_id_str:
            try:
                tenant_id = UUID(tenant_id_str)
            except ValueError:
                return {"status": "ignored"}
            tenant = session.get(Tenant, tenant_id)
            if tenant:
                items = obj.get("items", {}).get("data", [])
                if items:
                    price_id = items[0].get("price", {}).get("id", "")
                    plan_code = _plan_code_from_price_id(price_id)
                    if plan_code:
                        old_plan = tenant.plan_code
                        tenant.plan_code = plan_code
                        if plan_code != old_plan:
                            session.add(
                                TenantEventLog(
                                    tenant_id=tenant.id,
                                    entity_type="tenant",
                                    event_type="plan_changed",
                                    event_summary=(
                                        f"Plan changed from '{old_plan}' to '{plan_code}' via Stripe"
                                    ),
                                )
                            )
                tenant.stripe_subscription_id = obj.get("id")
                tenant.stripe_customer_id = obj.get("customer")
                session.add(tenant)
                session.commit()

    elif event["type"] == "customer.subscription.deleted":
        sub_id = obj.get("id")
        if sub_id:
            tenant = session.exec(
                select(Tenant).where(Tenant.stripe_subscription_id == sub_id)
            ).first()
            if tenant:
                tenant.stripe_subscription_id = None
                session.add(tenant)
                session.commit()

    return {"status": "ok"}
