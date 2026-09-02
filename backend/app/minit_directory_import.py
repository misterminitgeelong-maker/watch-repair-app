"""Plan/apply importing the Mister Minit "Organisation Graph" directory export
(see minit_directory_parser.py) into real tenants and owner accounts.

Unlike the existing TSS-xlsx importer (import_minit_shops in minit_provision.py),
which provisions every shop under the shared HQ owner login, this importer knows
each shop's real franchisee — name, email, mobile — from the directory export, so
it can:

  - give a single-site franchisee their own owner User (real email, a random
    placeholder password until they complete a shop-owner invite — see
    routes/shop_owner_invites.py) instead of sharing HQ's login;
  - give a multi-site franchisee (operates 2+ shops) their own ParentAccount,
    separate from HQ's, so once they've claimed one shop they see all of theirs
    in a multi-site switcher — while every shop *also* stays linked to HQ's own
    ParentAccount, unchanged, so HQ's existing "Manage shops" oversight keeps
    working exactly as it does today;
  - fall back to the shared HQ owner login for shops with no franchisee on file
    or no email on file (company-owned shops, and the handful of franchisee
    records missing contact details) — same as the existing importer, and
    flagged in the summary so those gaps can be chased down separately.

Existing tenants and existing owner User rows (credentials already set, possibly
already claimed via a real invite) are never modified — this only fills gaps.
"""

from __future__ import annotations

import secrets
from dataclasses import dataclass, field

from sqlmodel import Session, col, select

from .minit_directory_parser import DirectoryData, DirectoryFranchisee, DirectoryShop
from .minit_provision import (
    _get_or_create_parent,
    _link_tenant_to_parent,
    existing_shop_numbers_in_parent,
    tenants_by_shop_number_in_parent,
)
from .models import ParentAccount, Tenant, User
from .security import hash_password
from .shop_number import linked_tenant_ids_for_parent

_PREVIEW_LIMIT = 25
# Commit progress every N shops during apply, rather than one giant
# transaction — keeps memory bounded and surfaces a partial result if
# something downstream (e.g. a proxy timeout) cuts the request short.
_APPLY_FLUSH_EVERY = 50


def _tenant_slug(shop_number: str) -> str:
    return f"minit-{shop_number.strip()}"


def _shop_entry(shop: DirectoryShop) -> dict[str, str]:
    return {
        "shop_number": shop.shop_number,
        "name": shop.name,
        "slug": _tenant_slug(shop.shop_number),
        "area": shop.area,
        "region": shop.region,
        "address": shop.address,
        "ownership": shop.ownership,
    }


@dataclass
class _OwnerIdentity:
    email: str
    full_name: str
    #: Reason we fell back to the HQ shared login instead of a real franchisee
    #: identity — None when this is a real franchisee.
    fallback_reason: str | None = None


def _owner_identity_for_shop(
    shop: DirectoryShop,
    franchisee: DirectoryFranchisee | None,
    *,
    hq_owner_email: str,
    hq_owner_full_name: str,
) -> _OwnerIdentity:
    if franchisee is None:
        return _OwnerIdentity(hq_owner_email, hq_owner_full_name, "company_owned_no_franchisee")
    if not franchisee.email or "@" not in franchisee.email:
        return _OwnerIdentity(hq_owner_email, hq_owner_full_name, "franchisee_missing_email")
    full_name = franchisee.full_name.strip() or franchisee.business_name.strip() or franchisee.email
    return _OwnerIdentity(franchisee.email, full_name, None)


def _new_placeholder_password_hash() -> str:
    """An unusable random password — real credentials come from a shop-owner
    invite (routes/shop_owner_invites.py), never from this import."""
    return hash_password(secrets.token_urlsafe(32))


@dataclass
class _PlanCounts:
    total_in_export: int = 0
    open: int = 0
    closed_skipped: int = 0
    already_exists: int = 0
    would_create: int = 0


def plan_directory_import(
    session: Session,
    directory: DirectoryData,
    *,
    hq_owner_email: str,
    hq_owner_full_name: str = "Mister Minit HQ",
    plan_code: str = "booking_only",
    apply: bool = False,
) -> dict[str, object]:
    """Dry-run (default) or apply the directory import. Never touches an
    existing tenant's owner credentials — only fills in shops/owners/parent
    accounts that don't exist yet.

    Fast for a re-run over a mostly-already-imported export (no per-shop
    queries for shops that already exist) — but each brand-new owner still
    costs a bcrypt hash (~100-300ms, unavoidable, and deliberately not cheaper
    here: hash_password() is the same security-critical helper used for real
    user passwords everywhere else). A single request creating on the order
    of 300+ new owners at once can still approach a reverse proxy's request
    timeout; if this network ever needs a bulk load that large again, prefer
    running scripts/import_minit_directory.py directly (no HTTP timeout)
    over the HQ upload endpoint."""
    hq_email = hq_owner_email.strip().lower()
    parent = session.exec(select(ParentAccount).where(ParentAccount.owner_email == hq_email)).first()
    if not parent:
        return {
            "hq_parent_found": False,
            "note": "HQ parent account not found — seed Minit HQ first (seed_minit_pilot.py)",
            "shops_in_export": len(directory.shops),
            "franchisees_in_export": len(directory.franchisees),
        }

    franchisees_by_id = {f.id: f for f in directory.franchisees}
    existing_numbers = existing_shop_numbers_in_parent(session, parent.id, site_kind="retail")
    tenants_by_number = tenants_by_shop_number_in_parent(session, parent.id, site_kind="retail")

    counts = _PlanCounts(total_in_export=len(directory.shops))
    would_create: list[dict[str, str]] = []
    already_exists: list[dict[str, str]] = []
    warnings: list[dict[str, str]] = []

    single_site_count = 0
    multi_site_franchisee_ids: set[str] = set()
    fallback_no_franchisee = 0
    fallback_missing_email = 0

    for shop in directory.shops:
        if shop.status != "Open":
            counts.closed_skipped += 1
            continue
        counts.open += 1
        if not shop.shop_number:
            warnings.append({"kind": "missing_shop_number", "detail": shop.id})
            continue

        franchisee = franchisees_by_id.get(shop.franchisee_id) if shop.franchisee_id else None
        identity = _owner_identity_for_shop(
            shop, franchisee, hq_owner_email=hq_email, hq_owner_full_name=hq_owner_full_name
        )
        if identity.fallback_reason == "company_owned_no_franchisee":
            fallback_no_franchisee += 1
        elif identity.fallback_reason == "franchisee_missing_email":
            fallback_missing_email += 1
            warnings.append(
                {"kind": "franchisee_missing_email", "detail": f"{franchisee.full_name} ({shop.shop_number})"}
            )
        elif franchisee is not None:
            if franchisee.is_multi_site:
                multi_site_franchisee_ids.add(franchisee.id)
            else:
                single_site_count += 1

        entry = _shop_entry(shop)
        entry["owner_email"] = identity.email
        entry["owner_full_name"] = identity.full_name
        if identity.fallback_reason:
            entry["owner_source"] = identity.fallback_reason
        else:
            entry["owner_source"] = "franchisee_multi_site" if franchisee and franchisee.is_multi_site else "franchisee"

        if shop.shop_number in existing_numbers:
            counts.already_exists += 1
            if len(already_exists) < _PREVIEW_LIMIT:
                already_exists.append(entry)
        else:
            counts.would_create += 1
            if len(would_create) < _PREVIEW_LIMIT:
                would_create.append(entry)

    multi_site_franchisees = [franchisees_by_id[fid] for fid in multi_site_franchisee_ids]
    # Only count a multi-site franchisee's own ParentAccount as "would create" if
    # they don't already have one (e.g. a partial import ran before).
    existing_franchisee_parent_emails = (
        {
            p.owner_email
            for p in session.exec(
                select(ParentAccount).where(
                    col(ParentAccount.owner_email).in_([f.email for f in multi_site_franchisees])
                )
            ).all()
        }
        if multi_site_franchisees
        else set()
    )
    would_create_parent_accounts = [
        f for f in multi_site_franchisees if f.email not in existing_franchisee_parent_emails
    ]

    result: dict[str, object] = {
        "hq_parent_found": True,
        "parent_account_id": str(parent.id),
        "parent_account_name": parent.name,
        "dry_run": not apply,
        "shops": {
            "total_in_export": counts.total_in_export,
            "open": counts.open,
            "closed_skipped": counts.closed_skipped,
            "already_exists": counts.already_exists,
            "would_create": counts.would_create,
        },
        "franchisees": {
            "total_in_export": len(directory.franchisees),
            "single_site": single_site_count,
            "multi_site": len(multi_site_franchisee_ids),
            "would_create_parent_accounts": len(would_create_parent_accounts),
            "existing_parent_accounts_reused": len(multi_site_franchisees) - len(would_create_parent_accounts),
        },
        "fallback_to_hq_login": {
            "company_owned_no_franchisee": fallback_no_franchisee,
            "franchisee_missing_email": fallback_missing_email,
        },
        "would_create_sample": would_create,
        "would_create_truncated": counts.would_create > len(would_create),
        "already_exists_sample": already_exists,
        "already_exists_truncated": counts.already_exists > len(already_exists),
        "warnings_sample": warnings[:_PREVIEW_LIMIT],
        "warnings_count": len(warnings),
    }

    if not apply:
        return result

    # ── Apply ────────────────────────────────────────────────────────────────
    # Most calls are re-runs where the large majority of shops already exist —
    # preload everything that would otherwise be a per-shop SELECT, so a mostly-
    # unchanged 400+ shop export stays fast instead of doing hundreds of
    # redundant round-trips (and risking the proxy's request timeout).
    created_tenant_slugs: list[str] = []
    created_owner_count = 0
    created_franchisee_parent_count = 0
    franchisee_parents: dict[str, ParentAccount] = {}
    # tenant_ids already linked to each ParentAccount we touch, keyed by parent
    # id — lets _link_tenant_to_parent skip its existence-check query.
    linked_ids_by_parent: dict[object, set] = {parent.id: set(linked_tenant_ids_for_parent(session, parent.id))}
    # Emails that already had a ParentAccount before this run — used to tell a
    # genuinely-new franchisee ParentAccount apart from one _get_or_create_parent
    # merely reused, so the summary count is accurate rather than always "created".
    seen_existing_parent_emails = set(existing_franchisee_parent_emails)

    existing_tenant_ids = [t.id for t in tenants_by_number.values()]
    existing_owner_by_tenant_id: dict[object, User] = {}
    if existing_tenant_ids:
        for user in session.exec(
            select(User)
            .where(col(User.tenant_id).in_(existing_tenant_ids))
            .where(User.role == "owner")
            .where(User.is_active)
            .order_by(col(User.created_at).asc())
        ).all():
            existing_owner_by_tenant_id.setdefault(user.tenant_id, user)

    since_commit = 0

    for shop in directory.shops:
        if shop.status != "Open" or not shop.shop_number:
            continue
        franchisee = franchisees_by_id.get(shop.franchisee_id) if shop.franchisee_id else None
        identity = _owner_identity_for_shop(
            shop, franchisee, hq_owner_email=hq_email, hq_owner_full_name=hq_owner_full_name
        )

        tenant = tenants_by_number.get(shop.shop_number)
        is_new_tenant = tenant is None
        if is_new_tenant:
            tenant = Tenant(
                name=shop.name,
                slug=_tenant_slug(shop.shop_number),
                plan_code=plan_code,
                business_address=shop.address[:2000] if shop.address else None,
                shop_number=shop.shop_number,
                minit_area=shop.area or None,
                minit_region=shop.region or None,
                shop_phone=shop.phone or None,
                shop_email=shop.shop_email or None,
            )
            session.add(tenant)  # tenant.id is already set (client-side uuid4 default)
            tenants_by_number[shop.shop_number] = tenant
            created_tenant_slugs.append(tenant.slug)

            owner = User(
                tenant_id=tenant.id,
                email=identity.email,
                full_name=identity.full_name,
                role="owner",
                password_hash=_new_placeholder_password_hash(),
                is_active=True,
            )
            session.add(owner)
            created_owner_count += 1
            existing_owner_by_tenant_id[tenant.id] = owner
            _link_tenant_to_parent(
                session, parent=parent, tenant=tenant, owner=owner, linked_tenant_ids=linked_ids_by_parent[parent.id]
            )
            since_commit += 1
        else:
            # Existing tenant — guaranteed already linked to HQ (that's how it
            # showed up in tenants_by_number, which is scoped to this parent).
            # Never create or touch an owner here: the directory's franchisee
            # identity might be stale or simply not match who actually holds
            # this login (e.g. a real invite was already completed under a
            # different email). Only look up who the real owner is now, for
            # the multi-site parent-account link below.
            owner = existing_owner_by_tenant_id.get(tenant.id)
            if owner is None:
                continue

        if franchisee is not None and franchisee.is_multi_site and identity.fallback_reason is None:
            fp = franchisee_parents.get(franchisee.email)
            if fp is None:
                fp = _get_or_create_parent(
                    session,
                    name=franchisee.business_name.strip() or franchisee.full_name,
                    owner_email=franchisee.email,
                )
                if franchisee.email not in seen_existing_parent_emails:
                    created_franchisee_parent_count += 1
                    seen_existing_parent_emails.add(franchisee.email)
                franchisee_parents[franchisee.email] = fp
                linked_ids_by_parent[fp.id] = set(linked_tenant_ids_for_parent(session, fp.id))
            _link_tenant_to_parent(
                session, parent=fp, tenant=tenant, owner=owner, linked_tenant_ids=linked_ids_by_parent[fp.id]
            )
            since_commit += 1

        if since_commit >= _APPLY_FLUSH_EVERY:
            session.commit()
            since_commit = 0

    session.commit()
    result["created_tenant_count"] = len(created_tenant_slugs)
    result["created_tenant_slugs"] = created_tenant_slugs[:50]
    result["created_tenant_slugs_truncated"] = len(created_tenant_slugs) > 50
    result["created_owner_count"] = created_owner_count
    result["created_franchisee_parent_account_count"] = created_franchisee_parent_count
    return result
