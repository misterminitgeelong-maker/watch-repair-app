"""Xero OAuth and connection management for Mobile Services billing."""

import logging
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import RedirectResponse
from sqlmodel import Session

from ..config import settings
from ..database import get_session
from ..dependencies import AuthContext, require_owner
from ..models import Tenant, XeroConnectionStatusResponse
from ..xero_service import (
    apply_xero_token_response,
    build_xero_authorize_url,
    disconnect_xero,
    exchange_xero_code,
    parse_xero_oauth_state,
    xero_configured,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/v1/billing/xero", tags=["billing-xero"])


def _xero_status_for_tenant(tenant: Tenant) -> XeroConnectionStatusResponse:
    configured = xero_configured()
    connected = configured and (tenant.xero_connection_status or "") == "connected" and bool(
        tenant.xero_access_token
    )
    return XeroConnectionStatusResponse(
        configured=configured,
        connected=connected,
        connection_status=tenant.xero_connection_status,
        xero_tenant_id=tenant.xero_tenant_id,
        default_sales_account_code=tenant.xero_default_sales_account_code,
        default_tax_type=tenant.xero_default_tax_type,
    )


@router.get("/status", response_model=XeroConnectionStatusResponse)
def get_xero_connection_status(
    auth: AuthContext = Depends(require_owner),
    session: Session = Depends(get_session),
):
    tenant = session.get(Tenant, auth.tenant_id)
    if not tenant:
        raise HTTPException(status_code=404, detail="Tenant not found")
    return _xero_status_for_tenant(tenant)


@router.get("/connect")
def get_xero_connect_url(
    auth: AuthContext = Depends(require_owner),
    session: Session = Depends(get_session),
):
    if not xero_configured():
        raise HTTPException(status_code=503, detail="Xero is not configured on this server")
    tenant = session.get(Tenant, auth.tenant_id)
    if not tenant:
        raise HTTPException(status_code=404, detail="Tenant not found")
    return {"url": build_xero_authorize_url(tenant.id)}


@router.get("/callback", include_in_schema=False)
def xero_oauth_callback(
    code: Optional[str] = Query(default=None),
    state: Optional[str] = Query(default=None),
    error: Optional[str] = Query(default=None),
    session: Session = Depends(get_session),
):
    base = settings.public_base_url.rstrip("/")
    return_path = f"{base}/accounts?xero=return"
    if error:
        return RedirectResponse(url=f"{return_path}&xero_error={error}")
    if not code or not state:
        return RedirectResponse(url=f"{return_path}&xero_error=missing_code")
    try:
        tenant_id = parse_xero_oauth_state(state)
    except ValueError:
        return RedirectResponse(url=f"{return_path}&xero_error=invalid_state")
    tenant = session.get(Tenant, tenant_id)
    if not tenant:
        return RedirectResponse(url=f"{return_path}&xero_error=tenant_not_found")
    try:
        token_data = exchange_xero_code(code)
        apply_xero_token_response(session, tenant, token_data)
    except Exception:
        logger.exception("xero_oauth_callback_failed tenant=%s", tenant_id)
        tenant.xero_connection_status = "error"
        session.add(tenant)
        session.commit()
        return RedirectResponse(url=f"{return_path}&xero_error=token_exchange_failed")
    return RedirectResponse(url=f"{return_path}&xero=connected")


@router.post("/disconnect", response_model=XeroConnectionStatusResponse)
def disconnect_xero_connection(
    auth: AuthContext = Depends(require_owner),
    session: Session = Depends(get_session),
):
    tenant = session.get(Tenant, auth.tenant_id)
    if not tenant:
        raise HTTPException(status_code=404, detail="Tenant not found")
    disconnect_xero(session, tenant)
    session.refresh(tenant)
    return _xero_status_for_tenant(tenant)
