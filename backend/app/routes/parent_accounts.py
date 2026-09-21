"""
Cross-tenant by design: parent-account membership management across its shops.

Endpoints here take ``unscoped_session`` rather than ``get_session`` so the ORM
tenant filter in app/tenant_scope.py does not apply. That is deliberate and is
meant to be visible: an endpoint crossing the tenant boundary says so in its
signature, and these modules are the complete list of places that do.
"""
from calendar import monthrange
from datetime import datetime, timedelta, timezone
import json
import logging
from typing import Optional
from uuid import UUID, uuid4

from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile
from fastapi.concurrency import run_in_threadpool
from sqlalchemy import or_
from sqlalchemy.exc import IntegrityError
from sqlmodel import Session, col, func, select

from .. import email_client
from .. import sms as sms_service
from ..database import get_session, unscoped_session
from ..dependencies import (
    AuthContext,
    PLAN_FEATURES,
    VALID_PLAN_CODES,
    get_auth_context,
    normalize_plan_code,
    require_feature,
    require_owner,
)
from ..minit_branding import MINIT_HQ_PLAN, tenant_product
from ..minit_mobile_routing import resolve_mobile_operator_route
from ..minit_mobile_territory_import import import_mobile_suburb_routes, load_territory_routes_seed
from ..minit_mobile_operators import (
    index_tss_shops_by_number,
    load_mobile_operators_seed,
    resolve_mobile_operators,
)
from ..minit_directory_import import backfill_shared_login_owners, plan_directory_import
from ..minit_directory_parser import DirectoryData, DirectoryParseError, build_directory, extract_org_graph
from ..minit_provision import import_minit_mobile_operators, import_minit_shops
from ..minit_shops import parse_minit_shops_xlsx_detailed
from ..models import (
    NETWORK_ROLE_HQ,
    NETWORK_ROLE_OPERATOR,
    NETWORK_ROLE_RETAIL,
    MobileSuburbRoute,
    MobileSuburbRouteCreateRequest,
    MobileSuburbRouteOperatorSummary,
    MobileSuburbRouteRead,
    MobileSuburbRoutesSummary,
    ParentAccount,
    ParentAccountCreateTenantRequest,
    ParentImportShopsResponse,
    ParentImportTerritoryRoutesResponse,
    ParentProvisionShopRequest,
    ParentRoutingTestResponse,
    ParentAccountEventLog,
    ParentAccountEventLogRead,
    ParentAccountLinkTenantRequest,
    ParentAccountSite,
    ParentAccountSiteRead,
    ParentAccountSitesPageResponse,
    ParentAccountSummaryResponse,
    ParentLeadIngestConfigResponse,
    ParentMobileLeadDefaultTenantBody,
    ParentMobileLeadDispatchSettingsBody,
    ParentMobileLeadEscalationTenantBody,
    ParentMobileLeadWebhookSecretBody,
    Region,
    ShopBookingUsageResponse,
    ShopBookingUsageShopBreakdown,
    ShopMobileBookingRequest,
    ShopOwnerInvite,
    ShopOwnerInviteCreateRequest,
    ShopOwnerInviteRead,
    Tenant,
    User,
)
from ..config import settings
from ..parent_network import (
    link_site,
    normalize_region_code,
    parent_region_scope,
    parents_for_user,
    regions_for_parent,
    require_parent_role,
    site_for_tenant_in_parent,
    sites_for_parent,
)
from ..security import hash_password, hash_unusable_password
from ..minit_shops import MinitShopRow, tenant_slug_for_shop
from ..shop_number import (
    assert_shop_number_unique_in_parent,
    format_tenant_label,
    normalize_shop_number,
    validate_shop_number_format,
)

router = APIRouter(
    prefix="/v1/parent-accounts",
    tags=["parent-accounts"],
    dependencies=[Depends(require_feature("multi_site"))],
)

AU_STATES = frozenset({"ACT", "NSW", "NT", "QLD", "SA", "TAS", "VIC", "WA"})
MAX_IMPORT_SHOPS_XLSX_BYTES = 5 * 1024 * 1024
_ALLOWED_XLSX_SUFFIXES = frozenset({".xlsx", ".xlsm"})
_PLAN_KIND_TO_ROLE: dict[str, str | None] = {
    "all": None,
    "retail": NETWORK_ROLE_RETAIL,
    "operator": NETWORK_ROLE_OPERATOR,
}


def _owner_users_by_tenant(session: Session, tenant_ids: list[UUID]) -> dict[UUID, User]:
    """First active owner login per tenant — the person a site "belongs" to."""
    if not tenant_ids:
        return {}
    owners: dict[UUID, User] = {}
    for user in session.exec(
        select(User)
        .where(col(User.tenant_id).in_(tenant_ids))
        .where(User.role == "owner")
        .where(User.is_active == True)  # noqa: E712
        .order_by(col(User.created_at).asc(), col(User.id).asc())
    ).all():
        owners.setdefault(user.tenant_id, user)
    return owners


def _regions_by_id(session: Session, parent_id: UUID) -> dict[UUID, Region]:
    return {r.id: r for r in regions_for_parent(session, parent_id)}


def _site_reads_for_sites(
    session: Session,
    sites: list[ParentAccountSite],
    *,
    regions_by_id: dict[UUID, Region] | None = None,
) -> list[ParentAccountSiteRead]:
    tenant_ids = [site.tenant_id for site in sites]
    if not tenant_ids:
        return []
    tenants_by_id = {
        t.id: t
        for t in session.exec(select(Tenant).where(col(Tenant.id).in_(tenant_ids))).all()
    }
    owners = _owner_users_by_tenant(session, tenant_ids)
    if regions_by_id is None:
        regions_by_id = _regions_by_id(session, sites[0].parent_account_id)

    # Sites provisioned by hand (or by the pilot seed) get a copy of the HQ
    # login rather than a franchisee identity — the directory import is what
    # fills in real names, emails and mobiles. Flag those so HQ does not send
    # an owner invite straight back to itself.
    hq_parent = session.get(ParentAccount, sites[0].parent_account_id)
    hq_login_email = (hq_parent.owner_email or "").strip().lower() if hq_parent else ""

    reads: list[ParentAccountSiteRead] = []
    for site in sites:
        tenant = tenants_by_id.get(site.tenant_id)
        user = owners.get(site.tenant_id)
        if not tenant or not user:
            continue
        region = regions_by_id.get(site.region_id) if site.region_id else None
        reads.append(
            ParentAccountSiteRead(
                tenant_id=tenant.id,
                tenant_slug=tenant.slug,
                tenant_name=tenant.name,
                shop_number=tenant.shop_number,
                area=tenant.minit_area,
                region=region.name if region else tenant.minit_region,
                region_id=region.id if region else None,
                region_code=region.code if region else None,
                plan_code=normalize_plan_code(tenant.plan_code),
                network_role=site.network_role,
                owner_user_id=user.id,
                owner_email=user.email,
                owner_full_name=user.full_name,
                owner_mobile=user.mobile,
                owner_is_shared_hq_login=bool(
                    hq_login_email and (user.email or "").strip().lower() == hq_login_email
                ),
            )
        )
    return sorted(reads, key=lambda s: (s.tenant_name.lower(), s.tenant_slug.lower()))


def _to_summary(
    session: Session,
    parent: ParentAccount,
    *,
    include_sites: bool = False,
    my_role: str | None = None,
    my_region_id: UUID | None = None,
) -> ParentAccountSummaryResponse:
    all_sites = sites_for_parent(session, parent.id)
    if my_region_id is not None:
        all_sites = [site for site in all_sites if site.region_id == my_region_id]
    sites: list[ParentAccountSiteRead] = []
    if include_sites:
        sites = _site_reads_for_sites(session, all_sites)

    return ParentAccountSummaryResponse(
        parent_account_id=parent.id,
        parent_account_name=parent.name,
        owner_email=parent.owner_email,
        my_role=my_role,
        my_region_id=my_region_id,
        site_count=len(all_sites),
        sites=sites,
        mobile_lead_ingest_public_id=parent.mobile_lead_ingest_public_id,
        mobile_lead_webhook_secret_configured=bool(parent.mobile_lead_webhook_secret_hash),
        mobile_lead_default_tenant_id=parent.mobile_lead_default_tenant_id,
    )


def _lead_ingest_config(parent: ParentAccount) -> ParentLeadIngestConfigResponse:
    return ParentLeadIngestConfigResponse(
        parent_account_id=parent.id,
        mobile_lead_ingest_public_id=parent.mobile_lead_ingest_public_id,
        mobile_lead_webhook_secret_configured=bool(parent.mobile_lead_webhook_secret_hash),
        mobile_lead_default_tenant_id=parent.mobile_lead_default_tenant_id,
        mobile_lead_escalation_tenant_id=parent.mobile_lead_escalation_tenant_id,
        mobile_lead_offer_timeout_minutes=int(parent.mobile_lead_offer_timeout_minutes or 30),
        mobile_lead_max_operator_offers=int(parent.mobile_lead_max_operator_offers or 3),
        mobile_lead_force_hq_dispatch=bool(parent.mobile_lead_force_hq_dispatch),
    )


def _filtered_parent_sites(
    session: Session,
    parent_id: UUID,
    *,
    limit: int,
    offset: int,
    search: str | None,
    region: str | None,
    plan_kind: str | None,
) -> ParentAccountSitesPageResponse:
    kind = (plan_kind or "all").strip().lower()
    role_filter = _PLAN_KIND_TO_ROLE.get(kind)
    all_sites = sites_for_parent(session, parent_id, network_role=role_filter)
    if not all_sites:
        return ParentAccountSitesPageResponse(sites=[], total=0, limit=limit, offset=offset)

    regions_by_id = _regions_by_id(session, parent_id)
    region_filter = (region or "").strip()
    if region_filter:
        if region_filter.lower() == "unassigned":
            all_sites = [site for site in all_sites if site.region_id is None]
        else:
            # Accept a Region id, its code, or its display name.
            wanted = {
                r.id
                for r in regions_by_id.values()
                if str(r.id) == region_filter
                or r.code == normalize_region_code(region_filter)
                or r.name.lower() == region_filter.lower()
            }
            all_sites = [site for site in all_sites if site.region_id in wanted]
        if not all_sites:
            return ParentAccountSitesPageResponse(sites=[], total=0, limit=limit, offset=offset)

    site_by_tenant = {site.tenant_id: site for site in all_sites}
    stmt = select(Tenant).where(col(Tenant.id).in_(list(site_by_tenant)))

    search_term = (search or "").strip()
    if search_term:
        pattern = f"%{search_term}%"
        stmt = stmt.where(
            or_(
                Tenant.name.ilike(pattern),
                Tenant.slug.ilike(pattern),
                Tenant.shop_number.ilike(pattern),
                Tenant.minit_area.ilike(pattern),
                Tenant.minit_region.ilike(pattern),
            )
        )

    total = int(session.exec(select(func.count()).select_from(stmt.subquery())).one())
    tenants = session.exec(
        stmt.order_by(Tenant.name.asc(), Tenant.slug.asc()).offset(offset).limit(limit)
    ).all()
    if not tenants:
        return ParentAccountSitesPageResponse(sites=[], total=total, limit=limit, offset=offset)

    ordered_sites = [site_by_tenant[t.id] for t in tenants if t.id in site_by_tenant]
    sites = _site_reads_for_sites(session, ordered_sites, regions_by_id=regions_by_id)
    return ParentAccountSitesPageResponse(sites=sites, total=total, limit=limit, offset=offset)


def _normalize_suburb(name: str) -> str:
    return " ".join(name.strip().lower().split())


def _require_minit_hq(auth: AuthContext, session: Session) -> Tenant:
    tenant = session.get(Tenant, auth.tenant_id)
    if not tenant:
        raise HTTPException(status_code=401, detail="Invalid token")
    if normalize_plan_code(auth.plan_code) != MINIT_HQ_PLAN:
        raise HTTPException(status_code=403, detail="Minit HQ plan required")
    if tenant_product(tenant.slug) != "minit":
        raise HTTPException(status_code=403, detail="Minit product required")
    return tenant


def _get_parent_account_for_user(session: Session, user: User) -> ParentAccount:
    """The network this login acts on — by access row, then by account
    owner email, always in a fixed order (see parent_network.parents_for_user)."""
    parents = parents_for_user(session, user)
    if parents:
        return parents[0]
    raise HTTPException(status_code=404, detail="Parent account not found")


def _current_user(session: Session, auth: AuthContext) -> User:
    user = session.get(User, auth.user_id)
    if not user or not user.is_active:
        raise HTTPException(status_code=401, detail="Invalid token")
    return user


def _parent_for_read(session: Session, auth: AuthContext) -> tuple[User, ParentAccount, str]:
    """Any network-wide HQ role may read the network. Regional managers are
    refused here; endpoints that can confine themselves to one region use
    _parent_for_scoped_read instead."""
    user = _current_user(session, auth)
    parent = _get_parent_account_for_user(session, user)
    role = require_parent_role(session, parent, user, write=False)
    return user, parent, role


def _parent_for_scoped_read(
    session: Session, auth: AuthContext
) -> tuple[User, ParentAccount, str, UUID | None]:
    """Like _parent_for_read, but admits regional managers and returns the
    region they are confined to (None for network-wide access)."""
    user = _current_user(session, auth)
    parent = _get_parent_account_for_user(session, user)
    role = require_parent_role(session, parent, user, write=False, allow_region_scoped=True)
    return user, parent, role, parent_region_scope(session, parent, user)


def _parent_for_write(session: Session, auth: AuthContext) -> tuple[User, ParentAccount]:
    """Only hq_admin may change the network."""
    user = _current_user(session, auth)
    parent = _get_parent_account_for_user(session, user)
    require_parent_role(session, parent, user, write=True)
    return user, parent


def _normalize_plan_code(value: str | None) -> str:
    if value is None:
        return "pro"
    normalized = normalize_plan_code(value, default_if_empty="")
    if normalized not in VALID_PLAN_CODES:
        raise HTTPException(status_code=400, detail=f"Unsupported plan code '{value}'")
    return normalized


def _record_event(
    session: Session,
    *,
    parent_account_id: UUID,
    tenant_id: UUID | None,
    actor_user_id: UUID | None,
    actor_email: str | None,
    event_type: str,
    event_summary: str,
) -> None:
    session.add(
        ParentAccountEventLog(
            parent_account_id=parent_account_id,
            tenant_id=tenant_id,
            actor_user_id=actor_user_id,
            actor_email=actor_email,
            event_type=event_type,
            event_summary=event_summary,
        )
    )


def _tenant_linked_to_parent(session: Session, parent_id: UUID, tenant_id: UUID) -> bool:
    return site_for_tenant_in_parent(session, parent_id, tenant_id) is not None


@router.post("/me/mobile-lead-ingest/enable", response_model=ParentAccountSummaryResponse)
def enable_mobile_lead_ingest(
    auth: AuthContext = Depends(require_owner),
    session: Session = Depends(unscoped_session),
):
    """Assign a public ingest id for website POSTs (if not already set)."""
    current_user, parent = _parent_for_write(session, auth)
    if parent.mobile_lead_ingest_public_id is None:
        parent.mobile_lead_ingest_public_id = uuid4()
        _record_event(
            session,
            parent_account_id=parent.id,
            tenant_id=None,
            actor_user_id=current_user.id,
            actor_email=current_user.email,
            event_type="mobile_lead_ingest_enabled",
            event_summary="Enabled website mobile key lead ingest URL",
        )
        session.add(parent)
        session.commit()
    session.refresh(parent)
    return _to_summary(session, parent)


@router.put("/me/mobile-lead-ingest/secret", response_model=ParentAccountSummaryResponse)
def set_mobile_lead_webhook_secret(
    body: ParentMobileLeadWebhookSecretBody,
    auth: AuthContext = Depends(require_owner),
    session: Session = Depends(unscoped_session),
):
    current_user, parent = _parent_for_write(session, auth)
    if parent.mobile_lead_ingest_public_id is None:
        parent.mobile_lead_ingest_public_id = uuid4()
    parent.mobile_lead_webhook_secret_hash = hash_password(body.webhook_secret.strip())
    _record_event(
        session,
        parent_account_id=parent.id,
        tenant_id=None,
        actor_user_id=current_user.id,
        actor_email=current_user.email,
        event_type="mobile_lead_secret_set",
        event_summary="Set website mobile key lead webhook secret",
    )
    session.add(parent)
    session.commit()
    session.refresh(parent)
    return _to_summary(session, parent)


@router.delete("/me/mobile-lead-ingest/secret", response_model=ParentAccountSummaryResponse)
def clear_mobile_lead_webhook_secret(
    auth: AuthContext = Depends(require_owner),
    session: Session = Depends(unscoped_session),
):
    current_user, parent = _parent_for_write(session, auth)
    parent.mobile_lead_webhook_secret_hash = None
    _record_event(
        session,
        parent_account_id=parent.id,
        tenant_id=None,
        actor_user_id=current_user.id,
        actor_email=current_user.email,
        event_type="mobile_lead_secret_cleared",
        event_summary="Cleared website mobile key lead webhook secret",
    )
    session.add(parent)
    session.commit()
    session.refresh(parent)
    return _to_summary(session, parent)


@router.put("/me/mobile-lead-ingest/default-tenant", response_model=ParentAccountSummaryResponse)
def set_mobile_lead_default_tenant(
    body: ParentMobileLeadDefaultTenantBody,
    auth: AuthContext = Depends(require_owner),
    session: Session = Depends(unscoped_session),
):
    current_user, parent = _parent_for_write(session, auth)
    if body.tenant_id is None:
        parent.mobile_lead_default_tenant_id = None
        summary = "Cleared default site for unmatched suburbs"
    else:
        if not _tenant_linked_to_parent(session, parent.id, body.tenant_id):
            raise HTTPException(status_code=400, detail="That site is not linked to this parent account")
        parent.mobile_lead_default_tenant_id = body.tenant_id
        summary = "Set default site for website leads when suburb is not mapped"
    _record_event(
        session,
        parent_account_id=parent.id,
        tenant_id=body.tenant_id,
        actor_user_id=current_user.id,
        actor_email=current_user.email,
        event_type="mobile_lead_default_tenant",
        event_summary=summary,
    )
    session.add(parent)
    session.commit()
    session.refresh(parent)
    return _to_summary(session, parent)


@router.put("/me/mobile-lead-ingest/escalation-tenant", response_model=ParentLeadIngestConfigResponse)
def set_mobile_lead_escalation_tenant(
    body: ParentMobileLeadEscalationTenantBody,
    auth: AuthContext = Depends(require_owner),
    session: Session = Depends(unscoped_session),
):
    current_user, parent = _parent_for_write(session, auth)
    if body.tenant_id is None:
        parent.mobile_lead_escalation_tenant_id = None
        summary = "Cleared HQ escalation site for website leads"
    else:
        if not _tenant_linked_to_parent(session, parent.id, body.tenant_id):
            raise HTTPException(status_code=400, detail="That site is not linked to this parent account")
        parent.mobile_lead_escalation_tenant_id = body.tenant_id
        summary = "Set HQ escalation site when operators do not quote in time"
    _record_event(
        session,
        parent_account_id=parent.id,
        tenant_id=body.tenant_id,
        actor_user_id=current_user.id,
        actor_email=current_user.email,
        event_type="mobile_lead_escalation_tenant",
        event_summary=summary,
    )
    session.add(parent)
    session.commit()
    session.refresh(parent)
    return _lead_ingest_config(parent)


@router.put("/me/mobile-lead-ingest/dispatch-settings", response_model=ParentLeadIngestConfigResponse)
def set_mobile_lead_dispatch_settings(
    body: ParentMobileLeadDispatchSettingsBody,
    auth: AuthContext = Depends(require_owner),
    session: Session = Depends(unscoped_session),
):
    current_user, parent = _parent_for_write(session, auth)
    changes: list[str] = []
    if body.offer_timeout_minutes is not None:
        parent.mobile_lead_offer_timeout_minutes = body.offer_timeout_minutes
        changes.append(f"offer timeout {body.offer_timeout_minutes} min")
    if body.max_operator_offers is not None:
        parent.mobile_lead_max_operator_offers = body.max_operator_offers
        changes.append(f"max operator offers {body.max_operator_offers}")
    if body.force_hq_dispatch is not None:
        parent.mobile_lead_force_hq_dispatch = body.force_hq_dispatch
        changes.append("force HQ dispatch ON" if body.force_hq_dispatch else "force HQ dispatch OFF")
    if not changes:
        raise HTTPException(status_code=400, detail="No dispatch settings to update")
    _record_event(
        session,
        parent_account_id=parent.id,
        tenant_id=None,
        actor_user_id=current_user.id,
        actor_email=current_user.email,
        event_type="mobile_lead_dispatch_settings",
        event_summary="Updated website lead dispatch: " + ", ".join(changes),
    )
    session.add(parent)
    session.commit()
    session.refresh(parent)
    return _lead_ingest_config(parent)


@router.get("/me/mobile-lead-routes/summary", response_model=MobileSuburbRoutesSummary)
def mobile_suburb_routes_summary(
    auth: AuthContext = Depends(require_owner),
    session: Session = Depends(unscoped_session),
):
    """Route counts by operator — avoids loading thousands of suburb rows in HQ UI."""
    current_user, parent, _ = _parent_for_read(session, auth)
    total = session.exec(
        select(func.count())
        .select_from(MobileSuburbRoute)
        .where(MobileSuburbRoute.parent_account_id == parent.id)
    ).one()
    grouped = session.exec(
        select(
            MobileSuburbRoute.target_tenant_id,
            func.count().label("route_count"),
        )
        .where(MobileSuburbRoute.parent_account_id == parent.id)
        .group_by(MobileSuburbRoute.target_tenant_id)
        .order_by(func.count().desc())
    ).all()
    tenant_ids = [row[0] for row in grouped]
    tenants_by_id: dict[UUID, Tenant] = {}
    if tenant_ids:
        tenants = session.exec(select(Tenant).where(col(Tenant.id).in_(tenant_ids))).all()
        tenants_by_id = {t.id: t for t in tenants}
    operators: list[MobileSuburbRouteOperatorSummary] = []
    for tenant_id, route_count in grouped:
        tenant = tenants_by_id.get(tenant_id)
        operators.append(
            MobileSuburbRouteOperatorSummary(
                target_tenant_id=tenant_id,
                operator_name=tenant.name if tenant else "Unknown operator",
                operator_slug=tenant.slug if tenant else "",
                operator_shop_number=tenant.shop_number if tenant else None,
                route_count=int(route_count),
            )
        )
    return MobileSuburbRoutesSummary(total_routes=int(total), operators=operators)


@router.get("/me/mobile-lead-routes", response_model=list[MobileSuburbRouteRead])
def list_mobile_suburb_routes(
    search: str | None = Query(default=None, description="Filter by suburb name (case-insensitive)"),
    limit: int = Query(default=200, ge=1, le=500),
    auth: AuthContext = Depends(require_owner),
    session: Session = Depends(unscoped_session),
):
    current_user, parent, _ = _parent_for_read(session, auth)
    stmt = (
        select(MobileSuburbRoute)
        .where(MobileSuburbRoute.parent_account_id == parent.id)
        .order_by(MobileSuburbRoute.state_code, MobileSuburbRoute.suburb_normalized)
        .limit(limit)
    )
    if search and search.strip():
        needle = f"%{search.strip().lower()}%"
        stmt = stmt.where(col(MobileSuburbRoute.suburb_normalized).ilike(needle))
    rows = session.exec(stmt).all()
    return [
        MobileSuburbRouteRead(
            id=r.id,
            state_code=r.state_code,
            suburb_normalized=r.suburb_normalized,
            target_tenant_id=r.target_tenant_id,
        )
        for r in rows
    ]


@router.post("/me/mobile-lead-routes", response_model=MobileSuburbRouteRead)
def create_mobile_suburb_route(
    payload: MobileSuburbRouteCreateRequest,
    auth: AuthContext = Depends(require_owner),
    session: Session = Depends(unscoped_session),
):
    current_user, parent = _parent_for_write(session, auth)
    st = payload.state_code.strip().upper()
    if st not in AU_STATES:
        raise HTTPException(status_code=400, detail=f"Invalid state_code; use one of: {', '.join(sorted(AU_STATES))}")
    sub_norm = _normalize_suburb(payload.suburb)
    if not sub_norm:
        raise HTTPException(status_code=400, detail="suburb is required")
    if not _tenant_linked_to_parent(session, parent.id, payload.target_tenant_id):
        raise HTTPException(status_code=400, detail="Target site is not linked to this parent account")
    row = MobileSuburbRoute(
        parent_account_id=parent.id,
        state_code=st,
        suburb_normalized=sub_norm,
        target_tenant_id=payload.target_tenant_id,
    )
    session.add(row)
    try:
        session.flush()
    except IntegrityError:
        session.rollback()
        raise HTTPException(
            status_code=409,
            detail="A route for this state and suburb already exists",
        ) from None
    _record_event(
        session,
        parent_account_id=parent.id,
        tenant_id=payload.target_tenant_id,
        actor_user_id=current_user.id,
        actor_email=current_user.email,
        event_type="mobile_lead_route_added",
        event_summary=f"Mapped suburb '{sub_norm}' ({st}) to a linked site",
    )
    session.commit()
    session.refresh(row)
    return MobileSuburbRouteRead(
        id=row.id,
        state_code=row.state_code,
        suburb_normalized=row.suburb_normalized,
        target_tenant_id=row.target_tenant_id,
    )


@router.get("/me/routing/test", response_model=ParentRoutingTestResponse)
def test_mobile_operator_routing(
    suburb: str = Query(..., min_length=1),
    state_code: str = Query(..., min_length=2, max_length=8),
    auth: AuthContext = Depends(require_owner),
    session: Session = Depends(unscoped_session),
):
    """Preview which mobile operator would receive a lead for suburb + state."""
    _require_minit_hq(auth, session)
    current_user, parent, _ = _parent_for_read(session, auth)
    resolution = resolve_mobile_operator_route(
        session,
        parent_id=parent.id,
        suburb=suburb,
        state_code=state_code,
    )
    return ParentRoutingTestResponse(
        suburb=resolution.suburb,
        state_code=resolution.state_code,
        suburb_normalized=resolution.suburb_normalized,
        routing_rule=resolution.routing_rule,
        operator_tenant_id=resolution.operator_tenant_id,
        operator_slug=resolution.operator_slug,
        operator_name=resolution.operator_name,
        operator_shop_number=resolution.operator_shop_number,
        message=resolution.message,
    )


@router.delete("/me/mobile-lead-routes/{route_id}")
def delete_mobile_suburb_route(
    route_id: UUID,
    auth: AuthContext = Depends(require_owner),
    session: Session = Depends(unscoped_session),
):
    current_user, parent = _parent_for_write(session, auth)
    row = session.get(MobileSuburbRoute, route_id)
    if not row or row.parent_account_id != parent.id:
        raise HTTPException(status_code=404, detail="Route not found")
    session.delete(row)
    _record_event(
        session,
        parent_account_id=parent.id,
        tenant_id=row.target_tenant_id,
        actor_user_id=current_user.id,
        actor_email=current_user.email,
        event_type="mobile_lead_route_removed",
        event_summary=f"Removed suburb route {row.suburb_normalized} ({row.state_code})",
    )
    session.commit()
    return {"ok": True}


def _tenant_has_shop_mobile_booking(plan_code: str) -> bool:
    plan = normalize_plan_code(plan_code)
    return "shop_mobile_booking" in PLAN_FEATURES.get(plan, set())


@router.get("/me/shop-booking-usage", response_model=ShopBookingUsageResponse)
def get_shop_booking_usage(
    month: str = Query(..., pattern=r"^\d{4}-\d{2}$", description="Calendar month YYYY-MM"),
    auth: AuthContext = Depends(require_owner),
    session: Session = Depends(unscoped_session),
):
    """Per-shop booking counts for Minit-style billing (accepted + pending in month)."""
    current_user, parent, _ = _parent_for_read(session, auth)

    try:
        year_s, mon_s = month.split("-", 1)
        year, mon = int(year_s), int(mon_s)
        if mon < 1 or mon > 12:
            raise ValueError("month")
        last_day = monthrange(year, mon)[1]
        month_start = datetime(year, mon, 1, tzinfo=timezone.utc)
        month_end = datetime(year, mon, last_day, 23, 59, 59, tzinfo=timezone.utc)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail="month must be YYYY-MM") from exc

    retail_sites = sites_for_parent(session, parent.id, network_role=NETWORK_ROLE_RETAIL)
    member_tenant_ids = [site.tenant_id for site in retail_sites]
    tenants = (
        session.exec(select(Tenant).where(col(Tenant.id).in_(member_tenant_ids))).all()
        if member_tenant_ids
        else []
    )

    # Every retail site is a booking tenant; the breakdown lists those whose
    # plan can actually raise a booking (the rest are counted but have no rows).
    booking_tenant_count = len(tenants)
    shop_tenants: dict[UUID, Tenant] = {
        tenant.id: tenant for tenant in tenants if _tenant_has_shop_mobile_booking(tenant.plan_code)
    }

    counts: dict[tuple[UUID, str], int] = {}
    if shop_tenants:
        rows = session.exec(
            select(
                ShopMobileBookingRequest.requesting_tenant_id,
                ShopMobileBookingRequest.status,
                func.count(),
            )
            .where(ShopMobileBookingRequest.parent_account_id == parent.id)
            .where(col(ShopMobileBookingRequest.requesting_tenant_id).in_(list(shop_tenants)))
            .where(col(ShopMobileBookingRequest.status).in_(["accepted", "pending"]))
            .where(col(ShopMobileBookingRequest.created_at) >= month_start)
            .where(col(ShopMobileBookingRequest.created_at) <= month_end)
            .group_by(
                col(ShopMobileBookingRequest.requesting_tenant_id),
                col(ShopMobileBookingRequest.status),
            )
        ).all()
        counts = {(tid, status): int(n) for tid, status, n in rows}

    shops: list[ShopBookingUsageShopBreakdown] = [
        ShopBookingUsageShopBreakdown(
            tenant_id=tid,
            tenant_name=tenant.name,
            shop_number=tenant.shop_number,
            accepted_bookings_count=counts.get((tid, "accepted"), 0),
            pending_count=counts.get((tid, "pending"), 0),
        )
        for tid, tenant in shop_tenants.items()
    ]

    return ShopBookingUsageResponse(
        month=month,
        booking_tenant_count=booking_tenant_count,
        shops=sorted(shops, key=lambda s: s.tenant_name.lower()),
    )


@router.get("/me", response_model=ParentAccountSummaryResponse)
def get_parent_account_summary(
    include_sites: bool = Query(
        default=False,
        description="When false (default), omit the sites array for faster HQ loads.",
    ),
    auth: AuthContext = Depends(get_auth_context),
    session: Session = Depends(unscoped_session),
):
    user, parent, my_role, my_region_id = _parent_for_scoped_read(session, auth)
    return _to_summary(session, parent, include_sites=include_sites, my_role=my_role, my_region_id=my_region_id)


@router.get("/me/lead-ingest", response_model=ParentLeadIngestConfigResponse)
def get_parent_lead_ingest_config(
    auth: AuthContext = Depends(get_auth_context),
    session: Session = Depends(unscoped_session),
):
    user, parent, my_role = _parent_for_read(session, auth)
    return _lead_ingest_config(parent)


@router.get("/me/sites", response_model=ParentAccountSitesPageResponse)
def list_parent_account_sites(
    limit: int = Query(default=100, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
    search: str | None = Query(default=None),
    region: str | None = Query(default=None),
    plan_kind: str | None = Query(
        default=None,
        description="Filter by retail, operator, or all (default).",
    ),
    auth: AuthContext = Depends(get_auth_context),
    session: Session = Depends(unscoped_session),
):
    user, parent, _, my_region_id = _parent_for_scoped_read(session, auth)
    if plan_kind and plan_kind.strip().lower() not in {"retail", "operator", "all"}:
        raise HTTPException(status_code=400, detail="plan_kind must be retail, operator, or all")
    if my_region_id is not None:
        # A regional manager only ever sees their own region, whatever they ask for.
        region = str(my_region_id)

    return _filtered_parent_sites(
        session,
        parent.id,
        limit=limit,
        offset=offset,
        search=search,
        region=region,
        plan_kind=plan_kind,
    )


@router.get("/me/activity", response_model=list[ParentAccountEventLogRead])
def list_parent_account_activity(
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    auth: AuthContext = Depends(get_auth_context),
    session: Session = Depends(unscoped_session),
):
    user, parent, my_role = _parent_for_read(session, auth)

    safe_limit = max(1, min(limit, 200))
    rows = session.exec(
        select(ParentAccountEventLog)
        .where(ParentAccountEventLog.parent_account_id == parent.id)
        .order_by(ParentAccountEventLog.created_at.desc())
        .offset(offset)
        .limit(safe_limit)
    ).all()

    return [
        ParentAccountEventLogRead(
            id=row.id,
            parent_account_id=row.parent_account_id,
            tenant_id=row.tenant_id,
            actor_user_id=row.actor_user_id,
            actor_email=row.actor_email,
            event_type=row.event_type,
            event_summary=row.event_summary,
            created_at=row.created_at,
        )
        for row in rows
    ]


@router.post("/me/link-tenant", response_model=ParentAccountSummaryResponse)
def link_tenant_to_parent_account(
    payload: ParentAccountLinkTenantRequest,
    auth: AuthContext = Depends(require_owner),
    session: Session = Depends(unscoped_session),
):
    current_user, parent = _parent_for_write(session, auth)


    tenant_slug = payload.tenant_slug.strip().lower()
    owner_email = payload.owner_email.strip().lower()
    if not tenant_slug:
        raise HTTPException(status_code=400, detail="tenant_slug is required")
    if not owner_email or "@" not in owner_email:
        raise HTTPException(status_code=400, detail="owner_email is invalid")

    tenant = session.exec(select(Tenant).where(Tenant.slug == tenant_slug)).first()
    if not tenant:
        raise HTTPException(status_code=404, detail="Tenant not found")

    owner_user = session.exec(
        select(User)
        .where(User.tenant_id == tenant.id)
        .where(User.email == owner_email)
        .where(User.role == "owner")
        .where(User.is_active)
    ).first()
    if not owner_user:
        raise HTTPException(status_code=404, detail="Owner user not found for tenant")

    shop_number = validate_shop_number_format(payload.shop_number)
    if shop_number:
        assert_shop_number_unique_in_parent(
            session,
            parent_id=parent.id,
            shop_number=shop_number,
            exclude_tenant_id=tenant.id,
        )
        tenant.shop_number = shop_number
        session.add(tenant)

    created = link_site(session, parent_id=parent.id, tenant=tenant)

    if created is not None:
        _record_event(
            session,
            parent_account_id=parent.id,
            tenant_id=tenant.id,
            actor_user_id=current_user.id,
            actor_email=current_user.email,
            event_type="link_tenant",
            event_summary=f"Linked site '{tenant.name}' ({tenant.slug})",
        )
        session.commit()

    session.refresh(parent)
    return _to_summary(session, parent)


SHOP_OWNER_INVITE_EXPIRY_DAYS = 7

#: Plan/tier choices meaningful when inviting a Minit shop owner — a curated
#: subset of VALID_PLAN_CODES (no watch/shoe bundles; this flow is mobile-
#: services only). HQ picks one when sending the invite; leaving it unset
#: keeps the tenant's current plan.
MINIT_INVITE_PLAN_CODES: dict[str, str] = {
    "booking_only": "Retail shop — booking only",
    "basic_auto_key": "Mobile operator — Basic",
    "pro": "Mobile operator — Pro (multi-site)",
}


def _send_shop_owner_invite_notifications(
    session: Session,
    *,
    invite: ShopOwnerInvite,
    tenant: Tenant,
    owner: User,
) -> tuple[bool, bool]:
    """Best-effort: text and/or email the invite link to the franchisee. Never
    raises — a delivery failure shouldn't undo an invite that's already
    created; HQ can still copy the link from the response either way."""
    invite_url = f"{settings.public_base_url.rstrip('/')}/shop-invite/{invite.token}"
    email_sent = False
    sms_sent = False
    try:
        email_sent, _ = email_client.send_shop_owner_invite_email(
            to_email=owner.email,
            owner_full_name=owner.full_name,
            tenant_name=tenant.name,
            shop_number=tenant.shop_number,
            invite_url=invite_url,
            expiry_days=SHOP_OWNER_INVITE_EXPIRY_DAYS,
            session=session,
            tenant_id=tenant.id,
        )
    except Exception:
        logging.getLogger(__name__).exception("Failed to send shop-owner invite email for tenant %s", tenant.id)
    if (owner.mobile or "").strip():
        try:
            sms_sent = sms_service.notify_shop_owner_invite(
                session,
                tenant_id=tenant.id,
                to_phone=owner.mobile,
                tenant_name=tenant.name,
                shop_number=tenant.shop_number,
                invite_url=invite_url,
                expiry_days=SHOP_OWNER_INVITE_EXPIRY_DAYS,
            )
        except Exception:
            logging.getLogger(__name__).exception("Failed to send shop-owner invite SMS for tenant %s", tenant.id)
    return email_sent, sms_sent


def _shop_owner_invite_read(
    session: Session,
    invite: ShopOwnerInvite,
    *,
    email_sent: bool = False,
    sms_sent: bool = False,
) -> ShopOwnerInviteRead:
    tenant = session.get(Tenant, invite.tenant_id)
    owner = session.get(User, invite.owner_user_id)
    return ShopOwnerInviteRead(
        id=invite.id,
        tenant_id=invite.tenant_id,
        tenant_name=tenant.name if tenant else "",
        tenant_slug=tenant.slug if tenant else "",
        shop_number=tenant.shop_number if tenant else None,
        owner_email=owner.email if owner else "",
        owner_mobile=owner.mobile if owner else None,
        plan_code=tenant.plan_code if tenant else "",
        status=invite.status,
        invite_url=f"{settings.public_base_url.rstrip('/')}/shop-invite/{invite.token}",
        expires_at=invite.expires_at,
        created_at=invite.created_at,
        completed_at=invite.completed_at,
        email_sent=email_sent,
        sms_sent=sms_sent,
    )


@router.post("/me/sites/{tenant_id}/invite", response_model=ShopOwnerInviteRead)
def create_shop_owner_invite(
    tenant_id: UUID,
    payload: ShopOwnerInviteCreateRequest | None = None,
    auth: AuthContext = Depends(require_owner),
    session: Session = Depends(unscoped_session),
):
    """Create (or reissue) a one-time invite letting a shop set its own login,
    replacing the shared HQ owner credentials it was provisioned with.
    Optionally sets the shop's plan/tier at the same time."""
    current_user, parent = _parent_for_write(session, auth)


    tenant = session.get(Tenant, tenant_id)
    if not tenant:
        raise HTTPException(status_code=404, detail="Tenant not found")

    if not _tenant_linked_to_parent(session, parent.id, tenant.id):
        raise HTTPException(status_code=404, detail="Site is not linked to your account")

    owner_user = session.exec(
        select(User)
        .where(User.tenant_id == tenant.id)
        .where(User.role == "owner")
        .where(User.is_active)
        .order_by(col(User.created_at).asc())
    ).first()
    if not owner_user:
        raise HTTPException(status_code=404, detail="No owner user found for this site")

    requested_plan = (payload.plan_code if payload else None) or None
    if requested_plan:
        normalized_plan = requested_plan.strip().lower()
        if normalized_plan not in MINIT_INVITE_PLAN_CODES:
            raise HTTPException(
                status_code=400,
                detail=f"plan_code must be one of: {', '.join(MINIT_INVITE_PLAN_CODES)}",
            )
        if tenant.plan_code != normalized_plan:
            previous_plan = tenant.plan_code
            tenant.plan_code = normalized_plan
            session.add(tenant)
            _record_event(
                session,
                parent_account_id=parent.id,
                tenant_id=tenant.id,
                actor_user_id=current_user.id,
                actor_email=current_user.email,
                event_type="plan_changed",
                event_summary=f"Changed '{tenant.name}' plan from {previous_plan} to {normalized_plan}",
            )

    # Reissuing revokes any invite still pending for this tenant, so a shop
    # never has two live claim links.
    pending = session.exec(
        select(ShopOwnerInvite)
        .where(ShopOwnerInvite.tenant_id == tenant.id)
        .where(ShopOwnerInvite.status == "pending")
    ).all()
    for row in pending:
        row.status = "revoked"
        session.add(row)

    now = datetime.now(timezone.utc)
    invite = ShopOwnerInvite(
        tenant_id=tenant.id,
        parent_account_id=parent.id,
        owner_user_id=owner_user.id,
        created_by_user_id=current_user.id,
        expires_at=now + timedelta(days=SHOP_OWNER_INVITE_EXPIRY_DAYS),
    )
    session.add(invite)
    _record_event(
        session,
        parent_account_id=parent.id,
        tenant_id=tenant.id,
        actor_user_id=current_user.id,
        actor_email=current_user.email,
        event_type="shop_owner_invite_created",
        event_summary=f"Sent an owner-login invite for '{tenant.name}' ({tenant.slug})",
    )
    session.commit()
    session.refresh(invite)

    email_sent, sms_sent = _send_shop_owner_invite_notifications(session, invite=invite, tenant=tenant, owner=owner_user)
    session.commit()

    return _shop_owner_invite_read(session, invite, email_sent=email_sent, sms_sent=sms_sent)


@router.get("/me/sites/{tenant_id}/invite", response_model=Optional[ShopOwnerInviteRead])
def get_shop_owner_invite(
    tenant_id: UUID,
    auth: AuthContext = Depends(require_owner),
    session: Session = Depends(unscoped_session),
):
    """The most recent owner-login invite for a site, if any has ever been sent."""
    current_user, parent, _ = _parent_for_read(session, auth)


    if not _tenant_linked_to_parent(session, parent.id, tenant_id):
        raise HTTPException(status_code=404, detail="Site is not linked to your account")

    invite = session.exec(
        select(ShopOwnerInvite)
        .where(ShopOwnerInvite.tenant_id == tenant_id)
        .order_by(col(ShopOwnerInvite.created_at).desc())
    ).first()
    if not invite:
        return None
    return _shop_owner_invite_read(session, invite)


@router.post("/me/create-tenant", response_model=ParentAccountSummaryResponse)
def create_tenant_from_parent_account(
    payload: ParentAccountCreateTenantRequest,
    auth: AuthContext = Depends(require_owner),
    session: Session = Depends(unscoped_session),
):
    current_user, parent = _parent_for_write(session, auth)


    tenant_name = payload.tenant_name.strip()
    tenant_slug = payload.tenant_slug.strip().lower()
    if not tenant_name:
        raise HTTPException(status_code=400, detail="tenant_name is required")
    if not tenant_slug:
        raise HTTPException(status_code=400, detail="tenant_slug is required")

    existing_tenant = session.exec(select(Tenant).where(Tenant.slug == tenant_slug)).first()
    if existing_tenant:
        raise HTTPException(status_code=409, detail="Tenant slug already exists")

    shop_number = validate_shop_number_format(payload.shop_number)
    if shop_number:
        assert_shop_number_unique_in_parent(session, parent_id=parent.id, shop_number=shop_number)

    business_address = payload.business_address.strip()[:2000] if payload.business_address else None
    tenant = Tenant(
        name=tenant_name,
        slug=tenant_slug,
        plan_code=_normalize_plan_code(payload.plan_code),
        business_address=business_address,
        shop_number=shop_number,
    )
    session.add(tenant)
    session.flush()

    new_owner = User(
        tenant_id=tenant.id,
        email=current_user.email,
        full_name=current_user.full_name,
        role="owner",
        password_hash=current_user.password_hash,
        is_active=True,
    )
    session.add(new_owner)
    session.flush()

    link_site(session, parent_id=parent.id, tenant=tenant)
    _record_event(
        session,
        parent_account_id=parent.id,
        tenant_id=tenant.id,
        actor_user_id=current_user.id,
        actor_email=current_user.email,
        event_type="create_tenant",
        event_summary=f"Created and linked site '{tenant.name}' ({tenant.slug})",
    )

    session.commit()
    session.refresh(parent)
    return _to_summary(session, parent)


@router.post("/me/import-shops", response_model=ParentImportShopsResponse)
async def import_shops_from_xlsx(
    file: UploadFile = File(...),
    auth: AuthContext = Depends(require_owner),
    session: Session = Depends(unscoped_session),
):
    """Bulk create/update retail shops from a Minit shop-list Excel workbook (HQ only)."""
    _require_minit_hq(auth, session)
    current_user, parent = _parent_for_write(session, auth)

    filename = (file.filename or "").strip()
    if not filename:
        raise HTTPException(status_code=400, detail="File name is required")
    suffix = filename.lower().rsplit(".", 1)[-1] if "." in filename else ""
    if f".{suffix}" not in _ALLOWED_XLSX_SUFFIXES:
        raise HTTPException(status_code=400, detail="Only .xlsx or .xlsm workbooks are supported")

    raw_bytes = await file.read()
    if not raw_bytes:
        raise HTTPException(status_code=400, detail="Uploaded file is empty")
    if len(raw_bytes) > MAX_IMPORT_SHOPS_XLSX_BYTES:
        raise HTTPException(
            status_code=413,
            detail=f"File exceeds maximum size of {MAX_IMPORT_SHOPS_XLSX_BYTES // (1024 * 1024)} MB",
        )

    # Workbook parse plus N tenant provisions is CPU/DB-heavy and fully
    # synchronous; run it in a worker thread so it does not block the event
    # loop (and therefore every other request) for the duration of the import.
    return await run_in_threadpool(
        _import_shops_from_xlsx_sync,
        raw_bytes=raw_bytes,
        filename=filename,
        parent=parent,
        current_user=current_user,
        session=session,
    )


def _import_shops_from_xlsx_sync(
    *,
    raw_bytes: bytes,
    filename: str,
    parent: ParentAccount,
    current_user: User,
    session: Session,
) -> ParentImportShopsResponse:
    try:
        parsed = parse_minit_shops_xlsx_detailed(file_obj=raw_bytes, collect_row_errors=True)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    if not parsed.shops:
        return ParentImportShopsResponse(
            parsed_count=0,
            sheet_name=parsed.sheet_name,
            errors=parsed.errors or ["No valid shop rows found in workbook"],
        )

    summary = import_minit_shops(
        session,
        parent_name=parent.name,
        hq_owner_email=current_user.email,
        shops=parsed.shops,
        apply=True,
    )

    errors: list[str] = list(parsed.errors)
    if summary.get("error"):
        errors.append(str(summary["error"]))

    created = int(summary.get("created_count", 0))
    updated = int(summary.get("updated_count", 0))
    skipped = int(summary.get("skipped_count", summary.get("would_skip_count", 0)))

    _record_event(
        session,
        parent_account_id=parent.id,
        tenant_id=None,
        actor_user_id=current_user.id,
        actor_email=current_user.email,
        event_type="import_shops",
        event_summary=(
            f"Imported shops from {filename}: "
            f"{created} created, {updated} updated, {skipped} skipped"
        ),
    )
    session.commit()

    return ParentImportShopsResponse(
        created_count=created,
        updated_count=updated,
        skipped_count=skipped,
        parsed_count=len(parsed.shops),
        sheet_name=parsed.sheet_name,
        errors=errors[:100],
    )


MAX_IMPORT_DIRECTORY_BYTES = 8 * 1024 * 1024
_ALLOWED_DIRECTORY_SUFFIXES = frozenset({".html", ".htm"})


async def _read_directory_upload(file: UploadFile) -> DirectoryData:
    """Validate and parse an uploaded Organisation Graph HTML export. Shared by
    the directory import and the owner-contact backfill, which take the same
    file."""
    filename = (file.filename or "").strip()
    if not filename:
        raise HTTPException(status_code=400, detail="File name is required")
    suffix = filename.lower().rsplit(".", 1)[-1] if "." in filename else ""
    if f".{suffix}" not in _ALLOWED_DIRECTORY_SUFFIXES:
        raise HTTPException(status_code=400, detail="Only .html directory exports are supported")

    raw_bytes = await file.read()
    if not raw_bytes:
        raise HTTPException(status_code=400, detail="Uploaded file is empty")
    if len(raw_bytes) > MAX_IMPORT_DIRECTORY_BYTES:
        raise HTTPException(
            status_code=413,
            detail=f"File exceeds maximum size of {MAX_IMPORT_DIRECTORY_BYTES // (1024 * 1024)} MB",
        )

    try:
        html_text = raw_bytes.decode("utf-8")
        return build_directory(extract_org_graph(html_text))
    except UnicodeDecodeError as exc:
        raise HTTPException(status_code=400, detail="File is not valid UTF-8 text") from exc
    except DirectoryParseError as exc:
        raise HTTPException(status_code=400, detail=f"Could not read directory export: {exc}") from exc


@router.post("/me/backfill-shop-owner-contacts")
async def backfill_shop_owner_contacts(
    file: UploadFile = File(...),
    apply: bool = Query(default=False),
    auth: AuthContext = Depends(require_owner),
    session: Session = Depends(unscoped_session),
) -> dict[str, object]:
    """Preview (default) or apply filling in real franchisee contact details for
    shops still sharing the HQ login, from the same directory HTML export.

    The directory import only sets an owner identity on shops it creates, so
    shops loaded by the xlsx importer or added by hand keep the HQ login and
    never receive their contact details. This catches those up, and only those:
    a shop whose owner is already a real person is left alone.

    Preview (apply=false, the default) writes nothing — call again with
    apply=true, using the same file, once the preview looks right."""
    _require_minit_hq(auth, session)
    current_user, parent = _parent_for_write(session, auth)

    directory = await _read_directory_upload(file)
    summary = backfill_shared_login_owners(
        session, directory, hq_owner_email=current_user.email, apply=apply
    )

    if apply and summary.get("hq_parent_found"):
        _record_event(
            session,
            parent_account_id=parent.id,
            tenant_id=None,
            actor_user_id=current_user.id,
            actor_email=current_user.email,
            event_type="backfill_shop_owner_contacts",
            event_summary=(
                f"Filled in franchisee contact details for {summary.get('matched_count', 0)} "
                "shops that were sharing the HQ login"
            ),
        )
        session.commit()

    return summary


@router.post("/me/import-directory")
async def import_directory_export(
    file: UploadFile = File(...),
    apply: bool = Query(default=False),
    auth: AuthContext = Depends(require_owner),
    session: Session = Depends(unscoped_session),
) -> dict[str, object]:
    """Preview (default) or apply importing shops + real franchisee owners from
    a Mister Minit "Organisation Graph" directory HTML export (HQ only).

    Preview (apply=false, the default) makes no changes — call again with
    apply=true, using the same file, once you're happy with the preview."""
    _require_minit_hq(auth, session)
    current_user, parent = _parent_for_write(session, auth)

    # Captured before the read so the audit entry can name the file.
    filename = (file.filename or "").strip()
    directory = await _read_directory_upload(file)

    summary = plan_directory_import(session, directory, hq_owner_email=current_user.email, apply=apply)

    if apply and summary.get("hq_parent_found"):
        _record_event(
            session,
            parent_account_id=parent.id,
            tenant_id=None,
            actor_user_id=current_user.id,
            actor_email=current_user.email,
            event_type="import_directory",
            event_summary=(
                f"Imported directory from {filename}: "
                f"{summary.get('created_tenant_count', 0)} shops, "
                f"{summary.get('created_owner_count', 0)} owners, "
                f"{summary.get('created_franchisee_parent_account_count', 0)} franchisee accounts"
            ),
        )
        session.commit()

    return summary


@router.post("/me/import-operators", response_model=ParentImportShopsResponse)
async def import_mobile_operators_from_xlsx(
    file: UploadFile = File(...),
    auth: AuthContext = Depends(require_owner),
    session: Session = Depends(unscoped_session),
):
    """Bulk create/update mobile operators from bundled seed + TSS workbook (HQ only)."""
    _require_minit_hq(auth, session)
    current_user, parent = _parent_for_write(session, auth)

    filename = (file.filename or "").strip()
    if not filename:
        raise HTTPException(status_code=400, detail="File name is required")
    suffix = filename.lower().rsplit(".", 1)[-1] if "." in filename else ""
    if f".{suffix}" not in _ALLOWED_XLSX_SUFFIXES:
        raise HTTPException(status_code=400, detail="Only .xlsx or .xlsm workbooks are supported")

    raw_bytes = await file.read()
    if not raw_bytes:
        raise HTTPException(status_code=400, detail="Uploaded file is empty")
    if len(raw_bytes) > MAX_IMPORT_SHOPS_XLSX_BYTES:
        raise HTTPException(
            status_code=413,
            detail=f"File exceeds maximum size of {MAX_IMPORT_SHOPS_XLSX_BYTES // (1024 * 1024)} MB",
        )

    try:
        parsed = parse_minit_shops_xlsx_detailed(file_obj=raw_bytes, collect_row_errors=True)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    try:
        seeds = load_mobile_operators_seed()
    except (OSError, json.JSONDecodeError, KeyError) as exc:
        raise HTTPException(status_code=500, detail=f"Operator seed file error: {exc}") from exc

    operators, resolve_errors = resolve_mobile_operators(
        seeds, index_tss_shops_by_number(parsed.shops)
    )
    if resolve_errors:
        return ParentImportShopsResponse(
            parsed_count=len(seeds),
            sheet_name=parsed.sheet_name,
            errors=[f"{e['operator_label']} (#{e['shop_number']}): {e['error']}" for e in resolve_errors],
        )
    if not operators:
        return ParentImportShopsResponse(
            parsed_count=0,
            sheet_name=parsed.sheet_name,
            errors=parsed.errors or ["No operators resolved from seed + TSS workbook"],
        )

    try:
        summary = import_minit_mobile_operators(
            session,
            parent_id=parent.id,
            hq_owner=current_user,
            operators=operators,
            apply=True,
            commit=False,
        )
    except IntegrityError as exc:
        session.rollback()
        raise HTTPException(status_code=409, detail=f"Operator import conflict: {exc}") from exc
    except Exception as exc:
        session.rollback()
        raise HTTPException(status_code=500, detail=f"Operator import failed: {exc}") from exc

    errors: list[str] = list(parsed.errors)
    for row in resolve_errors:
        errors.append(f"{row['operator_label']} (#{row['shop_number']}): {row['error']}")
    if summary.get("error"):
        errors.append(str(summary["error"]))

    created = int(summary.get("created_count", 0))
    updated = int(summary.get("updated_count", 0))
    skipped = int(summary.get("skipped_count", summary.get("would_skip_count", 0)))

    _record_event(
        session,
        parent_account_id=parent.id,
        tenant_id=None,
        actor_user_id=current_user.id,
        actor_email=current_user.email,
        event_type="import_operators",
        event_summary=(
            f"Imported mobile operators from {filename}: "
            f"{created} created, {updated} updated, {skipped} skipped"
        ),
    )
    session.commit()

    return ParentImportShopsResponse(
        created_count=created,
        updated_count=updated,
        skipped_count=skipped,
        parsed_count=len(operators),
        sheet_name=parsed.sheet_name,
        errors=errors[:100],
    )


@router.post("/me/import-mobile-territory-routes", response_model=ParentImportTerritoryRoutesResponse)
def import_mobile_territory_routes(
    apply: bool = Query(default=False, description="When true, write routes to the database."),
    replace_existing: bool = Query(default=False, description="Delete existing routes before import."),
    auth: AuthContext = Depends(require_owner),
    session: Session = Depends(unscoped_session),
):
    """Import bundled AU territory suburb routes (HQ only). Dry-run by default."""
    _require_minit_hq(auth, session)
    current_user, parent = _parent_for_write(session, auth)

    try:
        routes, operators = load_territory_routes_seed()
    except (OSError, json.JSONDecodeError, ValueError) as exc:
        raise HTTPException(status_code=500, detail=f"Territory seed file error: {exc}") from exc

    try:
        summary = import_mobile_suburb_routes(
            session,
            parent_id=parent.id,
            routes=routes,
            operators=operators,
            apply=apply,
            replace_existing=replace_existing,
        )
    except Exception as exc:
        session.rollback()
        raise HTTPException(status_code=500, detail=f"Territory route import failed: {exc}") from exc

    if apply:
        _record_event(
            session,
            parent_account_id=parent.id,
            tenant_id=None,
            actor_user_id=current_user.id,
            actor_email=current_user.email,
            event_type="import_mobile_territory_routes",
            event_summary=(
                f"Imported mobile territory routes: "
                f"{summary.get('created_count', 0)} created, "
                f"{summary.get('updated_count', 0)} updated"
            ),
        )

    missing = summary.get("missing_operator_shop_numbers") or []
    return ParentImportTerritoryRoutesResponse(
        route_rows_in_file=int(summary.get("route_rows_in_file", 0)),
        would_create_count=int(summary.get("would_create_count", 0)),
        would_update_count=int(summary.get("would_update_count", 0)),
        would_skip_count=int(summary.get("would_skip_count", 0)),
        created_count=int(summary.get("created_count", 0)),
        updated_count=int(summary.get("updated_count", 0)),
        skipped_count=int(summary.get("skipped_count", 0)),
        pending_apply_count=int(summary.get("pending_apply_count", 0)),
        operator_coords_updated=int(summary.get("operator_coords_updated", 0)),
        missing_operator_shop_numbers=[str(x) for x in missing],
        applied=apply,
    )


#: What "+ Add shop" can create: shop_type -> (starting plan, network role).
#: A mobile operator is a van, not a shopfront, so it starts on the Auto Key
#: Basic plan and sits under the network's operator roll-up.
_PROVISION_SHOP_TYPES: dict[str, tuple[str, str]] = {
    "physical": ("booking_only", NETWORK_ROLE_RETAIL),
    "mobile": ("basic_auto_key", NETWORK_ROLE_OPERATOR),
}


@router.post("/me/provision-shop", response_model=ParentAccountSummaryResponse)
def provision_minit_retail_shop(
    payload: ParentProvisionShopRequest,
    auth: AuthContext = Depends(require_owner),
    session: Session = Depends(unscoped_session),
):
    """Create a Minit shop (slug minit-{shop_number}) under this parent — a
    physical shopfront on booking_only, or a mobile van operator on
    basic_auto_key."""
    current_user, parent = _parent_for_write(session, auth)

    shop_type = (payload.shop_type or "physical").strip().lower()
    if shop_type not in _PROVISION_SHOP_TYPES:
        raise HTTPException(
            status_code=400,
            detail=f"shop_type must be one of: {', '.join(sorted(_PROVISION_SHOP_TYPES))}",
        )
    plan_code, network_role = _PROVISION_SHOP_TYPES[shop_type]

    shop_number = validate_shop_number_format(payload.shop_number)
    if not shop_number:
        raise HTTPException(status_code=400, detail="shop_number is required")
    assert_shop_number_unique_in_parent(session, parent_id=parent.id, shop_number=shop_number)

    tenant_name = payload.tenant_name.strip()
    if not tenant_name:
        raise HTTPException(status_code=400, detail="tenant_name is required")
    tenant_slug = tenant_slug_for_shop(
        MinitShopRow(shop_number=normalize_shop_number(shop_number) or shop_number, name=tenant_name, area=None, region=None)
    )

    existing_tenant = session.exec(select(Tenant).where(Tenant.slug == tenant_slug)).first()
    if existing_tenant:
        raise HTTPException(status_code=409, detail="Shop slug already exists")

    business_address = payload.business_address.strip()[:2000] if payload.business_address else None
    tenant = Tenant(
        name=tenant_name,
        slug=tenant_slug,
        plan_code=plan_code,
        business_address=business_address,
        shop_number=shop_number,
    )
    session.add(tenant)
    session.flush()

    # With contact details to hand, give the shop its own owner row so that
    # "Invite owner" reaches the operator. Without them it falls back to a copy
    # of the HQ login, which is what this endpoint always did — and which is
    # why so many shops show as sharing HQ's login today.
    owner_email = (payload.owner_email or "").strip().lower()
    if owner_email:
        if "@" not in owner_email or owner_email.startswith("@") or owner_email.endswith("@"):
            raise HTTPException(status_code=400, detail="owner_email is not a valid email address")
        owner_full_name = (payload.owner_full_name or "").strip() or owner_email
        owner_mobile = (payload.owner_mobile or "").strip() or None
        # Unusable until they claim it through an invite — HQ still gets in via
        # "Open shop", which is authorised by the site table, not this password.
        owner_password_hash = hash_unusable_password()
    else:
        owner_full_name = current_user.full_name
        owner_mobile = None
        owner_password_hash = current_user.password_hash

    new_owner = User(
        tenant_id=tenant.id,
        email=owner_email or current_user.email,
        full_name=owner_full_name,
        role="owner",
        password_hash=owner_password_hash,
        is_active=True,
        mobile=owner_mobile,
    )
    session.add(new_owner)
    session.flush()

    link_site(session, parent_id=parent.id, tenant=tenant, network_role=network_role)
    _record_event(
        session,
        parent_account_id=parent.id,
        tenant_id=tenant.id,
        actor_user_id=current_user.id,
        actor_email=current_user.email,
        event_type="provision_shop",
        event_summary=f"Provisioned {shop_type} Minit shop '{tenant.name}' ({tenant.slug})",
    )
    session.commit()
    session.refresh(parent)
    return _to_summary(session, parent, include_sites=True)


@router.delete("/me/sites/{tenant_id}", response_model=ParentAccountSummaryResponse)
def unlink_tenant_from_parent_account(
    tenant_id: UUID,
    auth: AuthContext = Depends(require_owner),
    session: Session = Depends(unscoped_session),
):
    current_user, parent = _parent_for_write(session, auth)


    if tenant_id == auth.tenant_id:
        raise HTTPException(
            status_code=400,
            detail="Cannot unlink the currently active site. Switch to another site first.",
        )

    sites = sites_for_parent(session, parent.id)

    if len(sites) <= 1:
        raise HTTPException(status_code=400, detail="Cannot unlink the last remaining site")

    membership = next((site for site in sites if site.tenant_id == tenant_id), None)
    if not membership:
        raise HTTPException(status_code=404, detail="Site is not linked to this parent account")
    if membership.network_role == NETWORK_ROLE_HQ:
        raise HTTPException(status_code=400, detail="Cannot unlink the HQ site")

    tenant = session.get(Tenant, membership.tenant_id)
    tenant_name = tenant.name if tenant else str(membership.tenant_id)
    tenant_slug = tenant.slug if tenant else "unknown"

    for r in session.exec(
        select(MobileSuburbRoute).where(
            MobileSuburbRoute.parent_account_id == parent.id,
            MobileSuburbRoute.target_tenant_id == tenant_id,
        )
    ).all():
        session.delete(r)
    if parent.mobile_lead_default_tenant_id == tenant_id:
        parent.mobile_lead_default_tenant_id = None
        session.add(parent)
    if parent.mobile_lead_escalation_tenant_id == tenant_id:
        parent.mobile_lead_escalation_tenant_id = None
        session.add(parent)

    session.delete(membership)
    _record_event(
        session,
        parent_account_id=parent.id,
        tenant_id=membership.tenant_id,
        actor_user_id=current_user.id,
        actor_email=current_user.email,
        event_type="unlink_tenant",
        event_summary=f"Unlinked site '{tenant_name}' ({tenant_slug})",
    )
    session.commit()
    session.refresh(parent)
    return _to_summary(session, parent)
