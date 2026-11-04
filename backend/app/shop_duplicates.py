"""Find and retire duplicate records for one Minit shop number.

A physical location should be one site per shop number. Older imports and the
pre-network "pro" accounts left some numbers with two records (for example a
retail shop and its "Mobile Services" placeholder). This module lists those
groups and retires the duplicate WITHOUT deleting anything and without moving
business records: a duplicate that holds real work is blocked and reported.

What moves: suburb routes / lead settings that pointed at the duplicate, and
(optionally) named staff logins. The duplicate is suspended, off the network and
marked ``merged_into_tenant_id``, with a manifest in the HQ activity log so the
change can be reversed by hand.
"""
from __future__ import annotations

import json
from datetime import datetime, timezone
from uuid import UUID

from sqlalchemy import update
from sqlalchemy.exc import IntegrityError
from sqlmodel import Session, col, select

from .minit_mv_merge import (
    MvMergeError, ROUTING_REFERENCES, _tenant_reference_columns, business_record_counts,
    is_mobile_placeholder, merge_blockers, preview_token,
)
from .models import (
    ParentAccount, ParentAccountEventLog, ParentAccountSite, ParentAccountUser,
    ParentMobileReportingSource, ShopOwnerInvite, Tenant, User,
)
from .tenant_scope import without_scope

HQ_ROLE = "hq"


def _number(value: str | None) -> str:
    return (value or "").strip()


def members_for_parent(session: Session, parent_id: UUID) -> dict[UUID, dict]:
    """Every active tenant tied to the network, either as a site or a reporting link."""
    out: dict[UUID, dict] = {}
    with without_scope(session):
        sites = session.exec(select(ParentAccountSite).where(ParentAccountSite.parent_account_id == parent_id)).all()
        sources = session.exec(select(ParentMobileReportingSource).where(
            ParentMobileReportingSource.parent_account_id == parent_id)).all()
        ids = {s.tenant_id for s in sites} | {s.tenant_id for s in sources}
        tenants = {t.id: t for t in session.exec(select(Tenant).where(col(Tenant.id).in_(ids))).all()} if ids else {}
    for site in sites:
        if site.network_role == HQ_ROLE:
            continue
        out[site.tenant_id] = {"tenant": tenants.get(site.tenant_id), "site": site, "source": None}
    for source in sources:
        row = out.setdefault(source.tenant_id, {"tenant": tenants.get(source.tenant_id), "site": None, "source": None})
        row["source"] = source
    return {k: v for k, v in out.items() if v["tenant"] and v["tenant"].is_active and not v["tenant"].merged_into_tenant_id}


def _member_read(session: Session, parent_id: UUID, row: dict) -> dict:
    tenant, site, source = row["tenant"], row["site"], row["source"]
    records = business_record_counts(session, tenant.id)
    users = session.exec(select(User).where(User.tenant_id == tenant.id).where(User.is_active == True)).all()  # noqa: E712
    return {
        "tenant_id": tenant.id, "name": tenant.name, "slug": tenant.slug, "shop_number": tenant.shop_number,
        "plan_code": tenant.plan_code,
        "network_role": site.network_role if site else None,
        "is_member": site is not None,
        "reporting_link": source is not None and source.enabled,
        "placeholder": is_mobile_placeholder(tenant),
        "records": records, "record_total": sum(records.values()),
        "users": [{"id": u.id, "email": u.email, "full_name": u.full_name, "role": u.role} for u in users],
    }


def _suggest_keep(members: list[dict]) -> dict:
    return sorted(members, key=lambda m: (-m["record_total"], not m["is_member"] and 1 or 0, m["placeholder"], m["name"]))[0]


def find_duplicate_groups(session: Session, parent: ParentAccount, keep_ids: set[UUID] | None = None) -> list[dict]:
    """Groups of active records sharing a number. ``keep_ids`` lets the caller pick which record survives."""
    members = members_for_parent(session, parent.id)
    by_number: dict[str, list[UUID]] = {}
    for tid, row in members.items():
        number = _number(row["tenant"].shop_number)
        if number:
            by_number.setdefault(number, []).append(tid)
    groups = []
    for number, tids in sorted(by_number.items()):
        if len(tids) < 2:
            continue
        reads = [_member_read(session, parent.id, members[t]) for t in tids]
        chosen = [m for m in reads if keep_ids and m["tenant_id"] in keep_ids]
        keep = chosen[0] if len(chosen) == 1 else _suggest_keep(reads)
        keep_tenant = members[keep["tenant_id"]]["tenant"]
        for m in reads:
            if m["tenant_id"] == keep["tenant_id"]:
                m["blockers"], m["preview_token"] = [], None
                continue
            op = members[m["tenant_id"]]["tenant"]
            m["blockers"] = duplicate_blockers(session, parent.id, keep_tenant, op)
            m["preview_token"] = preview_token(session, parent.id, keep_tenant, op, blockers=m["blockers"])
        groups.append({"shop_number": number, "suggested_keep": keep["tenant_id"], "members": reads})
    return groups


def duplicate_blockers(session: Session, parent_id: UUID, keep: Tenant, retire: Tenant) -> list[str]:
    blockers = merge_blockers(session, parent_id, keep, retire, require_placeholder=False)
    if _number(keep.shop_number) != _number(retire.shop_number) or not _number(keep.shop_number):
        blockers.append("The two records must have the same shop number")
    return blockers


def shop_number_conflict(session: Session, parent_id: UUID, shop_number: str | None,
                         *, ignore_tenant_id: UUID | None = None, role: str | None = None) -> str | None:
    """Message naming an existing active record with this number in the network, else None."""
    number = _number(shop_number)
    if not number:
        return None
    for tid, row in members_for_parent(session, parent_id).items():
        if tid == ignore_tenant_id or _number(row["tenant"].shop_number) != number:
            continue
        return (f"Shop #{number} already exists as '{row['tenant'].name}'. "
                "Use Duplicate shop numbers to merge records instead of creating a second one.")
    return None


def retire_duplicate(
    session: Session, *, parent: ParentAccount, keep_tenant_id: UUID, retire_tenant_id: UUID, actor: User,
    expected_preview_token: str, move_user_ids: list[UUID] | None = None,
    user_email_overrides: dict[UUID, str] | None = None,
) -> dict:
    """Retire ``retire`` into ``keep``. Commits on success; raises MvMergeError otherwise."""
    if keep_tenant_id == retire_tenant_id:
        raise MvMergeError("Pick two different shops")
    session.exec(select(Tenant).where(col(Tenant.id).in_([keep_tenant_id, retire_tenant_id]))
                 .order_by(Tenant.id).with_for_update().execution_options(populate_existing=True)).all()
    members = members_for_parent(session, parent.id)
    if keep_tenant_id not in members or retire_tenant_id not in members:
        raise MvMergeError("Both shops must be active and tied to this network")
    keep, retire = members[keep_tenant_id]["tenant"], members[retire_tenant_id]["tenant"]
    retire_site, retire_source = members[retire_tenant_id]["site"], members[retire_tenant_id]["source"]
    blockers = duplicate_blockers(session, parent.id, keep, retire)
    if expected_preview_token != preview_token(session, parent.id, keep, retire, blockers=blockers):
        raise MvMergeError("Preview changed; refresh and review this pair again")
    if blockers:
        raise MvMergeError("; ".join(blockers))

    manifest = {"version": 1, "kind": "duplicate_shop_retired", "keep_tenant_id": str(keep.id),
                "retire_tenant_id": str(retire.id),
                "retire_before": {f: getattr(retire, f) for f in ("is_active", "auth_revoked_at", "merged_into_tenant_id", "mobile_dispatch_paused")},
                "deleted_site": retire_site.model_dump(mode="json") if retire_site else None,
                "disabled_reporting_link": retire_source.model_dump(mode="json") if retire_source else None,
                "deleted_grants": [], "revoked_invites": [], "references": [], "moved_users": []}

    moved: dict[str, int] = {}
    with without_scope(session):
        for table, column in _tenant_reference_columns():
            if (table.name, column.name) not in ROUTING_REFERENCES:
                continue
            scope = table.c.id if table.name == "parentaccount" else table.c.parent_account_id
            row_ids = list(session.execute(select(table.c.id).where(column == retire.id).where(scope == parent.id)).scalars())
            try:
                result = session.execute(update(table).where(column == retire.id).where(scope == parent.id).values({column.name: keep.id}))
            except IntegrityError as exc:
                session.rollback()
                raise MvMergeError(f"Reference conflict in {table.name}; no changes saved") from exc
            if result.rowcount:
                moved[f"{table.name}.{column.name}"] = int(result.rowcount)
                manifest["references"].append({"table": table.name, "column": column.name,
                                               "ids": [str(i) for i in row_ids], "before": str(retire.id), "after": str(keep.id)})

    # Named staff logins move to the kept shop (as managers, never owners).
    move_ids = set(move_user_ids or [])
    retire_users = session.exec(select(User).where(User.tenant_id == retire.id)).all()
    unknown = move_ids - {u.id for u in retire_users}
    if unknown:
        raise MvMergeError("A selected login does not belong to the shop being retired")
    for user in retire_users:
        if user.id not in move_ids:
            continue
        email = (user_email_overrides or {}).get(user.id, user.email).strip().lower()
        taken = session.exec(select(User.id).where(User.tenant_id == keep.id).where(User.email == email)).first()
        if taken:
            raise MvMergeError(f"{email} already has a login at the kept shop")
        manifest["moved_users"].append({"id": str(user.id), "from_email": user.email, "to_email": email, "from_role": user.role})
        user.tenant_id = keep.id
        user.email = email
        user.role = "manager"
        session.add(user)
    session.flush()

    for row in session.exec(select(ShopOwnerInvite).where(ShopOwnerInvite.tenant_id == retire.id)).all():
        if row.status == "pending":
            manifest["revoked_invites"].append({"id": str(row.id), "before": row.status})
            row.status = "revoked"
            session.add(row)
    remaining = [u.id for u in retire_users if u.id not in move_ids]
    if remaining:
        for grant in session.exec(select(ParentAccountUser).where(ParentAccountUser.parent_account_id == parent.id)
                                  .where(col(ParentAccountUser.user_id).in_(remaining))).all():
            manifest["deleted_grants"].append(grant.model_dump(mode="json"))
            session.delete(grant)
    if retire_site is not None:
        session.delete(retire_site)
    if retire_source is not None:
        retire_source.enabled = False
        retire_source.dispatch_enabled = False
        session.add(retire_source)
    retire.is_active = False
    retire.mobile_dispatch_paused = True
    retire.merged_into_tenant_id = keep.id
    retire.auth_revoked_at = datetime.now(timezone.utc)
    session.add(retire)
    session.add(ParentAccountEventLog(
        parent_account_id=parent.id, tenant_id=keep.id, actor_user_id=actor.id, actor_email=actor.email,
        event_type="duplicate_shop_retired", details_json=json.dumps(manifest, default=str, sort_keys=True),
        event_summary=(f"Retired duplicate '{retire.name}' ({retire.slug}) into '{keep.name}' ({keep.slug}) "
                       f"for shop #{keep.shop_number}; suspended, not deleted"),
    ))
    session.commit()
    return {"moved": moved, "users_moved": len(manifest["moved_users"])}
