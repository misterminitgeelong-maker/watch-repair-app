"""Parent-account network model: sites, users, roles and regions.

One place that answers "which shops are in this network", "what is each one",
"who can act on it" and "which region is it in" — so every route reads the
same tables the same way instead of re-deriving the answer from plan codes or
email strings.

Every lookup here is cross-tenant by design (a network spans its shops), so
each one lifts the ORM tenant scope for exactly the query it runs.
"""

from __future__ import annotations

from uuid import UUID

from fastapi import HTTPException
from sqlmodel import Session, col, select

from .dependencies import normalize_plan_code
from .models import (
    NETWORK_ROLE_HQ,
    NETWORK_ROLE_OPERATOR,
    NETWORK_ROLE_RETAIL,
    NETWORK_ROLES,
    PARENT_ROLE_HQ_ADMIN,
    PARENT_ROLE_HQ_VIEWER,
    PARENT_ROLES,
    ParentAccount,
    ParentAccountSite,
    ParentAccountUser,
    Region,
    Tenant,
    User,
)
from .tenant_scope import without_scope

#: Plans whose tenants act as mobile operators. Used only to *default* a
#: site's network_role at provisioning time — after that the site row is the
#: source of truth and billing can change without moving the shop.
OPERATOR_PLAN_CODES: frozenset[str] = frozenset(
    {
        "basic_auto_key",
        "basic_shoe_auto_key",
        "basic_watch_auto_key",
        "basic_all_tabs",
    }
)


# ── network_role ─────────────────────────────────────────────────────────────


def default_network_role_for_plan(plan_code: str | None) -> str:
    plan = normalize_plan_code(plan_code)
    if plan == "minit_hq":
        return NETWORK_ROLE_HQ
    if plan in OPERATOR_PLAN_CODES:
        return NETWORK_ROLE_OPERATOR
    return NETWORK_ROLE_RETAIL


def default_network_role_for_tenant(tenant: Tenant) -> str:
    """Plan-derived default, with the Minit HQ tenant recognised by slug as
    well — its plan is coerced to minit_hq lazily, on first login."""
    from .minit_branding import effective_plan_code, is_minit_hq_ui

    if is_minit_hq_ui(tenant):
        return NETWORK_ROLE_HQ
    return default_network_role_for_plan(effective_plan_code(tenant))


def validate_network_role(value: str | None) -> str:
    role = (value or "").strip().lower()
    if role not in NETWORK_ROLES:
        raise HTTPException(
            status_code=400,
            detail=f"network_role must be one of: {', '.join(sorted(NETWORK_ROLES))}",
        )
    return role


# ── sites ────────────────────────────────────────────────────────────────────


def sites_for_parent(
    session: Session,
    parent_id: UUID,
    *,
    network_role: str | None = None,
) -> list[ParentAccountSite]:
    stmt = (
        select(ParentAccountSite)
        .where(ParentAccountSite.parent_account_id == parent_id)
        .order_by(col(ParentAccountSite.created_at).asc(), col(ParentAccountSite.id).asc())
    )
    if network_role:
        stmt = stmt.where(ParentAccountSite.network_role == network_role)
    with without_scope(session):
        return list(session.exec(stmt).all())


def site_for_tenant_in_parent(session: Session, parent_id: UUID, tenant_id: UUID) -> ParentAccountSite | None:
    with without_scope(session):
        return session.exec(
            select(ParentAccountSite)
            .where(ParentAccountSite.parent_account_id == parent_id)
            .where(ParentAccountSite.tenant_id == tenant_id)
        ).first()


def sites_for_tenant(session: Session, tenant_id: UUID) -> list[ParentAccountSite]:
    """Every network this tenant belongs to, oldest link first."""
    with without_scope(session):
        return list(
            session.exec(
                select(ParentAccountSite)
                .where(ParentAccountSite.tenant_id == tenant_id)
                .order_by(col(ParentAccountSite.created_at).asc(), col(ParentAccountSite.id).asc())
            ).all()
        )


def parent_ids_for_tenant(session: Session, tenant_id: UUID) -> list[UUID]:
    return [s.parent_account_id for s in sites_for_tenant(session, tenant_id)]


def tenant_network_role(session: Session, tenant_id: UUID) -> str | None:
    """The tenant's role in its network. If it is in several, the role is
    taken from the HQ-anchored network first, then the oldest link."""
    sites = sites_for_tenant(session, tenant_id)
    if not sites:
        return None
    parent_ids = [s.parent_account_id for s in sites]
    hq_parents = _parents_with_hq_site(session, parent_ids)
    for site in sites:
        if site.parent_account_id in hq_parents:
            return site.network_role
    return sites[0].network_role


def tenant_is_operator(session: Session, tenant_id: UUID) -> bool:
    return tenant_network_role(session, tenant_id) == NETWORK_ROLE_OPERATOR


def _parents_with_hq_site(session: Session, parent_ids: list[UUID]) -> set[UUID]:
    if not parent_ids:
        return set()
    with without_scope(session):
        rows = session.exec(
            select(ParentAccountSite.parent_account_id)
            .where(col(ParentAccountSite.parent_account_id).in_(parent_ids))
            .where(ParentAccountSite.network_role == NETWORK_ROLE_HQ)
        ).all()
    return set(rows)


def resolve_common_parent_id(session: Session, *tenant_ids: UUID) -> UUID | None:
    """The one network all these tenants share.

    A shop and an operator can share more than one network (HQ's, plus a
    franchisee's own group if they own both). Bookings and reports are
    attributed to the network that has an HQ site, falling back to the
    oldest shared parent — deterministically, never by set iteration order.
    """
    if not tenant_ids:
        return None
    common: set[UUID] | None = None
    first_order: list[UUID] = []
    for tid in tenant_ids:
        ids = parent_ids_for_tenant(session, tid)
        if not first_order:
            first_order = ids
        common = set(ids) if common is None else (common & set(ids))
        if not common:
            return None
    assert common is not None
    ordered = [pid for pid in first_order if pid in common]
    hq_parents = _parents_with_hq_site(session, ordered)
    for pid in ordered:
        if pid in hq_parents:
            return pid
    return ordered[0] if ordered else None


def linked_tenant_ids_for_parent(
    session: Session,
    parent_id: UUID,
    *,
    network_role: str | None = None,
) -> list[UUID]:
    return [s.tenant_id for s in sites_for_parent(session, parent_id, network_role=network_role)]


def linked_tenants_for_parent(
    session: Session,
    parent_id: UUID,
    *,
    network_role: str | None = None,
) -> list[Tenant]:
    """All linked tenants in one query, in link order."""
    ids = linked_tenant_ids_for_parent(session, parent_id, network_role=network_role)
    if not ids:
        return []
    with without_scope(session):
        tenants = session.exec(select(Tenant).where(col(Tenant.id).in_(ids))).all()
    by_id = {t.id: t for t in tenants}
    return [by_id[tid] for tid in ids if tid in by_id]


def operator_tenants_for_parent(session: Session, parent_id: UUID) -> list[Tenant]:
    return linked_tenants_for_parent(session, parent_id, network_role=NETWORK_ROLE_OPERATOR)


def retail_tenants_for_parent(session: Session, parent_id: UUID) -> list[Tenant]:
    return linked_tenants_for_parent(session, parent_id, network_role=NETWORK_ROLE_RETAIL)


def link_site(
    session: Session,
    *,
    parent_id: UUID,
    tenant: Tenant,
    network_role: str | None = None,
    known_tenant_ids: set[UUID] | None = None,
    region_cache: dict[str, Region] | None = None,
) -> ParentAccountSite | None:
    """Add ``tenant`` to the network if it is not already there.

    Returns the new row, or None when the link already existed. The site's
    role defaults from the tenant's plan and its region from the tenant's
    raw TSS region string. ``known_tenant_ids`` / ``region_cache`` let bulk
    importers skip a query per row.
    """
    if known_tenant_ids is not None:
        if tenant.id in known_tenant_ids:
            return None
    elif site_for_tenant_in_parent(session, parent_id, tenant.id) is not None:
        return None
    site = ParentAccountSite(
        parent_account_id=parent_id,
        tenant_id=tenant.id,
        network_role=network_role or default_network_role_for_tenant(tenant),
        region_id=resolve_region_id_for_tenant(session, parent_id, tenant, cache=region_cache),
    )
    session.add(site)
    if known_tenant_ids is not None:
        known_tenant_ids.add(tenant.id)
    return site


# ── users / roles ────────────────────────────────────────────────────────────


def validate_parent_role(value: str | None) -> str:
    role = (value or "").strip().lower()
    if role not in PARENT_ROLES:
        raise HTTPException(
            status_code=400,
            detail=f"role must be one of: {', '.join(sorted(PARENT_ROLES))}",
        )
    return role


def parent_users(session: Session, parent_id: UUID) -> list[ParentAccountUser]:
    with without_scope(session):
        return list(
            session.exec(
                select(ParentAccountUser)
                .where(ParentAccountUser.parent_account_id == parent_id)
                .order_by(col(ParentAccountUser.created_at).asc(), col(ParentAccountUser.id).asc())
            ).all()
        )


def parent_user_row(session: Session, parent_id: UUID, user_id: UUID) -> ParentAccountUser | None:
    with without_scope(session):
        return session.exec(
            select(ParentAccountUser)
            .where(ParentAccountUser.parent_account_id == parent_id)
            .where(ParentAccountUser.user_id == user_id)
        ).first()


def grant_parent_role(
    session: Session,
    *,
    parent_id: UUID,
    user_id: UUID,
    role: str,
) -> ParentAccountUser:
    row = parent_user_row(session, parent_id, user_id)
    if row:
        if row.role != role:
            row.role = role
            session.add(row)
        return row
    row = ParentAccountUser(parent_account_id=parent_id, user_id=user_id, role=role)
    session.add(row)
    return row


def _hq_site_parent_ids_for_tenant(session: Session, tenant_id: UUID) -> list[UUID]:
    with without_scope(session):
        return list(
            session.exec(
                select(ParentAccountSite.parent_account_id)
                .where(ParentAccountSite.tenant_id == tenant_id)
                .where(ParentAccountSite.network_role == NETWORK_ROLE_HQ)
                .order_by(col(ParentAccountSite.created_at).asc(), col(ParentAccountSite.id).asc())
            ).all()
        )


def implicit_hq_role_for_tenant_user(user: User) -> str:
    """What a login inside the HQ tenant gets without an explicit grant.

    The HQ tenant *is* HQ: its owners run the network, everyone else there
    can read it. Explicit ParentAccountUser rows override this per person.
    """
    return PARENT_ROLE_HQ_ADMIN if user.role in ("owner", "platform_admin") else PARENT_ROLE_HQ_VIEWER


def parents_for_user(session: Session, user: User) -> list[ParentAccount]:
    """Networks this user can act on, in a fixed order.

    1. explicit access rows (oldest grant first);
    2. networks whose HQ site is the user's own tenant;
    3. for logins with neither, the parent account(s) whose ``owner_email``
       matches — that is what keeps the HQ owner's cloned credentials inside
       a provisioned shop working, and it stops matching the moment the shop
       completes its invite and takes its own email.
    """
    with without_scope(session):
        explicit = session.exec(
            select(ParentAccount)
            .join(ParentAccountUser, ParentAccountUser.parent_account_id == ParentAccount.id)
            .where(ParentAccountUser.user_id == user.id)
            .order_by(col(ParentAccountUser.created_at).asc(), col(ParentAccount.created_at).asc())
        ).all()
        hq_parent_ids = _hq_site_parent_ids_for_tenant(session, user.tenant_id)
        via_hq_site = (
            session.exec(
                select(ParentAccount)
                .where(col(ParentAccount.id).in_(hq_parent_ids))
                .order_by(col(ParentAccount.created_at).asc(), col(ParentAccount.id).asc())
            ).all()
            if hq_parent_ids and user.is_active
            else []
        )
        by_email = session.exec(
            select(ParentAccount)
            .where(ParentAccount.owner_email == user.email)
            .order_by(col(ParentAccount.created_at).asc(), col(ParentAccount.id).asc())
        ).all()
    ordered: list[ParentAccount] = []
    seen: set[UUID] = set()
    for parent in list(explicit) + list(via_hq_site) + list(by_email):
        if parent.id in seen:
            continue
        seen.add(parent.id)
        ordered.append(parent)
    return ordered


def parent_role_for_user(session: Session, parent: ParentAccount, user: User) -> str | None:
    """The user's network-level role, or None if they have no access.

    Explicit grant first; then the implicit role for logins inside the
    network's HQ tenant; then ``owner_email`` as the account owner, so the
    one email that always had full access keeps it.
    """
    row = parent_user_row(session, parent.id, user.id)
    if row:
        return row.role
    if not user.is_active:
        return None
    if parent.id in _hq_site_parent_ids_for_tenant(session, user.tenant_id):
        return implicit_hq_role_for_tenant_user(user)
    if parent.owner_email == user.email:
        return PARENT_ROLE_HQ_ADMIN
    return None


def require_parent_role(
    session: Session,
    parent: ParentAccount,
    user: User,
    *,
    write: bool,
) -> str:
    role = parent_role_for_user(session, parent, user)
    if role is None:
        raise HTTPException(status_code=403, detail="No access to this parent account")
    if write and role != PARENT_ROLE_HQ_ADMIN:
        raise HTTPException(status_code=403, detail="HQ admin role required")
    return role


def is_hq_viewer_or_admin(role: str | None) -> bool:
    return role in (PARENT_ROLE_HQ_ADMIN, PARENT_ROLE_HQ_VIEWER)


# ── regions ──────────────────────────────────────────────────────────────────


def normalize_region_code(value: str | None) -> str | None:
    """``" vic  south "`` → ``"VIC SOUTH"``. None when blank."""
    if value is None:
        return None
    code = " ".join(value.strip().upper().split())
    return code[:40] or None


def regions_for_parent(session: Session, parent_id: UUID) -> list[Region]:
    with without_scope(session):
        return list(
            session.exec(
                select(Region)
                .where(Region.parent_account_id == parent_id)
                .order_by(col(Region.created_at).asc(), col(Region.id).asc())
            ).all()
        )


def region_by_code(session: Session, parent_id: UUID, code: str) -> Region | None:
    with without_scope(session):
        return session.exec(
            select(Region)
            .where(Region.parent_account_id == parent_id)
            .where(Region.code == code)
        ).first()


def get_or_create_region(
    session: Session,
    *,
    parent_id: UUID,
    code: str,
    name: str | None = None,
    cache: dict[str, Region] | None = None,
) -> Region:
    """Upsert by normalised code. ``cache`` lets importers avoid a query per row."""
    if cache is not None and code in cache:
        return cache[code]
    region = region_by_code(session, parent_id, code)
    if region is None:
        region = Region(parent_account_id=parent_id, code=code, name=(name or code)[:120])
        session.add(region)
        session.flush()
    if cache is not None:
        cache[code] = region
    return region


def resolve_region_id_for_tenant(
    session: Session,
    parent_id: UUID,
    tenant: Tenant,
    *,
    cache: dict[str, Region] | None = None,
) -> UUID | None:
    """Map the tenant's raw TSS region string onto this network's Region rows."""
    code = normalize_region_code(tenant.minit_region)
    if not code:
        return None
    return get_or_create_region(session, parent_id=parent_id, code=code, cache=cache).id


def sync_site_region_from_tenant(
    session: Session,
    *,
    parent_id: UUID,
    tenant: Tenant,
    cache: dict[str, Region] | None = None,
) -> None:
    """After an import changes ``tenant.minit_region``, point the site at the
    matching Region (creating it if needed)."""
    site = site_for_tenant_in_parent(session, parent_id, tenant.id)
    if site is None:
        return
    region_id = resolve_region_id_for_tenant(session, parent_id, tenant, cache=cache)
    if site.region_id != region_id:
        site.region_id = region_id
        session.add(site)
