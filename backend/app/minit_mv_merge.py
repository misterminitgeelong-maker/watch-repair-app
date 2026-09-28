"""Fold each mobile van's duplicate "Mobile Services" shop into its "(MV)" shop.

Two imports created every mobile van twice:

* the mobile-operator import made "Mobile Services <place>" — a network
  *operator* numbered after the retail shop the van is based at, with routing
  but no franchisee (it runs on HQ's shared login);
* the franchisee directory import made "<place> (MV)" — the van's own Minit
  number and its real franchisee, but set up as a booking-only *retail* shop.

Merging keeps the (MV) shop — the person, the number, and any invite already
sent to it — makes it the operator, and points everything that referenced the
"Mobile Services" shop (suburb routes, lead dispatch, booking targets, KPI
snapshots, network defaults) at it. The "Mobile Services" shop is unlinked from
the network and suspended, never deleted, so a wrong merge can be undone.

A "Mobile Services" shop that holds real work (customers, jobs, quotes,
invoices, payments) is not merged: moving a shop's records between tenants is
a different, riskier job, and the preview says so instead.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import datetime, timezone
from uuid import UUID

from sqlalchemy import func as sa_func
from sqlalchemy import update
from sqlalchemy.exc import IntegrityError
from sqlmodel import Session, SQLModel, col, select

from .models import (
    NETWORK_ROLE_OPERATOR,
    ParentAccount,
    ParentAccountEventLog,
    ParentAccountSite,
    ParentAccountUser,
    ShopOwnerInvite,
    Tenant,
    User,
)
from .tenant_scope import without_scope

#: Records that mean a shop has actually been used. Setup rows (users, logs,
#: counters, settings) don't block a merge.
BUSINESS_TABLES = (
    "customer",
    "autokeyjob",
    "autokeyquote",
    "autokeyinvoice",
    "repairjob",
    "shoerepairjob",
    "quote",
    "invoice",
    "payment",
    "customerorder",
    "customeraccount",
    "stockitem",
)

_BOOKING_ONLY_PLANS = {"booking_only", ""}


def _phone_key(value: str | None) -> str:
    """Last nine digits: enough to compare 0401 001 308 with +61401001308."""
    digits = re.sub(r"\D", "", value or "")
    return digits[-9:] if len(digits) >= 8 else ""


def _place_key(name: str | None) -> str:
    text = (name or "").lower()
    text = text.replace("(mv)", " ").replace("mobile services", " ")
    return re.sub(r"[^a-z0-9]+", "", text)


def is_mv_name(name: str | None) -> bool:
    return "(mv)" in (name or "").lower()


@dataclass
class MvMergeCandidate:
    mv_tenant_id: UUID
    mv_name: str
    mv_shop_number: str | None
    mv_owner: str
    operator_tenant_id: UUID | None = None
    operator_name: str | None = None
    operator_shop_number: str | None = None
    #: phone | shop_number | name — why these two were paired.
    reasons: list[str] = field(default_factory=list)
    #: Ticked on the review screen by default (strong evidence, no conflict).
    preselected: bool = False
    #: Why this pair needs a human look, or can't be merged at all.
    note: str | None = None
    blocked: bool = False


def _owners_by_tenant(session: Session, tenant_ids: list[UUID]) -> dict[UUID, User]:
    owners: dict[UUID, User] = {}
    if not tenant_ids:
        return owners
    for user in session.exec(
        select(User)
        .where(col(User.tenant_id).in_(tenant_ids))
        .where(User.role == "owner")
        .order_by(col(User.created_at).asc())
    ).all():
        owners.setdefault(user.tenant_id, user)
    return owners


def business_record_counts(session: Session, tenant_id: UUID) -> dict[str, int]:
    """Rows of real work a shop holds, by table (only tables with any)."""
    counts: dict[str, int] = {}
    tables = SQLModel.metadata.tables
    with without_scope(session):
        for name in BUSINESS_TABLES:
            table = tables.get(name)
            if table is None or "tenant_id" not in table.c:
                continue
            n = session.execute(
                select(sa_func.count()).select_from(table).where(table.c.tenant_id == tenant_id)
            ).scalar_one()
            if n:
                counts[name] = int(n)
    return counts


def _seed_dispatch_phones_by_place() -> dict[str, str]:
    """Dispatch phone per operator from the operator seed file, keyed by place.

    Backs up the tenant's own dispatch phone, which older imports didn't always
    store. Keyed by name because TSS matching renumbered some operators.
    """
    try:
        from .minit_mobile_operators import load_mobile_operators_seed

        return {
            _place_key(op.operator_label): _phone_key(op.dispatch_phone)
            for op in load_mobile_operators_seed()
            if _place_key(op.operator_label) and _phone_key(op.dispatch_phone)
        }
    except Exception:
        return {}


def find_mv_merge_candidates(session: Session, parent_id: UUID) -> list[MvMergeCandidate]:
    sites = session.exec(select(ParentAccountSite).where(ParentAccountSite.parent_account_id == parent_id)).all()
    tenant_ids = [s.tenant_id for s in sites]
    tenants = {t.id: t for t in session.exec(select(Tenant).where(col(Tenant.id).in_(tenant_ids))).all()} if tenant_ids else {}
    owners = _owners_by_tenant(session, tenant_ids)

    mvs = [s for s in sites if s.tenant_id in tenants and is_mv_name(tenants[s.tenant_id].name)]
    operators = [
        s for s in sites
        if s.tenant_id in tenants
        and s.network_role == NETWORK_ROLE_OPERATOR
        and not is_mv_name(tenants[s.tenant_id].name)
    ]

    seed_phones = _seed_dispatch_phones_by_place()

    def op_phones(tenant: Tenant) -> set[str]:
        owner = owners.get(tenant.id)
        keys = {_phone_key(tenant.mobile_dispatch_phone), _phone_key(tenant.shop_phone)}
        keys.add(seed_phones.get(_place_key(tenant.name), ""))
        if owner is not None:
            keys.add(_phone_key(owner.mobile))
        return {k for k in keys if k}

    def mv_phones(tenant: Tenant) -> set[str]:
        owner = owners.get(tenant.id)
        keys = {_phone_key(tenant.shop_phone)}
        if owner is not None:
            keys.add(_phone_key(owner.mobile))
        return {k for k in keys if k}

    candidates: list[MvMergeCandidate] = []
    for mv_site in mvs:
        mv = tenants[mv_site.tenant_id]
        owner = owners.get(mv.id)
        candidate = MvMergeCandidate(
            mv_tenant_id=mv.id,
            mv_name=mv.name,
            mv_shop_number=mv.shop_number,
            mv_owner=(owner.full_name if owner else "") or "",
        )
        by_reason: dict[str, list[Tenant]] = {"phone": [], "shop_number": [], "name": []}
        for op_site in operators:
            op = tenants[op_site.tenant_id]
            if mv_phones(mv) & op_phones(op):
                by_reason["phone"].append(op)
            if mv.shop_number and op.shop_number and mv.shop_number.strip() == op.shop_number.strip():
                by_reason["shop_number"].append(op)
            if _place_key(mv.name) and _place_key(mv.name) == _place_key(op.name):
                by_reason["name"].append(op)

        matched = {op.id: op for ops in by_reason.values() for op in ops}
        if not matched:
            candidate.note = "No matching Mobile Services shop"
            candidates.append(candidate)
            continue
        if len(matched) > 1:
            names = ", ".join(sorted(op.name for op in matched.values()))
            # Keep the strongest match visible, but make the human choose.
            strongest = (by_reason["phone"] or by_reason["shop_number"] or by_reason["name"])[0]
            candidate.operator_tenant_id = strongest.id
            candidate.operator_name = strongest.name
            candidate.operator_shop_number = strongest.shop_number
            candidate.reasons = [r for r, ops in by_reason.items() if strongest in ops]
            candidate.note = f"Matches more than one shop ({names}) — check before merging"
            candidates.append(candidate)
            continue

        op = next(iter(matched.values()))
        candidate.operator_tenant_id = op.id
        candidate.operator_name = op.name
        candidate.operator_shop_number = op.shop_number
        candidate.reasons = [r for r, ops in by_reason.items() if op in ops]
        strong = "phone" in candidate.reasons or "shop_number" in candidate.reasons
        candidate.preselected = strong
        if not strong:
            candidate.note = "Name matches but the phone numbers differ — check it's the same van"
        candidates.append(candidate)

    # One Mobile Services shop can only fold into one van.
    claimed: dict[UUID, list[MvMergeCandidate]] = {}
    for c in candidates:
        if c.operator_tenant_id is not None:
            claimed.setdefault(c.operator_tenant_id, []).append(c)
    for group in claimed.values():
        if len(group) > 1:
            for c in group:
                c.preselected = False
                c.note = "Another MV shop matches the same Mobile Services shop — pick one"

    for c in candidates:
        if c.operator_tenant_id is None:
            continue
        work = business_record_counts(session, c.operator_tenant_id)
        if work:
            c.blocked = True
            c.preselected = False
            summary = ", ".join(f"{n} {t}" for t, n in sorted(work.items()))
            c.note = f"The Mobile Services shop already holds records ({summary}) — not merged automatically"

    return sorted(candidates, key=lambda c: (c.operator_tenant_id is None, c.mv_name.lower()))


def unmatched_operators(session: Session, parent_id: UUID, candidates: list[MvMergeCandidate]) -> list[Tenant]:
    matched = {c.operator_tenant_id for c in candidates if c.operator_tenant_id}
    sites = session.exec(
        select(ParentAccountSite)
        .where(ParentAccountSite.parent_account_id == parent_id)
        .where(ParentAccountSite.network_role == NETWORK_ROLE_OPERATOR)
    ).all()
    out: list[Tenant] = []
    for site in sites:
        tenant = session.get(Tenant, site.tenant_id)
        if tenant is not None and site.tenant_id not in matched and not is_mv_name(tenant.name):
            out.append(tenant)
    return sorted(out, key=lambda t: t.name.lower())


class MvMergeError(ValueError):
    pass


def _tenant_reference_columns():
    """Every column pointing at a shop other than the owning ``tenant_id``."""
    for table in SQLModel.metadata.tables.values():
        for column in table.columns:
            if column.name == "tenant_id":
                continue
            if any(fk.column.table.name == "tenant" for fk in column.foreign_keys):
                yield table, column


def merge_mv_into_operator(
    session: Session,
    *,
    parent: ParentAccount,
    mv_tenant_id: UUID,
    operator_tenant_id: UUID,
    actor: User,
) -> dict[str, int]:
    """Make the (MV) shop the operator and retire the Mobile Services shop.

    Returns how many references moved, per table. Commits on success.
    """
    if mv_tenant_id == operator_tenant_id:
        raise MvMergeError("Pick two different shops")
    mv_site = session.exec(
        select(ParentAccountSite)
        .where(ParentAccountSite.parent_account_id == parent.id)
        .where(ParentAccountSite.tenant_id == mv_tenant_id)
    ).first()
    op_site = session.exec(
        select(ParentAccountSite)
        .where(ParentAccountSite.parent_account_id == parent.id)
        .where(ParentAccountSite.tenant_id == operator_tenant_id)
    ).first()
    mv = session.get(Tenant, mv_tenant_id)
    op = session.get(Tenant, operator_tenant_id)
    if mv_site is None or op_site is None or mv is None or op is None:
        raise MvMergeError("Both shops must be linked to this network")
    if not is_mv_name(mv.name):
        raise MvMergeError(f"'{mv.name}' is not an (MV) shop")
    if op_site.network_role != NETWORK_ROLE_OPERATOR or is_mv_name(op.name):
        raise MvMergeError(f"'{op.name}' is not a Mobile Services operator")
    work = business_record_counts(session, op.id)
    if work:
        raise MvMergeError(f"'{op.name}' already holds records and was not merged")

    moved: dict[str, int] = {}
    with without_scope(session):
        for table, column in _tenant_reference_columns():
            stmt = update(table).where(column == op.id).values({column.name: mv.id})
            try:
                with session.begin_nested():
                    result = session.execute(stmt)
            except IntegrityError:
                # The van already has its own row where the operator had one
                # (a per-day snapshot, say). The van's row wins; drop the other.
                with session.begin_nested():
                    result = session.execute(table.delete().where(column == op.id))
            if result.rowcount:
                moved[f"{table.name}.{column.name}"] = int(result.rowcount)

    # The van inherits what made the other shop an operator.
    if (mv.plan_code or "") in _BOOKING_ONLY_PLANS and op.plan_code:
        mv.plan_code = op.plan_code
    if not (mv.mobile_dispatch_phone or "").strip() and op.mobile_dispatch_phone:
        mv.mobile_dispatch_phone = op.mobile_dispatch_phone
    if not (mv.business_address or "").strip() and op.business_address:
        mv.business_address = op.business_address
    if not (mv.shop_phone or "").strip() and op.shop_phone:
        mv.shop_phone = op.shop_phone
    if not (mv.shop_email or "").strip() and op.shop_email:
        mv.shop_email = op.shop_email
    session.add(mv)
    mv_site.network_role = NETWORK_ROLE_OPERATOR
    if mv_site.region_id is None and op_site.region_id is not None:
        mv_site.region_id = op_site.region_id
    session.add(mv_site)

    # Retire the Mobile Services shop: off the network, suspended, no
    # lingering HQ grants or claim links. Nothing is deleted.
    for row in session.exec(select(ShopOwnerInvite).where(ShopOwnerInvite.tenant_id == op.id)).all():
        if row.status == "pending":
            row.status = "revoked"
            session.add(row)
    op_user_ids = [u.id for u in session.exec(select(User).where(User.tenant_id == op.id)).all()]
    if op_user_ids:
        for grant in session.exec(
            select(ParentAccountUser)
            .where(ParentAccountUser.parent_account_id == parent.id)
            .where(col(ParentAccountUser.user_id).in_(op_user_ids))
        ).all():
            session.delete(grant)
    session.delete(op_site)
    op.is_active = False
    op.auth_revoked_at = datetime.now(timezone.utc)
    session.add(op)

    session.add(
        ParentAccountEventLog(
            parent_account_id=parent.id,
            tenant_id=mv.id,
            actor_user_id=actor.id,
            actor_email=actor.email,
            event_type="mobile_van_merged",
            event_summary=(
                f"Merged '{op.name}' (#{op.shop_number or '-'}, {op.slug}) into '{mv.name}' "
                f"(#{mv.shop_number or '-'}, {mv.slug}); '{op.slug}' suspended, not deleted"
            ),
        )
    )
    session.commit()
    return moved
