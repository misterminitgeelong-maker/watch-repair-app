"""Shop counter POS: what the till sells from, the sales it reports back, and end-of-day totals.

The till is offline-first: it rings sales up against the catalogue it last
downloaded and posts them here from a queue, sometimes hours later. So:

* ``GET /catalogue`` hands the till one complete published price book version,
  with the shop's local overrides already applied.
* ``POST /sales`` is idempotent on the till's own ``client_sale_id``; posting
  the same sale twice returns the first copy. The server re-checks the
  arithmetic but keeps the till's prices, because the sale already happened.
* Refunds are sales with ``status="refund"`` and negative quantities and
  amounts, so every report is a plain sum.
"""
from __future__ import annotations

import json
from collections import defaultdict
from datetime import date, datetime, timezone
from typing import Literal, Optional
from uuid import UUID
from zoneinfo import ZoneInfo

from fastapi import APIRouter, Depends, HTTPException, Query, Response
from pydantic import BaseModel, Field, model_validator
from sqlalchemy.exc import IntegrityError
from sqlmodel import Session, select

from ..database import get_session
from ..dependencies import AuthContext, require_feature
from ..loyalty_utils import earn_points
from ..models import (
    NETWORK_ROLE_HQ,
    Customer,
    ParentAccountSite,
    PosPriceBook,
    PosPriceBookVersion,
    PosSale,
    PosSaleLine,
    PosShopSettings,
    PosTender,
    Tenant,
)
from ..pos_catalogue import OverrideIn, apply_overrides, parse_catalogue
from ..tenant_scope import without_scope

router = APIRouter(prefix="/v1/pos", tags=["pos"])

require_pos = require_feature("pos")
MANAGER_ROLES = ("owner", "manager", "platform_admin")


def _shop_region(tenant: Tenant) -> str:
    return "NZ" if (tenant.minit_region or "").strip().upper() == "NZ" else "AU"


def resolve_price_book(session: Session, tenant: Tenant) -> Optional[PosPriceBook]:
    """The published book this shop sells from.

    In order: the book HQ (or the owner) assigned to the shop; the shop's own
    default book; its network's default book for the shop's region. Archived
    and never-published books are skipped.
    """
    region = _shop_region(tenant)

    def usable(book: Optional[PosPriceBook]) -> bool:
        return book is not None and not book.archived and book.published_version > 0

    with without_scope(session):
        settings = session.exec(select(PosShopSettings).where(PosShopSettings.tenant_id == tenant.id)).first()
        if settings and settings.price_book_id:
            book = session.get(PosPriceBook, settings.price_book_id)
            if usable(book):
                return book

        own = session.exec(
            select(PosPriceBook)
            .where(PosPriceBook.tenant_id == tenant.id)
            .where(PosPriceBook.is_default == True)  # noqa: E712
            .where(PosPriceBook.archived == False)  # noqa: E712
            .where(PosPriceBook.published_version > 0)
            .order_by(PosPriceBook.created_at)
        ).first()
        if own:
            return own

        parent_ids = session.exec(
            select(ParentAccountSite.parent_account_id)
            .where(ParentAccountSite.tenant_id == tenant.id)
            .where(ParentAccountSite.network_role != NETWORK_ROLE_HQ)
        ).all()
        if not parent_ids:
            return None
        return session.exec(
            select(PosPriceBook)
            .where(PosPriceBook.parent_account_id.in_(parent_ids))  # type: ignore[union-attr]
            .where(PosPriceBook.region == region)
            .where(PosPriceBook.is_default == True)  # noqa: E712
            .where(PosPriceBook.archived == False)  # noqa: E712
            .where(PosPriceBook.published_version > 0)
            .order_by(PosPriceBook.created_at)
        ).first()


def _settings(session: Session, tenant_id: UUID) -> PosShopSettings:
    return session.exec(select(PosShopSettings).where(PosShopSettings.tenant_id == tenant_id)).first() or PosShopSettings(
        tenant_id=tenant_id
    )


def _tenant(session: Session, auth: AuthContext) -> Tenant:
    tenant = session.get(Tenant, auth.tenant_id)
    if tenant is None:
        raise HTTPException(status_code=401, detail="Invalid token")
    return tenant


def _published_version(session: Session, book: PosPriceBook) -> PosPriceBookVersion:
    with without_scope(session):
        return session.exec(
            select(PosPriceBookVersion)
            .where(PosPriceBookVersion.price_book_id == book.id)
            .where(PosPriceBookVersion.version == book.published_version)
        ).one()


def _book_item_keys(session: Session, book: PosPriceBook) -> set[str]:
    return {item.key for item in parse_catalogue(_published_version(session, book).content_json).items}


# ── Catalogue ────────────────────────────────────────────────────────────────

@router.get("/catalogue")
def get_catalogue(
    response: Response,
    auth: AuthContext = Depends(require_pos),
    session: Session = Depends(get_session),
):
    tenant = _tenant(session, auth)
    book = resolve_price_book(session, tenant)
    if book is None:
        raise HTTPException(status_code=404, detail="No price book has been published for this shop yet")
    version = _published_version(session, book)
    settings = _settings(session, tenant.id)
    # HQ can switch local pricing off; the shop's saved overrides then sit unused until it is switched back on.
    overrides = json.loads(settings.overrides_json or "{}") if book.allow_shop_overrides else {}
    catalogue = apply_overrides(parse_catalogue(version.content_json), overrides)
    # Tills poll this; the tag changes when HQ publishes or the shop edits an override.
    response.headers["ETag"] = f'"{book.id}:{book.published_version}:{settings.updated_at.timestamp():.0f}"'
    return {
        "price_book_id": str(book.id),
        "name": book.name,
        "version": book.published_version,
        "published_at": version.published_at.isoformat(),
        "region": book.region,
        "currency": book.currency,
        "gst_rate_bp": book.gst_rate_bp,
        "cash_rounding_cents": book.cash_rounding_cents,
        "allow_shop_overrides": book.allow_shop_overrides,
        "override_count": len(overrides),
        "catalogue": catalogue.model_dump(),
    }


# ── Shop overrides (local prices, hidden items) ──────────────────────────────

@router.get("/overrides")
def list_overrides(auth: AuthContext = Depends(require_pos), session: Session = Depends(get_session)):
    return json.loads(_settings(session, auth.tenant_id).overrides_json or "{}")


@router.put("/overrides/{item_key}")
def put_override(
    item_key: str,
    body: OverrideIn,
    auth: AuthContext = Depends(require_pos),
    session: Session = Depends(get_session),
):
    if auth.role not in MANAGER_ROLES:
        raise HTTPException(status_code=403, detail="Only owners and managers can change shop prices")
    book = resolve_price_book(session, _tenant(session, auth))
    if book is None or item_key not in _book_item_keys(session, book):
        raise HTTPException(status_code=404, detail="That item is not in this shop's price book")
    if not book.allow_shop_overrides:
        raise HTTPException(status_code=403, detail="Head office has switched off local pricing for this shop's price book")
    settings = _settings(session, auth.tenant_id)
    overrides = json.loads(settings.overrides_json or "{}")
    change = body.model_dump(exclude_none=True, exclude_defaults=True)
    if change:
        overrides[item_key] = change
    else:
        overrides.pop(item_key, None)
    settings.overrides_json = json.dumps(overrides, sort_keys=True)
    settings.updated_at = datetime.now(timezone.utc)
    session.add(settings)
    session.commit()
    return overrides


@router.delete("/overrides/{item_key}")
def delete_override(item_key: str, auth: AuthContext = Depends(require_pos), session: Session = Depends(get_session)):
    if auth.role not in MANAGER_ROLES:
        raise HTTPException(status_code=403, detail="Only owners and managers can change shop prices")
    settings = _settings(session, auth.tenant_id)
    overrides = json.loads(settings.overrides_json or "{}")
    if item_key not in overrides:
        raise HTTPException(status_code=404, detail="This shop has no override for that item")
    overrides.pop(item_key)
    settings.overrides_json = json.dumps(overrides, sort_keys=True)
    settings.updated_at = datetime.now(timezone.utc)
    session.add(settings)
    session.commit()
    return overrides


# ── Sales ────────────────────────────────────────────────────────────────────

class SaleLineIn(BaseModel):
    item_key: str = Field(min_length=1, max_length=120)
    item_name: str = Field(min_length=1, max_length=200)
    category_key: Optional[str] = Field(default=None, max_length=120)
    category_name: Optional[str] = Field(default=None, max_length=120)
    group_key: Optional[str] = Field(default=None, max_length=120)
    unit_price_cents: int = Field(ge=0, le=10_000_000)
    #: Negative on a refund.
    qty: int = Field(ge=-1000, le=1000)
    combo_cents: int = 0
    combo_label: Optional[str] = Field(default=None, max_length=120)
    gst_free: bool = False
    is_service: bool = True
    job_type: Optional[Literal["watch", "shoe", "autokey"]] = None
    job_id: Optional[UUID] = None


class TenderIn(BaseModel):
    tender_type: Literal["eftpos", "cash", "voucher", "account", "points"]
    amount_cents: int
    #: Cash handed over, for the change line on the receipt.
    tendered_cents: Optional[int] = None
    provider: Optional[str] = Field(default=None, max_length=32)
    reference: Optional[str] = Field(default=None, max_length=64)
    auth_code: Optional[str] = Field(default=None, max_length=32)
    card_type: Optional[str] = Field(default=None, max_length=32)
    masked_pan: Optional[str] = Field(default=None, max_length=32)


class SaleIn(BaseModel):
    client_sale_id: str = Field(min_length=8, max_length=64)
    till_id: str = Field(min_length=1, max_length=64)
    staff_name: Optional[str] = Field(default=None, max_length=120)
    customer_id: Optional[UUID] = None
    status: Literal["paid", "refund"] = "paid"
    occurred_at: datetime
    price_book_id: Optional[UUID] = None
    price_book_version: Optional[int] = None
    gst_rate_bp: int = Field(ge=0, le=5000)
    gross_cents: int
    combo_cents: int = 0
    discount_cents: int = 0
    discount_reason: Optional[str] = Field(default=None, max_length=200)
    total_cents: int
    gst_cents: int
    rounding_cents: int = Field(default=0, ge=-50, le=50)
    note: Optional[str] = Field(default=None, max_length=2000)
    refund_of_sale_id: Optional[UUID] = None
    lines: list[SaleLineIn] = Field(min_length=1, max_length=200)
    tenders: list[TenderIn] = Field(min_length=1, max_length=20)

    @model_validator(mode="after")
    def _arithmetic(self) -> "SaleIn":
        problems: list[str] = []
        sign = -1 if self.status == "refund" else 1
        if any(line.qty * sign <= 0 for line in self.lines):
            problems.append("line quantities must be positive on a sale and negative on a refund")
        gross = sum(line.unit_price_cents * line.qty for line in self.lines)
        if gross != self.gross_cents:
            problems.append(f"gross_cents {self.gross_cents} != sum of lines {gross}")
        combos = sum(line.combo_cents for line in self.lines)
        if combos != self.combo_cents:
            problems.append(f"combo_cents {self.combo_cents} != sum of line combos {combos}")
        if self.gross_cents - self.combo_cents - self.discount_cents != self.total_cents:
            problems.append("total_cents must equal gross_cents - combo_cents - discount_cents")
        tendered = sum(t.amount_cents for t in self.tenders)
        if tendered != self.total_cents + self.rounding_cents:
            problems.append(f"tenders add up to {tendered}, expected total + rounding = {self.total_cents + self.rounding_cents}")
        # GST can't exceed the GST in the whole total (it is less when lines are GST-free).
        ceiling = abs(self.total_cents) * self.gst_rate_bp // (10000 + self.gst_rate_bp) + len(self.lines)
        if abs(self.gst_cents) > ceiling or (self.gst_cents and (self.gst_cents > 0) != (self.total_cents > 0)):
            problems.append("gst_cents is out of range for the total")
        if self.status == "refund" and self.total_cents > 0:
            problems.append("a refund's total must be zero or negative")
        if self.status == "paid" and self.total_cents < 0:
            problems.append("a sale's total cannot be negative")
        if problems:
            raise ValueError("; ".join(problems))
        return self


def _sale_out(sale: PosSale, lines: list[PosSaleLine], tenders: list[PosTender]) -> dict:
    return {
        "id": str(sale.id),
        "client_sale_id": sale.client_sale_id,
        "till_id": sale.till_id,
        "staff_name": sale.staff_name,
        "customer_id": str(sale.customer_id) if sale.customer_id else None,
        "status": sale.status,
        "occurred_at": sale.occurred_at.isoformat(),
        "business_date": sale.business_date.isoformat(),
        "price_book_version": sale.price_book_version,
        "gross_cents": sale.gross_cents,
        "combo_cents": sale.combo_cents,
        "discount_cents": sale.discount_cents,
        "discount_reason": sale.discount_reason,
        "total_cents": sale.total_cents,
        "gst_cents": sale.gst_cents,
        "rounding_cents": sale.rounding_cents,
        "refund_of_sale_id": str(sale.refund_of_sale_id) if sale.refund_of_sale_id else None,
        "loyalty_points_earned": sale.loyalty_points_earned,
        "lines": [
            {
                "item_key": l.item_key,
                "item_name": l.item_name,
                "category_name": l.category_name,
                "unit_price_cents": l.unit_price_cents,
                "qty": l.qty,
                "combo_cents": l.combo_cents,
                "combo_label": l.combo_label,
                "job_type": l.job_type,
                "job_id": str(l.job_id) if l.job_id else None,
            }
            for l in lines
        ],
        "tenders": [
            {
                "tender_type": t.tender_type,
                "amount_cents": t.amount_cents,
                "tendered_cents": t.tendered_cents,
                "provider": t.provider,
                "reference": t.reference,
                "card_type": t.card_type,
                "masked_pan": t.masked_pan,
            }
            for t in tenders
        ],
    }


def _load_sale(session: Session, sale: PosSale) -> dict:
    lines = session.exec(select(PosSaleLine).where(PosSaleLine.sale_id == sale.id).order_by(PosSaleLine.position)).all()
    tenders = session.exec(select(PosTender).where(PosTender.sale_id == sale.id).order_by(PosTender.position)).all()
    return _sale_out(sale, list(lines), list(tenders))


def _existing(session: Session, tenant_id: UUID, client_sale_id: str) -> Optional[PosSale]:
    return session.exec(
        select(PosSale).where(PosSale.tenant_id == tenant_id).where(PosSale.client_sale_id == client_sale_id)
    ).first()


def _as_utc(value: datetime) -> datetime:
    return value.replace(tzinfo=timezone.utc) if value.tzinfo is None else value.astimezone(timezone.utc)


@router.post("/sales", status_code=201)
def post_sale(
    body: SaleIn,
    response: Response,
    auth: AuthContext = Depends(require_pos),
    session: Session = Depends(get_session),
):
    existing = _existing(session, auth.tenant_id, body.client_sale_id)
    if existing:
        response.status_code = 200
        return {**_load_sale(session, existing), "duplicate": True}

    tenant = _tenant(session, auth)
    if body.customer_id:
        customer = session.get(Customer, body.customer_id)
        if customer is None or customer.tenant_id != auth.tenant_id:
            raise HTTPException(status_code=422, detail="Customer not found in this shop")
    if body.refund_of_sale_id:
        original = session.get(PosSale, body.refund_of_sale_id)
        if original is None or original.tenant_id != auth.tenant_id:
            raise HTTPException(status_code=422, detail="The sale being refunded was not found in this shop")

    occurred = _as_utc(body.occurred_at)
    try:
        zone = ZoneInfo(tenant.timezone or "Australia/Melbourne")
    except Exception:  # noqa: BLE001 - a bad stored zone shouldn't lose a sale
        zone = ZoneInfo("Australia/Melbourne")
    sale = PosSale(
        tenant_id=auth.tenant_id,
        client_sale_id=body.client_sale_id,
        till_id=body.till_id,
        staff_user_id=auth.user_id,
        staff_name=body.staff_name,
        customer_id=body.customer_id,
        status=body.status,
        occurred_at=occurred,
        business_date=occurred.astimezone(zone).date(),
        price_book_id=body.price_book_id,
        price_book_version=body.price_book_version,
        gst_rate_bp=body.gst_rate_bp,
        gross_cents=body.gross_cents,
        combo_cents=body.combo_cents,
        discount_cents=body.discount_cents,
        discount_reason=body.discount_reason,
        total_cents=body.total_cents,
        gst_cents=body.gst_cents,
        rounding_cents=body.rounding_cents,
        note=body.note,
        refund_of_sale_id=body.refund_of_sale_id,
    )
    session.add(sale)
    try:
        session.flush()
    except IntegrityError:
        # The same sale arrived twice at once (two retries racing); the other one won.
        session.rollback()
        existing = _existing(session, auth.tenant_id, body.client_sale_id)
        if existing is None:
            raise
        response.status_code = 200
        return {**_load_sale(session, existing), "duplicate": True}

    lines = [PosSaleLine(tenant_id=auth.tenant_id, sale_id=sale.id, position=i, **l.model_dump()) for i, l in enumerate(body.lines)]
    tenders = [PosTender(tenant_id=auth.tenant_id, sale_id=sale.id, position=i, **t.model_dump()) for i, t in enumerate(body.tenders)]
    session.add_all(lines + tenders)

    if body.customer_id and body.status == "paid" and body.total_cents > 0:
        sale.loyalty_points_earned = earn_points(
            session,
            auth.tenant_id,
            body.customer_id,
            amount_cents=body.total_cents,
            idempotency_key=f"pos_sale:{sale.id}",
            note=f"Counter sale {body.till_id}",
        )
        session.add(sale)

    session.commit()
    session.refresh(sale)
    return {**_sale_out(sale, lines, tenders), "duplicate": False}


@router.get("/sales")
def list_sales(
    business_date: Optional[date] = None,
    till_id: Optional[str] = None,
    customer_id: Optional[UUID] = None,
    limit: int = Query(default=100, ge=1, le=500),
    auth: AuthContext = Depends(require_pos),
    session: Session = Depends(get_session),
):
    stmt = select(PosSale).where(PosSale.tenant_id == auth.tenant_id)
    if business_date:
        stmt = stmt.where(PosSale.business_date == business_date)
    if till_id:
        stmt = stmt.where(PosSale.till_id == till_id)
    if customer_id:
        stmt = stmt.where(PosSale.customer_id == customer_id)
    sales = session.exec(stmt.order_by(PosSale.occurred_at.desc()).limit(limit)).all()  # type: ignore[attr-defined]
    return [_load_sale(session, s) for s in sales]


@router.get("/sales/{sale_id}")
def get_sale(sale_id: UUID, auth: AuthContext = Depends(require_pos), session: Session = Depends(get_session)):
    sale = session.get(PosSale, sale_id)
    if sale is None or sale.tenant_id != auth.tenant_id:
        raise HTTPException(status_code=404, detail="Sale not found")
    return _load_sale(session, sale)


# ── End of day ───────────────────────────────────────────────────────────────

@router.get("/z-report")
def z_report(
    business_date: date,
    till_id: Optional[str] = None,
    auth: AuthContext = Depends(require_pos),
    session: Session = Depends(get_session),
):
    """Totals for one trading day: what the shop took, by tender, category and staff member."""
    stmt = select(PosSale).where(PosSale.tenant_id == auth.tenant_id).where(PosSale.business_date == business_date)
    if till_id:
        stmt = stmt.where(PosSale.till_id == till_id)
    sales = session.exec(stmt).all()
    ids = [s.id for s in sales]
    lines = session.exec(select(PosSaleLine).where(PosSaleLine.sale_id.in_(ids))).all() if ids else []  # type: ignore[attr-defined]
    tenders = session.exec(select(PosTender).where(PosTender.sale_id.in_(ids))).all() if ids else []  # type: ignore[attr-defined]

    by_tender: dict[str, dict] = defaultdict(lambda: {"count": 0, "amount_cents": 0})
    for t in tenders:
        by_tender[t.tender_type]["count"] += 1
        by_tender[t.tender_type]["amount_cents"] += t.amount_cents

    by_category: dict[str, dict] = defaultdict(lambda: {"qty": 0, "gross_cents": 0, "combo_cents": 0})
    for l in lines:
        row = by_category[l.category_name or "Other"]
        row["qty"] += l.qty
        row["gross_cents"] += l.unit_price_cents * l.qty
        row["combo_cents"] += l.combo_cents

    by_staff: dict[str, dict] = defaultdict(lambda: {"sales": 0, "total_cents": 0})
    for s in sales:
        row = by_staff[s.staff_name or "Unknown"]
        row["sales"] += 1 if s.status == "paid" else 0
        row["total_cents"] += s.total_cents

    paid = [s for s in sales if s.status == "paid"]
    refunds = [s for s in sales if s.status == "refund"]
    return {
        "business_date": business_date.isoformat(),
        "till_id": till_id,
        "sale_count": len(paid),
        "refund_count": len(refunds),
        "gross_cents": sum(s.gross_cents for s in sales),
        "combo_cents": sum(s.combo_cents for s in sales),
        "discount_cents": sum(s.discount_cents for s in sales),
        "refund_cents": sum(s.total_cents for s in refunds),
        "net_cents": sum(s.total_cents for s in sales),
        "gst_cents": sum(s.gst_cents for s in sales),
        "rounding_cents": sum(s.rounding_cents for s in sales),
        "average_sale_cents": (sum(s.total_cents for s in paid) // len(paid)) if paid else 0,
        "by_tender": dict(sorted(by_tender.items())),
        "by_category": dict(sorted(by_category.items(), key=lambda kv: -kv[1]["gross_cents"])),
        "by_staff": dict(sorted(by_staff.items())),
    }
