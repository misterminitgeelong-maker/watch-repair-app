"""Characterisation tests for every Stripe event type the webhook handles.

Written *before* splitting `stripe_webhook` into per-event handlers, against the
original 197-line if/elif ladder, so the refactor has something to be measured
against. Of the seven event types the endpoint handled, exactly one
(`customer.subscription.updated`) had a test — and that one was about
idempotency, not about what the branch does.

These assert observable outcomes — what ends up in the database — rather than
how the code is arranged, so they stay meaningful after the split.
"""
from __future__ import annotations

import json
import time
from uuid import UUID, uuid4

import pytest
import stripe
from sqlmodel import Session, select

from app.config import settings
from app.database import engine
from app.models import Tenant

WEBHOOK_SECRET = "whsec_test_secret"


@pytest.fixture
def stripe_configured(monkeypatch):
    monkeypatch.setattr(settings, "stripe_secret_key", "sk_test_123")
    monkeypatch.setattr(settings, "stripe_webhook_secret", WEBHOOK_SECRET)


def _signed(payload: str) -> dict[str, str]:
    ts = int(time.time())
    sig = stripe.WebhookSignature._compute_signature(f"{ts}.{payload}", WEBHOOK_SECRET)
    return {"stripe-signature": f"t={ts},v1={sig}", "content-type": "application/json"}


def _event(event_type: str, obj: dict) -> str:
    return json.dumps(
        {
            "id": f"evt_{uuid4().hex[:12]}",
            "object": "event",
            "api_version": "2024-06-20",
            "type": event_type,
            "data": {"object": obj},
        }
    )


def _post(client, event_type: str, obj: dict):
    payload = _event(event_type, obj)
    return client.post("/v1/billing/webhook", content=payload, headers=_signed(payload))


def _tenant_id(client, auth_headers) -> UUID:
    me = client.get("/v1/auth/session", headers=auth_headers)
    assert me.status_code == 200, me.text
    return UUID(me.json()["tenant_id"])


def _reload(tenant_id: UUID) -> Tenant:
    with Session(engine) as s:
        return s.get(Tenant, tenant_id)


def _set(tenant_id: UUID, **fields) -> None:
    with Session(engine) as s:
        t = s.get(Tenant, tenant_id)
        for k, v in fields.items():
            setattr(t, k, v)
        s.add(t)
        s.commit()


# ── customer.subscription.created / updated ───────────────────────────────────


def test_subscription_created_records_ids_and_clears_signup_pending(
    client, auth_headers, stripe_configured
):
    tid = _tenant_id(client, auth_headers)
    _set(tid, signup_payment_pending=True, stripe_subscription_id=None)

    r = _post(client, "customer.subscription.created", {
        "id": "sub_created_1", "object": "subscription", "customer": "cus_created_1",
        "status": "active", "trial_end": None,
        "metadata": {"tenant_id": str(tid)}, "items": {"data": []},
    })

    assert r.status_code == 200
    t = _reload(tid)
    assert t.stripe_subscription_id == "sub_created_1"
    assert t.stripe_customer_id == "cus_created_1"
    assert t.signup_payment_pending is False
    assert t.subscription_status == "active"


def test_subscription_trial_end_is_stored_and_cleared_with_status(
    client, auth_headers, stripe_configured
):
    """trial_end is kept while trialing and cleared once the status moves on."""
    tid = _tenant_id(client, auth_headers)

    _post(client, "customer.subscription.updated", {
        "id": "sub_trial", "object": "subscription", "customer": "cus_trial",
        "status": "trialing", "trial_end": 1893456000,  # 2030-01-01
        "metadata": {"tenant_id": str(tid)}, "items": {"data": []},
    })
    assert _reload(tid).trial_end is not None

    _post(client, "customer.subscription.updated", {
        "id": "sub_trial", "object": "subscription", "customer": "cus_trial",
        "status": "active", "trial_end": None,
        "metadata": {"tenant_id": str(tid)}, "items": {"data": []},
    })
    assert _reload(tid).trial_end is None


def test_subscription_event_with_a_malformed_tenant_id_is_ignored(
    client, auth_headers, stripe_configured
):
    r = _post(client, "customer.subscription.updated", {
        "id": "sub_bad", "object": "subscription", "customer": "cus_bad",
        "status": "active", "trial_end": None,
        "metadata": {"tenant_id": "not-a-uuid"}, "items": {"data": []},
    })
    assert r.status_code == 200
    assert r.json()["status"] == "ignored"


def test_subscription_event_for_an_unknown_tenant_is_a_no_op(
    client, auth_headers, stripe_configured
):
    r = _post(client, "customer.subscription.updated", {
        "id": "sub_ghost", "object": "subscription", "customer": "cus_ghost",
        "status": "active", "trial_end": None,
        "metadata": {"tenant_id": str(uuid4())}, "items": {"data": []},
    })
    assert r.status_code == 200


# ── customer.subscription.deleted ─────────────────────────────────────────────


def test_subscription_deleted_cancels_and_re_gates_the_tenant(
    client, auth_headers, stripe_configured
):
    tid = _tenant_id(client, auth_headers)
    _set(tid, stripe_subscription_id="sub_del_1", subscription_status="active",
         signup_payment_pending=False)

    r = _post(client, "customer.subscription.deleted", {"id": "sub_del_1", "object": "subscription"})

    assert r.status_code == 200
    t = _reload(tid)
    assert t.stripe_subscription_id is None
    assert t.subscription_status == "canceled"
    assert t.trial_end is None
    assert t.signup_payment_pending is True, "a cancelled tenant must be gated again"


# ── invoice.payment_failed / invoice.paid ─────────────────────────────────────


def test_payment_failed_marks_past_due(client, auth_headers, stripe_configured):
    tid = _tenant_id(client, auth_headers)
    _set(tid, stripe_subscription_id="sub_pf_1", subscription_status="active")

    _post(client, "invoice.payment_failed", {"id": "in_1", "subscription": "sub_pf_1"})

    assert _reload(tid).subscription_status == "past_due"


def test_invoice_paid_recovers_only_from_past_due(client, auth_headers, stripe_configured):
    """The branch is deliberately narrow: it revives a past_due tenant and does
    not otherwise overwrite whatever status the subscription events set."""
    tid = _tenant_id(client, auth_headers)

    _set(tid, stripe_subscription_id="sub_ip_1", subscription_status="past_due")
    _post(client, "invoice.paid", {"id": "in_2", "subscription": "sub_ip_1"})
    assert _reload(tid).subscription_status == "active"

    _set(tid, subscription_status="trialing")
    _post(client, "invoice.paid", {"id": "in_3", "subscription": "sub_ip_1"})
    assert _reload(tid).subscription_status == "trialing", "must not clobber a non past_due status"


# ── account.updated (Stripe Connect) ──────────────────────────────────────────


def test_account_updated_syncs_connect_capability_flags(
    client, auth_headers, stripe_configured
):
    tid = _tenant_id(client, auth_headers)
    _set(tid, stripe_connect_account_id="acct_1")

    _post(client, "account.updated", {
        "id": "acct_1", "object": "account",
        "charges_enabled": True, "payouts_enabled": True, "details_submitted": True,
        "metadata": {},
    })

    t = _reload(tid)
    assert t.stripe_connect_charges_enabled is True
    assert t.stripe_connect_payouts_enabled is True
    assert t.stripe_connect_details_submitted is True


def test_account_updated_falls_back_to_tenant_id_metadata(
    client, auth_headers, stripe_configured
):
    """Connect accounts are matched by account id, or by metadata when this is
    the first event and the id has not been stored yet."""
    tid = _tenant_id(client, auth_headers)
    _set(tid, stripe_connect_account_id=None)

    _post(client, "account.updated", {
        "id": "acct_new_1", "object": "account",
        "charges_enabled": True, "payouts_enabled": False, "details_submitted": True,
        "metadata": {"tenant_id": str(tid)},
    })

    t = _reload(tid)
    assert t.stripe_connect_account_id == "acct_new_1", "account id should be adopted"
    assert t.stripe_connect_charges_enabled is True
    assert t.stripe_connect_payouts_enabled is False


# ── checkout.session.completed ────────────────────────────────────────────────


def test_checkout_session_for_a_non_subscription_without_purpose_is_a_no_op(
    client, auth_headers, stripe_configured
):
    r = _post(client, "checkout.session.completed", {
        "id": "cs_1", "object": "checkout.session", "mode": "payment",
        "metadata": {}, "payment_status": "paid",
    })
    assert r.status_code == 200
    assert r.json()["status"] == "ok"


def test_checkout_session_ignores_an_unknown_auto_key_invoice(
    client, auth_headers, stripe_configured
):
    r = _post(client, "checkout.session.completed", {
        "id": "cs_2", "object": "checkout.session", "mode": "payment",
        "metadata": {"purpose": "auto_key_invoice", "auto_key_invoice_id": str(uuid4())},
        "payment_status": "paid", "amount_total": 1000,
    })
    assert r.status_code == 200
    assert r.json()["status"] == "ok"


def test_checkout_session_with_a_malformed_invoice_id_is_a_no_op(
    client, auth_headers, stripe_configured
):
    r = _post(client, "checkout.session.completed", {
        "id": "cs_3", "object": "checkout.session", "mode": "payment",
        "metadata": {"purpose": "auto_key_invoice", "auto_key_invoice_id": "nope"},
        "payment_status": "paid",
    })
    assert r.status_code == 200
    assert r.json()["status"] == "ok"


# ── dispatch behaviour ────────────────────────────────────────────────────────


def test_an_unhandled_event_type_is_acknowledged(client, auth_headers, stripe_configured):
    """Stripe retries anything it does not get a 2xx for, so an event type this
    app does not care about must still be acknowledged rather than erroring."""
    r = _post(client, "customer.created", {"id": "cus_x", "object": "customer"})
    assert r.status_code == 200
    assert r.json()["status"] == "ok"


# ── fixes from the Sep 2026 walkthrough ─────────────────────────────────────────


def test_incomplete_subscription_does_not_unlock_the_shop(client, auth_headers, stripe_configured):
    tid = _tenant_id(client, auth_headers)
    _set(tid, signup_payment_pending=True, stripe_subscription_id=None)
    r = _post(client, "customer.subscription.created", {
        "id": "sub_incomplete_1", "object": "subscription", "customer": "cus_inc_1",
        "status": "incomplete", "trial_end": None,
        "metadata": {"tenant_id": str(tid)}, "items": {"data": []},
    })
    assert r.status_code == 200
    assert _reload(tid).signup_payment_pending is True


def test_a_failed_handler_lets_stripe_retry_the_same_event(client, auth_headers, stripe_configured, monkeypatch):
    import app.routes.billing as billing

    tid = _tenant_id(client, auth_headers)
    _set(tid, signup_payment_pending=True, stripe_subscription_id=None)
    payload = _event("customer.subscription.created", {
        "id": "sub_retry_1", "object": "subscription", "customer": "cus_retry_1",
        "status": "active", "trial_end": None,
        "metadata": {"tenant_id": str(tid)}, "items": {"data": []},
    })
    real = billing._WEBHOOK_HANDLERS["customer.subscription.created"]

    def _boom(*_a, **_k):
        raise RuntimeError("database blip")

    monkeypatch.setitem(billing._WEBHOOK_HANDLERS, "customer.subscription.created", _boom)
    with pytest.raises(RuntimeError):
        client.post("/v1/billing/webhook", content=payload, headers=_signed(payload))
    monkeypatch.setitem(billing._WEBHOOK_HANDLERS, "customer.subscription.created", real)

    retry = client.post("/v1/billing/webhook", content=payload, headers=_signed(payload))
    assert retry.status_code == 200
    assert retry.json().get("status") != "duplicate"
    assert _reload(tid).stripe_subscription_id == "sub_retry_1"


def test_card_payment_on_an_already_paid_invoice_alerts_the_shop(client, auth_headers, stripe_configured):
    from app.models import AutoKeyInvoice, AutoKeyJob, Customer, TenantEventLog

    tid = _tenant_id(client, auth_headers)
    with Session(engine) as s:
        customer = Customer(tenant_id=tid, full_name="Double Payer")
        s.add(customer)
        s.flush()
        job = AutoKeyJob(tenant_id=tid, customer_id=customer.id, job_number=f"AK-{uuid4().hex[:6]}", title="Key")
        s.add(job)
        s.flush()
        invoice = AutoKeyInvoice(
            tenant_id=tid, auto_key_job_id=job.id, invoice_number=f"INV-{uuid4().hex[:6]}",
            status="paid", total_cents=12000, subtotal_cents=12000,
        )
        s.add(invoice)
        s.commit()
        invoice_id = invoice.id

    r = _post(client, "checkout.session.completed", {
        "id": "cs_double_1", "object": "checkout.session", "mode": "payment",
        "metadata": {"purpose": "auto_key_invoice", "auto_key_invoice_id": str(invoice_id)},
        "payment_status": "paid", "amount_total": 12000,
    })
    assert r.status_code == 200
    with Session(engine) as s:
        alert = s.exec(
            select(TenantEventLog)
            .where(TenantEventLog.entity_id == invoice_id)
            .where(TenantEventLog.event_type == "card_payment_needs_attention")
        ).first()
        assert alert is not None
        assert "already paid" in alert.event_summary
