"""Create Mister Minit parent account, HQ, pilot shops, and bulk-imported sites."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from uuid import UUID

from sqlmodel import Session, select

from .minit_shops import MinitShopRow, tenant_slug_for_shop
from .models import ParentAccount, ParentAccountMembership, Tenant, User
from .security import hash_password
from .shop_number import linked_tenants_for_parent, normalize_shop_number


@dataclass
class MinitProvisionResult:
    parent_account_id: UUID
    parent_account_name: str
    hq_tenant_slug: str
    hq_owner_email: str
    created_tenant_slugs: list[str]
    skipped_shop_numbers: list[str]


def existing_shop_numbers_in_parent(session: Session, parent_id: UUID) -> set[str]:
    return {
        num
        for tenant in linked_tenants_for_parent(session, parent_id)
        if (num := tenant.shop_number)
    }


def existing_slugs_in_parent(session: Session, parent_id: UUID) -> set[str]:
    return {t.slug for t in linked_tenants_for_parent(session, parent_id)}


def _get_or_create_parent(
    session: Session,
    *,
    name: str,
    owner_email: str,
) -> ParentAccount:
    email = owner_email.strip().lower()
    parent = session.exec(select(ParentAccount).where(ParentAccount.owner_email == email)).first()
    if parent:
        if parent.name != name:
            parent.name = name
            session.add(parent)
        return parent
    parent = ParentAccount(name=name, owner_email=email)
    session.add(parent)
    session.flush()
    return parent


def _get_or_create_hq_tenant(
    session: Session,
    *,
    slug: str,
    name: str,
    owner_email: str,
    owner_password: str,
    owner_full_name: str = "Mister Minit HQ",
) -> tuple[Tenant, User]:
    email = owner_email.strip().lower()
    tenant = session.exec(select(Tenant).where(Tenant.slug == slug)).first()
    if not tenant:
        tenant = Tenant(name=name, slug=slug, plan_code="minit_hq")
        session.add(tenant)
        session.flush()
    elif tenant.plan_code != "minit_hq":
        tenant.plan_code = "minit_hq"
        session.add(tenant)
        session.flush()

    owner = session.exec(
        select(User).where(User.tenant_id == tenant.id).where(User.email == email)
    ).first()
    if not owner:
        owner = User(
            tenant_id=tenant.id,
            email=email,
            full_name=owner_full_name,
            role="owner",
            password_hash=hash_password(owner_password),
            is_active=True,
        )
        session.add(owner)
        session.flush()
    else:
        owner.password_hash = hash_password(owner_password)
        owner.is_active = True
        owner.role = "owner"
        session.add(owner)
        session.flush()
    return tenant, owner


def _link_tenant_to_parent(
    session: Session,
    *,
    parent: ParentAccount,
    tenant: Tenant,
    owner: User,
) -> None:
    existing = session.exec(
        select(ParentAccountMembership)
        .where(ParentAccountMembership.parent_account_id == parent.id)
        .where(ParentAccountMembership.tenant_id == tenant.id)
    ).first()
    if not existing:
        session.add(
            ParentAccountMembership(
                parent_account_id=parent.id,
                tenant_id=tenant.id,
                user_id=owner.id,
            )
        )


def _create_child_tenant(
    session: Session,
    *,
    parent: ParentAccount,
    hq_owner: User,
    shop: MinitShopRow,
    plan_code: str,
    tenant_slug: str | None = None,
) -> Tenant | None:
    """Create a site tenant owned by HQ credentials. Returns None if slug exists elsewhere."""
    slug = (tenant_slug or tenant_slug_for_shop(shop)).strip().lower()
    shop_number = normalize_shop_number(shop.shop_number)
    if not shop_number:
        return None

    existing = session.exec(select(Tenant).where(Tenant.slug == slug)).first()
    if existing:
        if existing.shop_number != shop_number:
            existing.shop_number = shop_number
            existing.name = shop.name
            existing.business_address = shop.business_address[:2000]
            session.add(existing)
        tenant = existing
    else:
        tenant = Tenant(
            name=shop.name,
            slug=slug,
            plan_code=plan_code,
            business_address=shop.business_address[:2000] if shop.business_address else None,
            shop_number=shop_number,
        )
        session.add(tenant)
        session.flush()

    site_owner = session.exec(
        select(User).where(User.tenant_id == tenant.id).where(User.email == hq_owner.email)
    ).first()
    if not site_owner:
        site_owner = User(
            tenant_id=tenant.id,
            email=hq_owner.email,
            full_name=hq_owner.full_name,
            role="owner",
            password_hash=hq_owner.password_hash,
            is_active=True,
        )
        session.add(site_owner)
        session.flush()

    _link_tenant_to_parent(session, parent=parent, tenant=tenant, owner=site_owner)
    return tenant


def sync_hq_owner_password_to_parent_sites(session: Session, *, parent_id: UUID, hq_owner: User) -> int:
    """Keep pilot site logins in sync when HQ password is reset. Returns count of users updated."""
    updated = 0
    for tenant in linked_tenants_for_parent(session, parent_id):
        if tenant.id == hq_owner.tenant_id:
            continue
        site_owner = session.exec(
            select(User).where(User.tenant_id == tenant.id).where(User.email == hq_owner.email)
        ).first()
        if site_owner and site_owner.password_hash != hq_owner.password_hash:
            site_owner.password_hash = hq_owner.password_hash
            site_owner.is_active = True
            session.add(site_owner)
            updated += 1
    return updated


# Pilot sites for dev/staging (shop numbers from TSS export + mobile operator 3904).
MINIT_PILOT_RETAIL_SHOPS: tuple[dict[str, str], ...] = (
    {"shop_number": "3269", "name": "Chadstone", "area": "VIC SOUTH", "region": "VIC"},
    {"shop_number": "4278", "name": "Toowoomba", "area": "QLD WEST", "region": "QLD"},
)
MINIT_PILOT_OPERATOR = {
    "shop_number": "3904",
    "name": "Mobile Operator",
    "area": None,
    "region": "VIC",
}


def ensure_minit_pilot_account(
    session: Session,
    *,
    parent_name: str,
    hq_tenant_slug: str,
    hq_tenant_name: str,
    hq_owner_email: str,
    hq_owner_password: str,
) -> MinitProvisionResult:
    """Idempotently create Mister Minit HQ, parent account, pilot shops, and mobile operator."""
    hq_tenant, hq_owner = _get_or_create_hq_tenant(
        session,
        slug=hq_tenant_slug,
        name=hq_tenant_name,
        owner_email=hq_owner_email,
        owner_password=hq_owner_password,
    )
    parent = _get_or_create_parent(session, name=parent_name, owner_email=hq_owner_email)
    _link_tenant_to_parent(session, parent=parent, tenant=hq_tenant, owner=hq_owner)

    existing_numbers = existing_shop_numbers_in_parent(session, parent.id)
    created: list[str] = []
    skipped: list[str] = []

    for spec in MINIT_PILOT_RETAIL_SHOPS:
        shop = MinitShopRow(
            shop_number=spec["shop_number"],
            name=spec["name"],
            area=spec.get("area"),
            region=spec.get("region"),
        )
        if shop.shop_number in existing_numbers:
            skipped.append(shop.shop_number)
            continue
        tenant = _create_child_tenant(
            session,
            parent=parent,
            hq_owner=hq_owner,
            shop=shop,
            plan_code="booking_only",
        )
        if tenant:
            created.append(tenant.slug)
            existing_numbers.add(shop.shop_number)

    op = MinitShopRow(
        shop_number=MINIT_PILOT_OPERATOR["shop_number"],
        name=MINIT_PILOT_OPERATOR["name"],
        area=MINIT_PILOT_OPERATOR.get("area"),
        region=MINIT_PILOT_OPERATOR.get("region"),
    )
    if op.shop_number not in existing_numbers:
        op_tenant = _create_child_tenant(
            session,
            parent=parent,
            hq_owner=hq_owner,
            shop=op,
            plan_code="basic_auto_key",
            tenant_slug="minit-mobile-3904",
        )
        if op_tenant:
            created.append(op_tenant.slug)
    else:
        skipped.append(op.shop_number)

    sync_hq_owner_password_to_parent_sites(session, parent_id=parent.id, hq_owner=hq_owner)

    session.commit()
    return MinitProvisionResult(
        parent_account_id=parent.id,
        parent_account_name=parent.name,
        hq_tenant_slug=hq_tenant.slug,
        hq_owner_email=hq_owner.email,
        created_tenant_slugs=created,
        skipped_shop_numbers=skipped,
    )


def import_minit_shops(
    session: Session,
    *,
    parent_name: str,
    hq_owner_email: str,
    shops: list[MinitShopRow],
    plan_code: str = "booking_only",
    apply: bool = False,
    on_progress: Callable[[int, int, str], None] | None = None,
) -> dict[str, object]:
    """Dry-run or apply bulk retail shop creation under the Minit parent account."""
    email = hq_owner_email.strip().lower()
    parent = session.exec(select(ParentAccount).where(ParentAccount.owner_email == email)).first()
    if not parent:
        preview = [
            {
                "shop_number": s.shop_number,
                "name": s.name,
                "slug": tenant_slug_for_shop(s),
                "business_address": s.business_address,
            }
            for s in shops
        ]
        return {
            "parent_found": False,
            "would_create_count": len(shops),
            "would_skip_count": 0,
            "note": "Parent account not found — run seed_minit_pilot.py first for accurate duplicate skips",
            "would_create": preview[:20],
            "would_create_truncated": len(preview) > 20,
        }

    existing_numbers = existing_shop_numbers_in_parent(session, parent.id)
    existing_slugs = existing_slugs_in_parent(session, parent.id)

    would_create: list[dict[str, str]] = []
    would_skip: list[dict[str, str]] = []

    for shop in shops:
        slug = tenant_slug_for_shop(shop)
        reason = None
        if shop.shop_number in existing_numbers:
            reason = "duplicate_shop_number"
        elif slug in existing_slugs:
            reason = "duplicate_slug"
        entry = {
            "shop_number": shop.shop_number,
            "name": shop.name,
            "slug": slug,
            "business_address": shop.business_address,
            "state_code": shop.state_code or "",
        }
        if reason:
            entry["skip_reason"] = reason
            would_skip.append(entry)
        else:
            would_create.append(entry)

    result: dict[str, object] = {
        "parent_found": True,
        "parent_account_id": str(parent.id),
        "parent_account_name": parent.name,
        "would_create_count": len(would_create),
        "would_skip_count": len(would_skip),
        "would_create": would_create[:20],
        "would_skip": would_skip[:20],
    }
    if len(would_create) > 20:
        result["would_create_truncated"] = True
    if len(would_skip) > 20:
        result["would_skip_truncated"] = True

    if not apply:
        return result

    hq_owner = session.exec(select(User).where(User.email == email).where(User.role == "owner")).first()
    if not hq_owner:
        result["error"] = "HQ owner user not found; run pilot seed first"
        return result

    created_slugs: list[str] = []
    skipped_apply = 0
    total = len(shops)
    for index, shop in enumerate(shops, start=1):
        if shop.shop_number in existing_numbers:
            skipped_apply += 1
            if on_progress and index % 25 == 0:
                on_progress(index, total, "skip")
            continue
        slug = tenant_slug_for_shop(shop)
        if slug in existing_slugs or session.exec(select(Tenant).where(Tenant.slug == slug)).first():
            skipped_apply += 1
            if on_progress and index % 25 == 0:
                on_progress(index, total, "skip")
            continue
        row = MinitShopRow(
            shop_number=shop.shop_number,
            name=shop.name,
            area=shop.area,
            region=shop.region,
        )
        tenant = _create_child_tenant(
            session,
            parent=parent,
            hq_owner=hq_owner,
            shop=row,
            plan_code=plan_code,
        )
        if tenant:
            created_slugs.append(tenant.slug)
            existing_numbers.add(shop.shop_number)
            existing_slugs.add(tenant.slug)
        if on_progress and (index % 25 == 0 or index == total):
            on_progress(index, total, "create")

    session.commit()
    result["created_count"] = len(created_slugs)
    result["skipped_count"] = skipped_apply
    result["created_slugs"] = created_slugs[:50]
    if len(created_slugs) > 50:
        result["created_slugs_truncated"] = True
    return result
