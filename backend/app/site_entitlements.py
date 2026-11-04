"""Entitlements on a site: what it can use and who pays.

Billing to a network counts active entitlements whose payer is the network,
never sites. This module proposes the starting set from today's plans
(``plan_backfill``), applies it only against a matching preview token, and
reports usage for invoicing.
"""
from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from uuid import UUID

from sqlmodel import Session, col, select

from .dependencies import normalize_plan_code
from .minit_branding import is_minit_hq_ui
from .models import ParentAccount, ParentAccountEventLog, ParentAccountSite, SiteEntitlement, Tenant, User
from .tenant_scope import without_scope

KINDS = ("booking", "mobile_services", "pro")
PAYERS = ("parent", "tenant", "comp")  # comp = free, never invoiced


def _is_minit_parent(session: Session, parent_id: UUID) -> bool:
    with without_scope(session):
        hq = session.exec(select(ParentAccountSite).where(ParentAccountSite.parent_account_id == parent_id)
                          .where(ParentAccountSite.network_role == "hq")).all()
        tenants = session.exec(select(Tenant).where(col(Tenant.id).in_([h.tenant_id for h in hq]))).all() if hq else []
    return any(is_minit_hq_ui(t) for t in tenants)


def active_entitlements(session: Session, parent_id: UUID) -> list[SiteEntitlement]:
    with without_scope(session):
        return list(session.exec(select(SiteEntitlement).where(SiteEntitlement.parent_account_id == parent_id)
                                 .where(SiteEntitlement.ended_at == None)).all())  # noqa: E711


# Sites that never get an entitlement, with the reason shown on the dry run (Sam, 4 Nov 2026).
EXCLUDED_SHOP_NUMBERS = {
    "0101": "MinitR test record; ignored",
    "01111": "Rhett test record; ignored",
    "3904": "Mobile Operator #3904 is unidentified; Sam to confirm before anything is granted",
}
#: Pro that is given free (never invoiced to Minit or the shop).
COMPED_PRO_SLUGS = {"minit-6441": "Complimentary Pro (Baldivis tester)"}
#: Support office's own vans: mobile services only, no booking, never folded into a shop.
SUPPORT_OFFICE_VAN_NUMBERS = {"4903"}


def plan_backfill(session: Session, parent: ParentAccount) -> dict:
    """Entitlements we would create, from each site's PLAN, plus what we skip or flag.

    booking_only -> booking; operator plans (basic_auto_key, minit_operator) -> mobile_services;
    anything else on a network shop -> booking. Pro adds pro (paid by the shop, or comped).
    Only Minit networks get a proposal.
    """
    from .minit_mv_merge import is_mobile_placeholder
    from .parent_network import OPERATOR_PLAN_CODES

    out: dict = {"rows": [], "skipped": [], "flagged": []}
    if not _is_minit_parent(session, parent.id):
        return out
    have = {(e.site_id, e.kind) for e in active_entitlements(session, parent.id)}
    with without_scope(session):
        sites = session.exec(select(ParentAccountSite).where(ParentAccountSite.parent_account_id == parent.id)).all()
        tenants = {t.id: t for t in session.exec(select(Tenant).where(
            col(Tenant.id).in_([s.tenant_id for s in sites]))).all()} if sites else {}

    def ident(site, tenant):
        return {"site_id": str(site.id), "tenant_id": str(tenant.id), "name": tenant.name,
                "shop_number": tenant.shop_number}

    def add(site, tenant, kind, payer):
        if (site.id, kind) not in have:
            out["rows"].append({**ident(site, tenant), "kind": kind, "payer": payer})

    for site in sites:
        tenant = tenants.get(site.tenant_id)
        if not tenant or not tenant.is_active or tenant.merged_into_tenant_id or site.network_role == "hq":
            continue
        number = (tenant.shop_number or "").strip()
        if number in EXCLUDED_SHOP_NUMBERS:
            out["skipped"].append({**ident(site, tenant), "reason": EXCLUDED_SHOP_NUMBERS[number]})
            continue
        if is_mobile_placeholder(tenant):
            out["skipped"].append({**ident(site, tenant), "reason": "Imported Mobile Services placeholder, never invited"})
            continue
        plan = normalize_plan_code(tenant.plan_code)
        is_operator_plan = plan in OPERATOR_PLAN_CODES
        if is_operator_plan != (site.network_role == "operator"):
            out["flagged"].append({**ident(site, tenant), "plan": plan, "network_role": site.network_role,
                                   "note": "Role and plan disagree; granted by plan. Confirm whether it is a van only or a shop with a van"})
        if number in SUPPORT_OFFICE_VAN_NUMBERS:
            add(site, tenant, "mobile_services", "parent")
            continue
        if is_operator_plan:
            add(site, tenant, "mobile_services", "parent")
        else:
            add(site, tenant, "booking", "parent")
        if tenant.slug in COMPED_PRO_SLUGS:
            add(site, tenant, "pro", "comp")
        elif plan == "pro":
            add(site, tenant, "pro", "tenant")
    key = lambda r: (r["kind"], r["shop_number"] or "", r["name"], r["site_id"])  # noqa: E731
    out["rows"].sort(key=key)
    out["skipped"].sort(key=lambda r: (r["shop_number"] or "", r["name"]))
    out["flagged"].sort(key=lambda r: (r["shop_number"] or "", r["name"]))
    return out


def backfill_token(rows: list[dict]) -> str:
    return hashlib.sha256(json.dumps(rows, sort_keys=True).encode()).hexdigest()


def apply_backfill(session: Session, *, parent: ParentAccount, actor: User, expected_token: str) -> int:
    rows = plan_backfill(session, parent)["rows"]
    if backfill_token(rows) != expected_token:
        raise ValueError("Preview changed; refresh and review again")
    now = datetime.now(timezone.utc)
    for r in rows:
        session.add(SiteEntitlement(site_id=UUID(r["site_id"]), parent_account_id=parent.id, kind=r["kind"],
                                    payer=r["payer"], started_at=now, source="plan_backfill"))
    session.add(ParentAccountEventLog(
        parent_account_id=parent.id, actor_user_id=actor.id, actor_email=actor.email,
        event_type="entitlements_backfilled", details_json=json.dumps(rows, sort_keys=True),
        event_summary=f"Granted {len(rows)} starting entitlements from current plans"))
    session.commit()
    return len(rows)


def usage(session: Session, parent_id: UUID) -> dict:
    """Active entitlements by kind and payer, for invoicing the network."""
    out: dict[str, dict[str, int]] = {}
    for e in active_entitlements(session, parent_id):
        out.setdefault(e.kind, {}).setdefault(e.payer, 0)
        out[e.kind][e.payer] += 1
    return out


def mobile_services_tenant_ids(session: Session, parent_id: UUID) -> set[UUID]:
    """Tenants whose site holds an active mobile_services entitlement."""
    with without_scope(session):
        rows = session.exec(
            select(ParentAccountSite.tenant_id)
            .join(SiteEntitlement, SiteEntitlement.site_id == ParentAccountSite.id)
            .where(ParentAccountSite.parent_account_id == parent_id)
            .where(SiteEntitlement.kind == "mobile_services")
            .where(SiteEntitlement.ended_at == None)  # noqa: E711
        ).all()
    return set(rows)


def mv_numbers_by_tenant(session: Session, parent_id: UUID) -> dict[UUID, str]:
    with without_scope(session):
        rows = session.exec(select(ParentAccountSite.tenant_id, ParentAccountSite.mv_number)
                            .where(ParentAccountSite.parent_account_id == parent_id)
                            .where(ParentAccountSite.mv_number != None)).all()  # noqa: E711
    return {tid: mv for tid, mv in rows if mv}
