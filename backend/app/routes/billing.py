"""Billing, plan limits, and Stripe subscription management."""

import logging
from datetime import datetime, timezone
from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Depends, Header, HTTPException, Request
from sqlmodel import Session, func, select

from ..config import settings
from ..database import get_session
from ..dependencies import PLAN_LIMITS, AuthContext, get_auth_context, normalize_plan_code, require_owner
from ..models import (
    AutoKeyInvoice,
    AutoKeyJob,
    BillingCheckoutPlanRequest,
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
        price_map[settings.stripe_price_watch] = "basic_watch"
    if settings.stripe_price_shoe:
        price_map[settings.stripe_price_shoe] = "basic_shoe"
    if settings.stripe_price_auto_key:
        price_map[settings.stripe_price_auto_key] = "basic_auto_key"
    if settings.stripe_price_enterprise:
        price_map[settings.stripe_price_enterprise] = "pro"
    if settings.stripe_price_pro:
        price_map[settings.stripe_price_pro] = "pro"
    return price_map.get(price_id)


def _tabs_count_for_plan(plan_code: str) -> int:
    mapping = {
        "basic_watch": 1,
        "basic_shoe": 1,
        "basic_auto_key": 1,
        "basic_watch_shoe": 2,
        "basic_watch_auto_key": 2,
        "basic_shoe_auto_key": 2,
        "basic_all_tabs": 3,
    }
    return mapping.get(plan_code, 0)


def _line_items_for_plan(plan_code: str) -> list[dict[str, int | str]]:
    if plan_code == "pro":
        pro_price = settings.stripe_price_pro or settings.stripe_price_enterprise
        if not pro_price:
            raise HTTPException(status_code=503, detail="Stripe Pro price is not configured")
        return [{"price": pro_price, "quantity": 1}]

    tabs_count = _tabs_count_for_plan(plan_code)
    if tabs_count <= 0:
        raise HTTPException(status_code=400, detail=f"Unsupported plan code '{plan_code}'")

    if not settings.stripe_price_basic_base:
        raise HTTPException(status_code=503, detail="Stripe Basic base price is not configured")

    items: list[dict[str, int | str]] = [{"price": settings.stripe_price_basic_base, "quantity": 1}]
    addon_count = max(0, tabs_count - 1)
    if addon_count > 0:
        if not settings.stripe_price_basic_addon_tab:
            raise HTTPException(status_code=503, detail="Stripe Basic add-on tab price is not configured")
        items.append({"price": settings.stripe_price_basic_addon_tab, "quantity": addon_count})

    return items


def _extract_plan_code_from_subscription(obj: dict) -> Optional[str]:
    metadata_plan = obj.get("metadata", {}).get("target_plan_code")
    if metadata_plan:
        return normalize_plan_code(metadata_plan, default_if_empty="") or None

    items = obj.get("items", {}).get("data", [])
    for item in items:
        price_id = item.get("price", {}).get("id", "")
        plan_code = _plan_code_from_price_id(price_id)
        if plan_code:
            return plan_code
    return None


# ── Limits (no Stripe required) ───────────────────────────────────────────────

@router.get("/limits", response_model=BillingLimitsResponse)
def get_billing_limits(
    auth: AuthContext = Depends(get_auth_context),
    session: Session = Depends(get_session),
):
    plan_code = auth.plan_code
    limits = PLAN_LIMITS.get(plan_code, PLAN_LIMITS["pro"])

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
            "metadata": {
                "tenant_id": str(tenant.id),
                "tenant_slug": tenant.slug,
                "target_plan_code": plan_code,
            }
        },
    )
    return {"checkout_url": checkout_session.url}


@router.post("/checkout/plan")
def create_checkout_session_for_plan(
    payload: BillingCheckoutPlanRequest,
    auth: AuthContext = Depends(require_owner),
    session: Session = Depends(get_session),
):
    stripe = _get_stripe()
    plan_code = normalize_plan_code(payload.plan_code, default_if_empty="")
    if not plan_code:
        raise HTTPException(status_code=400, detail="Invalid plan code")

    tenant = session.get(Tenant, auth.tenant_id)
    user = session.get(User, auth.user_id)
    if not tenant or not user:
        raise HTTPException(status_code=404, detail="Tenant not found")

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

    line_items = _line_items_for_plan(plan_code)
    return_url = f"{settings.public_base_url}/accounts"
    checkout_session = stripe.checkout.Session.create(
        customer=tenant.stripe_customer_id,
        mode="subscription",
        line_items=line_items,
        success_url=f"{return_url}?billing=success",
        cancel_url=f"{return_url}?billing=cancelled",
        subscription_data={
            "metadata": {
                "tenant_id": str(tenant.id),
                "tenant_slug": tenant.slug,
                "target_plan_code": plan_code,
            }
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
                plan_code = _extract_plan_code_from_subscription(obj)
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

    elif event["type"] == "checkout.session.completed":
        meta = obj.get("metadata") or {}
        if meta.get("purpose") != "auto_key_invoice":
            return {"status": "ok"}
        inv_raw = meta.get("auto_key_invoice_id")
        if not inv_raw:
            return {"status": "ok"}
        try:
            inv_uuid = UUID(str(inv_raw))
        except ValueError:
            return {"status": "ok"}
        invoice = session.get(AutoKeyInvoice, inv_uuid)
        if not invoice or invoice.status != "unpaid":
            return {"status": "ok"}
        if (obj.get("payment_status") or "") != "paid":
            return {"status": "ok"}
        amount_total = obj.get("amount_total")
        if amount_total is not None and int(amount_total) != int(invoice.total_cents):
            logging.getLogger(__name__).warning(
                "Stripe checkout amount_total %s != invoice.total_cents %s for invoice %s",
                amount_total,
                invoice.total_cents,
                invoice.id,
            )
            return {"status": "ok"}
        invoice.status = "paid"
        invoice.payment_method = "stripe"
        invoice.paid_at = datetime.now(timezone.utc)
        session.add(invoice)
        session.commit()

    return {"status": "ok"}
