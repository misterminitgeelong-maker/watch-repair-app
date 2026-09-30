"""Fold each mobile van's duplicate "Mobile Services" shop into its "(MV)" shop.

Two imports created every mobile van twice:

* the mobile-operator import made "Mobile Services <place>" — a network
  *operator* numbered after the retail shop the van is based at, with routing
  but no franchisee (it runs on HQ's shared login);
* the franchisee directory import made "<place> (MV)" — the van's own Minit
  number and its real franchisee, but set up as a booking-only *retail* shop.

Merging keeps the (MV) shop — the person, the number, and any invite already
sent to it — makes it the operator, and points everything that referenced the
"Mobile Services" shop's future routing at it. Historical snapshots stay intact;
existing work and dispatch references block automatic retirement. The source is
suspended and its network/access links removed, with a before/after audit manifest.

A "Mobile Services" shop that holds real work (customers, jobs, quotes,
invoices, payments) is not merged: moving a shop's records between tenants is
a different, riskier job, and the preview says so instead.
"""
from __future__ import annotations

import re
import json
import hashlib
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

# Unknown tenant-owned tables block retirement by default. These setup/audit
# rows deliberately remain on the suspended source, with their original IDs.
PRESERVED_SETUP_TABLES = {
    "user", "parentaccountsite", "shopownerinvite", "parentlinkrequest",
    "parentaccounteventlog", "tenanteventlog", "mutationidempotencykey",
    "repairjobnumbercounter", "shoerepairjobnumbercounter", "invoicenumbercounter",
    "smslog", "emaillog", "importlog", "usernotificationpreference",
    "refreshsession",
}

ROUTING_REFERENCES = {
    ("mobilesuburbroute", "target_tenant_id"),
    ("parentaccount", "mobile_lead_default_tenant_id"),
    ("parentaccount", "mobile_lead_escalation_tenant_id"),
}
HISTORICAL_REFERENCES = {
    ("mobile_kpi_daily_snapshot", "operator_tenant_id"),
    ("vswt_weekly_shop_metric", "uploaded_by_tenant_id"),
}

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
    network_role: str = "retail"
    dispatch_paused: bool = True
    shop_phone: str | None = None
    shop_email: str | None = None
    dispatch_phone: str | None = None
    dispatch_phone_source: str = "missing"
    dispatch_email: str | None = None
    proposed_plan_code: str = ""
    routes_to_move: int = 0
    readiness_issues: list[str] = field(default_factory=list)
    preview_token: str = ""


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
        for name, table in tables.items():
            if name in PRESERVED_SETUP_TABLES or "tenant_id" not in table.c:
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
        and is_mobile_placeholder(tenants[s.tenant_id])
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
        mv = tenants[c.mv_tenant_id]
        op = tenants.get(c.operator_tenant_id)
        site = next(s for s in sites if s.tenant_id == mv.id)
        c.network_role = site.network_role
        c.dispatch_paused = mv.mobile_dispatch_paused or site.network_role != NETWORK_ROLE_OPERATOR
        c.shop_phone = mv.shop_phone or (op.shop_phone if op else None)
        c.shop_email = mv.shop_email or (op.shop_email if op else None)
        c.dispatch_phone = effective_dispatch_phone(mv, op)
        c.dispatch_phone_source = "MV dispatch" if (mv.mobile_dispatch_phone or "").strip() else (
            "Mobile Services dispatch" if op and (op.mobile_dispatch_phone or "").strip() else "missing")
        from .sms import operator_dispatch_email
        c.dispatch_email = c.shop_email or operator_dispatch_email(session, mv)
        c.proposed_plan_code = proposed_plan(mv, op)
        if op:
            from .models import MobileSuburbRoute
            c.routes_to_move = session.exec(select(sa_func.count()).select_from(MobileSuburbRoute)
                .where(MobileSuburbRoute.parent_account_id == parent_id).where(MobileSuburbRoute.target_tenant_id == op.id)).one()
        c.readiness_issues = readiness_issues(session, mv, op)
        if not c.dispatch_email:
            c.readiness_issues.append("No dispatch email; SMS is required")
        if not c.shop_phone:
            c.readiness_issues.append("No shop contact phone")
        if op is not None:
            blockers = merge_blockers(session, parent_id, mv, op)
        else:
            blockers = []
        if blockers:
            c.blocked = True
            c.preselected = False
            c.note = "; ".join(blockers)
        c.preview_token = preview_token(session, parent_id, mv, op, blockers=blockers)

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


def is_mobile_placeholder(tenant: Tenant) -> bool:
    return (tenant.slug.startswith("minit-mobile-") and not is_mv_name(tenant.name)
            and tenant.is_active and not tenant.merged_into_tenant_id)


def effective_dispatch_phone(mv: Tenant, op: Tenant | None = None) -> str | None:
    return ((mv.mobile_dispatch_phone or "").strip()
            or ((op.mobile_dispatch_phone or "").strip() if op else "") or None)


def valid_dispatch_phone(phone: str | None) -> bool:
    # Validate AU mobile / international format, not actual delivery. HQ confirms ownership.
    value = re.sub(r"[\s()\-]", "", phone or "")
    return bool(re.fullmatch(r"04\d{8}|\+614\d{8}|\+[1-9]\d{7,14}", value))


def proposed_plan(mv: Tenant, op: Tenant | None = None) -> str:
    return (op.plan_code if op else "basic_auto_key") if (mv.plan_code or "") in _BOOKING_ONLY_PLANS else mv.plan_code


def readiness_issues(session: Session, mv: Tenant, op: Tenant | None = None, phone: str | None = None) -> list[str]:
    from .dependencies import PLAN_FEATURES, normalize_plan_code
    from .parent_network import tenant_is_live
    issues: list[str] = []
    if not mv.is_active or mv.merged_into_tenant_id:
        issues.append("MV shop is inactive or retired")
    if not tenant_is_live(session, mv.id):
        issues.append("The franchisee must accept their invite before dispatch activation")
    if not valid_dispatch_phone(phone if phone is not None else effective_dispatch_phone(mv, op)):
        issues.append("A valid, confirmed dispatch mobile is required; shop phone is not used automatically")
    if "auto_key" not in PLAN_FEATURES.get(normalize_plan_code(proposed_plan(mv, op)), set()):
        issues.append("The proposed plan does not allow auto-key work")
    if not session.exec(select(User).where(User.tenant_id == mv.id).where(User.is_active == True)).first():  # noqa: E712
        issues.append("No active user can access this shop")
    return issues


def merge_blockers(session: Session, parent_id: UUID, mv: Tenant, op: Tenant) -> list[str]:
    blockers = []
    work = business_record_counts(session, op.id)
    if work:
        blockers.append("Source holds records: " + ", ".join(f"{n} {t}" for t, n in sorted(work.items())))
    if not mv.is_active or mv.merged_into_tenant_id or not is_mobile_placeholder(op):
        blockers.append("Both shops must be active; source must be an imported Mobile Services placeholder")
    other_sites = session.exec(select(ParentAccountSite).where(ParentAccountSite.tenant_id == op.id)
                               .where(ParentAccountSite.parent_account_id != parent_id)).all()
    if other_sites:
        blockers.append("Source belongs to another network; review separately")
    for table, column in _tenant_reference_columns():
        key = (table.name, column.name)
        if key in HISTORICAL_REFERENCES:
            continue
        stmt = select(sa_func.count()).select_from(table).where(column == op.id)
        if key in ROUTING_REFERENCES:
            scope = table.c.id if table.name == "parentaccount" else table.c.parent_account_id
            stmt = stmt.where(scope != parent_id)
        if session.execute(stmt).scalar_one():
            blockers.append(f"Review existing references: {table.name}.{column.name}")
    # JSON isn't a foreign key. Never leave an in-flight or saved candidate list pointing at retirement.
    from .models import MobileLeadDispatch
    for dispatch in session.exec(select(MobileLeadDispatch)).all():
        try:
            candidates = json.loads(dispatch.candidate_operator_ids_json)
            if not isinstance(candidates, list):
                raise ValueError("Expected candidate array")
        except (TypeError, ValueError):
            blockers.append("Invalid dispatch candidate data; review before merging")
            break
        if any(str(value) == str(op.id) for value in candidates):
            blockers.append("Source appears in a dispatch candidate list; resolve it before merging")
            break
    return blockers


def preview_token(session: Session, parent_id: UUID, mv: Tenant, op: Tenant | None,
                  *, blockers: list[str] | None = None) -> str:
    """Bind confirmation to identities, contacts, membership, routes and current blockers."""
    fields = ("id", "name", "slug", "shop_number", "plan_code", "is_active", "mobile_dispatch_paused",
              "merged_into_tenant_id", "mobile_dispatch_phone", "shop_phone", "shop_email", "business_address",
              "base_lat", "base_lng", "ring_radius_km")
    tenants = [mv] + ([op] if op else [])
    state = {"tenants": [{f: getattr(t, f) for f in fields} for t in tenants],
             "sites": [s.model_dump(mode="json") for s in session.exec(select(ParentAccountSite)
                       .where(col(ParentAccountSite.tenant_id).in_([t.id for t in tenants]))
                       .order_by(ParentAccountSite.id)).all()],
             "blockers": blockers if blockers is not None else (merge_blockers(session, parent_id, mv, op) if op else [])}
    state["users"] = [{f: getattr(u, f) for f in ("id", "tenant_id", "email", "full_name", "mobile", "is_active", "role")}
                      for u in session.exec(select(User).where(col(User.tenant_id).in_([t.id for t in tenants]))
                                            .order_by(User.id)).all()]
    state["routes"] = []
    if op:
        for table, column in _tenant_reference_columns():
            if (table.name, column.name) in ROUTING_REFERENCES:
                state["routes"].extend({"table": table.name, "column": column.name, "id": r[0]}
                                       for r in session.execute(select(table.c.id).where(column == op.id).order_by(table.c.id)))
    return hashlib.sha256(json.dumps(state, default=str, sort_keys=True).encode()).hexdigest()


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
    expected_preview_token: str | None = None,
    activate_dispatch: bool = False,
    dispatch_phone: str | None = None,
) -> dict[str, int]:
    """Make the (MV) shop the operator and retire the Mobile Services shop.

    Returns how many references moved, per table. Commits on success.
    """
    if mv_tenant_id == operator_tenant_id:
        raise MvMergeError("Pick two different shops")
    # Serialise competing merges. Production rollout must also quiesce affected writers.
    session.exec(select(Tenant).where(col(Tenant.id).in_([mv_tenant_id, operator_tenant_id]))
                 .order_by(Tenant.id).with_for_update().execution_options(populate_existing=True)).all()
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
    if op_site.network_role != NETWORK_ROLE_OPERATOR or not is_mobile_placeholder(op):
        raise MvMergeError(f"'{op.name}' is not a Mobile Services operator")
    blockers = merge_blockers(session, parent.id, mv, op)
    if expected_preview_token is not None and expected_preview_token != preview_token(session, parent.id, mv, op, blockers=blockers):
        raise MvMergeError("Preview changed; refresh and review this pair again")
    if blockers:
        raise MvMergeError("; ".join(blockers))
    phone = dispatch_phone.strip() if dispatch_phone is not None else effective_dispatch_phone(mv, op)
    if activate_dispatch:
        issues = readiness_issues(session, mv, op, phone)
        if issues:
            raise MvMergeError("; ".join(issues))

    changed_fields = ("plan_code", "mobile_dispatch_phone", "mobile_dispatch_paused", "business_address",
                      "shop_phone", "shop_email", "base_lat", "base_lng", "ring_radius_km",
                      "is_active", "auth_revoked_at", "merged_into_tenant_id")
    manifest = {"version": 1, "source_tenant_id": str(op.id), "destination_tenant_id": str(mv.id),
                "tenant_before": {str(t.id): {f: getattr(t, f) for f in changed_fields} for t in (mv, op)},
                "site_before": mv_site.model_dump(mode="json"), "deleted_links": [op_site.model_dump(mode="json")],
                "deleted_grants": [], "revoked_invites": [], "references": []}

    moved: dict[str, int] = {}
    with without_scope(session):
        for table, column in _tenant_reference_columns():
            if (table.name, column.name) not in ROUTING_REFERENCES:
                continue
            scope = table.c.id if table.name == "parentaccount" else table.c.parent_account_id
            row_ids = list(session.execute(select(table.c.id).where(column == op.id).where(scope == parent.id)).scalars())
            stmt = update(table).where(column == op.id).where(scope == parent.id).values({column.name: mv.id})
            try:
                result = session.execute(stmt)
            except IntegrityError as exc:
                session.rollback()
                raise MvMergeError(f"Reference conflict in {table.name}; no changes saved") from exc
            if result.rowcount:
                moved[f"{table.name}.{column.name}"] = int(result.rowcount)
                manifest["references"].append({"table": table.name, "column": column.name,
                                               "ids": [str(i) for i in row_ids], "before": str(op.id), "after": str(mv.id)})

    # The van inherits what made the other shop an operator.
    if (mv.plan_code or "") in _BOOKING_ONLY_PLANS and op.plan_code:
        mv.plan_code = op.plan_code
    if not (mv.mobile_dispatch_phone or "").strip() and op.mobile_dispatch_phone:
        mv.mobile_dispatch_phone = op.mobile_dispatch_phone
    if dispatch_phone is not None:
        mv.mobile_dispatch_phone = phone or None
    mv.mobile_dispatch_paused = not activate_dispatch
    if not (mv.business_address or "").strip() and op.business_address:
        mv.business_address = op.business_address
    if not (mv.shop_phone or "").strip() and op.shop_phone:
        mv.shop_phone = op.shop_phone
    if not (mv.shop_email or "").strip() and op.shop_email:
        mv.shop_email = op.shop_email
    if mv.base_lat is None and mv.base_lng is None:
        mv.base_lat, mv.base_lng = op.base_lat, op.base_lng
        mv.ring_radius_km = op.ring_radius_km
    session.add(mv)
    mv_site.network_role = NETWORK_ROLE_OPERATOR
    if mv_site.region_id is None and op_site.region_id is not None:
        mv_site.region_id = op_site.region_id
    session.add(mv_site)

    # Retire the Mobile Services shop: off the network, suspended, no
    # lingering HQ grants or claim links. Business records are never deleted.
    for row in session.exec(select(ShopOwnerInvite).where(ShopOwnerInvite.tenant_id == op.id)).all():
        if row.status == "pending":
            manifest["revoked_invites"].append({"id": str(row.id), "before": row.status, "after": "revoked"})
            row.status = "revoked"
            session.add(row)
    op_user_ids = [u.id for u in session.exec(select(User).where(User.tenant_id == op.id)).all()]
    if op_user_ids:
        for grant in session.exec(
            select(ParentAccountUser)
            .where(ParentAccountUser.parent_account_id == parent.id)
            .where(col(ParentAccountUser.user_id).in_(op_user_ids))
        ).all():
            manifest["deleted_grants"].append(grant.model_dump(mode="json"))
            session.delete(grant)
    session.delete(op_site)
    op.is_active = False
    op.mobile_dispatch_paused = True
    op.merged_into_tenant_id = mv.id
    op.auth_revoked_at = datetime.now(timezone.utc)
    session.add(op)

    manifest["tenant_after"] = {str(t.id): {f: getattr(t, f) for f in changed_fields} for t in (mv, op)}
    manifest["site_after"] = mv_site.model_dump(mode="json")

    session.add(
        ParentAccountEventLog(
            parent_account_id=parent.id,
            tenant_id=mv.id,
            actor_user_id=actor.id,
            actor_email=actor.email,
            event_type="mobile_van_merged",
            details_json=json.dumps(manifest, default=str, sort_keys=True),
            event_summary=(
                f"Merged '{op.name}' (#{op.shop_number or '-'}, {op.slug}) into '{mv.name}' "
                f"(#{mv.shop_number or '-'}, {mv.slug}); '{op.slug}' suspended, not deleted"
            ),
        )
    )
    session.commit()
    return moved


def update_mv_operator(session: Session, *, parent: ParentAccount, tenant_id: UUID, actor: User,
                       activate: bool = False, dispatch_phone: str | None = None,
                       expected_preview_token: str) -> str:
    """Classify safely, or explicitly activate a reviewed van without a remaining duplicate."""
    tenant = session.exec(select(Tenant).where(Tenant.id == tenant_id).with_for_update()
                          .execution_options(populate_existing=True)).first()
    site = session.exec(select(ParentAccountSite).where(ParentAccountSite.parent_account_id == parent.id)
                        .where(ParentAccountSite.tenant_id == tenant_id)).first()
    if not tenant or not site or site.network_role == "hq" or not tenant.is_active or not is_mv_name(tenant.name) or tenant.merged_into_tenant_id:
        raise MvMergeError("Choose an active MV shop in this network")
    candidate = next((c for c in find_mv_merge_candidates(session, parent.id) if c.mv_tenant_id == tenant_id), None)
    if not candidate or candidate.preview_token != expected_preview_token:
        raise MvMergeError("Preview changed; refresh and review this shop again")
    before = {"network_role": site.network_role, "dispatch_paused": tenant.mobile_dispatch_paused,
              "plan_code": tenant.plan_code, "dispatch_phone": tenant.mobile_dispatch_phone}
    if activate:
        if candidate.operator_tenant_id:
            raise MvMergeError("Resolve the matching Mobile Services operator before activating this MV")
        issues = readiness_issues(session, tenant, phone=dispatch_phone)
        if issues:
            raise MvMergeError("; ".join(issues))
        tenant.plan_code = proposed_plan(tenant)
        tenant.mobile_dispatch_phone = (dispatch_phone or tenant.mobile_dispatch_phone or "").strip()
        tenant.mobile_dispatch_paused = False
    elif site.network_role != NETWORK_ROLE_OPERATOR:
        tenant.mobile_dispatch_paused = True
    site.network_role = NETWORK_ROLE_OPERATOR
    session.add(tenant)
    session.add(site)
    after = {"network_role": site.network_role, "dispatch_paused": tenant.mobile_dispatch_paused,
             "plan_code": tenant.plan_code, "dispatch_phone": tenant.mobile_dispatch_phone}
    session.add(ParentAccountEventLog(parent_account_id=parent.id, tenant_id=tenant.id,
                actor_user_id=actor.id, actor_email=actor.email,
                event_type="mobile_operator_activated" if activate else "mobile_operator_classified",
                event_summary=f"{'Activated dispatch for' if activate else 'Classified as operator:'} {tenant.name}",
                details_json=json.dumps({"before": before, "after": after})))
    session.commit()
    return "Dispatch activated" if activate else "Classified as operator; existing dispatch state preserved"
