"""Billing, plan limits, and Stripe subscription management."""

import logging
from datetime import datetime, timezone

logger = logging.getLogger(__name__)
from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Depends, Header, HTTPException, Request
from sqlalchemy import text
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
    StripeWebhookEvent,
    Tenant,
    TenantEventLog,
    User,
)
from sqlalchemy.exc import IntegrityError

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

    counts = session.execute(
        text("""
            SELECT
                (SELECT COUNT(*) FROM "user"        WHERE tenant_id = :tid::uuid AND is_active = true) AS user_count,
                (SELECT COUNT(*) FROM repairjob     WHERE tenant_id = :tid::uuid) AS repair_job_count,
                (SELECT COUNT(*) FROM shoerepairjob WHERE tenant_id = :tid::uuid) AS shoe_job_count,
                (SELECT COUNT(*) FROM autokeyjob    WHERE tenant_id = :tid::uuid) AS auto_key_count
        """),
        {"tid": str(auth.tenant_id)},
    ).one()
    user_count = int(counts.user_count)
    repair_job_count = int(counts.repair_job_count)
    shoe_job_count = int(counts.shoe_job_count)
    auto_key_count = int(counts.auto_key_count)

    tenant = session.get(Tenant, auth.tenant_id)
    stripe_sub_id = tenant.stripe_subscription_id if tenant else None
    stripe_cust_id = tenant.stripe_customer_id if tenant else None
    conn_present = bool(tenant and (tenant.stripe_connect_account_id or "").strip())
    conn_charges = bool(tenant and tenant.stripe_connect_charges_enabled)
    conn_payouts = bool(tenant and tenant.stripe_connect_payouts_enabled)
    conn_details = bool(tenant and tenant.stripe_connect_details_submitted)

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
        stripe_connect_account_present=conn_present,
        stripe_connect_charges_enabled=conn_charges,
        stripe_connect_payouts_enabled=conn_payouts,
        stripe_connect_details_submitted=conn_details,
    )


def _refresh_tenant_connect_status(session: Session, tenant: Tenant) -> None:
    if not tenant.stripe_connect_account_id:
        return
    try:
        stripe = _get_stripe()
        acct = stripe.Account.retrieve(tenant.stripe_connect_account_id)
    except HTTPException:
        return
    except Exception:
        logging.getLogger(__name__).exception("Stripe Connect retrieve failed for %s", tenant.stripe_connect_account_id)
        return
    tenant.stripe_connect_charges_enabled = bool(acct.get("charges_enabled"))
    tenant.stripe_connect_payouts_enabled = bool(acct.get("payouts_enabled"))
    tenant.stripe_connect_details_submitted = bool(acct.get("details_submitted"))
    session.add(tenant)


@router.post("/connect/account-link")
def create_stripe_connect_account_link(
    auth: AuthContext = Depends(require_owner),
    session: Session = Depends(get_session),
):
    """Create or continue Express Connect onboarding; returns Stripe-hosted onboarding URL."""
    stripe = _get_stripe()
    tenant = session.get(Tenant, auth.tenant_id)
    if not tenant:
        raise HTTPException(status_code=404, detail="Tenant not found")

    country = (settings.stripe_connect_default_country or "AU").strip().upper()[:2]
    if len(country) != 2:
        raise HTTPException(status_code=503, detail="Invalid STRIPE_CONNECT_DEFAULT_COUNTRY")

    if not tenant.stripe_connect_account_id:
        account = stripe.Account.create(
            type="express",
            country=country,
            capabilities={"card_payments": {"requested": True}, "transfers": {"requested": True}},
            metadata={"tenant_id": str(tenant.id), "tenant_slug": tenant.slug},
            business_profile={"name": (tenant.name or "Shop")[:100]},
        )
        tenant.stripe_connect_account_id = account.id
        tenant.stripe_connect_charges_enabled = bool(account.get("charges_enabled"))
        tenant.stripe_connect_payouts_enabled = bool(account.get("payouts_enabled"))
        tenant.stripe_connect_details_submitted = bool(account.get("details_submitted"))
        session.add(tenant)
        session.add(
            TenantEventLog(
                tenant_id=tenant.id,
                entity_type="tenant",
                event_type="stripe_connect_account_created",
                event_summary="Stripe Express connected account created for invoice payouts",
            )
        )
        session.commit()
        session.refresh(tenant)

    base = settings.public_base_url.rstrip("/")
    link = stripe.AccountLink.create(
        account=tenant.stripe_connect_account_id,
        refresh_url=f"{base}/accounts?connect=refresh",
        return_url=f"{base}/accounts?connect=return",
        type="account_onboarding",
    )
    return {"url": link.url}


@router.post("/connect/refresh")
def refresh_stripe_connect_status(
    auth: AuthContext = Depends(require_owner),
    session: Session = Depends(get_session),
):
    """Pull latest Connect capability flags from Stripe (e.g. after returning from onboarding)."""
    tenant = session.get(Tenant, auth.tenant_id)
    if not tenant or not tenant.stripe_connect_account_id:
        raise HTTPException(status_code=400, detail="No Stripe Connect account for this workspace.")
    _refresh_tenant_connect_status(session, tenant)
    session.commit()
    session.refresh(tenant)
    return {
        "stripe_connect_charges_enabled": tenant.stripe_connect_charges_enabled,
        "stripe_connect_payouts_enabled": tenant.stripe_connect_payouts_enabled,
        "stripe_connect_details_submitted": tenant.stripe_connect_details_submitted,
    }


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
    subscription_data: dict = {
        "metadata": {
            "tenant_id": str(tenant.id),
            "tenant_slug": tenant.slug,
            "target_plan_code": plan_code,
        }
    }
    if settings.stripe_trial_period_days > 0:
        subscription_data["trial_period_days"] = settings.stripe_trial_period_days
    checkout_session = stripe.checkout.Session.create(
        customer=tenant.stripe_customer_id,
        mode="subscription",
        line_items=[{"price": payload.price_id, "quantity": 1}],
        success_url=f"{return_url}?billing=success",
        cancel_url=f"{return_url}?billing=cancelled",
        subscription_data=subscription_data,
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
    subscription_data_plan: dict = {
        "metadata": {
            "tenant_id": str(tenant.id),
            "tenant_slug": tenant.slug,
            "target_plan_code": plan_code,
        }
    }
    if settings.stripe_trial_period_days > 0:
        subscription_data_plan["trial_period_days"] = settings.stripe_trial_period_days
    checkout_session = stripe.checkout.Session.create(
        customer=tenant.stripe_customer_id,
        mode="subscription",
        line_items=line_items,
        success_url=f"{return_url}?billing=success",
        cancel_url=f"{return_url}?billing=cancelled",
        subscription_data=subscription_data_plan,
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

    # Idempotency: Stripe retries any delivery that doesn't receive a 2xx in
    # time. Insert event.id into a ledger table under a unique constraint; a
    # duplicate delivery will fail the insert and we short-circuit. This must
    # happen BEFORE any side effects so that concurrent retries can't both
    # commit plan changes / event log entries for the same event.
    event_id = event.get("id") if isinstance(event, dict) else getattr(event, "id", None)
    if event_id:
        try:
            session.add(StripeWebhookEvent(event_id=event_id, event_type=event.get("type", "")))
            session.commit()
        except IntegrityError:
            session.rollback()
            logger.info("stripe_webhook.duplicate event_id=%s type=%s", event_id, event.get("type"))
            return {"status": "duplicate", "event_id": event_id}

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
                tenant.signup_payment_pending = False
                # Sync subscription lifecycle status
                stripe_status = obj.get("status")
                if stripe_status in ("trialing", "active", "past_due", "canceled", "unpaid", "incomplete", "incomplete_expired"):
                    tenant.subscription_status = stripe_status
                raw_trial_end = obj.get("trial_end")
                if raw_trial_end:
                    tenant.trial_end = datetime.fromtimestamp(int(raw_trial_end), tz=timezone.utc)
                elif stripe_status != "trialing":
                    tenant.trial_end = None
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
                tenant.subscription_status = "canceled"
                tenant.trial_end = None
                tenant.signup_payment_pending = True
                session.add(tenant)
                session.commit()

    elif event["type"] == "invoice.payment_failed":
        sub_id = (obj.get("subscription") or "")
        if sub_id:
            tenant = session.exec(
                select(Tenant).where(Tenant.stripe_subscription_id == sub_id)
            ).first()
            if tenant:
                tenant.subscription_status = "past_due"
                session.add(tenant)
                session.commit()

    elif event["type"] == "invoice.paid":
        sub_id = (obj.get("subscription") or "")
        if sub_id:
            tenant = session.exec(
                select(Tenant).where(Tenant.stripe_subscription_id == sub_id)
            ).first()
            if tenant and tenant.subscription_status == "past_due":
                tenant.subscription_status = "active"
                session.add(tenant)
                session.commit()

    elif event["type"] == "checkout.session.completed":
        # SaaS signup: unlock tenant as soon as Checkout completes (subscription.* may arrive slightly later).
        if (obj.get("mode") or "") == "subscription":
            sub_id = obj.get("subscription")
            if sub_id:
                try:
                    _stripe.api_key = settings.stripe_secret_key
                    sub = _stripe.Subscription.retrieve(sub_id)
                    tenant_id_str = (sub.get("metadata") or {}).get("tenant_id")
                    if tenant_id_str:
                        try:
                            tid = UUID(str(tenant_id_str))
                        except ValueError:
                            tid = None
                        if tid:
                            tenant = session.get(Tenant, tid)
                            if tenant:
                                tenant.signup_payment_pending = False
                                tenant.stripe_subscription_id = str(sub_id)
                                cust = obj.get("customer")
                                if cust:
                                    tenant.stripe_customer_id = str(cust)
                                session.add(tenant)
                                session.commit()
                except Exception:
                    logging.getLogger(__name__).exception("checkout.session.completed subscription unlock failed")
            return {"status": "ok"}
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
        # Auto-advance job status to invoice_paid
        job = session.get(AutoKeyJob, invoice.auto_key_job_id)
        if job and job.status != "invoice_paid":
            job.status = "invoice_paid"
            session.add(job)
        session.commit()

    elif event["type"] == "account.updated":
        acct_id = obj.get("id")
        meta = obj.get("metadata") or {}
        tenant = None
        if acct_id:
            tenant = session.exec(
                select(Tenant).where(Tenant.stripe_connect_account_id == acct_id)
            ).first()
        if not tenant and meta.get("tenant_id"):
            try:
                tid = UUID(str(meta["tenant_id"]))
                tenant = session.get(Tenant, tid)
            except ValueError:
                tenant = None
        if tenant:
            if acct_id and not (tenant.stripe_connect_account_id or "").strip():
                tenant.stripe_connect_account_id = acct_id
            tenant.stripe_connect_charges_enabled = bool(obj.get("charges_enabled"))
            tenant.stripe_connect_payouts_enabled = bool(obj.get("payouts_enabled"))
            tenant.stripe_connect_details_submitted = bool(obj.get("details_submitted"))
            session.add(tenant)
            session.commit()

    return {"status": "ok"}
