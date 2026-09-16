"""Minit HQ network administration: support access into shops, site
attributes, HQ staff roles and regions.

Cross-tenant by design, like the rest of the parent-account surface — every
endpoint takes ``unscoped_session`` and is gated by the caller's network role
(see ``parent_network``), not by whose email is on a shop's owner row.
"""

from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import Session, col, func, select

from ..database import unscoped_session
from ..dependencies import AuthContext, get_auth_context, require_feature, require_owner
from ..models import (
    NETWORK_ROLE_HQ,
    PARENT_ROLE_HQ_ADMIN,
    ParentAccount,
    ParentAccountSite,
    ParentAccountSiteRead,
    ParentAccountSiteUpdateRequest,
    ParentAccountUserGrantRequest,
    ParentAccountUserRead,
    ParentEnterShopRequest,
    ParentEnterShopResponse,
    Region,
    RegionCreateRequest,
    RegionRead,
    RegionUpdateRequest,
    Tenant,
    TenantEventLog,
    User,
)
from ..parent_network import (
    grant_parent_role,
    implicit_hq_role_for_tenant_user,
    normalize_region_code,
    parent_role_for_user,
    parent_user_row,
    parent_users,
    region_by_code,
    regions_for_parent,
    site_for_tenant_in_parent,
    sites_for_parent,
    validate_network_role,
    validate_parent_role,
)
from ..security import create_access_token
from .parent_accounts import (
    _owner_users_by_tenant,
    _parent_for_read,
    _parent_for_scoped_read,
    _parent_for_write,
    _record_event,
    _site_reads_for_sites,
)

router = APIRouter(
    prefix="/v1/parent-accounts",
    tags=["parent-network"],
    dependencies=[Depends(require_feature("multi_site"))],
)

#: Support sessions into a linked shop last this long and cannot be refreshed.
HQ_ENTER_SHOP_MINUTES = 30


# ── HQ support access into a linked shop ─────────────────────────────────────


@router.post("/me/sites/{tenant_id}/enter", response_model=ParentEnterShopResponse)
def enter_linked_shop(
    tenant_id: UUID,
    payload: ParentEnterShopRequest | None = None,
    auth: AuthContext = Depends(require_owner),
    session: Session = Depends(unscoped_session),
):
    """Open a short support session inside one of the network's own shops.

    Provisioned shops start out sharing HQ's login, and the moment a shop
    takes its own credentials that shared login stops working — which used to
    mean HQ lost the ability to get into the shops it had most successfully
    onboarded. This is the front door instead: any HQ admin can enter any
    linked site, authorised by the site table rather than by whose email
    happens to be on the shop's owner row.

    The token is anchored on the shop's first active owner login and carries
    that login's own role, so the auth layer treats it like any other session
    for that user. It lasts HQ_ENTER_SHOP_MINUTES and has no refresh token.
    Both the shop's audit log and the network's activity feed record who
    entered.
    """
    current_user, parent = _parent_for_write(session, auth)

    site = site_for_tenant_in_parent(session, parent.id, tenant_id)
    if site is None:
        raise HTTPException(status_code=404, detail="Site is not linked to your account")
    tenant = session.get(Tenant, tenant_id)
    if not tenant:
        raise HTTPException(status_code=404, detail="Tenant not found")
    if not tenant.is_active:
        raise HTTPException(status_code=403, detail="That shop is suspended")
    if tenant.id == auth.tenant_id:
        raise HTTPException(status_code=400, detail="You are already in this site")

    owner = _owner_users_by_tenant(session, [tenant.id]).get(tenant.id)
    if owner is None:
        raise HTTPException(status_code=400, detail="This shop has no active owner account")

    # The reason is what makes this accountable rather than merely audited:
    # it lands in the shop's own inbox, so the shop sees HQ was in and why.
    reason = (payload.reason if payload else None) or ""
    reason = " ".join(reason.split())[:300]
    reason_suffix = f" — {reason}" if reason else ""
    session.add(
        TenantEventLog(
            tenant_id=tenant.id,
            actor_user_id=current_user.id,
            actor_email=current_user.email,
            entity_type="session",
            entity_id=owner.id,
            event_type="hq_enter_shop",
            event_summary=(
                f"HQ ({current_user.full_name or current_user.email}, {parent.name}) opened this shop "
                f"for up to {HQ_ENTER_SHOP_MINUTES} min{reason_suffix}"
            ),
        )
    )
    _record_event(
        session,
        parent_account_id=parent.id,
        tenant_id=tenant.id,
        actor_user_id=current_user.id,
        actor_email=current_user.email,
        event_type="enter_shop",
        event_summary=f"Entered '{tenant.name}' ({tenant.slug}) as {owner.email}{reason_suffix}",
    )
    session.commit()

    access_token, expires = create_access_token(
        tenant.id, owner.id, owner.role, expires_minutes=HQ_ENTER_SHOP_MINUTES
    )
    return ParentEnterShopResponse(
        access_token=access_token,
        expires_in_seconds=expires,
        tenant_id=tenant.id,
        tenant_slug=tenant.slug,
        tenant_name=tenant.name,
        acting_as_user_id=owner.id,
        acting_as_email=owner.email,
    )


# ── site attributes: network role, region ────────────────────────────────────


@router.patch("/me/sites/{tenant_id}", response_model=ParentAccountSiteRead)
def update_linked_site(
    tenant_id: UUID,
    payload: ParentAccountSiteUpdateRequest,
    auth: AuthContext = Depends(require_owner),
    session: Session = Depends(unscoped_session),
):
    """Change what a site *is* in the network without touching its plan."""
    current_user, parent = _parent_for_write(session, auth)
    site = site_for_tenant_in_parent(session, parent.id, tenant_id)
    if site is None:
        raise HTTPException(status_code=404, detail="Site is not linked to your account")
    tenant = session.get(Tenant, tenant_id)
    if not tenant:
        raise HTTPException(status_code=404, detail="Tenant not found")

    changes: list[str] = []
    if payload.network_role is not None:
        role = validate_network_role(payload.network_role)
        if role == NETWORK_ROLE_HQ and site.network_role != NETWORK_ROLE_HQ:
            raise HTTPException(status_code=400, detail="A site cannot be promoted to HQ")
        if site.network_role == NETWORK_ROLE_HQ and role != NETWORK_ROLE_HQ:
            raise HTTPException(status_code=400, detail="The HQ site cannot change role")
        if role != site.network_role:
            changes.append(f"role {site.network_role} -> {role}")
            site.network_role = role

    if payload.clear_region:
        if site.region_id is not None:
            changes.append("region cleared")
            site.region_id = None
    elif payload.region_id is not None:
        region = session.get(Region, payload.region_id)
        if region is None or region.parent_account_id != parent.id:
            raise HTTPException(status_code=404, detail="Region not found")
        if site.region_id != region.id:
            changes.append(f"region -> {region.name}")
            site.region_id = region.id

    if changes:
        session.add(site)
        _record_event(
            session,
            parent_account_id=parent.id,
            tenant_id=tenant.id,
            actor_user_id=current_user.id,
            actor_email=current_user.email,
            event_type="site_updated",
            event_summary=f"Updated '{tenant.name}': " + ", ".join(changes),
        )
        session.commit()
        session.refresh(site)

    return _site_reads_for_sites(session, [site])[0]


# ── network users (HQ staff) ─────────────────────────────────────────────────


def _parent_user_reads(session: Session, parent: ParentAccount) -> list[ParentAccountUserRead]:
    """Everyone with effective network access: explicit grants, then the HQ
    tenant's own staff (implicit), then account-owner logins elsewhere."""
    rows = parent_users(session, parent.id)
    explicit_by_user = {r.user_id: r for r in rows}

    hq_sites = sites_for_parent(session, parent.id, network_role=NETWORK_ROLE_HQ)
    hq_tenant_ids = [site.tenant_id for site in hq_sites]
    site_tenant_ids = [site.tenant_id for site in sites_for_parent(session, parent.id)]

    candidates: list[User] = []
    seen: set[UUID] = set()
    if explicit_by_user:
        for u in session.exec(
            select(User).where(col(User.id).in_(list(explicit_by_user))).order_by(col(User.created_at).asc())
        ).all():
            if u.id not in seen:
                seen.add(u.id)
                candidates.append(u)
    if hq_tenant_ids:
        for u in session.exec(
            select(User)
            .where(col(User.tenant_id).in_(hq_tenant_ids))
            .where(User.is_active == True)  # noqa: E712
            .order_by(col(User.created_at).asc(), col(User.id).asc())
        ).all():
            if u.id not in seen:
                seen.add(u.id)
                candidates.append(u)
    # Account-owner logins outside the HQ tenant are the shared credentials a
    # provisioned shop starts with — the same human, already listed above when
    # the network has an HQ site. Only a generic group (no HQ site) needs them.
    if site_tenant_ids and parent.owner_email and not hq_tenant_ids:
        for u in session.exec(
            select(User)
            .where(col(User.tenant_id).in_(site_tenant_ids))
            .where(User.email == parent.owner_email)
            .where(User.is_active == True)  # noqa: E712
            .order_by(col(User.created_at).asc(), col(User.id).asc())
        ).all():
            if u.id not in seen:
                seen.add(u.id)
                candidates.append(u)

    tenant_ids = list({u.tenant_id for u in candidates})
    tenants_by_id = {
        t.id: t for t in session.exec(select(Tenant).where(col(Tenant.id).in_(tenant_ids))).all()
    } if tenant_ids else {}
    regions_by_id = {r.id: r for r in regions_for_parent(session, parent.id)}

    reads: list[ParentAccountUserRead] = []
    for user in candidates:
        row = explicit_by_user.get(user.id)
        region_id = row.region_id if row is not None else None
        if row is not None:
            role, source, since = row.role, "explicit", row.created_at
        elif user.tenant_id in hq_tenant_ids:
            role, source, since = implicit_hq_role_for_tenant_user(user), "hq_site", user.created_at
        else:
            role, source, since = PARENT_ROLE_HQ_ADMIN, "owner_email", user.created_at
        tenant = tenants_by_id.get(user.tenant_id)
        region = regions_by_id.get(region_id) if region_id else None
        reads.append(
            ParentAccountUserRead(
                user_id=user.id,
                tenant_id=user.tenant_id,
                tenant_slug=tenant.slug if tenant else "",
                email=user.email,
                full_name=user.full_name,
                tenant_role=user.role,
                role=role,
                region_id=region.id if region else None,
                region_name=region.name if region else None,
                source=source,
                is_active=user.is_active,
                created_at=since,
            )
        )
    return reads


def _admin_count(session: Session, parent: ParentAccount) -> int:
    return sum(1 for r in _parent_user_reads(session, parent) if r.role == PARENT_ROLE_HQ_ADMIN)


@router.get("/me/users", response_model=list[ParentAccountUserRead])
def list_parent_account_users(
    auth: AuthContext = Depends(get_auth_context),
    session: Session = Depends(unscoped_session),
):
    """Everyone with explicit network-level access."""
    _user, parent, _ = _parent_for_read(session, auth)
    return _parent_user_reads(session, parent)


@router.put("/me/users", response_model=list[ParentAccountUserRead])
def grant_parent_account_role(
    payload: ParentAccountUserGrantRequest,
    auth: AuthContext = Depends(require_owner),
    session: Session = Depends(unscoped_session),
):
    """Give a user in one of the network's sites an HQ role, or change it.

    Several people can now be HQ — an operations manager and a finance
    controller with different access — without anyone sharing an email.
    """
    current_user, parent = _parent_for_write(session, auth)
    role = validate_parent_role(payload.role)

    target: User | None = None
    if payload.user_id is not None:
        target = session.get(User, payload.user_id)
    elif payload.email:
        email = payload.email.strip().lower()
        site_tenant_ids = [site.tenant_id for site in sites_for_parent(session, parent.id)]
        if site_tenant_ids:
            target = session.exec(
                select(User)
                .where(User.email == email)
                .where(col(User.tenant_id).in_(site_tenant_ids))
                .where(User.is_active == True)  # noqa: E712
                .order_by(col(User.created_at).asc())
            ).first()
    else:
        raise HTTPException(status_code=400, detail="user_id or email is required")
    if target is None or not target.is_active:
        raise HTTPException(status_code=404, detail="User not found in this network")
    if site_for_tenant_in_parent(session, parent.id, target.tenant_id) is None:
        raise HTTPException(status_code=400, detail="That user's shop is not linked to this network")

    previous = parent_role_for_user(session, parent, target)
    if previous == PARENT_ROLE_HQ_ADMIN and role != PARENT_ROLE_HQ_ADMIN and _admin_count(session, parent) <= 1:
        raise HTTPException(status_code=400, detail="Cannot demote the last HQ admin")
    region: Region | None = None
    if payload.region_id is not None and role != PARENT_ROLE_HQ_ADMIN:
        region = session.get(Region, payload.region_id)
        if region is None or region.parent_account_id != parent.id:
            raise HTTPException(status_code=404, detail="Region not found")
    grant_parent_role(
        session, parent_id=parent.id, user_id=target.id, role=role, region_id=region.id if region else None
    )
    scope_text = f" for {region.name} only" if region else ""
    _record_event(
        session,
        parent_account_id=parent.id,
        tenant_id=target.tenant_id,
        actor_user_id=current_user.id,
        actor_email=current_user.email,
        event_type="parent_role_granted",
        event_summary=(
            f"Set {target.email} to {role}{scope_text}"
            if previous is None
            else f"Changed {target.email} from {previous} to {role}{scope_text}"
        ),
    )
    session.commit()
    return _parent_user_reads(session, parent)


@router.delete("/me/users/{user_id}", response_model=list[ParentAccountUserRead])
def revoke_parent_account_role(
    user_id: UUID,
    auth: AuthContext = Depends(require_owner),
    session: Session = Depends(unscoped_session),
):
    """Remove an explicit grant. Their shop login is untouched.

    Access implied by being in the HQ tenant is not a grant and cannot be
    revoked here — deactivate the user in the HQ tenant instead, or set them
    to hq_viewer explicitly.
    """
    current_user, parent = _parent_for_write(session, auth)
    row = parent_user_row(session, parent.id, user_id)
    if row is None:
        raise HTTPException(status_code=404, detail="User has no explicit access to this network")
    if user_id == current_user.id:
        raise HTTPException(status_code=400, detail="You cannot revoke your own access")
    if row.role == PARENT_ROLE_HQ_ADMIN and _admin_count(session, parent) <= 1:
        raise HTTPException(status_code=400, detail="Cannot remove the last HQ admin")
    target = session.get(User, user_id)
    session.delete(row)
    _record_event(
        session,
        parent_account_id=parent.id,
        tenant_id=target.tenant_id if target else None,
        actor_user_id=current_user.id,
        actor_email=current_user.email,
        event_type="parent_role_revoked",
        event_summary=f"Removed network access for {target.email if target else user_id}",
    )
    session.commit()
    return _parent_user_reads(session, parent)


# ── regions ──────────────────────────────────────────────────────────────────


def _region_reads(session: Session, parent: ParentAccount) -> list[RegionRead]:
    regions = regions_for_parent(session, parent.id)
    counts = {
        region_id: int(n)
        for region_id, n in session.exec(
            select(ParentAccountSite.region_id, func.count())
            .where(ParentAccountSite.parent_account_id == parent.id)
            .where(col(ParentAccountSite.region_id).is_not(None))
            .group_by(ParentAccountSite.region_id)
        ).all()
    }
    return [
        RegionRead(
            id=r.id,
            code=r.code,
            name=r.name,
            manager_name=r.manager_name,
            manager_email=r.manager_email,
            manager_phone=r.manager_phone,
            escalation_email=r.escalation_email,
            notes=r.notes,
            weekly_report_opt_in=bool(r.weekly_report_opt_in),
            last_weekly_report_sent_at=r.last_weekly_report_sent_at,
            site_count=counts.get(r.id, 0),
            created_at=r.created_at,
        )
        for r in regions
    ]


def _clean_optional(value: str | None, limit: int) -> str | None:
    if value is None:
        return None
    cleaned = value.strip()[:limit]
    return cleaned or None


@router.get("/me/regions", response_model=list[RegionRead])
def list_regions(
    auth: AuthContext = Depends(get_auth_context),
    session: Session = Depends(unscoped_session),
):
    """All regions for HQ; a regional manager sees only their own."""
    _user, parent, _, scope = _parent_for_scoped_read(session, auth)
    reads = _region_reads(session, parent)
    if scope is not None:
        reads = [r for r in reads if r.id == scope]
    return reads


@router.post("/me/regions", response_model=RegionRead)
def create_region(
    payload: RegionCreateRequest,
    auth: AuthContext = Depends(require_owner),
    session: Session = Depends(unscoped_session),
):
    current_user, parent = _parent_for_write(session, auth)
    name = payload.name.strip()
    if not name:
        raise HTTPException(status_code=400, detail="name is required")
    code = normalize_region_code(payload.code or name)
    if not code:
        raise HTTPException(status_code=400, detail="code is required")
    if region_by_code(session, parent.id, code) is not None:
        raise HTTPException(status_code=409, detail=f"Region '{code}' already exists")
    region = Region(
        parent_account_id=parent.id,
        code=code,
        name=name[:120],
        manager_name=_clean_optional(payload.manager_name, 200),
        manager_email=_clean_optional(payload.manager_email, 320),
        manager_phone=_clean_optional(payload.manager_phone, 80),
        escalation_email=_clean_optional(payload.escalation_email, 320),
        notes=_clean_optional(payload.notes, 2000),
    )
    session.add(region)
    _record_event(
        session,
        parent_account_id=parent.id,
        tenant_id=None,
        actor_user_id=current_user.id,
        actor_email=current_user.email,
        event_type="region_created",
        event_summary=f"Created region '{region.name}' ({region.code})",
    )
    session.commit()
    return next(r for r in _region_reads(session, parent) if r.id == region.id)


@router.patch("/me/regions/{region_id}", response_model=RegionRead)
def update_region(
    region_id: UUID,
    payload: RegionUpdateRequest,
    auth: AuthContext = Depends(require_owner),
    session: Session = Depends(unscoped_session),
):
    current_user, parent = _parent_for_write(session, auth)
    region = session.get(Region, region_id)
    if region is None or region.parent_account_id != parent.id:
        raise HTTPException(status_code=404, detail="Region not found")

    changes: list[str] = []
    if payload.name is not None:
        name = payload.name.strip()[:120]
        if not name:
            raise HTTPException(status_code=400, detail="name cannot be empty")
        if name != region.name:
            changes.append(f"name -> {name}")
            region.name = name
    for field, limit in (
        ("manager_name", 200),
        ("manager_email", 320),
        ("manager_phone", 80),
        ("escalation_email", 320),
        ("notes", 2000),
    ):
        value = getattr(payload, field)
        if value is None:
            continue
        cleaned = _clean_optional(value, limit)
        if cleaned != getattr(region, field):
            changes.append(field.replace("_", " "))
            setattr(region, field, cleaned)
    if payload.weekly_report_opt_in is not None and payload.weekly_report_opt_in != bool(region.weekly_report_opt_in):
        if payload.weekly_report_opt_in and not (region.manager_email or "").strip():
            raise HTTPException(status_code=400, detail="Set a manager email before turning on the weekly report")
        region.weekly_report_opt_in = payload.weekly_report_opt_in
        changes.append("weekly report " + ("on" if payload.weekly_report_opt_in else "off"))

    if changes:
        session.add(region)
        _record_event(
            session,
            parent_account_id=parent.id,
            tenant_id=None,
            actor_user_id=current_user.id,
            actor_email=current_user.email,
            event_type="region_updated",
            event_summary=f"Updated region '{region.name}': " + ", ".join(changes),
        )
        session.commit()
    return next(r for r in _region_reads(session, parent) if r.id == region.id)


@router.delete("/me/regions/{region_id}", response_model=list[RegionRead])
def delete_region(
    region_id: UUID,
    auth: AuthContext = Depends(require_owner),
    session: Session = Depends(unscoped_session),
):
    """Delete a region; its sites become unassigned."""
    current_user, parent = _parent_for_write(session, auth)
    region = session.get(Region, region_id)
    if region is None or region.parent_account_id != parent.id:
        raise HTTPException(status_code=404, detail="Region not found")
    for site in sites_for_parent(session, parent.id):
        if site.region_id == region.id:
            site.region_id = None
            session.add(site)
    session.delete(region)
    _record_event(
        session,
        parent_account_id=parent.id,
        tenant_id=None,
        actor_user_id=current_user.id,
        actor_email=current_user.email,
        event_type="region_deleted",
        event_summary=f"Deleted region '{region.name}' ({region.code})",
    )
    session.commit()
    return _region_reads(session, parent)
