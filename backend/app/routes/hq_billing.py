"""Bundled monthly Minit-style HQ invoice summary (read-only; nothing is charged).

Platform admins name the network with ``parent_account_id``; an HQ owner/admin
always gets their own network. Routing / Prospecting add-ons are explicit query
flags because no per-HQ add-on setting exists yet.
"""
from __future__ import annotations

from datetime import datetime, timezone
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import Response
from sqlmodel import Session, select

from ..database import unscoped_session
from ..dependencies import AuthContext, get_auth_context
from ..minit_billing import (
    InvoiceSummary,
    SiteForBilling,
    compute_invoice,
    parse_month,
    summary_to_csv,
    summary_to_dict,
)
from ..models import ParentAccount, ParentAccountSite, Tenant, User
from ..parent_network import parents_for_user, require_parent_role
from ..regions import is_nz_minit_placement

router = APIRouter(prefix="/v1/hq-billing", tags=["hq-billing"])


def _resolve_parent(session: Session, auth: AuthContext, parent_account_id: UUID | None) -> ParentAccount:
    if auth.role == "platform_admin":
        if parent_account_id is None:
            raise HTTPException(status_code=422, detail="parent_account_id is required for platform admins")
        parent = session.get(ParentAccount, parent_account_id)
        if not parent:
            raise HTTPException(status_code=404, detail="Parent account not found")
        return parent
    if auth.role != "owner" or auth.support_actor_user_id is not None:
        raise HTTPException(status_code=403, detail="Owner access required")
    user = session.get(User, auth.user_id)
    if not user or not user.is_active:
        raise HTTPException(status_code=401, detail="Invalid token")
    parents = parents_for_user(session, user)
    if not parents:
        raise HTTPException(status_code=403, detail="No access to a parent account")
    parent = parents[0]
    if parent_account_id is not None and parent_account_id != parent.id:
        raise HTTPException(status_code=403, detail="No access to this parent account")
    require_parent_role(session, parent, user, write=True)  # HQ admin only
    return parent


def build_summary(
    session: Session, parent: ParentAccount, month: str | None, routing: bool, prospecting: bool
) -> InvoiceSummary:
    try:
        billing_month = parse_month(month) if month else datetime.now(timezone.utc).date().replace(day=1)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc))
    rows = session.exec(
        select(ParentAccountSite, Tenant)
        .join(Tenant, Tenant.id == ParentAccountSite.tenant_id)
        .where(ParentAccountSite.parent_account_id == parent.id)
    ).all()
    sites = [
        SiteForBilling(
            tenant_id=str(t.id),
            name=t.name,
            network_role=s.network_role,
            is_active=bool(t.is_active),
            billing_exempt=bool(t.billing_exempt),
            shop_number=t.shop_number,
            is_nz=is_nz_minit_placement(t.minit_region, t.minit_area)
            or (t.default_currency or "").strip().upper() == "NZD",
        )
        for s, t in rows
    ]
    return compute_invoice(sites, billing_month, routing=routing, prospecting=prospecting)


@router.get("/monthly-summary")
def monthly_summary(
    month: str | None = Query(default=None, description="YYYY-MM, default current month"),
    routing: bool = False,
    prospecting: bool = False,
    parent_account_id: UUID | None = None,
    auth: AuthContext = Depends(get_auth_context),
    session: Session = Depends(unscoped_session),
):
    parent = _resolve_parent(session, auth, parent_account_id)
    data = summary_to_dict(build_summary(session, parent, month, routing, prospecting))
    data["parent_account_id"] = str(parent.id)
    return data


@router.get("/monthly-summary.csv")
def monthly_summary_csv(
    month: str | None = None,
    routing: bool = False,
    prospecting: bool = False,
    parent_account_id: UUID | None = None,
    auth: AuthContext = Depends(get_auth_context),
    session: Session = Depends(unscoped_session),
):
    parent = _resolve_parent(session, auth, parent_account_id)
    inv = build_summary(session, parent, month, routing, prospecting)
    return Response(
        summary_to_csv(inv),
        media_type="text/csv",
        headers={"Content-Disposition": f'attachment; filename="hq-billing-{inv.billing_month:%Y-%m}.csv"'},
    )
