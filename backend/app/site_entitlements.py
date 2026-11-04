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
PAYERS = ("parent", "tenant")


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


def plan_backfill(session: Session, parent: ParentAccount) -> list[dict]:
    """Rows we would create from current plans. Only Minit networks get a proposal."""
    if not _is_minit_parent(session, parent.id):
        return []
    have = {(e.site_id, e.kind) for e in active_entitlements(session, parent.id)}
    with without_scope(session):
        sites = session.exec(select(ParentAccountSite).where(ParentAccountSite.parent_account_id == parent.id)).all()
        tenants = {t.id: t for t in session.exec(select(Tenant).where(
            col(Tenant.id).in_([s.tenant_id for s in sites]))).all()} if sites else {}
    rows: list[dict] = []

    def add(site, tenant, kind, payer):
        if (site.id, kind) not in have:
            rows.append({"site_id": str(site.id), "tenant_id": str(tenant.id), "name": tenant.name,
                         "shop_number": tenant.shop_number, "kind": kind, "payer": payer})

    for site in sites:
        tenant = tenants.get(site.tenant_id)
        if not tenant or not tenant.is_active or tenant.merged_into_tenant_id or site.network_role == "hq":
            continue
        if site.network_role == "operator":
            add(site, tenant, "mobile_services", "parent")
            continue
        add(site, tenant, "booking", "parent")
        if normalize_plan_code(tenant.plan_code) == "pro":
            add(site, tenant, "pro", "tenant")
    return sorted(rows, key=lambda r: (r["kind"], r["shop_number"] or "", r["name"], r["site_id"]))


def backfill_token(rows: list[dict]) -> str:
    return hashlib.sha256(json.dumps(rows, sort_keys=True).encode()).hexdigest()


def apply_backfill(session: Session, *, parent: ParentAccount, actor: User, expected_token: str) -> int:
    rows = plan_backfill(session, parent)
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
