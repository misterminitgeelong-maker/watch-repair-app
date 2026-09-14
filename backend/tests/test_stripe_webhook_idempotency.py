"""Stripe redelivers webhook events; the same event ID must only be applied once."""
import json
import time
from uuid import UUID

import pytest
import stripe
from sqlmodel import Session, select

from app.config import settings
from app.database import engine
from app.models import StripeWebhookEvent, Tenant, TenantEventLog

WEBHOOK_SECRET = "whsec_test_secret"


def _signed_headers(payload: str) -> dict[str, str]:
    ts = int(time.time())
    sig = stripe.WebhookSignature._compute_signature(f"{ts}.{payload}", WEBHOOK_SECRET)
    return {"stripe-signature": f"t={ts},v1={sig}", "content-type": "application/json"}


def _subscription_updated_event(event_id: str, tenant_id: str, plan_code: str) -> str:
    return json.dumps(
        {
            "id": event_id,
            "object": "event",
            "api_version": "2024-06-20",
            "type": "customer.subscription.updated",
            "data": {
                "object": {
                    "id": "sub_test_123",
                    "object": "subscription",
                    "customer": "cus_test_123",
                    "status": "active",
                    "trial_end": None,
                    "metadata": {"tenant_id": tenant_id, "target_plan_code": plan_code},
                    "items": {"data": []},
                }
            },
        }
    )


@pytest.fixture
def stripe_configured(monkeypatch):
    monkeypatch.setattr(settings, "stripe_secret_key", "sk_test_123")
    monkeypatch.setattr(settings, "stripe_webhook_secret", WEBHOOK_SECRET)


def _tenant_id_for(token_headers: dict[str, str], client) -> UUID:
    me = client.get("/v1/auth/session", headers=token_headers)
    assert me.status_code == 200, me.text
    return UUID(me.json()["tenant_id"])


def test_redelivered_event_is_applied_once(client, auth_headers, stripe_configured):
    tenant_id = _tenant_id_for(auth_headers, client)
    with Session(engine) as s:
        assert s.get(Tenant, tenant_id).plan_code == "basic_watch"

    event_id = f"evt_{tenant_id.hex[:12]}"
    payload = _subscription_updated_event(event_id, str(tenant_id), "pro")

    first = client.post("/v1/billing/webhook", content=payload, headers=_signed_headers(payload))
    assert first.status_code == 200, first.text
    assert first.json() == {"status": "ok"}

    second = client.post("/v1/billing/webhook", content=payload, headers=_signed_headers(payload))
    assert second.status_code == 200, second.text
    assert second.json() == {"status": "duplicate"}

    with Session(engine) as s:
        tenant = s.get(Tenant, tenant_id)
        assert tenant.plan_code == "pro"
        assert tenant.stripe_subscription_id == "sub_test_123"
        rows = s.exec(
            select(TenantEventLog).where(
                TenantEventLog.tenant_id == tenant_id,
                TenantEventLog.event_type == "plan_changed",
            )
        ).all()
        assert len(rows) == 1
        assert s.get(StripeWebhookEvent, event_id) is not None


def test_stale_redelivery_does_not_reapply_old_plan(client, auth_headers, stripe_configured):
    """A retry of an older event landing after a newer one must not roll the plan back."""
    tenant_id = _tenant_id_for(auth_headers, client)
    older = _subscription_updated_event(f"evt_old_{tenant_id.hex[:8]}", str(tenant_id), "pro")
    newer = _subscription_updated_event(f"evt_new_{tenant_id.hex[:8]}", str(tenant_id), "basic_watch")

    for payload in (older, newer, older):
        res = client.post("/v1/billing/webhook", content=payload, headers=_signed_headers(payload))
        assert res.status_code == 200, res.text

    with Session(engine) as s:
        assert s.get(Tenant, tenant_id).plan_code == "basic_watch"
        rows = s.exec(
            select(TenantEventLog).where(
                TenantEventLog.tenant_id == tenant_id,
                TenantEventLog.event_type == "plan_changed",
            )
        ).all()
        # basic_watch -> pro, pro -> basic_watch; the stale redelivery adds nothing.
        assert len(rows) == 2


def test_bad_signature_is_rejected(client, stripe_configured):
    payload = _subscription_updated_event("evt_bad", "00000000-0000-0000-0000-000000000000", "pro")
    res = client.post(
        "/v1/billing/webhook",
        content=payload,
        headers={"stripe-signature": "t=1,v1=deadbeef", "content-type": "application/json"},
    )
    assert res.status_code == 400
