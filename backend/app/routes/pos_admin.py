"""Price book management: HQ (or an independent shop's owner) edits the till layout, items,
prices and combo deals, publishes versions, and assigns books to shops.

Who manages what:

* An HQ manages its network's books (``PosPriceBook.parent_account_id``) and
  decides which shop sells from which book.
* An independent shop's owner or manager manages the shop's own books
  (``PosPriceBook.tenant_id``).

Books owned by a network have no ``tenant_id``, so these routes use an
unscoped session and check ownership themselves in ``_book_for_write``.
"""
from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any, Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlmodel import Session, select

from ..database import unscoped_session
from ..dependencies import AuthContext, get_auth_context, normalize_plan_code
from ..hq_access import require_hq
from ..minit_branding import MINIT_HQ_PLAN
from ..models import NETWORK_ROLE_HQ, ParentAccountSite, PosPriceBook, PosPriceBookVersion, PosShopSettings, Tenant
from ..pos_catalogue import CatalogueError, parse_catalogue

router = APIRouter(prefix="/v1/pos/admin", tags=["pos-admin"])

REGION_DEFAULTS = {
    "AU": {"currency": "AUD", "gst_rate_bp": 1000, "cash_rounding_cents": 5},
    "NZ": {"currency": "NZD", "gst_rate_bp": 1500, "cash_rounding_cents": 10},
}


class Owner(BaseModel):
    parent_account_id: Optional[UUID] = None
    tenant_id: Optional[UUID] = None


def _owner(auth: AuthContext, session: Session) -> Owner:
    """The network or shop whose price books the caller manages."""
    if normalize_plan_code(auth.plan_code) == MINIT_HQ_PLAN:
        tenant = require_hq(auth, session)
        site = session.exec(
            select(ParentAccountSite)
            .where(ParentAccountSite.tenant_id == tenant.id)
            .where(ParentAccountSite.network_role == NETWORK_ROLE_HQ)
            .order_by(ParentAccountSite.created_at.asc())
        ).first()
        if site is None:
            raise HTTPException(status_code=403, detail="HQ account required")
        return Owner(parent_account_id=site.parent_account_id)
    if auth.role not in ("owner", "manager", "platform_admin"):
        raise HTTPException(status_code=403, detail="Only owners and managers can edit price books")
    return Owner(tenant_id=auth.tenant_id)


def _owns(owner: Owner, book: PosPriceBook) -> bool:
    if owner.parent_account_id:
        return book.parent_account_id == owner.parent_account_id
    return book.tenant_id == owner.tenant_id


def _book(session: Session, owner: Owner, book_id: UUID) -> PosPriceBook:
    book = session.get(PosPriceBook, book_id)
    if book is None or not _owns(owner, book):
        raise HTTPException(status_code=404, detail="Price book not found")
    return book


def _network_shop_ids(session: Session, parent_account_id: UUID) -> set[UUID]:
    rows = session.exec(
        select(ParentAccountSite.tenant_id)
        .where(ParentAccountSite.parent_account_id == parent_account_id)
        .where(ParentAccountSite.network_role != NETWORK_ROLE_HQ)
    ).all()
    return set(rows)


def _summary(book: PosPriceBook) -> dict[str, Any]:
    return {
        "id": str(book.id),
        "name": book.name,
        "region": book.region,
        "currency": book.currency,
        "gst_rate_bp": book.gst_rate_bp,
        "cash_rounding_cents": book.cash_rounding_cents,
        "is_default": book.is_default,
        "archived": book.archived,
        "published_version": book.published_version,
        "draft_updated_at": book.draft_updated_at.isoformat(),
    }


def _validated_json(catalogue: dict) -> str:
    try:
        parsed = parse_catalogue(catalogue)
    except CatalogueError as exc:
        raise HTTPException(status_code=422, detail=f"Catalogue is not valid: {exc}") from exc
    return parsed.model_dump_json()


def _clear_other_defaults(session: Session, book: PosPriceBook) -> None:
    others = session.exec(
        select(PosPriceBook)
        .where(PosPriceBook.id != book.id)
        .where(PosPriceBook.region == book.region)
        .where(PosPriceBook.is_default == True)  # noqa: E712
        .where(
            PosPriceBook.parent_account_id == book.parent_account_id
            if book.parent_account_id
            else PosPriceBook.tenant_id == book.tenant_id
        )
    ).all()
    for other in others:
        other.is_default = False
        session.add(other)


# ── Books ────────────────────────────────────────────────────────────────────

class BookCreate(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    region: str = Field(default="AU", pattern="^(AU|NZ)$")
    is_default: bool = False
    #: Optional starting content, e.g. an imported price list.
    catalogue: Optional[dict] = None


class BookPatch(BaseModel):
    name: Optional[str] = Field(default=None, min_length=1, max_length=120)
    is_default: Optional[bool] = None
    archived: Optional[bool] = None
    cash_rounding_cents: Optional[int] = Field(default=None, ge=1, le=100)


@router.get("/price-books")
def list_price_books(auth: AuthContext = Depends(get_auth_context), session: Session = Depends(unscoped_session)):
    owner = _owner(auth, session)
    stmt = select(PosPriceBook).order_by(PosPriceBook.created_at)
    stmt = stmt.where(PosPriceBook.parent_account_id == owner.parent_account_id) if owner.parent_account_id else stmt.where(PosPriceBook.tenant_id == owner.tenant_id)
    return [_summary(b) for b in session.exec(stmt).all()]


@router.post("/price-books", status_code=201)
def create_price_book(body: BookCreate, auth: AuthContext = Depends(get_auth_context), session: Session = Depends(unscoped_session)):
    owner = _owner(auth, session)
    book = PosPriceBook(
        parent_account_id=owner.parent_account_id,
        tenant_id=owner.tenant_id,
        name=body.name.strip(),
        region=body.region,
        is_default=body.is_default,
        draft_json=_validated_json(body.catalogue or {}),
        **REGION_DEFAULTS[body.region],
    )
    session.add(book)
    session.flush()
    if book.is_default:
        _clear_other_defaults(session, book)
    session.commit()
    session.refresh(book)
    return _summary(book)


@router.get("/price-books/{book_id}")
def get_price_book(book_id: UUID, auth: AuthContext = Depends(get_auth_context), session: Session = Depends(unscoped_session)):
    book = _book(session, _owner(auth, session), book_id)
    versions = session.exec(
        select(PosPriceBookVersion).where(PosPriceBookVersion.price_book_id == book.id).order_by(PosPriceBookVersion.version.desc())
    ).all()
    shops = session.exec(select(PosShopSettings.tenant_id).where(PosShopSettings.price_book_id == book.id)).all()
    return {
        **_summary(book),
        "draft": json.loads(book.draft_json),
        "versions": [{"version": v.version, "note": v.note, "published_at": v.published_at.isoformat()} for v in versions],
        "assigned_shop_ids": [str(t) for t in shops],
    }


@router.patch("/price-books/{book_id}")
def update_price_book(book_id: UUID, body: BookPatch, auth: AuthContext = Depends(get_auth_context), session: Session = Depends(unscoped_session)):
    book = _book(session, _owner(auth, session), book_id)
    for field, value in body.model_dump(exclude_none=True).items():
        setattr(book, field, value.strip() if isinstance(value, str) else value)
    if body.is_default:
        _clear_other_defaults(session, book)
    session.add(book)
    session.commit()
    session.refresh(book)
    return _summary(book)


# ── Draft, publish, history ──────────────────────────────────────────────────

class DraftIn(BaseModel):
    catalogue: dict
    #: draft_updated_at the editor loaded; a mismatch means someone else saved in between.
    expected_updated_at: Optional[datetime] = None


class PublishIn(BaseModel):
    note: Optional[str] = Field(default=None, max_length=500)


@router.put("/price-books/{book_id}/draft")
def save_draft(book_id: UUID, body: DraftIn, auth: AuthContext = Depends(get_auth_context), session: Session = Depends(unscoped_session)):
    book = _book(session, _owner(auth, session), book_id)
    if body.expected_updated_at and _as_utc(body.expected_updated_at) != _as_utc(book.draft_updated_at):
        raise HTTPException(status_code=409, detail="Someone else saved this price book since you opened it. Reload to see their changes.")
    book.draft_json = _validated_json(body.catalogue)
    book.draft_updated_at = datetime.now(timezone.utc)
    session.add(book)
    session.commit()
    session.refresh(book)
    return {**_summary(book), "draft": json.loads(book.draft_json)}


@router.post("/price-books/{book_id}/publish")
def publish(book_id: UUID, body: PublishIn, auth: AuthContext = Depends(get_auth_context), session: Session = Depends(unscoped_session)):
    book = _book(session, _owner(auth, session), book_id)
    content = _validated_json(json.loads(book.draft_json))
    book.published_version += 1
    session.add(
        PosPriceBookVersion(
            price_book_id=book.id,
            version=book.published_version,
            content_json=content,
            note=body.note,
            published_by_user_id=auth.user_id,
        )
    )
    session.add(book)
    session.commit()
    return {"version": book.published_version}


@router.get("/price-books/{book_id}/versions/{version}")
def get_version(book_id: UUID, version: int, auth: AuthContext = Depends(get_auth_context), session: Session = Depends(unscoped_session)):
    book = _book(session, _owner(auth, session), book_id)
    row = session.exec(
        select(PosPriceBookVersion).where(PosPriceBookVersion.price_book_id == book.id).where(PosPriceBookVersion.version == version)
    ).first()
    if row is None:
        raise HTTPException(status_code=404, detail="Version not found")
    return {"version": row.version, "note": row.note, "published_at": row.published_at.isoformat(), "catalogue": json.loads(row.content_json)}


@router.post("/price-books/{book_id}/versions/{version}/restore")
def restore_version(book_id: UUID, version: int, auth: AuthContext = Depends(get_auth_context), session: Session = Depends(unscoped_session)):
    """Copy an old version into the draft. Nothing reaches tills until it is published again."""
    book = _book(session, _owner(auth, session), book_id)
    row = session.exec(
        select(PosPriceBookVersion).where(PosPriceBookVersion.price_book_id == book.id).where(PosPriceBookVersion.version == version)
    ).first()
    if row is None:
        raise HTTPException(status_code=404, detail="Version not found")
    book.draft_json = row.content_json
    book.draft_updated_at = datetime.now(timezone.utc)
    session.add(book)
    session.commit()
    return {**_summary(book), "draft": json.loads(book.draft_json)}


# ── Which shop sells from which book ─────────────────────────────────────────

class AssignIn(BaseModel):
    tenant_ids: list[UUID]


@router.get("/shops")
def list_shops(auth: AuthContext = Depends(get_auth_context), session: Session = Depends(unscoped_session)):
    owner = _owner(auth, session)
    ids = _network_shop_ids(session, owner.parent_account_id) if owner.parent_account_id else {owner.tenant_id}
    tenants = session.exec(select(Tenant).where(Tenant.id.in_(ids)).order_by(Tenant.name)).all()  # type: ignore[union-attr]
    settings = {s.tenant_id: s for s in session.exec(select(PosShopSettings).where(PosShopSettings.tenant_id.in_(ids))).all()}  # type: ignore[attr-defined]
    return [
        {
            "tenant_id": str(t.id),
            "name": t.name,
            "shop_number": getattr(t, "shop_number", None),
            "price_book_id": str(settings[t.id].price_book_id) if t.id in settings and settings[t.id].price_book_id else None,
        }
        for t in tenants
    ]


@router.put("/price-books/{book_id}/shops")
def assign_shops(book_id: UUID, body: AssignIn, auth: AuthContext = Depends(get_auth_context), session: Session = Depends(unscoped_session)):
    owner = _owner(auth, session)
    book = _book(session, owner, book_id)
    allowed = _network_shop_ids(session, owner.parent_account_id) if owner.parent_account_id else {owner.tenant_id}
    outside = [str(t) for t in body.tenant_ids if t not in allowed]
    if outside:
        raise HTTPException(status_code=403, detail=f"Not shops in your network: {', '.join(outside)}")
    for tenant_id in body.tenant_ids:
        row = session.exec(select(PosShopSettings).where(PosShopSettings.tenant_id == tenant_id)).first() or PosShopSettings(tenant_id=tenant_id)
        row.price_book_id = book.id
        row.updated_at = datetime.now(timezone.utc)
        session.add(row)
    session.commit()
    return {"assigned": len(body.tenant_ids)}


def _as_utc(value: datetime) -> datetime:
    return value.replace(tzinfo=timezone.utc) if value.tzinfo is None else value.astimezone(timezone.utc)
