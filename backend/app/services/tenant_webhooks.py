"""Fire-and-forget outbound webhooks for tenant integrations."""

from __future__ import annotations

import hashlib
import hmac
import json
import logging
from datetime import datetime, timezone
from uuid import UUID

import httpx
from sqlmodel import Session, select

from ..models import TenantWebhookSubscription

logger = logging.getLogger(__name__)


def dispatch_tenant_webhooks(
    session: Session,
    *,
    tenant_id: UUID,
    event_type: str,
    payload: dict,
) -> None:
    subs = session.exec(
        select(TenantWebhookSubscription)
        .where(TenantWebhookSubscription.tenant_id == tenant_id)
        .where(TenantWebhookSubscription.is_active == True)  # noqa: E712
    ).all()
    body = json.dumps({
        "event": event_type,
        "occurred_at": datetime.now(timezone.utc).isoformat(),
        "data": payload,
    }).encode("utf-8")
    for sub in subs:
        types = {t.strip() for t in (sub.event_types or "").split(",") if t.strip()}
        if event_type not in types and "*" not in types:
            continue
        sig = hmac.new(sub.secret.encode("utf-8"), body, hashlib.sha256).hexdigest()
        try:
            httpx.post(
                sub.url,
                content=body,
                headers={
                    "Content-Type": "application/json",
                    "X-Mainspring-Event": event_type,
                    "X-Mainspring-Signature": sig,
                },
                timeout=5.0,
            )
        except Exception as exc:
            logger.warning("webhook delivery failed sub=%s: %s", sub.id, exc)
