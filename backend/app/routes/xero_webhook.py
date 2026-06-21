"""Xero webhooks — inbound invoice status (PAID / VOIDED)."""

import json
import logging

from fastapi import APIRouter, Depends, Header, HTTPException, Request
from sqlmodel import Session, select

from ..config import settings
from ..database import get_session
from ..models import AutoKeyInvoice, Invoice, Tenant
from ..xero_service import (
    fetch_xero_invoice_status,
    mark_auto_key_invoice_paid_from_xero,
    mark_auto_key_invoice_voided_from_xero,
    mark_repair_invoice_paid_from_xero,
    mark_repair_invoice_voided_from_xero,
    verify_xero_webhook_signature,
    xero_configured,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/v1/webhooks", tags=["webhooks"])


@router.post("/xero", include_in_schema=False)
async def xero_webhook(
    request: Request,
    x_xero_signature: str = Header(alias="x-xero-signature", default=""),
    session: Session = Depends(get_session),
):
    body = await request.body()
    if (settings.xero_webhook_key or "").strip():
        if not verify_xero_webhook_signature(body, x_xero_signature):
            raise HTTPException(status_code=401, detail="Invalid Xero webhook signature")
    elif settings.app_env == "production":
        raise HTTPException(status_code=503, detail="Xero webhook key not configured")

    try:
        payload = json.loads(body.decode("utf-8")) if body else {}
    except json.JSONDecodeError:
        return {"status": "ok"}

    events = payload.get("events") or []
    for event in events:
        category = (event.get("eventCategory") or "").upper()
        if category != "INVOICE":
            continue
        resource_id = event.get("resourceId")
        xero_org_id = event.get("tenantId")
        if not resource_id or not xero_org_id:
            continue

        tenant = session.exec(
            select(Tenant).where(Tenant.xero_tenant_id == str(xero_org_id))
        ).first()
        if not tenant or not xero_configured():
            continue
        if (tenant.xero_connection_status or "") != "connected":
            continue

        # An invoice in Xero maps to either an auto-key/mobile invoice or a core
        # watch/shoe repair invoice; check both by Xero invoice id.
        ak_invoice = session.exec(
            select(AutoKeyInvoice).where(AutoKeyInvoice.xero_invoice_id == str(resource_id))
        ).first()
        repair_invoice = None
        if not ak_invoice:
            repair_invoice = session.exec(
                select(Invoice).where(Invoice.xero_invoice_id == str(resource_id))
            ).first()
        if not ak_invoice and not repair_invoice:
            continue

        try:
            status = fetch_xero_invoice_status(session, tenant, str(resource_id))
        except Exception:
            logger.exception("xero_webhook.fetch_invoice_failed xero_id=%s", resource_id)
            continue

        if ak_invoice is not None:
            if status == "PAID":
                if mark_auto_key_invoice_paid_from_xero(session, ak_invoice):
                    logger.info("xero_webhook.invoice_paid invoice=%s", ak_invoice.id)
            elif status == "VOIDED":
                if mark_auto_key_invoice_voided_from_xero(session, ak_invoice):
                    logger.info("xero_webhook.invoice_voided invoice=%s", ak_invoice.id)
        else:
            if status == "PAID":
                if mark_repair_invoice_paid_from_xero(session, repair_invoice):
                    logger.info("xero_webhook.repair_invoice_paid invoice=%s", repair_invoice.id)
            elif status == "VOIDED":
                if mark_repair_invoice_voided_from_xero(session, repair_invoice):
                    logger.info("xero_webhook.repair_invoice_voided invoice=%s", repair_invoice.id)

    session.commit()
    return {"status": "ok"}
