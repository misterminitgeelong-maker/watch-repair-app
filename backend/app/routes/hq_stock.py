"""HQ shoe catalogue, parts and stock across locations (workshops, shops, warehouse).

Two entry points over the same logic:

* ``/v1/parent-accounts/me/stock/...``: the HQ manages the catalogue, locations,
  stock and transfers, and reads reports.
* ``/v1/stock/...``: staff at a shop or workshop in the HQ's network see the
  model list, look up purchases, scan stock in and out of their own location and
  record parts used on a repair.

Cross-tenant by design (catalogue and stock belong to the HQ, not to one shop),
so both take ``unscoped_session``.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone
from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy import func, or_
from sqlmodel import Session, col, select

from ..database import unscoped_session
from ..dependencies import AuthContext, get_auth_context
from ..hq_access import require_hq
from ..hq_settings import get_hq_config
from ..models import (
    HqPurchaseRecord,
    HqShoeModel,
    HqShoeModelPart,
    Shoe,
    ShoeJobPartUse,
    ShoeRepairJob,
    StockLevel,
    StockLocation,
    StockMovement,
    StockPart,
    StockTransfer,
    StockTransferLine,
)
from ..parent_network import parent_ids_for_tenant
from .parent_accounts import _parent_for_read, _parent_for_write

hq_router = APIRouter(prefix="/v1/parent-accounts/me/stock", tags=["hq-stock"])
shop_router = APIRouter(prefix="/v1/stock", tags=["stock"])

LOCATION_KINDS = ("workshop", "store", "warehouse")
PART_TYPES = ("footbed", "sole", "upper", "buckle", "liner", "other")


# ── access ────────────────────────────────────────────────────────────────────

@dataclass
class Access:
    parent_id: UUID
    user_id: UUID
    #: Locations the caller may move stock for; None means every location (HQ).
    location_ids: Optional[set[UUID]]
    is_hq: bool


def _hq_read(session: Session, auth: AuthContext) -> Access:
    require_hq(auth, session, "stock")
    _, parent, _ = _parent_for_read(session, auth)
    return Access(parent.id, auth.user_id, None, True)


def _hq_write(session: Session, auth: AuthContext) -> Access:
    require_hq(auth, session, "stock")
    user, parent = _parent_for_write(session, auth)
    return Access(parent.id, user.id, None, True)


def _shop_access(session: Session, auth: AuthContext) -> Access:
    """A shop in a network whose HQ has the stock module; limited to its own locations."""
    for parent_id in parent_ids_for_tenant(session, auth.tenant_id):
        config = get_hq_config(session, parent_id)
        if config is not None and config.has_module("stock"):
            mine = {
                loc.id
                for loc in session.exec(
                    select(StockLocation).where(
                        StockLocation.parent_account_id == parent_id,
                        StockLocation.tenant_id == auth.tenant_id,
                        StockLocation.active == True,  # noqa: E712
                    )
                ).all()
            }
            return Access(parent_id, auth.user_id, mine, False)
    raise HTTPException(status_code=403, detail="Stock is not enabled for this shop's network")


def _check_location(session: Session, access: Access, location_id: UUID, *, mine: bool) -> StockLocation:
    loc = session.get(StockLocation, location_id)
    if not loc or loc.parent_account_id != access.parent_id:
        raise HTTPException(status_code=404, detail="Location not found")
    if mine and access.location_ids is not None and loc.id not in access.location_ids:
        raise HTTPException(status_code=403, detail="That location belongs to another shop")
    return loc


def _find_part(session: Session, parent_id: UUID, *, part_id: UUID | None = None, sku: str | None = None) -> StockPart:
    part = None
    if part_id:
        part = session.get(StockPart, part_id)
    elif sku:
        part = session.exec(
            select(StockPart).where(StockPart.parent_account_id == parent_id, func.lower(StockPart.sku) == sku.strip().lower())
        ).first()
    if not part or part.parent_account_id != parent_id:
        raise HTTPException(status_code=404, detail=f"Part not found{f' for scan {sku!r}' if sku else ''}")
    return part


# ── stock core ────────────────────────────────────────────────────────────────

def _level(session: Session, parent_id: UUID, location_id: UUID, part_id: UUID) -> StockLevel:
    row = session.exec(select(StockLevel).where(StockLevel.location_id == location_id, StockLevel.part_id == part_id)).first()
    if row is None:
        row = StockLevel(parent_account_id=parent_id, location_id=location_id, part_id=part_id, quantity=0)
        session.add(row)
        session.flush()
    return row


def _move(
    session: Session, access: Access, location_id: UUID, part_id: UUID, delta: int, kind: str,
    *, note: str | None = None, transfer_id: UUID | None = None, job_id: UUID | None = None,
) -> StockLevel:
    level = _level(session, access.parent_id, location_id, part_id)
    level.quantity += delta
    level.updated_at = datetime.now(timezone.utc)
    session.add(level)
    session.add(StockMovement(
        parent_account_id=access.parent_id, location_id=location_id, part_id=part_id, quantity=delta, kind=kind,
        transfer_id=transfer_id, shoe_repair_job_id=job_id, note=note, user_id=access.user_id,
    ))
    return level


# ── request / response shapes ─────────────────────────────────────────────────

class PartIn(BaseModel):
    sku: str = Field(min_length=1, max_length=80)
    name: str = Field(min_length=1, max_length=200)
    part_type: Optional[str] = Field(default=None, max_length=40)
    cost_cents: int = Field(default=0, ge=0, le=100_000_000)
    reorder_level: int = Field(default=0, ge=0, le=1_000_000)


class PartPatch(BaseModel):
    name: Optional[str] = Field(default=None, min_length=1, max_length=200)
    part_type: Optional[str] = Field(default=None, max_length=40)
    cost_cents: Optional[int] = Field(default=None, ge=0, le=100_000_000)
    reorder_level: Optional[int] = Field(default=None, ge=0, le=1_000_000)
    active: Optional[bool] = None


class ModelIn(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    category: Optional[str] = Field(default=None, max_length=40)


class ModelPatch(BaseModel):
    name: Optional[str] = Field(default=None, min_length=1, max_length=120)
    category: Optional[str] = Field(default=None, max_length=40)
    active: Optional[bool] = None


class ModelPartIn(BaseModel):
    part_id: UUID
    size: Optional[str] = Field(default=None, max_length=40)
    quantity: int = Field(default=1, ge=1, le=100)


class LocationIn(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    kind: str = "workshop"
    tenant_id: Optional[UUID] = None


class LocationPatch(BaseModel):
    name: Optional[str] = Field(default=None, min_length=1, max_length=120)
    kind: Optional[str] = None
    tenant_id: Optional[UUID] = None
    active: Optional[bool] = None


class AdjustIn(BaseModel):
    location_id: UUID
    part_id: Optional[UUID] = None
    sku: Optional[str] = None  # a barcode scan
    quantity: int = Field(ge=-1_000_000, le=1_000_000)  # signed change
    kind: str = "receive"  # receive | adjust
    note: Optional[str] = Field(default=None, max_length=300)


class SyncRow(BaseModel):
    sku: str
    quantity: int = Field(ge=0, le=1_000_000)


class SyncIn(BaseModel):
    location_id: UUID
    rows: list[SyncRow] = Field(max_length=5000)
    #: Create unknown SKUs as new parts (named after the SKU) instead of reporting them.
    create_missing: bool = False


class TransferLineIn(BaseModel):
    part_id: Optional[UUID] = None
    sku: Optional[str] = None
    quantity: int = Field(gt=0, le=1_000_000)


class TransferIn(BaseModel):
    from_location_id: UUID
    to_location_id: UUID
    lines: list[TransferLineIn] = Field(min_length=1, max_length=200)
    note: Optional[str] = Field(default=None, max_length=300)


class ReceiveLineIn(BaseModel):
    part_id: Optional[UUID] = None
    sku: Optional[str] = None
    quantity: int = Field(ge=0, le=1_000_000)


class ReceiveIn(BaseModel):
    #: Omit to receive everything that was sent; list lines to receive what was actually scanned in.
    lines: Optional[list[ReceiveLineIn]] = None


class PurchaseRow(BaseModel):
    purchase_ref: str = Field(min_length=1, max_length=120)
    purchase_date: Optional[date] = None
    store: Optional[str] = Field(default=None, max_length=120)
    customer_name: Optional[str] = Field(default=None, max_length=200)
    customer_email: Optional[str] = Field(default=None, max_length=254)
    customer_phone: Optional[str] = Field(default=None, max_length=40)
    model_name: Optional[str] = Field(default=None, max_length=120)
    size: Optional[str] = Field(default=None, max_length=40)


class PurchaseImportIn(BaseModel):
    rows: list[PurchaseRow] = Field(max_length=5000)


class JobPartIn(BaseModel):
    part_id: Optional[UUID] = None
    sku: Optional[str] = None
    quantity: int = Field(default=1, gt=0, le=1000)
    location_id: Optional[UUID] = None


def _part_out(p: StockPart) -> dict:
    return {
        "id": str(p.id), "sku": p.sku, "name": p.name, "part_type": p.part_type,
        "cost_cents": p.cost_cents, "reorder_level": p.reorder_level, "active": p.active,
    }


def _location_out(loc: StockLocation) -> dict:
    return {"id": str(loc.id), "name": loc.name, "kind": loc.kind, "tenant_id": str(loc.tenant_id) if loc.tenant_id else None, "active": loc.active}


def _transfer_out(session: Session, t: StockTransfer) -> dict:
    lines = session.exec(select(StockTransferLine).where(StockTransferLine.transfer_id == t.id)).all()
    parts = {p.id: p for p in session.exec(select(StockPart).where(col(StockPart.id).in_([l.part_id for l in lines]))).all()} if lines else {}
    return {
        "id": str(t.id), "status": t.status, "from_location_id": str(t.from_location_id), "to_location_id": str(t.to_location_id),
        "note": t.note, "created_at": t.created_at, "received_at": t.received_at,
        "lines": [
            {"part_id": str(l.part_id), "sku": parts[l.part_id].sku, "name": parts[l.part_id].name,
             "quantity": l.quantity, "received_quantity": l.received_quantity}
            for l in lines if l.part_id in parts
        ],
    }


def _levels_out(session: Session, parent_id: UUID, location_ids: Optional[set[UUID]], location_id: UUID | None) -> list[dict]:
    q = select(StockLevel, StockPart, StockLocation).where(
        StockLevel.parent_account_id == parent_id, StockLevel.part_id == StockPart.id, StockLevel.location_id == StockLocation.id,
    )
    if location_id:
        q = q.where(StockLevel.location_id == location_id)
    if location_ids is not None:
        q = q.where(col(StockLevel.location_id).in_(location_ids or {UUID(int=0)}))
    out = []
    for level, part, loc in session.exec(q.order_by(StockLocation.name, StockPart.name)).all():
        out.append({
            "location_id": str(loc.id), "location_name": loc.name, "part_id": str(part.id), "sku": part.sku, "name": part.name,
            "part_type": part.part_type, "quantity": level.quantity, "reorder_level": part.reorder_level,
            "low": part.reorder_level > 0 and level.quantity <= part.reorder_level,
        })
    return out


# ── shared handlers ───────────────────────────────────────────────────────────

def _list_parts(session: Session, a: Access) -> list[dict]:
    return [_part_out(p) for p in session.exec(select(StockPart).where(StockPart.parent_account_id == a.parent_id).order_by(StockPart.name)).all()]


def _create_transfer(session: Session, a: Access, payload: TransferIn) -> dict:
    src = _check_location(session, a, payload.from_location_id, mine=True)
    dst = _check_location(session, a, payload.to_location_id, mine=False)
    if src.id == dst.id:
        raise HTTPException(status_code=422, detail="Choose two different locations")
    transfer = StockTransfer(parent_account_id=a.parent_id, from_location_id=src.id, to_location_id=dst.id, note=payload.note, created_by_user_id=a.user_id)
    session.add(transfer)
    session.flush()
    wanted: dict[UUID, int] = {}
    for line in payload.lines:
        part = _find_part(session, a.parent_id, part_id=line.part_id, sku=line.sku)
        wanted[part.id] = wanted.get(part.id, 0) + line.quantity
    for part_id, qty in wanted.items():
        have = _level(session, a.parent_id, src.id, part_id).quantity
        if have < qty:
            part = session.get(StockPart, part_id)
            session.rollback()
            raise HTTPException(status_code=409, detail=f"Only {have} of {part.name} ({part.sku}) at {src.name}; cannot send {qty}")
        session.add(StockTransferLine(transfer_id=transfer.id, part_id=part_id, quantity=qty))
        _move(session, a, src.id, part_id, -qty, "transfer_out", transfer_id=transfer.id, note=f"To {dst.name}")
    session.commit()
    session.refresh(transfer)
    return _transfer_out(session, transfer)


def _receive_transfer(session: Session, a: Access, transfer_id: UUID, payload: ReceiveIn) -> dict:
    transfer = session.get(StockTransfer, transfer_id)
    if not transfer or transfer.parent_account_id != a.parent_id:
        raise HTTPException(status_code=404, detail="Transfer not found")
    dst = _check_location(session, a, transfer.to_location_id, mine=True)
    if transfer.status != "in_transit":
        raise HTTPException(status_code=409, detail=f"Transfer is already {transfer.status}")
    lines = session.exec(select(StockTransferLine).where(StockTransferLine.transfer_id == transfer.id)).all()
    by_part = {l.part_id: l for l in lines}
    if payload.lines is None:
        got = {l.part_id: l.quantity for l in lines}
    else:
        got = {}
        for rl in payload.lines:
            part = _find_part(session, a.parent_id, part_id=rl.part_id, sku=rl.sku)
            if part.id not in by_part:
                raise HTTPException(status_code=422, detail=f"{part.name} ({part.sku}) is not on this transfer")
            got[part.id] = got.get(part.id, 0) + rl.quantity
    for part_id, qty in got.items():
        line = by_part[part_id]
        qty = min(qty, line.quantity)
        line.received_quantity = qty
        session.add(line)
        if qty:
            _move(session, a, dst.id, part_id, qty, "transfer_in", transfer_id=transfer.id)
    transfer.status = "received"
    transfer.received_at = datetime.now(timezone.utc)
    session.add(transfer)
    session.commit()
    session.refresh(transfer)
    return _transfer_out(session, transfer)


def _adjust(session: Session, a: Access, payload: AdjustIn) -> dict:
    if payload.kind not in ("receive", "adjust"):
        raise HTTPException(status_code=422, detail="kind must be receive or adjust")
    loc = _check_location(session, a, payload.location_id, mine=True)
    part = _find_part(session, a.parent_id, part_id=payload.part_id, sku=payload.sku)
    if payload.kind == "receive" and payload.quantity < 0:
        raise HTTPException(status_code=422, detail="Receiving cannot be negative; use adjust")
    level = _move(session, a, loc.id, part.id, payload.quantity, payload.kind, note=payload.note)
    session.commit()
    return {"location_id": str(loc.id), "part_id": str(part.id), "sku": part.sku, "name": part.name, "quantity": level.quantity}


def _search_purchases(session: Session, a: Access, q: str) -> list[dict]:
    q = q.strip()
    if len(q) < 3:
        return []
    like = f"%{q.lower()}%"
    rows = session.exec(
        select(HqPurchaseRecord).where(
            HqPurchaseRecord.parent_account_id == a.parent_id,
            or_(
                func.lower(HqPurchaseRecord.purchase_ref).like(like),
                func.lower(func.coalesce(HqPurchaseRecord.customer_name, "")).like(like),
                func.lower(func.coalesce(HqPurchaseRecord.customer_email, "")).like(like),
                func.coalesce(HqPurchaseRecord.customer_phone, "").like(f"%{q}%"),
            ),
        ).order_by(col(HqPurchaseRecord.purchase_date).desc()).limit(25)
    ).all()
    return [
        {"id": str(r.id), "purchase_ref": r.purchase_ref, "purchase_date": r.purchase_date, "store": r.store,
         "customer_name": r.customer_name, "customer_email": r.customer_email, "customer_phone": r.customer_phone,
         "model_name": r.model_name, "size": r.size}
        for r in rows
    ]


def _models_with_parts(session: Session, a: Access) -> list[dict]:
    models = session.exec(select(HqShoeModel).where(HqShoeModel.parent_account_id == a.parent_id).order_by(HqShoeModel.name)).all()
    return [{"id": str(m.id), "name": m.name, "category": m.category, "active": m.active} for m in models]


def _bom_for(session: Session, parent_id: UUID, model_name: str | None, size: str | None) -> list[dict]:
    if not model_name:
        return []
    model = session.exec(
        select(HqShoeModel).where(HqShoeModel.parent_account_id == parent_id, func.lower(HqShoeModel.name) == model_name.strip().lower())
    ).first()
    if not model:
        return []
    rows = session.exec(select(HqShoeModelPart).where(HqShoeModelPart.model_id == model.id)).all()
    chosen: dict[UUID, HqShoeModelPart] = {}
    wanted = (size or "").strip().lower()
    for row in rows:
        row_size = (row.size or "").strip().lower()
        if row_size and row_size != wanted:
            continue
        # A size-specific row overrides the all-sizes row for the same part.
        if row.part_id not in chosen or row_size:
            chosen[row.part_id] = row
    parts = {p.id: p for p in session.exec(select(StockPart).where(col(StockPart.id).in_(list(chosen)))).all()} if chosen else {}
    return [
        {"part_id": str(pid), "sku": parts[pid].sku, "name": parts[pid].name, "part_type": parts[pid].part_type, "quantity": row.quantity}
        for pid, row in chosen.items() if pid in parts
    ]


# ── HQ routes ─────────────────────────────────────────────────────────────────

@hq_router.get("/parts")
def hq_list_parts(auth: AuthContext = Depends(get_auth_context), session: Session = Depends(unscoped_session)):
    return _list_parts(session, _hq_read(session, auth))


@hq_router.post("/parts", status_code=201)
def hq_create_part(payload: PartIn, auth: AuthContext = Depends(get_auth_context), session: Session = Depends(unscoped_session)):
    a = _hq_write(session, auth)
    if payload.part_type and payload.part_type not in PART_TYPES:
        raise HTTPException(status_code=422, detail=f"part_type must be one of {', '.join(PART_TYPES)}")
    sku = payload.sku.strip()
    if session.exec(select(StockPart).where(StockPart.parent_account_id == a.parent_id, func.lower(StockPart.sku) == sku.lower())).first():
        raise HTTPException(status_code=409, detail="A part with that SKU already exists")
    part = StockPart(parent_account_id=a.parent_id, sku=sku, name=payload.name.strip(), part_type=payload.part_type,
                     cost_cents=payload.cost_cents, reorder_level=payload.reorder_level)
    session.add(part)
    session.commit()
    return _part_out(part)


@hq_router.patch("/parts/{part_id}")
def hq_update_part(part_id: UUID, payload: PartPatch, auth: AuthContext = Depends(get_auth_context), session: Session = Depends(unscoped_session)):
    a = _hq_write(session, auth)
    part = _find_part(session, a.parent_id, part_id=part_id)
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(part, field, value)
    session.add(part)
    session.commit()
    return _part_out(part)


@hq_router.get("/models")
def hq_list_models(auth: AuthContext = Depends(get_auth_context), session: Session = Depends(unscoped_session)):
    return _models_with_parts(session, _hq_read(session, auth))


@hq_router.post("/models", status_code=201)
def hq_create_model(payload: ModelIn, auth: AuthContext = Depends(get_auth_context), session: Session = Depends(unscoped_session)):
    a = _hq_write(session, auth)
    name = payload.name.strip()
    if session.exec(select(HqShoeModel).where(HqShoeModel.parent_account_id == a.parent_id, func.lower(HqShoeModel.name) == name.lower())).first():
        raise HTTPException(status_code=409, detail="A model with that name already exists")
    model = HqShoeModel(parent_account_id=a.parent_id, name=name, category=payload.category)
    session.add(model)
    session.commit()
    return {"id": str(model.id), "name": model.name, "category": model.category, "active": model.active}


@hq_router.patch("/models/{model_id}")
def hq_update_model(model_id: UUID, payload: ModelPatch, auth: AuthContext = Depends(get_auth_context), session: Session = Depends(unscoped_session)):
    a = _hq_write(session, auth)
    model = session.get(HqShoeModel, model_id)
    if not model or model.parent_account_id != a.parent_id:
        raise HTTPException(status_code=404, detail="Model not found")
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(model, field, value)
    session.add(model)
    session.commit()
    return {"id": str(model.id), "name": model.name, "category": model.category, "active": model.active}


@hq_router.get("/models/{model_id}/parts")
def hq_model_parts(model_id: UUID, auth: AuthContext = Depends(get_auth_context), session: Session = Depends(unscoped_session)):
    a = _hq_read(session, auth)
    model = session.get(HqShoeModel, model_id)
    if not model or model.parent_account_id != a.parent_id:
        raise HTTPException(status_code=404, detail="Model not found")
    rows = session.exec(select(HqShoeModelPart).where(HqShoeModelPart.model_id == model.id)).all()
    parts = {p.id: p for p in session.exec(select(StockPart).where(col(StockPart.id).in_([r.part_id for r in rows]))).all()} if rows else {}
    return [
        {"part_id": str(r.part_id), "sku": parts[r.part_id].sku, "name": parts[r.part_id].name, "size": r.size, "quantity": r.quantity}
        for r in rows if r.part_id in parts
    ]


@hq_router.put("/models/{model_id}/parts")
def hq_set_model_parts(model_id: UUID, payload: list[ModelPartIn], auth: AuthContext = Depends(get_auth_context), session: Session = Depends(unscoped_session)):
    """Replace the whole parts list for a model (sizes left empty apply to every size)."""
    a = _hq_write(session, auth)
    model = session.get(HqShoeModel, model_id)
    if not model or model.parent_account_id != a.parent_id:
        raise HTTPException(status_code=404, detail="Model not found")
    for line in payload:
        _find_part(session, a.parent_id, part_id=line.part_id)
    for old in session.exec(select(HqShoeModelPart).where(HqShoeModelPart.model_id == model.id)).all():
        session.delete(old)
    session.flush()
    for line in payload:
        session.add(HqShoeModelPart(parent_account_id=a.parent_id, model_id=model.id, part_id=line.part_id,
                                    size=(line.size or "").strip() or None, quantity=line.quantity))
    session.commit()
    return {"count": len(payload)}


@hq_router.get("/locations")
def hq_list_locations(auth: AuthContext = Depends(get_auth_context), session: Session = Depends(unscoped_session)):
    a = _hq_read(session, auth)
    return [_location_out(l) for l in session.exec(select(StockLocation).where(StockLocation.parent_account_id == a.parent_id).order_by(StockLocation.name)).all()]


@hq_router.post("/locations", status_code=201)
def hq_create_location(payload: LocationIn, auth: AuthContext = Depends(get_auth_context), session: Session = Depends(unscoped_session)):
    a = _hq_write(session, auth)
    if payload.kind not in LOCATION_KINDS:
        raise HTTPException(status_code=422, detail=f"kind must be one of {', '.join(LOCATION_KINDS)}")
    name = payload.name.strip()
    if session.exec(select(StockLocation).where(StockLocation.parent_account_id == a.parent_id, StockLocation.name == name)).first():
        raise HTTPException(status_code=409, detail="A location with that name already exists")
    if payload.tenant_id and payload.tenant_id not in {s for s in _network_tenant_ids(session, a.parent_id)}:
        raise HTTPException(status_code=422, detail="That shop is not in this network")
    loc = StockLocation(parent_account_id=a.parent_id, name=name, kind=payload.kind, tenant_id=payload.tenant_id)
    session.add(loc)
    session.commit()
    return _location_out(loc)


@hq_router.patch("/locations/{location_id}")
def hq_update_location(location_id: UUID, payload: LocationPatch, auth: AuthContext = Depends(get_auth_context), session: Session = Depends(unscoped_session)):
    a = _hq_write(session, auth)
    loc = _check_location(session, a, location_id, mine=False)
    data = payload.model_dump(exclude_unset=True)
    if "kind" in data and data["kind"] not in LOCATION_KINDS:
        raise HTTPException(status_code=422, detail=f"kind must be one of {', '.join(LOCATION_KINDS)}")
    if data.get("tenant_id") and data["tenant_id"] not in set(_network_tenant_ids(session, a.parent_id)):
        raise HTTPException(status_code=422, detail="That shop is not in this network")
    for field, value in data.items():
        setattr(loc, field, value)
    session.add(loc)
    session.commit()
    return _location_out(loc)


def _network_tenant_ids(session: Session, parent_id: UUID) -> list[UUID]:
    from ..models import ParentAccountSite

    return list(session.exec(select(ParentAccountSite.tenant_id).where(ParentAccountSite.parent_account_id == parent_id)).all())


@hq_router.get("/levels")
def hq_levels(location_id: UUID | None = Query(default=None), auth: AuthContext = Depends(get_auth_context), session: Session = Depends(unscoped_session)):
    a = _hq_read(session, auth)
    return _levels_out(session, a.parent_id, None, location_id)


@hq_router.post("/adjust")
def hq_adjust(payload: AdjustIn, auth: AuthContext = Depends(get_auth_context), session: Session = Depends(unscoped_session)):
    return _adjust(session, _hq_write(session, auth), payload)


@hq_router.post("/sync")
def hq_sync(payload: SyncIn, auth: AuthContext = Depends(get_auth_context), session: Session = Depends(unscoped_session)):
    """Set stock for a location to the counts in a feed from their inventory system (by SKU)."""
    a = _hq_write(session, auth)
    loc = _check_location(session, a, payload.location_id, mine=False)
    unknown: list[str] = []
    updated = 0
    for row in payload.rows:
        sku = row.sku.strip()
        if not sku:
            continue
        part = session.exec(select(StockPart).where(StockPart.parent_account_id == a.parent_id, func.lower(StockPart.sku) == sku.lower())).first()
        if part is None:
            if not payload.create_missing:
                unknown.append(sku)
                continue
            part = StockPart(parent_account_id=a.parent_id, sku=sku, name=sku)
            session.add(part)
            session.flush()
        current = _level(session, a.parent_id, loc.id, part.id).quantity
        if current != row.quantity:
            _move(session, a, loc.id, part.id, row.quantity - current, "sync", note="Inventory feed")
            updated += 1
    session.commit()
    return {"updated": updated, "unknown_skus": unknown}


@hq_router.get("/transfers")
def hq_transfers(status: str | None = Query(default=None, max_length=20), auth: AuthContext = Depends(get_auth_context), session: Session = Depends(unscoped_session)):
    a = _hq_read(session, auth)
    q = select(StockTransfer).where(StockTransfer.parent_account_id == a.parent_id)
    if status:
        q = q.where(StockTransfer.status == status)
    return [_transfer_out(session, t) for t in session.exec(q.order_by(col(StockTransfer.created_at).desc()).limit(200)).all()]


@hq_router.post("/transfers", status_code=201)
def hq_create_transfer(payload: TransferIn, auth: AuthContext = Depends(get_auth_context), session: Session = Depends(unscoped_session)):
    return _create_transfer(session, _hq_write(session, auth), payload)


@hq_router.post("/transfers/{transfer_id}/receive")
def hq_receive_transfer(transfer_id: UUID, payload: ReceiveIn, auth: AuthContext = Depends(get_auth_context), session: Session = Depends(unscoped_session)):
    return _receive_transfer(session, _hq_write(session, auth), transfer_id, payload)


@hq_router.post("/purchases/import")
def hq_import_purchases(payload: PurchaseImportIn, auth: AuthContext = Depends(get_auth_context), session: Session = Depends(unscoped_session)):
    """Add or update sales records by receipt/order reference."""
    a = _hq_write(session, auth)
    created = updated = 0
    for row in payload.rows:
        ref = row.purchase_ref.strip()
        existing = session.exec(select(HqPurchaseRecord).where(HqPurchaseRecord.parent_account_id == a.parent_id, HqPurchaseRecord.purchase_ref == ref)).first()
        data = row.model_dump()
        data["purchase_ref"] = ref
        if existing:
            for field, value in data.items():
                setattr(existing, field, value)
            session.add(existing)
            updated += 1
        else:
            session.add(HqPurchaseRecord(parent_account_id=a.parent_id, **data))
            created += 1
    session.commit()
    return {"created": created, "updated": updated}


@hq_router.get("/purchases")
def hq_search_purchases(q: str = Query(default="", max_length=100), auth: AuthContext = Depends(get_auth_context), session: Session = Depends(unscoped_session)):
    return _search_purchases(session, _hq_read(session, auth), q)


@hq_router.get("/summary")
def hq_stock_summary(auth: AuthContext = Depends(get_auth_context), session: Session = Depends(unscoped_session)):
    """Low stock, transfers on the way, and parts used in the last 30 days."""
    a = _hq_read(session, auth)
    levels = _levels_out(session, a.parent_id, None, None)
    since = datetime.now(timezone.utc) - timedelta(days=30)
    used = session.exec(
        select(StockPart.sku, StockPart.name, func.sum(-StockMovement.quantity))
        .where(StockMovement.parent_account_id == a.parent_id, StockMovement.kind == "use", StockMovement.created_at >= since,
               StockMovement.part_id == StockPart.id)
        .group_by(StockPart.sku, StockPart.name).order_by(func.sum(-StockMovement.quantity).desc()).limit(20)
    ).all()
    in_transit = session.exec(select(func.count()).select_from(StockTransfer).where(StockTransfer.parent_account_id == a.parent_id, StockTransfer.status == "in_transit")).one()
    return {
        "low_stock": [l for l in levels if l["low"]],
        "in_transit_transfers": in_transit,
        "parts_used_30d": [{"sku": s, "name": n, "quantity": int(q)} for s, n, q in used],
        "locations": len({l["location_id"] for l in levels}),
    }


# ── shop / workshop routes ────────────────────────────────────────────────────

@shop_router.get("/models")
def shop_models(auth: AuthContext = Depends(get_auth_context), session: Session = Depends(unscoped_session)):
    """Active models for the intake dropdown."""
    a = _shop_access(session, auth)
    return [m for m in _models_with_parts(session, a) if m["active"]]


@shop_router.get("/locations")
def shop_locations(auth: AuthContext = Depends(get_auth_context), session: Session = Depends(unscoped_session)):
    """This shop's own locations, plus every other location in the network as transfer targets."""
    a = _shop_access(session, auth)
    locs = session.exec(select(StockLocation).where(StockLocation.parent_account_id == a.parent_id, StockLocation.active == True).order_by(StockLocation.name)).all()  # noqa: E712
    return [{**_location_out(l), "mine": l.id in (a.location_ids or set())} for l in locs]


@shop_router.get("/parts")
def shop_parts(auth: AuthContext = Depends(get_auth_context), session: Session = Depends(unscoped_session)):
    return [p for p in _list_parts(session, _shop_access(session, auth)) if p["active"]]


@shop_router.get("/levels")
def shop_levels(auth: AuthContext = Depends(get_auth_context), session: Session = Depends(unscoped_session)):
    a = _shop_access(session, auth)
    return _levels_out(session, a.parent_id, a.location_ids, None)


@shop_router.post("/adjust")
def shop_adjust(payload: AdjustIn, auth: AuthContext = Depends(get_auth_context), session: Session = Depends(unscoped_session)):
    return _adjust(session, _shop_access(session, auth), payload)


@shop_router.get("/transfers")
def shop_transfers(auth: AuthContext = Depends(get_auth_context), session: Session = Depends(unscoped_session)):
    """Transfers to or from this shop's locations."""
    a = _shop_access(session, auth)
    mine = a.location_ids or {UUID(int=0)}
    rows = session.exec(
        select(StockTransfer).where(
            StockTransfer.parent_account_id == a.parent_id,
            or_(col(StockTransfer.from_location_id).in_(mine), col(StockTransfer.to_location_id).in_(mine)),
        ).order_by(col(StockTransfer.created_at).desc()).limit(100)
    ).all()
    return [_transfer_out(session, t) for t in rows]


@shop_router.post("/transfers", status_code=201)
def shop_create_transfer(payload: TransferIn, auth: AuthContext = Depends(get_auth_context), session: Session = Depends(unscoped_session)):
    return _create_transfer(session, _shop_access(session, auth), payload)


@shop_router.post("/transfers/{transfer_id}/receive")
def shop_receive_transfer(transfer_id: UUID, payload: ReceiveIn, auth: AuthContext = Depends(get_auth_context), session: Session = Depends(unscoped_session)):
    return _receive_transfer(session, _shop_access(session, auth), transfer_id, payload)


@shop_router.get("/purchases/search")
def shop_search_purchases(q: str = Query(default="", max_length=100), auth: AuthContext = Depends(get_auth_context), session: Session = Depends(unscoped_session)):
    return _search_purchases(session, _shop_access(session, auth), q)


def _job_for_shop(session: Session, auth: AuthContext, job_id: UUID) -> tuple[ShoeRepairJob, Shoe | None]:
    job = session.get(ShoeRepairJob, job_id)
    if not job or job.tenant_id != auth.tenant_id:
        raise HTTPException(status_code=404, detail="Job not found")
    return job, session.get(Shoe, job.shoe_id)


@shop_router.get("/jobs/{job_id}/suggested-parts")
def shop_suggested_parts(job_id: UUID, auth: AuthContext = Depends(get_auth_context), session: Session = Depends(unscoped_session)):
    """Parts the shoe's model and size normally need, with stock at this shop's locations."""
    a = _shop_access(session, auth)
    _, shoe = _job_for_shop(session, auth, job_id)
    bom = _bom_for(session, a.parent_id, shoe.model_name if shoe else None, shoe.size if shoe else None)
    if not bom:
        return []
    mine = a.location_ids or set()
    stock: dict[str, int] = {}
    if mine:
        for level in session.exec(select(StockLevel).where(col(StockLevel.location_id).in_(mine))).all():
            stock[str(level.part_id)] = stock.get(str(level.part_id), 0) + level.quantity
    return [{**row, "in_stock": stock.get(row["part_id"], 0)} for row in bom]


@shop_router.get("/jobs/{job_id}/parts")
def shop_job_parts(job_id: UUID, auth: AuthContext = Depends(get_auth_context), session: Session = Depends(unscoped_session)):
    _shop_access(session, auth)
    _job_for_shop(session, auth, job_id)
    rows = session.exec(select(ShoeJobPartUse).where(ShoeJobPartUse.shoe_repair_job_id == job_id).order_by(ShoeJobPartUse.created_at)).all()
    parts = {p.id: p for p in session.exec(select(StockPart).where(col(StockPart.id).in_([r.part_id for r in rows]))).all()} if rows else {}
    return [{"id": str(r.id), "part_id": str(r.part_id), "sku": parts[r.part_id].sku, "name": parts[r.part_id].name,
             "quantity": r.quantity, "location_id": str(r.location_id), "created_at": r.created_at} for r in rows if r.part_id in parts]


@shop_router.post("/jobs/{job_id}/parts", status_code=201)
def shop_use_part(job_id: UUID, payload: JobPartIn, auth: AuthContext = Depends(get_auth_context), session: Session = Depends(unscoped_session)):
    """Record a part used on a repair and take it out of the shop's stock.

    Stock may go below zero: counts are often behind the workbench, and blocking
    a repair for a miscount would be worse. Low and negative levels show on the
    stock screens so they get corrected.
    """
    a = _shop_access(session, auth)
    job, _ = _job_for_shop(session, auth, job_id)
    part = _find_part(session, a.parent_id, part_id=payload.part_id, sku=payload.sku)
    mine = a.location_ids or set()
    if payload.location_id:
        loc = _check_location(session, a, payload.location_id, mine=True)
    elif len(mine) == 1:
        loc = session.get(StockLocation, next(iter(mine)))
    else:
        raise HTTPException(status_code=422, detail="Choose which location the part came from" if mine else "This shop has no stock location yet")
    use = ShoeJobPartUse(tenant_id=auth.tenant_id, shoe_repair_job_id=job.id, part_id=part.id, location_id=loc.id,
                         quantity=payload.quantity, created_by_user_id=auth.user_id)
    session.add(use)
    level = _move(session, a, loc.id, part.id, -payload.quantity, "use", job_id=job.id, note=job.job_number)
    session.commit()
    return {"id": str(use.id), "part_id": str(part.id), "sku": part.sku, "name": part.name, "quantity": use.quantity,
            "location_id": str(loc.id), "stock_left": level.quantity}
