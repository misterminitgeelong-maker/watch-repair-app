import csv
import io
from datetime import datetime, timezone
from uuid import UUID

import openpyxl
from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile
from fastapi.responses import StreamingResponse
from sqlalchemy import or_
from sqlmodel import Session, func, select

from ..database import get_session
from ..dependencies import AuthContext, get_auth_context, require_manager_or_above
from ..models import (
    StockAdjustment,
    StockImportSummaryResponse,
    StockItem,
    StockItemRead,
    StocktakeGroupSummaryRead,
    StocktakeLine,
    StocktakeLineBulkUpsertRequest,
    StocktakeLineInput,
    StocktakeLineRead,
    StocktakeLineUpdate,
    StocktakeProgressRead,
    StocktakeReportRead,
    StocktakeSession,
    StocktakeSessionCreate,
    StocktakeSessionDetailRead,
    StocktakeSessionRead,
)
from ..stock_utils import build_full_description, group_name_for_code, load_stock_sheets, merge_stock_records


router = APIRouter(prefix="/v1", tags=["stocktakes"])


def _serialize_stock_item(item: StockItem) -> StockItemRead:
    return StockItemRead(
        id=item.id,
        tenant_id=item.tenant_id,
        item_code=item.item_code,
        group_code=item.group_code,
        group_name=item.group_name,
        item_description=item.item_description,
        description2=item.description2,
        description3=item.description3,
        full_description=item.full_description,
        unit_description=item.unit_description,
        pack_description=item.pack_description,
        pack_qty=item.pack_qty,
        cost_price_cents=item.cost_price_cents,
        retail_price_cents=item.retail_price_cents,
        system_stock_qty=item.system_stock_qty,
        is_active=item.is_active,
        created_at=item.created_at,
        updated_at=item.updated_at,
    )


def _line_variance_value(expected_qty: float, counted_qty: float | None, cost_price_cents: int) -> int | None:
    if counted_qty is None:
        return None
    return int(round((counted_qty - expected_qty) * cost_price_cents))


def _build_stocktake_progress(session_db: Session, stocktake_session_id: UUID) -> StocktakeProgressRead:
    total_items = int(
        session_db.exec(
            select(func.count()).select_from(StocktakeLine).where(StocktakeLine.stocktake_session_id == stocktake_session_id)
        ).one()
    )
    counted_items = int(
        session_db.exec(
            select(func.count())
            .select_from(StocktakeLine)
            .where(StocktakeLine.stocktake_session_id == stocktake_session_id)
            .where(StocktakeLine.counted_qty.is_not(None))
        ).one()
    )
    return StocktakeProgressRead(counted_items=counted_items, total_items=total_items)


def _serialize_stocktake_session(session_db: Session, stocktake_session: StocktakeSession) -> StocktakeSessionRead:
    return StocktakeSessionRead(
        id=stocktake_session.id,
        tenant_id=stocktake_session.tenant_id,
        name=stocktake_session.name,
        status=stocktake_session.status,
        created_by_user_id=stocktake_session.created_by_user_id,
        completed_by_user_id=stocktake_session.completed_by_user_id,
        group_code_filter=stocktake_session.group_code_filter,
        group_name_filter=stocktake_session.group_name_filter,
        search_filter=stocktake_session.search_filter,
        notes=stocktake_session.notes,
        created_at=stocktake_session.created_at,
        completed_at=stocktake_session.completed_at,
        progress=_build_stocktake_progress(session_db, stocktake_session.id),
    )


def _list_stock_items_query(auth: AuthContext, *, search: str | None, group_code: str | None, group_name: str | None, hide_zero_stock: bool):
    query = select(StockItem).where(StockItem.tenant_id == auth.tenant_id).where(StockItem.is_active.is_(True))
    if group_code:
        query = query.where(StockItem.group_code == group_code.strip().upper())
    if group_name:
        query = query.where(StockItem.group_name == group_name.strip())
    if search:
        token = f"%{search.strip()}%"
        query = query.where(
            or_(
                StockItem.item_code.ilike(token),
                StockItem.item_description.ilike(token),
                StockItem.full_description.ilike(token),
            )
        )
    if hide_zero_stock:
        query = query.where(StockItem.system_stock_qty != 0)
    return query.order_by(StockItem.group_code, StockItem.item_code)


def _get_session_or_404(session_db: Session, auth: AuthContext, stocktake_session_id: UUID) -> StocktakeSession:
    stocktake_session = session_db.get(StocktakeSession, stocktake_session_id)
    if not stocktake_session or stocktake_session.tenant_id != auth.tenant_id:
        raise HTTPException(status_code=404, detail="Stocktake session not found")
    return stocktake_session


def _get_line_or_404(session_db: Session, auth: AuthContext, stocktake_session_id: UUID, line_id: UUID) -> StocktakeLine:
    line = session_db.get(StocktakeLine, line_id)
    if not line or line.tenant_id != auth.tenant_id or line.stocktake_session_id != stocktake_session_id:
        raise HTTPException(status_code=404, detail="Stocktake line not found")
    return line


def _serialize_lines(session_db: Session, lines: list[StocktakeLine]) -> list[StocktakeLineRead]:
    if not lines:
        return []
    item_ids = [line.stock_item_id for line in lines]
    items = session_db.exec(select(StockItem).where(StockItem.id.in_(item_ids))).all()
    items_by_id = {item.id: item for item in items}
    result: list[StocktakeLineRead] = []
    for line in lines:
        item = items_by_id.get(line.stock_item_id)
        if not item:
            continue
        result.append(
            StocktakeLineRead(
                id=line.id,
                stocktake_session_id=line.stocktake_session_id,
                stock_item_id=line.stock_item_id,
                expected_qty=line.expected_qty,
                counted_qty=line.counted_qty,
                variance_qty=line.variance_qty,
                variance_value_cents=line.variance_value_cents,
                counted_by_user_id=line.counted_by_user_id,
                counted_at=line.counted_at,
                notes=line.notes,
                item_code=item.item_code,
                group_code=item.group_code,
                group_name=item.group_name,
                item_description=item.item_description,
                full_description=item.full_description,
                system_stock_qty=item.system_stock_qty,
                cost_price_cents=item.cost_price_cents,
                retail_price_cents=item.retail_price_cents,
            )
        )
    return result


def _session_detail(
    session_db: Session,
    stocktake_session: StocktakeSession,
    *,
    search: str | None,
    group_code: str | None,
    group_name: str | None,
    hide_zero_stock: bool,
    hide_counted: bool,
) -> StocktakeSessionDetailRead:
    line_query = select(StocktakeLine).where(StocktakeLine.stocktake_session_id == stocktake_session.id)
    if hide_counted:
        line_query = line_query.where(StocktakeLine.counted_qty.is_(None))
    lines = session_db.exec(line_query.order_by(StocktakeLine.created_at)).all()
    serialized = _serialize_lines(session_db, lines)

    filtered: list[StocktakeLineRead] = []
    search_token = (search or "").strip().lower()
    normalized_group_code = (group_code or "").strip().upper()
    normalized_group_name = (group_name or "").strip().lower()

    for line in serialized:
        if normalized_group_code and line.group_code != normalized_group_code:
            continue
        if normalized_group_name and (line.group_name or "").lower() != normalized_group_name:
            continue
        if hide_zero_stock and line.system_stock_qty == 0:
            continue
        if search_token:
            haystack = " ".join(filter(None, [line.item_code, line.item_description, line.full_description])).lower()
            if search_token not in haystack:
                continue
        filtered.append(line)

    session_read = _serialize_stocktake_session(session_db, stocktake_session)
    return StocktakeSessionDetailRead(**session_read.model_dump(), lines=filtered)


def _apply_line_count(line: StocktakeLine, item: StockItem, payload: StocktakeLineInput | StocktakeLineUpdate, auth: AuthContext) -> None:
    if payload.counted_qty is None:
        return
    if payload.counted_qty < 0 and not payload.allow_negative:
        raise HTTPException(status_code=400, detail="Negative counted quantities require explicit approval")
    line.counted_qty = payload.counted_qty
    line.variance_qty = payload.counted_qty - line.expected_qty
    line.variance_value_cents = _line_variance_value(line.expected_qty, payload.counted_qty, item.cost_price_cents)
    line.notes = payload.notes if payload.notes is not None else line.notes
    line.counted_by_user_id = auth.user_id
    line.counted_at = datetime.now(timezone.utc)
    line.updated_at = datetime.now(timezone.utc)


def _build_report(session_db: Session, stocktake_session: StocktakeSession) -> StocktakeReportRead:
    lines = session_db.exec(
        select(StocktakeLine).where(StocktakeLine.stocktake_session_id == stocktake_session.id).order_by(StocktakeLine.created_at)
    ).all()
    serialized_lines = _serialize_lines(session_db, lines)

    matched = 0
    missing = 0
    over_count = 0
    total_variance_qty = 0.0
    total_variance_value_cents = 0
    groups: dict[str, StocktakeGroupSummaryRead] = {}

    for line in serialized_lines:
        variance_qty = line.variance_qty or 0
        variance_value = line.variance_value_cents or 0
        total_variance_qty += variance_qty
        total_variance_value_cents += variance_value

        if line.counted_qty is not None:
            if variance_qty == 0:
                matched += 1
            elif variance_qty < 0:
                missing += 1
            else:
                over_count += 1

        group_key = line.group_code or "UNASSIGNED"
        group_summary = groups.get(group_key)
        if not group_summary:
            group_summary = StocktakeGroupSummaryRead(
                group_code=group_key,
                group_name=line.group_name,
            )
            groups[group_key] = group_summary
        group_summary.item_count += 1
        if line.counted_qty is not None:
            group_summary.counted_count += 1
        if variance_qty != 0:
            group_summary.variance_count += 1
        group_summary.total_variance_qty += variance_qty
        group_summary.total_variance_value_cents += variance_value

    return StocktakeReportRead(
        session=_serialize_stocktake_session(session_db, stocktake_session),
        matched_item_count=matched,
        missing_item_count=missing,
        over_count_item_count=over_count,
        total_variance_qty=total_variance_qty,
        total_variance_value_cents=total_variance_value_cents,
        groups=sorted(groups.values(), key=lambda group: group.group_code),
    )


def _report_rows(report: StocktakeReportRead) -> list[dict[str, str | int | float]]:
    rows: list[dict[str, str | int | float]] = []
    rows.append(
        {
            "Section": "Summary",
            "Group Code": "ALL",
            "Group Name": report.session.name,
            "Items Counted": report.session.progress.counted_items,
            "Total Items": report.session.progress.total_items,
            "Variance Count": report.missing_item_count + report.over_count_item_count,
            "Variance Qty": report.total_variance_qty,
            "Variance Value": report.total_variance_value_cents / 100,
        }
    )
    for group in report.groups:
        rows.append(
            {
                "Section": "Group",
                "Group Code": group.group_code,
                "Group Name": group.group_name or "",
                "Items Counted": group.counted_count,
                "Total Items": group.item_count,
                "Variance Count": group.variance_count,
                "Variance Qty": group.total_variance_qty,
                "Variance Value": group.total_variance_value_cents / 100,
            }
        )
    return rows


@router.post("/stock/import", response_model=StockImportSummaryResponse)
async def import_stock_master(
    file: UploadFile = File(...),
    auth: AuthContext = Depends(require_manager_or_above),
    session_db: Session = Depends(get_session),
):
    raw_bytes = await file.read()
    if not raw_bytes:
        raise HTTPException(status_code=400, detail="Uploaded file is empty")

    try:
        sheets = load_stock_sheets(file.filename or "stock-import", raw_bytes)
        merged_items, meta = merge_stock_records(sheets)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    if not merged_items:
        raise HTTPException(status_code=400, detail="No stock items were found in the uploaded file")

    existing_items = session_db.exec(select(StockItem).where(StockItem.tenant_id == auth.tenant_id)).all()
    existing_by_code = {item.item_code.upper(): item for item in existing_items}
    created = 0
    updated = 0
    now = datetime.now(timezone.utc)

    for raw_item in merged_items:
        item_code = raw_item["item_code"].upper()
        existing = existing_by_code.get(item_code)
        if existing:
            existing.group_code = raw_item.get("group_code") or existing.group_code
            existing.group_name = raw_item.get("group_name") or group_name_for_code(existing.group_code)
            existing.item_description = raw_item.get("item_description") or existing.item_description
            existing.description2 = raw_item.get("description2")
            existing.description3 = raw_item.get("description3")
            existing.full_description = raw_item.get("full_description") or build_full_description(existing.item_description, existing.description2, existing.description3)
            existing.unit_description = raw_item.get("unit_description")
            existing.pack_description = raw_item.get("pack_description")
            existing.pack_qty = raw_item.get("pack_qty") or 0
            existing.cost_price_cents = raw_item.get("cost_price_cents") or 0
            existing.retail_price_cents = raw_item.get("retail_price_cents") or 0
            if raw_item.get("system_stock_qty") is not None:
                existing.system_stock_qty = raw_item["system_stock_qty"]
            existing.is_active = True
            existing.updated_at = now
            session_db.add(existing)
            updated += 1
            continue

        session_db.add(
            StockItem(
                tenant_id=auth.tenant_id,
                item_code=raw_item["item_code"],
                group_code=raw_item.get("group_code") or "",
                group_name=raw_item.get("group_name"),
                item_description=raw_item.get("item_description"),
                description2=raw_item.get("description2"),
                description3=raw_item.get("description3"),
                full_description=raw_item.get("full_description"),
                unit_description=raw_item.get("unit_description"),
                pack_description=raw_item.get("pack_description"),
                pack_qty=raw_item.get("pack_qty") or 0,
                cost_price_cents=raw_item.get("cost_price_cents") or 0,
                retail_price_cents=raw_item.get("retail_price_cents") or 0,
                system_stock_qty=raw_item.get("system_stock_qty") or 0,
                is_active=True,
                created_at=now,
                updated_at=now,
            )
        )
        created += 1

    session_db.commit()
    return StockImportSummaryResponse(
        imported=len(merged_items),
        created=created,
        updated=updated,
        sources=meta["source_counts"],
        sheet_names=meta["sheet_names"],
    )


@router.get("/stock/items", response_model=list[StockItemRead])
def list_stock_items(
    search: str | None = Query(default=None),
    group_code: str | None = Query(default=None),
    group_name: str | None = Query(default=None),
    hide_zero_stock: bool = Query(default=False),
    auth: AuthContext = Depends(get_auth_context),
    session_db: Session = Depends(get_session),
):
    items = session_db.exec(
        _list_stock_items_query(
            auth,
            search=search,
            group_code=group_code,
            group_name=group_name,
            hide_zero_stock=hide_zero_stock,
        )
    ).all()
    return [_serialize_stock_item(item) for item in items]


@router.get("/stock/items/{item_id}", response_model=StockItemRead)
def get_stock_item(
    item_id: UUID,
    auth: AuthContext = Depends(get_auth_context),
    session_db: Session = Depends(get_session),
):
    item = session_db.get(StockItem, item_id)
    if not item or item.tenant_id != auth.tenant_id:
        raise HTTPException(status_code=404, detail="Stock item not found")
    return _serialize_stock_item(item)


@router.post("/stocktakes", response_model=StocktakeSessionRead, status_code=201)
def create_stocktake_session(
    payload: StocktakeSessionCreate,
    auth: AuthContext = Depends(get_auth_context),
    session_db: Session = Depends(get_session),
):
    items = session_db.exec(
        _list_stock_items_query(
            auth,
            search=payload.search,
            group_code=payload.group_code,
            group_name=payload.group_name,
            hide_zero_stock=payload.hide_zero_stock,
        )
    ).all()
    if not items:
        raise HTTPException(status_code=400, detail="No stock items matched the requested scope")

    stocktake_session = StocktakeSession(
        tenant_id=auth.tenant_id,
        name=payload.name.strip(),
        status="in_progress",
        created_by_user_id=auth.user_id,
        group_code_filter=payload.group_code.strip().upper() if payload.group_code else None,
        group_name_filter=payload.group_name.strip() if payload.group_name else None,
        search_filter=payload.search.strip() if payload.search else None,
        notes=payload.notes,
    )
    session_db.add(stocktake_session)
    session_db.flush()

    now = datetime.now(timezone.utc)
    for item in items:
        session_db.add(
            StocktakeLine(
                tenant_id=auth.tenant_id,
                stocktake_session_id=stocktake_session.id,
                stock_item_id=item.id,
                expected_qty=item.system_stock_qty,
                created_at=now,
                updated_at=now,
            )
        )

    session_db.commit()
    session_db.refresh(stocktake_session)
    return _serialize_stocktake_session(session_db, stocktake_session)


@router.get("/stocktakes", response_model=list[StocktakeSessionRead])
def list_stocktake_sessions(
    status: str | None = Query(default=None),
    auth: AuthContext = Depends(get_auth_context),
    session_db: Session = Depends(get_session),
):
    query = select(StocktakeSession).where(StocktakeSession.tenant_id == auth.tenant_id)
    if status:
        query = query.where(StocktakeSession.status == status)
    sessions = session_db.exec(query.order_by(StocktakeSession.created_at.desc())).all()
    return [_serialize_stocktake_session(session_db, stocktake_session) for stocktake_session in sessions]


@router.get("/stocktakes/{stocktake_session_id}", response_model=StocktakeSessionDetailRead)
def get_stocktake_session(
    stocktake_session_id: UUID,
    search: str | None = Query(default=None),
    group_code: str | None = Query(default=None),
    group_name: str | None = Query(default=None),
    hide_zero_stock: bool = Query(default=False),
    hide_counted: bool = Query(default=False),
    auth: AuthContext = Depends(get_auth_context),
    session_db: Session = Depends(get_session),
):
    stocktake_session = _get_session_or_404(session_db, auth, stocktake_session_id)
    return _session_detail(
        session_db,
        stocktake_session,
        search=search,
        group_code=group_code,
        group_name=group_name,
        hide_zero_stock=hide_zero_stock,
        hide_counted=hide_counted,
    )


@router.post("/stocktakes/{stocktake_session_id}/lines", response_model=list[StocktakeLineRead])
def bulk_upsert_stocktake_lines(
    stocktake_session_id: UUID,
    payload: StocktakeLineBulkUpsertRequest,
    auth: AuthContext = Depends(get_auth_context),
    session_db: Session = Depends(get_session),
):
    stocktake_session = _get_session_or_404(session_db, auth, stocktake_session_id)
    if stocktake_session.status in {"completed", "approved"}:
        raise HTTPException(status_code=400, detail="Completed stocktakes cannot be edited")

    touched_lines: list[StocktakeLine] = []
    item_ids = [line.stock_item_id for line in payload.lines]
    items = session_db.exec(select(StockItem).where(StockItem.id.in_(item_ids))).all() if item_ids else []
    items_by_id = {item.id: item for item in items}
    existing_lines = session_db.exec(
        select(StocktakeLine)
        .where(StocktakeLine.stocktake_session_id == stocktake_session_id)
        .where(StocktakeLine.stock_item_id.in_(item_ids))
    ).all() if item_ids else []
    lines_by_item_id = {line.stock_item_id: line for line in existing_lines}

    now = datetime.now(timezone.utc)
    for line_payload in payload.lines:
        item = items_by_id.get(line_payload.stock_item_id)
        if not item or item.tenant_id != auth.tenant_id:
            raise HTTPException(status_code=404, detail="One or more stock items were not found")
        line = lines_by_item_id.get(line_payload.stock_item_id)
        if not line:
            line = StocktakeLine(
                tenant_id=auth.tenant_id,
                stocktake_session_id=stocktake_session_id,
                stock_item_id=item.id,
                expected_qty=item.system_stock_qty,
                created_at=now,
                updated_at=now,
            )
        _apply_line_count(line, item, line_payload, auth)
        session_db.add(line)
        touched_lines.append(line)

    stocktake_session.status = "in_progress"
    session_db.add(stocktake_session)
    session_db.commit()

    for line in touched_lines:
        session_db.refresh(line)
    return _serialize_lines(session_db, touched_lines)


@router.patch("/stocktakes/{stocktake_session_id}/lines/{line_id}", response_model=StocktakeLineRead)
def update_stocktake_line(
    stocktake_session_id: UUID,
    line_id: UUID,
    payload: StocktakeLineUpdate,
    auth: AuthContext = Depends(get_auth_context),
    session_db: Session = Depends(get_session),
):
    stocktake_session = _get_session_or_404(session_db, auth, stocktake_session_id)
    if stocktake_session.status in {"completed", "approved"}:
        raise HTTPException(status_code=400, detail="Completed stocktakes cannot be edited")

    line = _get_line_or_404(session_db, auth, stocktake_session_id, line_id)
    item = session_db.get(StockItem, line.stock_item_id)
    if not item or item.tenant_id != auth.tenant_id:
        raise HTTPException(status_code=404, detail="Stock item not found")

    _apply_line_count(line, item, payload, auth)
    if payload.notes is not None:
        line.notes = payload.notes
    session_db.add(line)
    session_db.commit()
    session_db.refresh(line)
    return _serialize_lines(session_db, [line])[0]


@router.post("/stocktakes/{stocktake_session_id}/complete", response_model=StocktakeReportRead)
def complete_stocktake_session(
    stocktake_session_id: UUID,
    auth: AuthContext = Depends(require_manager_or_above),
    session_db: Session = Depends(get_session),
):
    stocktake_session = _get_session_or_404(session_db, auth, stocktake_session_id)
    if stocktake_session.status in {"completed", "approved"}:
        return _build_report(session_db, stocktake_session)

    lines = session_db.exec(select(StocktakeLine).where(StocktakeLine.stocktake_session_id == stocktake_session.id)).all()
    items = session_db.exec(
        select(StockItem).where(StockItem.id.in_([line.stock_item_id for line in lines]))
    ).all() if lines else []
    items_by_id = {item.id: item for item in items}
    now = datetime.now(timezone.utc)

    for line in lines:
        item = items_by_id.get(line.stock_item_id)
        if not item:
            continue
        previous_qty = item.system_stock_qty
        new_qty = line.counted_qty if line.counted_qty is not None else line.expected_qty
        if previous_qty != new_qty:
            session_db.add(
                StockAdjustment(
                    tenant_id=auth.tenant_id,
                    stock_item_id=item.id,
                    stocktake_session_id=stocktake_session.id,
                    old_qty=previous_qty,
                    new_qty=new_qty,
                    variance_qty=new_qty - previous_qty,
                    variance_value_cents=int(round((new_qty - previous_qty) * item.cost_price_cents)),
                    reason=f"Stocktake {stocktake_session.name}",
                    created_at=now,
                )
            )
            item.system_stock_qty = new_qty
            item.updated_at = now
            session_db.add(item)

    stocktake_session.status = "completed"
    stocktake_session.completed_by_user_id = auth.user_id
    stocktake_session.completed_at = now
    session_db.add(stocktake_session)
    session_db.commit()
    session_db.refresh(stocktake_session)
    return _build_report(session_db, stocktake_session)


@router.get("/stocktakes/{stocktake_session_id}/report", response_model=StocktakeReportRead)
def get_stocktake_report(
    stocktake_session_id: UUID,
    auth: AuthContext = Depends(get_auth_context),
    session_db: Session = Depends(get_session),
):
    stocktake_session = _get_session_or_404(session_db, auth, stocktake_session_id)
    return _build_report(session_db, stocktake_session)


@router.get("/stocktakes/{stocktake_session_id}/export")
def export_stocktake_report(
    stocktake_session_id: UUID,
    format: str = Query(default="csv", pattern="^(csv|xlsx)$"),
    auth: AuthContext = Depends(get_auth_context),
    session_db: Session = Depends(get_session),
):
    stocktake_session = _get_session_or_404(session_db, auth, stocktake_session_id)
    report = _build_report(session_db, stocktake_session)
    rows = _report_rows(report)

    if format == "csv":
        buffer = io.StringIO()
        writer = csv.DictWriter(buffer, fieldnames=list(rows[0].keys()) if rows else ["Section"])
        writer.writeheader()
        writer.writerows(rows)
        encoded = io.BytesIO(buffer.getvalue().encode("utf-8"))
        return StreamingResponse(
            encoded,
            media_type="text/csv",
            headers={"Content-Disposition": f'attachment; filename="stocktake-{stocktake_session.id}.csv"'},
        )

    workbook = openpyxl.Workbook()
    sheet = workbook.active
    sheet.title = "Stocktake Report"
    if rows:
        headers = list(rows[0].keys())
        sheet.append(headers)
        for row in rows:
            sheet.append([row.get(header) for header in headers])
    binary = io.BytesIO()
    workbook.save(binary)
    binary.seek(0)
    return StreamingResponse(
        binary,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f'attachment; filename="stocktake-{stocktake_session.id}.xlsx"'},
    )