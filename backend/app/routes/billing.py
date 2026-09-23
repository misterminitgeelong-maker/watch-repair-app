"""Billing, plan limits, and Stripe subscription management."""

import logging
from datetime import datetime, timezone
from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Depends, Header, HTTPException, Request
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError
from sqlmodel import Session, func, select

from ..config import settings
from ..database import engine, get_session, unscoped_session
from ..dependencies import PLAN_LIMITS, AuthContext, get_auth_context, normalize_plan_code, require_owner
from ..models import (
    AutoKeyInvoice,
    AutoKeyJob,
    BillingCheckoutPlanRequest,
    BillingCheckoutRequest,
    BillingLimitsResponse,
    BillingPlanLimits,
    BillingLimitsUsage,
    NETWORK_ROLE_HQ,
    RepairJob,
    ShoeRepairJob,
    StripeWebhookEvent,
    Tenant,
    TenantEventLog,
    User,
)
from ..parent_network import sites_for_parent, sites_for_tenant

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


SHOP_PLAN_CODE = "basic_all_tabs"
_MINIT_PLAN_CODES = frozenset({"minit_hq", "booking_only"})
_LEGACY_BASIC_PLAN_CODES = frozenset(
    {
        "basic_watch",
        "basic_shoe",
        "basic_auto_key",
        "basic_watch_shoe",
        "basic_watch_auto_key",
        "basic_shoe_auto_key",
        "basic_all_tabs",
    }
)


def extra_location_quantity(site_count: int) -> int:
    """First location is included in Pro; additional sites are +A$25 each."""
    return max(0, int(site_count) - 1)


def _checkout_target_plan_code(plan_code: str) -> str:
    """New Checkout collapses the old tab ladder onto Shop (all tabs) or Pro."""
    if plan_code == "pro":
        return "pro"
    if plan_code in _LEGACY_BASIC_PLAN_CODES:
        return SHOP_PLAN_CODE
    raise HTTPException(status_code=400, detail=f"Unsupported plan code '{plan_code}'")


def _plan_code_from_price_id(price_id: str) -> Optional[str]:
    """Map a Stripe Price to a plan. Extra-location add-on returns None (not a plan)."""
    if not price_id:
        return None
    if settings.stripe_price_extra_location and price_id == settings.stripe_price_extra_location:
        return None
    price_map: dict[str, str] = {}
    if settings.stripe_price_shop:
        price_map[settings.stripe_price_shop] = SHOP_PLAN_CODE
    if settings.stripe_price_pro:
        price_map[settings.stripe_price_pro] = "pro"
    if settings.stripe_price_pro_legacy:
        price_map[settings.stripe_price_pro_legacy] = "pro"
    if settings.stripe_price_enterprise:
        price_map[settings.stripe_price_enterprise] = "pro"
    # Grandfathered tab-ladder prices — existing subscriptions only.
    if settings.stripe_price_watch:
        price_map[settings.stripe_price_watch] = "basic_watch"
    if settings.stripe_price_shoe:
        price_map[settings.stripe_price_shoe] = "basic_shoe"
    if settings.stripe_price_auto_key:
        price_map[settings.stripe_price_auto_key] = "basic_auto_key"
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


def _pro_price_id_for_new_checkout() -> str:
    pro_price = settings.stripe_price_pro or settings.stripe_price_enterprise
    if not pro_price:
        raise HTTPException(status_code=503, detail="Stripe Pro price is not configured")
    return pro_price


def _line_items_for_plan(plan_code: str, extra_location_qty: int = 0) -> list[dict[str, int | str]]:
    target = _checkout_target_plan_code(plan_code)
    if target == "pro":
        items: list[dict[str, int | str]] = [{"price": _pro_price_id_for_new_checkout(), "quantity": 1}]
        qty = max(0, extra_location_qty)
        if qty > 0:
            extra_price = settings.stripe_price_extra_location
            if not extra_price:
                raise HTTPException(
                    status_code=503,
                    detail="Stripe extra-location price is not configured",
                )
            items.append({"price": extra_price, "quantity": qty})
        return items

    if settings.stripe_price_shop:
        return [{"price": settings.stripe_price_shop, "quantity": 1}]

    # Dev/fallback: old tab-ladder Prices until STRIPE_PRICE_SHOP is set.
    tabs_count = _tabs_count_for_plan(target)
    if tabs_count <= 0:
        raise HTTPException(status_code=400, detail=f"Unsupported plan code '{plan_code}'")
    if not settings.stripe_price_basic_base:
        raise HTTPException(status_code=503, detail="Stripe Shop price is not configured")
    items = [{"price": settings.stripe_price_basic_base, "quantity": 1}]
    addon_count = max(0, tabs_count - 1)
    if addon_count > 0:
        if not settings.stripe_price_basic_addon_tab:
            raise HTTPException(status_code=503, detail="Stripe Basic add-on tab price is not configured")
        items.append({"price": settings.stripe_price_basic_addon_tab, "quantity": addon_count})
    return items


def _parent_id_for_tenant(session: Session, tenant_id: UUID) -> Optional[UUID]:
    sites = sites_for_tenant(session, tenant_id)
    if not sites:
        return None
    hq = next((site for site in sites if site.network_role == NETWORK_ROLE_HQ), None)
    return (hq or sites[0]).parent_account_id


def extra_location_quantity_for_parent(session: Session, parent_id: UUID) -> int:
    return extra_location_quantity(len(sites_for_parent(session, parent_id)))


def extra_location_quantity_for_tenant(session: Session, tenant_id: UUID) -> int:
    parent_id = _parent_id_for_tenant(session, tenant_id)
    if parent_id is None:
        return 0
    return extra_location_quantity_for_parent(session, parent_id)


def _billing_tenant_for_parent(session: Session, parent_id: UUID) -> Optional[Tenant]:
    hq_sites = sites_for_parent(session, parent_id, network_role=NETWORK_ROLE_HQ)
    if hq_sites:
        tenant = session.get(Tenant, hq_sites[0].tenant_id)
        if tenant:
            return tenant
    for site in sites_for_parent(session, parent_id):
        tenant = session.get(Tenant, site.tenant_id)
        if tenant and (tenant.stripe_subscription_id or "").strip():
            return tenant
    return None


def sync_extra_location_subscription(session: Session, parent_id: UUID) -> None:
    """Set the Pro subscription's extra-location item quantity to site_count - 1.

    No-op when Stripe is off, the parent is Minit, or there is no Pro subscription.
    Fails the request if Stripe is on, extra sites exist, and the extra Price is missing.
    """
    billing_tenant = _billing_tenant_for_parent(session, parent_id)
    if billing_tenant is None:
        return
    plan = normalize_plan_code(billing_tenant.plan_code)
    if plan in _MINIT_PLAN_CODES:
        return
    qty = extra_location_quantity_for_parent(session, parent_id)
    if qty <= 0 and not (billing_tenant.stripe_subscription_id or "").strip():
        return
    if not _stripe_configured():
        return
    if plan != "pro":
        return
    extra_price = settings.stripe_price_extra_location
    if qty > 0 and not extra_price:
        raise HTTPException(
            status_code=503,
            detail="Stripe extra-location price is not configured; cannot bill additional sites",
        )
    sub_id = (billing_tenant.stripe_subscription_id or "").strip()
    if not sub_id:
        if qty > 0:
            raise HTTPException(
                status_code=409,
                detail="Subscribe to Pro before adding extra shop locations",
            )
        return
    if not extra_price:
        return

    stripe = _get_stripe()
    try:
        sub = stripe.Subscription.retrieve(sub_id, expand=["items.data.price"])
        items = (sub.get("items") or {}).get("data") or []
        extra_item = None
        for item in items:
            price = item.get("price") or {}
            price_id = price.get("id") if isinstance(price, dict) else getattr(price, "id", None)
            if price_id == extra_price:
                extra_item = item
                break
        if qty <= 0:
            if extra_item:
                stripe.SubscriptionItem.delete(extra_item["id"])
            return
        current_qty = int(extra_item.get("quantity") or 0) if extra_item else 0
        if extra_item:
            if current_qty != qty:
                stripe.SubscriptionItem.modify(
                    extra_item["id"],
                    quantity=qty,
                    proration_behavior="create_prorations",
                )
        else:
            stripe.SubscriptionItem.create(
                subscription=sub_id,
                price=extra_price,
                quantity=qty,
                proration_behavior="create_prorations",
            )
    except HTTPException:
        raise
    except Exception:
        logging.getLogger(__name__).exception(
            "extra_location_sync_failed parent=%s tenant=%s", parent_id, billing_tenant.id
        )
        raise HTTPException(status_code=502, detail="Could not update extra-location billing on Stripe")


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
    session: Session = Depends(unscoped_session),
):
    plan_code = auth.plan_code
    limits = PLAN_LIMITS.get(plan_code, PLAN_LIMITS["pro"])

    counts = session.execute(
        text("""
            SELECT
                (SELECT COUNT(*) FROM "user"        WHERE tenant_id = CAST(:tid AS uuid) AND is_active = true) AS user_count,
                (SELECT COUNT(*) FROM repairjob     WHERE tenant_id = CAST(:tid AS uuid)) AS repair_job_count,
                (SELECT COUNT(*) FROM shoerepairjob WHERE tenant_id = CAST(:tid AS uuid)) AS shoe_job_count,
                (SELECT COUNT(*) FROM autokeyjob    WHERE tenant_id = CAST(:tid AS uuid)) AS auto_key_count
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
    xero_cfg = bool(
        (getattr(settings, "xero_client_id", "") or "").strip()
        and (getattr(settings, "xero_client_secret", "") or "").strip()
    )
    xero_conn = bool(
        tenant
        and (tenant.xero_connection_status or "") == "connected"
        and (tenant.xero_access_token or "").strip()
    )

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
        xero_configured=xero_cfg,
        xero_connected=xero_conn,
        xero_connection_status=tenant.xero_connection_status if tenant else None,
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
    session: Session = Depends(unscoped_session),
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
    session: Session = Depends(unscoped_session),
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
    session: Session = Depends(unscoped_session),
):
    stripe = _get_stripe()
    plan_code = _plan_code_from_price_id(payload.price_id)
    if not plan_code:
        raise HTTPException(status_code=400, detail="Unknown price ID — check Stripe price configuration")
    if plan_code in _LEGACY_BASIC_PLAN_CODES or plan_code == "pro":
        plan_code = _checkout_target_plan_code(plan_code)

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

    extra_qty = extra_location_quantity_for_tenant(session, tenant.id) if plan_code == "pro" else 0
    line_items = _line_items_for_plan(plan_code, extra_location_qty=extra_qty)
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
        line_items=line_items,
        success_url=f"{return_url}?billing=success",
        cancel_url=f"{return_url}?billing=cancelled",
        subscription_data=subscription_data,
    )
    return {"checkout_url": checkout_session.url}


@router.post("/checkout/plan")
def create_checkout_session_for_plan(
    payload: BillingCheckoutPlanRequest,
    auth: AuthContext = Depends(require_owner),
    session: Session = Depends(unscoped_session),
):
    stripe = _get_stripe()
    requested_plan = normalize_plan_code(payload.plan_code, default_if_empty="")
    if not requested_plan:
        raise HTTPException(status_code=400, detail="Invalid plan code")
    plan_code = _checkout_target_plan_code(requested_plan)

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

    extra_qty = extra_location_quantity_for_tenant(session, tenant.id) if plan_code == "pro" else 0
    line_items = _line_items_for_plan(plan_code, extra_location_qty=extra_qty)
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
    session: Session = Depends(unscoped_session),
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

# ── Stripe webhook event handlers ─────────────────────────────────────────────
# One function per event type, dispatched through _WEBHOOK_HANDLERS below. This
# was a single 197-line if/elif ladder with tenant lookup, plan extraction,
# status mapping and trial-date handling inlined in every branch.
#
# Each handler returns a status dict to answer with immediately, or None to fall
# through to the default acknowledgement. That mirrors the early `return`s the
# ladder already had, rather than changing when the endpoint answers early.


def _handle_subscription_upsert(session: Session, obj, _stripe) -> dict | None:
    """Subscription created or updated: sync plan, ids, status and trial end.

    Returns a status dict to send back immediately, or None to fall through
    to the default {"status": "ok"} acknowledgement.
    """
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
            # Sync subscription lifecycle status
            stripe_status = obj.get("status")
            # Only a subscription that is actually paying (or in its trial)
            # opens the shop. "incomplete" means the first payment hasn't gone
            # through; used to unlock anyway. A subscription that has lapsed
            # for good gates the shop again (past_due keeps its grace period).
            if stripe_status in ("active", "trialing"):
                tenant.signup_payment_pending = False
            elif stripe_status in ("unpaid", "incomplete_expired", "canceled") and not tenant.billing_exempt:
                tenant.signup_payment_pending = True
            if stripe_status in ("trialing", "active", "past_due", "canceled", "unpaid", "incomplete", "incomplete_expired"):
                tenant.subscription_status = stripe_status
            raw_trial_end = obj.get("trial_end")
            if raw_trial_end:
                tenant.trial_end = datetime.fromtimestamp(int(raw_trial_end), tz=timezone.utc)
            elif stripe_status != "trialing":
                tenant.trial_end = None
            session.add(tenant)
            session.commit()


def _handle_subscription_deleted(session: Session, obj, _stripe) -> dict | None:
    """Subscription cancelled: clear it and gate the tenant again.

    Returns a status dict to send back immediately, or None to fall through
    to the default {"status": "ok"} acknowledgement.
    """
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


def _handle_invoice_payment_failed(session: Session, obj, _stripe) -> dict | None:
    """A failed charge puts the tenant past_due.

    Returns a status dict to send back immediately, or None to fall through
    to the default {"status": "ok"} acknowledgement.
    """
    sub_id = (obj.get("subscription") or "")
    if sub_id:
        tenant = session.exec(
            select(Tenant).where(Tenant.stripe_subscription_id == sub_id)
        ).first()
        if tenant:
            tenant.subscription_status = "past_due"
            session.add(tenant)
            session.commit()


def _handle_invoice_paid(session: Session, obj, _stripe) -> dict | None:
    """A paid invoice revives a past_due tenant, and nothing else.

    Returns a status dict to send back immediately, or None to fall through
    to the default {"status": "ok"} acknowledgement.
    """
    sub_id = (obj.get("subscription") or "")
    if sub_id:
        tenant = session.exec(
            select(Tenant).where(Tenant.stripe_subscription_id == sub_id)
        ).first()
        if tenant and tenant.subscription_status == "past_due":
            tenant.subscription_status = "active"
            session.add(tenant)
            session.commit()


def _handle_checkout_completed(session: Session, obj, _stripe) -> dict | None:
    """Checkout finished: either a SaaS signup or an auto-key invoice payment.

    Returns a status dict to send back immediately, or None to fall through
    to the default {"status": "ok"} acknowledgement.
    """
    # SaaS signup: unlock tenant as soon as Checkout completes (subscription.* may arrive slightly later).
    if (obj.get("mode") or "") == "subscription":
        sub_id = obj.get("subscription")
        # Async methods (e.g. BECS direct debit) complete checkout before the
        # money arrives; the subscription webhook unlocks those once it does.
        paid = (obj.get("payment_status") or "") in ("paid", "no_payment_required")
        if sub_id and paid:
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
                # Let Stripe retry rather than acknowledge an unlock that didn't happen.
                raise
        return {"status": "ok"}
    # Invoice checkouts used to be destination charges on the platform account. New ones are
    # charged on the shop's own account and arrive through the Connect endpoint instead; this
    # path only finishes sessions started before that change.
    return _apply_invoice_checkout(session, obj, connect_account=None)


def _apply_invoice_checkout(session: Session, obj, *, connect_account: str | None) -> dict | None:
    """Mark an auto-key invoice paid from a completed Checkout session.

    ``connect_account`` is the connected account the event came from, when it
    came through the Connect endpoint; the invoice must belong to that shop.
    """
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
    if not invoice:
        return {"status": "ok"}
    if connect_account is not None:
        owner = session.get(Tenant, invoice.tenant_id)
        if not owner or (owner.stripe_connect_account_id or "").strip() != connect_account:
            # Metadata is only ours to trust when the money landed in the shop that owns the invoice.
            logging.getLogger(__name__).warning(
                "stripe.invoice_checkout_wrong_account invoice=%s account=%s", invoice.id, connect_account
            )
            return {"status": "ok"}
    if (obj.get("payment_status") or "") != "paid":
        return {"status": "ok"}
    amount_total = obj.get("amount_total")
    problem: str | None = None
    if invoice.status != "unpaid":
        problem = f"was already {invoice.status}"
    elif amount_total is not None and int(amount_total) != int(invoice.total_cents):
        problem = f"was for {invoice.total_cents} cents but {amount_total} cents was charged"
    if problem:
        # The customer's card was charged but the invoice can't take it (a
        # second checkout tab, paid in cash first, amount changed). This used
        # to be a log line; it needs a person to refund or reconcile it.
        logging.getLogger(__name__).error(
            "stripe.invoice_payment_unmatched invoice=%s session=%s problem=%s",
            invoice.id,
            obj.get("id"),
            problem,
        )
        session.add(
            TenantEventLog(
                tenant_id=invoice.tenant_id,
                entity_type="auto_key_invoice",
                entity_id=invoice.id,
                event_type="card_payment_needs_attention",
                event_summary=(
                    f"Card payment of {(int(amount_total or 0)) / 100:.2f} for invoice {invoice.invoice_number} "
                    f"{problem}. Check Stripe (checkout {obj.get('id')}) and refund if it's a double payment."
                ),
            )
        )
        session.commit()
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


def _handle_account_updated(session: Session, obj, _stripe) -> dict | None:
    """Stripe Connect capability flags changed for a connected account.

    Returns a status dict to send back immediately, or None to fall through
    to the default {"status": "ok"} acknowledgement.
    """
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



def _handle_connected_account_event(session: Session, event, obj, _stripe) -> dict | None:
    """An event from a shop's connected account (delivered via the Connect endpoint).

    Only what a connected account is allowed to tell us is handled: its own
    capability flags and card payments for its own invoices. Subscription and
    signup events are platform-only; a shop could otherwise create its own
    Checkout session with our metadata and unlock itself.
    """
    account = str(event.get("account") or "")
    event_type = event["type"]
    if event_type == "account.updated":
        if obj.get("id") != account:
            return {"status": "ok"}
        return _handle_account_updated(session, obj, _stripe)
    if event_type == "checkout.session.completed" and (obj.get("mode") or "") == "payment":
        return _apply_invoice_checkout(session, obj, connect_account=account)
    return {"status": "ok"}


_WEBHOOK_HANDLERS = {
    "customer.subscription.created": _handle_subscription_upsert,
    "customer.subscription.updated": _handle_subscription_upsert,
    "customer.subscription.deleted": _handle_subscription_deleted,
    "invoice.payment_failed": _handle_invoice_payment_failed,
    "invoice.paid": _handle_invoice_paid,
    "checkout.session.completed": _handle_checkout_completed,
    "account.updated": _handle_account_updated,
}


@router.post("/webhook")
async def stripe_webhook(
    request: Request,
    stripe_signature: str = Header(alias="stripe-signature", default=""),
    session: Session = Depends(unscoped_session),
):
    if not _stripe_configured():
        raise HTTPException(status_code=400, detail="Stripe not configured")
    secrets = [x for x in (settings.stripe_webhook_secret, settings.stripe_connect_webhook_secret) if x]
    if not secrets:
        raise HTTPException(status_code=503, detail="Stripe webhook secret not configured")

    try:
        import stripe as _stripe
        _stripe.api_key = settings.stripe_secret_key
    except ImportError:
        raise HTTPException(status_code=503, detail="Stripe library not installed")

    body = await request.body()
    # One URL serves both the platform endpoint and the Connect endpoint; each has its own secret.
    event = None
    for secret in secrets:
        try:
            event = _stripe.Webhook.construct_event(body, stripe_signature, secret)
            break
        except Exception:
            continue
    if event is None:
        raise HTTPException(status_code=400, detail="Invalid webhook signature")

    # Idempotency: Stripe redelivers events (retries, manual resends), so record
    # the event ID before applying it and acknowledge any repeat with a 200 so
    # Stripe stops retrying. A concurrent duplicate loses on the primary key.
    event_id = event["id"]
    if event_id:
        session.add(StripeWebhookEvent(id=event_id, event_type=event["type"]))
        try:
            session.commit()
        except IntegrityError:
            session.rollback()
            return {"status": "duplicate"}

    obj = event.data.object

    if event.get("account"):
        connected_event = event

        def handler(sess, o, st):
            return _handle_connected_account_event(sess, connected_event, o, st)
    else:
        handler = _WEBHOOK_HANDLERS.get(event["type"])
    if handler is not None:
        try:
            result = handler(session, obj, _stripe)
        except Exception:
            # The event id was recorded above so a concurrent duplicate is
            # skipped. If handling failed, forget it again: otherwise Stripe's
            # retry is answered "duplicate" and the update is lost for good.
            session.rollback()
            if event_id:
                with Session(engine) as cleanup:
                    row = cleanup.get(StripeWebhookEvent, event_id)
                    if row is not None:
                        cleanup.delete(row)
                        cleanup.commit()
            raise
        if result is not None:
            return result

    # Stripe retries anything it does not get a 2xx for, so every other event
    # type is acknowledged rather than erroring.
    return {"status": "ok"}
