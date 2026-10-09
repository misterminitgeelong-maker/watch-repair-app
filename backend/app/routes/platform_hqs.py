"""Platform admin: create and configure company HQs.

An HQ is a tenant on the HQ plan that is the hub of a parent account, plus an
``HqSettings`` row (branding, modules, shop plans). Minit is one of these; this
is how every later company is set up, with no code or seed script.
"""
from __future__ import annotations

import json
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import func
from sqlalchemy.exc import IntegrityError
from sqlmodel import Session, select

from ..database import unscoped_session
from ..dependencies import AuthContext, VALID_PLAN_CODES, require_platform_admin
from ..hq_settings import HQ_MODULES, HqConfig, upsert_hq_settings
from ..minit_branding import MINIT_HQ_PLAN
from ..models import (
    NETWORK_ROLE_HQ,
    HqSettings,
    ParentAccount,
    ParentAccountEventLog,
    ParentAccountSite,
    Tenant,
    TenantEventLog,
    User,
)
from ..parent_network import link_site
from .auth import _normalize_slug, _validate_new_slug
from .hq_owner_invites import InviteRequest, create_hq_invite

router = APIRouter(prefix="/v1/platform-admin", tags=["platform-admin"])

#: Plans a company's shops can be given. The HQ plan is never one of them.
_SELECTABLE_SITE_PLANS = sorted(p for p in VALID_PLAN_CODES if p != MINIT_HQ_PLAN)


class HqSettingsPayload(BaseModel):
    display_name: str = Field(min_length=1, max_length=200)
    logo_url: str | None = Field(default=None, max_length=2000)
    brand_color: str | None = Field(default=None, max_length=20)
    modules: list[str] = Field(default_factory=list)
    site_plans: list[str] = Field(default_factory=list)


class CreateHqRequest(HqSettingsPayload):
    slug: str = Field(min_length=3, max_length=40)
    owner_name: str = Field(min_length=1, max_length=200)
    owner_email: str = Field(min_length=3, max_length=254)
    send_invite: bool = True


def _config(payload: HqSettingsPayload, product_key: str) -> HqConfig:
    modules = set(payload.modules)
    unknown = modules - set(HQ_MODULES)
    if unknown:
        raise HTTPException(400, f"Unknown modules: {', '.join(sorted(unknown))}.")
    plans = set(payload.site_plans)
    bad = plans - set(_SELECTABLE_SITE_PLANS)
    if bad:
        raise HTTPException(400, f"Unsupported shop plans: {', '.join(sorted(bad))}.")
    colour = (payload.brand_color or "").strip() or None
    if colour and not (len(colour) in (4, 7) and colour.startswith("#") and all(c in "0123456789abcdefABCDEF" for c in colour[1:])):
        raise HTTPException(400, "Brand colour must be a hex colour such as #1a2b3c.")
    logo = (payload.logo_url or "").strip() or None
    if logo and not logo.lower().startswith("https://"):
        raise HTTPException(400, "Logo URL must start with https://.")
    return HqConfig(
        product_key=product_key,
        display_name=payload.display_name.strip(),
        logo_url=logo,
        brand_color=colour,
        modules=frozenset(modules),
        site_plans=frozenset(plans),
    )


def _read(session: Session, parent: ParentAccount, settings_row: HqSettings) -> dict:
    hq_site = session.exec(
        select(ParentAccountSite)
        .where(ParentAccountSite.parent_account_id == parent.id, ParentAccountSite.network_role == NETWORK_ROLE_HQ)
        .order_by(ParentAccountSite.created_at.asc())
    ).first()
    tenant = session.get(Tenant, hq_site.tenant_id) if hq_site else None
    shops = session.exec(
        select(func.count()).select_from(ParentAccountSite)
        .where(ParentAccountSite.parent_account_id == parent.id, ParentAccountSite.network_role != NETWORK_ROLE_HQ)
    ).one()
    return {
        "parent_account_id": str(parent.id),
        "tenant_id": str(tenant.id) if tenant else None,
        "tenant_slug": tenant.slug if tenant else None,
        "product_key": settings_row.product_key,
        "display_name": settings_row.display_name,
        "logo_url": settings_row.logo_url,
        "brand_color": settings_row.brand_color,
        "modules": json.loads(settings_row.modules_json or "[]"),
        "site_plans": json.loads(settings_row.site_plans_json or "[]"),
        "shop_count": int(shops or 0),
    }


@router.get("/hqs")
def list_hqs(auth: AuthContext = Depends(require_platform_admin), session: Session = Depends(unscoped_session)):
    rows = session.exec(select(HqSettings).order_by(HqSettings.created_at.asc())).all()
    out = []
    for row in rows:
        parent = session.get(ParentAccount, row.parent_account_id)
        if parent:
            out.append(_read(session, parent, row))
    return {"hqs": out, "available_modules": list(HQ_MODULES), "available_site_plans": _SELECTABLE_SITE_PLANS}


def _audit(session: Session, parent: ParentAccount, tenant: Tenant | None, actor: User | None, event: str, summary: str, details: dict | None = None) -> None:
    session.add(ParentAccountEventLog(
        parent_account_id=parent.id,
        tenant_id=tenant.id if tenant else None,
        actor_user_id=actor.id if actor else None,
        actor_email=actor.email if actor else None,
        event_type=event,
        event_summary=summary,
        details_json=json.dumps(details) if details else None,
    ))


@router.post("/hqs", status_code=201)
def create_hq(payload: CreateHqRequest, auth: AuthContext = Depends(require_platform_admin), session: Session = Depends(unscoped_session)):
    slug = _normalize_slug(payload.slug)
    _validate_new_slug(slug)
    if session.exec(select(Tenant).where(Tenant.slug == slug)).first():
        raise HTTPException(409, "That account ID is already taken.")
    owner_email = payload.owner_email.strip().lower()
    if owner_email.count("@") != 1 or any(c.isspace() for c in owner_email) or not all(owner_email.split("@")):
        raise HTTPException(400, "Enter a valid owner email.")
    product_key = slug  # stable, unique per company
    config = _config(payload, product_key)
    actor = session.get(User, auth.user_id)

    tenant = Tenant(name=f"{config.display_name} HQ", slug=slug, plan_code=MINIT_HQ_PLAN, is_minit=False)
    session.add(tenant)
    try:
        session.flush()
    except IntegrityError:
        session.rollback()
        raise HTTPException(409, "That account ID is already taken.")
    parent = ParentAccount(name=config.display_name, owner_email=owner_email)
    session.add(parent)
    session.flush()
    link_site(session, parent_id=parent.id, tenant=tenant, network_role=NETWORK_ROLE_HQ)
    row = upsert_hq_settings(session, parent.id, config)
    session.add(TenantEventLog(
        tenant_id=tenant.id, actor_user_id=auth.user_id, actor_email=actor.email if actor else "platform_admin",
        entity_type="tenant", entity_id=tenant.id, event_type="platform_admin_hq_created",
        event_summary=f"HQ '{config.display_name}' created by platform admin.",
    ))
    _audit(session, parent, tenant, actor, "hq_created", f"HQ '{config.display_name}' created",
           {"modules": sorted(config.modules), "site_plans": sorted(config.site_plans)})
    session.commit()

    result = _read(session, parent, row)
    invite = create_hq_invite(
        InviteRequest(parent_account_id=parent.id, tenant_id=tenant.id, email=owner_email,
                      full_name=payload.owner_name, send_email=payload.send_invite),
        auth, session,
    )
    return {**result, "invite_url": invite.get("invite_url"), "email_sent": invite.get("email_sent", False)}


@router.patch("/hqs/{parent_account_id}")
def update_hq(parent_account_id: UUID, payload: HqSettingsPayload, auth: AuthContext = Depends(require_platform_admin), session: Session = Depends(unscoped_session)):
    row = session.exec(select(HqSettings).where(HqSettings.parent_account_id == parent_account_id)).first()
    parent = session.get(ParentAccount, parent_account_id)
    if not row or not parent:
        raise HTTPException(404, "HQ not found.")
    before = {"modules": json.loads(row.modules_json or "[]"), "site_plans": json.loads(row.site_plans_json or "[]"), "display_name": row.display_name}
    config = _config(payload, row.product_key)
    upsert_hq_settings(session, parent_account_id, config)
    actor = session.get(User, auth.user_id)
    _audit(session, parent, None, actor, "hq_settings_updated", f"HQ settings updated for '{config.display_name}'",
           {"before": before, "after": {"modules": sorted(config.modules), "site_plans": sorted(config.site_plans), "display_name": config.display_name}})
    session.commit()
    return _read(session, parent, session.exec(select(HqSettings).where(HqSettings.parent_account_id == parent_account_id)).one())
