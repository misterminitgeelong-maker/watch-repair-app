"""VSWT Regional Intelligence.

Ingests Mister Minit HQ's weekly "VSWT-WSS" regional Excel export (one row per shop, covering
every shop in the VSWT region) into a shared table, then serves each logged-in shop its own
rank against the rest of the region — and against a "peer group" of comparable franchise stores —
across every KPI HQ tracks.

Not tenant-scoped like most Mainspring tables: this is shared regional reference data. A shop's
own row is found via `Tenant.shop_number` (already used elsewhere for Minit shop identity), so
there is no picker — whatever shop is logged in sees its own numbers automatically. Endpoints
return `{"available": False, ...}` rather than 404 when the logged-in tenant has no shop_number,
or when that shop_number isn't present in the region's data yet — the frontend uses this to decide
whether to show the section at all, the same way the Reports page already hides the shoe-repair
section when there's nothing to show.

See app/vswt_kpis.py for the column layout / KPI list this parser and these rankings are built
from — keep field names in sync with that module rather than re-deriving them here.
"""
from __future__ import annotations

import io
import csv
import statistics
from datetime import date, datetime, timezone
from typing import Any, Literal, Optional
from uuid import UUID

import openpyxl
from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile
from fastapi.concurrency import run_in_threadpool
from fastapi.responses import Response
from sqlmodel import Session, delete as sa_delete, select

from ..database import get_session
from ..dependencies import AuthContext, get_auth_context, require_manager_or_above
from ..models import (
    Tenant,
    UserNotificationPreference,
    VswtReportTarget,
    VswtWeekAnnotation,
    VswtWeeklyShopMetric,
)
from ..pdf_vswt_report import build_weekly_report_pdf
from ..vswt_kpis import (
    CATEGORY_SALES_KEYS,
    COLUMN_MAP,
    KPI_BY_KEY,
    KPI_DEFS,
    KPI_GROUPS,
    KpiDef,
    PEER_COMP_STATUS,
    PEER_FORMAT,
    clean_cell,
)
from sqlmodel import SQLModel

router = APIRouter(prefix="/v1/reports/vswt", tags=["vswt"])

_DATA_START_ROW = 6  # 1-based Excel row; shop rows start here
_WEEK_NUMBER_ROW = 3  # 1-based Excel row: "Week Number:" label in col A, value in col C
_WEEK_NUMBER_COL = 3  # column C


# ── Parsing (Summary sheet -> list[dict]) ───────────────────────────────────────────────────

def _parse_vswt_workbook(raw_bytes: bytes, filename: str) -> dict[str, Any]:
    # read_only=True makes openpyxl stream the sheet instead of building its full in-memory
    # object model (styles, formatting, merged cells, etc.) — we only ever read cell values via
    # iter_rows(), so this is a large speed/memory win on real HQ export files, which carry much
    # more formatting than the column data we actually use. Without it, a handful of files
    # uploaded together was slow enough (CPU-bound, single-worker deployment) to trip the
    # platform's health check and get the request killed mid-response.
    try:
        wb = openpyxl.load_workbook(io.BytesIO(raw_bytes), data_only=True, read_only=True)
    except Exception as exc:
        raise HTTPException(
            status_code=400, detail=f"Could not read '{filename}' as an Excel file: {exc}"
        ) from exc

    try:
        sheet = None
        for name in wb.sheetnames:
            if name.strip().lower() == "summary":
                sheet = wb[name]
                break
        if sheet is None:
            sheet = wb.active
        grid = list(sheet.iter_rows(values_only=True))
    finally:
        wb.close()

    internal_week_raw = None
    if len(grid) >= _WEEK_NUMBER_ROW:
        row = grid[_WEEK_NUMBER_ROW - 1]
        if row and len(row) >= _WEEK_NUMBER_COL:
            internal_week_raw = clean_cell(row[_WEEK_NUMBER_COL - 1])
    internal_week: Optional[int] = None
    if isinstance(internal_week_raw, (int, float)):
        internal_week = int(internal_week_raw)

    rows: list[dict[str, Any]] = []
    for r in grid[_DATA_START_ROW - 1:]:
        if not r or len(r) < 2:
            continue
        shop_number = clean_cell(r[1])  # column B
        if shop_number in (None, ""):
            continue
        row: dict[str, Any] = {}
        for field, col in COLUMN_MAP:
            value = clean_cell(r[col - 1]) if len(r) >= col else None
            row[field] = value
        sn = row.get("shop_number")
        if isinstance(sn, float) and sn.is_integer():
            row["shop_number"] = str(int(sn))
        elif sn is not None:
            row["shop_number"] = str(sn).strip()
        rows.append(row)

    return {
        "filename": filename,
        "internal_week": internal_week,
        "rows": rows,
        "shop_count": len(rows),
    }


# ── Ranking helpers (ported from the reference app's rankOf/average/peerRows) ──────────────

def _rank_of(week_rows: list[VswtWeeklyShopMetric], key: str, value: Optional[float]) -> Optional[int]:
    if value is None:
        return None
    higher = sum(1 for r in week_rows if getattr(r, key) is not None and getattr(r, key) > value)
    return higher + 1


def _average(values: list[Optional[float]]) -> Optional[float]:
    vals = [v for v in values if v is not None]
    if not vals:
        return None
    return sum(vals) / len(vals)


def _peer_rows(week_rows: list[VswtWeeklyShopMetric]) -> list[VswtWeeklyShopMetric]:
    return [r for r in week_rows if r.store_format == PEER_FORMAT and r.comp_status == PEER_COMP_STATUS]


def _find_shop(week_rows: list[VswtWeeklyShopMetric], shop_number: str) -> Optional[VswtWeeklyShopMetric]:
    return next((r for r in week_rows if r.shop_number == shop_number), None)


def _ranks_for_week(week_rows: list[VswtWeeklyShopMetric], key: str) -> dict[str, int]:
    """Rank of every shop with a non-null `key` value for one week, all at once — O(n log n)
    instead of calling `_rank_of` once per shop (which is itself O(n), so O(n^2) over a whole
    week). Same "1 + count of strictly-greater values" tie semantics as `_rank_of`; used where we
    need every shop's rank for a week, not just one shop's (e.g. consistency leaderboards)."""
    present = sorted(
        ((r.shop_number, getattr(r, key)) for r in week_rows if getattr(r, key) is not None),
        key=lambda pair: pair[1],
        reverse=True,
    )
    ranks: dict[str, int] = {}
    for i, (shop_number, value) in enumerate(present):
        prev_shop, prev_value = present[i - 1] if i > 0 else (None, None)
        ranks[shop_number] = ranks[prev_shop] if value == prev_value else i + 1
    return ranks


def _rank_in_averages(averages: dict[str, float], shop_number: str) -> Optional[int]:
    """Same ranking rule as `_rank_of`, but over a plain {shop_number: average_value} dict rather
    than ORM rows — for ranking a shop's Month/Year average against the rest of the region's."""
    value = averages.get(shop_number)
    if value is None:
        return None
    higher = sum(1 for v in averages.values() if v > value)
    return higher + 1


def _all_weeks(session: Session) -> list[int]:
    return list(
        session.exec(
            select(VswtWeeklyShopMetric.week_seq).distinct().order_by(VswtWeeklyShopMetric.week_seq)
        ).all()
    )


def _week_rows(session: Session, week: int) -> list[VswtWeeklyShopMetric]:
    return list(
        session.exec(select(VswtWeeklyShopMetric).where(VswtWeeklyShopMetric.week_seq == week)).all()
    )


def _shop_history(session: Session, shop_number: str, weeks: list[int]) -> dict[int, VswtWeeklyShopMetric]:
    """One shop's rows for the given weeks, in a single query.

    The cockpit needs the whole network only for the selected and previous
    weeks (ranks, averages); every other week it only needs the one shop, so
    loading all shops for all weeks was ~400x more rows than it used.
    """
    if not weeks:
        return {}
    rows = session.exec(
        select(VswtWeeklyShopMetric)
        .where(VswtWeeklyShopMetric.shop_number == shop_number)
        .where(VswtWeeklyShopMetric.week_seq.in_(weeks))  # type: ignore[attr-defined]
    ).all()
    return {r.week_seq: r for r in rows}


def _shop_number_for(auth: AuthContext, session: Session) -> Optional[str]:
    tenant = session.get(Tenant, auth.tenant_id)
    if not tenant or not tenant.shop_number:
        return None
    return tenant.shop_number


def _pct_delta(current: Optional[float], baseline: Optional[float]) -> Optional[float]:
    if current is None or baseline in (None, 0):
        return None
    return (current - baseline) / abs(baseline)


def _target_value_map(session: Session, tenant_id: UUID, shop_number: str) -> dict[str, float]:
    rows = session.exec(
        select(VswtReportTarget)
        .where(VswtReportTarget.tenant_id == tenant_id)
        .where(VswtReportTarget.shop_number == shop_number)
    ).all()
    return {row.metric_key: row.target_value for row in rows}


def _annotation_rows(session: Session, tenant_id: UUID, shop_number: str) -> list[VswtWeekAnnotation]:
    return list(
        session.exec(
            select(VswtWeekAnnotation)
            .where(VswtWeekAnnotation.tenant_id == tenant_id)
            .where(VswtWeekAnnotation.shop_number == shop_number)
            .order_by(VswtWeekAnnotation.week_seq.desc())
        ).all()
    )


def _annotation_dict(row: VswtWeekAnnotation) -> dict[str, Any]:
    return {
        "id": str(row.id),
        "week": row.week_seq,
        "event_type": row.event_type,
        "note": row.note,
        "created_at": row.created_at,
        "updated_at": row.updated_at,
    }


_LAST_YEAR_KEYS = {
    "sales_ty": "sales_ly",
    "customer_ty": "customer_ly",
    "jobs_ty": "jobs_ly",
}


def _derived_value(row: Optional[VswtWeeklyShopMetric], key: str) -> Optional[float]:
    if row is None:
        return None
    if key == "avg_sale":
        return row.sales_ty / row.customer_ty if row.sales_ty is not None and row.customer_ty else None
    if key == "jobs_per_customer":
        return row.jobs_ty / row.customer_ty if row.jobs_ty is not None and row.customer_ty else None
    return getattr(row, key, None)


def _build_cockpit_data(
    session: Session,
    *,
    auth: AuthContext,
    target_shop_number: str,
    selected_week: Optional[int] = None,
    comparison: str = "previous",
) -> dict[str, Any]:
    all_weeks = _all_weeks(session)
    if not all_weeks:
        return {"available": False, "reason": "no_data"}
    week = selected_week if selected_week in all_weeks else all_weeks[-1]
    week_index = all_weeks.index(week)
    visible_weeks = all_weeks[: week_index + 1]
    current_rows = _week_rows(session, week)
    current = _find_shop(current_rows, target_shop_number)
    if current is None:
        return {"available": False, "reason": "shop_not_found"}

    previous_week = visible_weeks[-2] if len(visible_weeks) > 1 else None
    previous_rows = _week_rows(session, previous_week) if previous_week is not None else []
    previous = _find_shop(previous_rows, target_shop_number) if previous_week is not None else None
    # Rolling baselines look back at most 52 weeks; the sales-decline check at 4.
    history = _shop_history(session, target_shop_number, visible_weeks[-53:])
    peers = _peer_rows(current_rows)
    targets = _target_value_map(session, auth.tenant_id, target_shop_number)
    own_shop = _shop_number_for(auth, session)

    metric_defs: list[dict[str, str]] = [
        {"key": k.key, "label": k.label, "group": k.group, "type": k.type}
        for k in KPI_DEFS
    ] + [
        {"key": "avg_sale", "label": "Average sale", "group": "Headline", "type": "currency"},
        {"key": "jobs_per_customer", "label": "Jobs per customer", "group": "Conversion", "type": "ratio"},
    ]

    rows: list[dict[str, Any]] = []
    for definition in metric_defs:
        key = definition["key"]
        current_value = _derived_value(current, key)
        previous_value = _derived_value(previous, key)

        rolling: dict[int, Optional[float]] = {}
        rolling_counts: dict[int, int] = {}
        # Rolling baselines exclude the selected week, so they answer whether the current result
        # improved on the established run-rate rather than blending the current result into it.
        prior_weeks = visible_weeks[:-1]
        for window in (4, 13, 52):
            values = [_derived_value(history.get(w), key) for w in prior_weeks[-window:]]
            present = [v for v in values if v is not None]
            rolling[window] = _average(present)
            rolling_counts[window] = len(present)

        ly_key = _LAST_YEAR_KEYS.get(key)
        last_year = getattr(current, ly_key) if ly_key else None
        comparison_value = {
            "previous": previous_value,
            "4w": rolling[4],
            "13w": rolling[13],
            "52w": rolling[52],
            "last_year": last_year,
        }.get(comparison, previous_value)
        rank = _rank_of(current_rows, key, current_value) if key in KPI_BY_KEY else None
        previous_rank = (
            _rank_of(previous_rows, key, previous_value)
            if previous_rows and key in KPI_BY_KEY
            else None
        )
        region_values = [_derived_value(r, key) for r in current_rows]
        peer_values = [_derived_value(r, key) for r in peers]
        rows.append(
            {
                **definition,
                "current": current_value,
                "previous": previous_value,
                "rolling_4": rolling[4],
                "rolling_13": rolling[13],
                "rolling_52": rolling[52],
                "rolling_counts": {str(k): v for k, v in rolling_counts.items()},
                "last_year": last_year,
                "comparison": comparison_value,
                "delta": current_value - comparison_value if current_value is not None and comparison_value is not None else None,
                "delta_pct": _pct_delta(current_value, comparison_value),
                "region_avg": _average(region_values),
                "peer_avg": _average(peer_values),
                "rank": rank,
                "previous_rank": previous_rank,
                "rank_change": previous_rank - rank if rank is not None and previous_rank is not None else None,
                "target": targets.get(key),
                "target_variance": current_value - targets[key] if current_value is not None and key in targets else None,
            }
        )

    category_drivers = []
    for key, label in CATEGORY_SALES_KEYS:
        current_value = _derived_value(current, key)
        previous_value = _derived_value(previous, key)
        category_drivers.append(
            {
                "key": key,
                "label": label,
                "current": current_value,
                "previous": previous_value,
                "delta": current_value - previous_value if current_value is not None and previous_value is not None else None,
                "share_of_sales": current_value / current.sales_ty if current_value is not None and current.sales_ty else None,
            }
        )
    category_drivers.sort(key=lambda row: abs(row["delta"] or 0), reverse=True)

    current_avg_sale = _derived_value(current, "avg_sale")
    previous_avg_sale = _derived_value(previous, "avg_sale")
    volume_effect = (
        (current.customer_ty - previous.customer_ty) * previous_avg_sale
        if current.customer_ty is not None and previous and previous.customer_ty is not None and previous_avg_sale is not None
        else None
    )
    value_effect = (
        (current_avg_sale - previous_avg_sale) * current.customer_ty
        if current_avg_sale is not None and previous_avg_sale is not None and current.customer_ty is not None
        else None
    )

    by_key = {row["key"]: row for row in rows}
    alerts: list[dict[str, str]] = []
    sales = by_key["sales_ty"]
    if sales["delta_pct"] is not None and sales["delta_pct"] <= -0.10:
        alerts.append({"severity": "critical", "title": "Sales below comparison", "message": f"Sales are {abs(sales['delta_pct']) * 100:.1f}% below the selected baseline."})
    elif sales["delta_pct"] is not None and sales["delta_pct"] < 0:
        alerts.append({"severity": "warning", "title": "Sales softened", "message": f"Sales are {abs(sales['delta_pct']) * 100:.1f}% below the selected baseline."})
    if sales["rank_change"] is not None and sales["rank_change"] <= -10:
        alerts.append({"severity": "warning", "title": "Regional rank fell", "message": f"Sales rank dropped {abs(sales['rank_change'])} places from the previous week."})
    if sales["target_variance"] is not None and sales["target_variance"] < 0:
        alerts.append({"severity": "warning", "title": "Sales target at risk", "message": f"The shop is ${abs(sales['target_variance']):,.0f} below its weekly sales target."})

    sales_history = [_derived_value(history.get(w), "sales_ty") for w in visible_weeks[-4:]]
    present_sales = [v for v in sales_history if v is not None]
    if len(present_sales) >= 3 and all(present_sales[i] < present_sales[i - 1] for i in range(1, len(present_sales))):
        alerts.append({"severity": "critical", "title": "Three-week sales decline", "message": "Sales have fallen in each of the last three reported weeks."})
    weakest_category = min((d for d in category_drivers if d["delta"] is not None), key=lambda d: d["delta"], default=None)
    strongest_category = max((d for d in category_drivers if d["delta"] is not None), key=lambda d: d["delta"], default=None)
    if weakest_category and weakest_category["delta"] < 0:
        alerts.append({"severity": "info", "title": f"{weakest_category['label']} is the largest drag", "message": f"Category sales fell ${abs(weakest_category['delta']):,.0f} from the previous week."})
    if strongest_category and strongest_category["delta"] > 0:
        alerts.append({"severity": "positive", "title": f"{strongest_category['label']} led growth", "message": f"Category sales increased ${strongest_category['delta']:,.0f} from the previous week."})
    if not alerts:
        alerts.append({"severity": "positive", "title": "No material exceptions", "message": "No major negative movements were detected for the selected comparison."})

    annotations = (
        [_annotation_dict(row) for row in _annotation_rows(session, auth.tenant_id, target_shop_number)]
        if target_shop_number == own_shop
        else []
    )
    latest_pref = session.exec(
        select(UserNotificationPreference)
        .where(UserNotificationPreference.tenant_id == auth.tenant_id)
        .where(UserNotificationPreference.user_id == auth.user_id)
    ).first()

    return {
        "available": True,
        "shop_number": target_shop_number,
        "shop_name": current.shop_name,
        "area_name": current.area_name,
        "viewing_own_shop": target_shop_number == own_shop,
        "week": week,
        "previous_week": previous_week,
        "weeks": all_weeks,
        "comparison": comparison,
        "region_size": len(current_rows),
        "peer_size": len(peers),
        "source": {
            "filename": current.source_filename,
            "uploaded_at": current.uploaded_at,
            "shops_in_upload": len(current_rows),
        },
        "rows": rows,
        "drivers": {
            "category_sales": category_drivers,
            "sales_bridge": {
                "total_change": current.sales_ty - previous.sales_ty if current.sales_ty is not None and previous and previous.sales_ty is not None else None,
                "customer_volume_effect": volume_effect,
                "average_sale_effect": value_effect,
            },
        },
        "alerts": alerts,
        "annotations": annotations,
        "targets": targets,
        "email_weekly_report": bool(latest_pref and latest_pref.email_weekly_regional_report),
        "last_weekly_report_sent_at": latest_pref.last_weekly_regional_report_sent_at if latest_pref else None,
    }


# ── Upload / commit ──────────────────────────────────────────────────────────────────────

@router.post("/upload")
async def upload_vswt_files(
    files: list[UploadFile] = File(...),
    auth: AuthContext = Depends(require_manager_or_above),
    session: Session = Depends(get_session),
):
    if not files:
        raise HTTPException(status_code=400, detail="No files provided.")

    parsed: list[dict[str, Any]] = []
    failed: list[str] = []
    for f in files:
        if not f.filename:
            continue
        raw = await f.read()
        try:
            result = await run_in_threadpool(_parse_vswt_workbook, raw, f.filename)
        except HTTPException:
            failed.append(f.filename)
            continue
        if not result["rows"]:
            failed.append(f.filename)
            continue
        parsed.append(result)

    if not parsed:
        raise HTTPException(
            status_code=400,
            detail=(
                "Couldn't read any shop rows from the selected file(s) — make sure they're "
                "VSWT-WSS files with a Summary tab."
            ),
        )

    existing_weeks = set(_all_weeks(session))
    used = set(existing_weeks)
    # Assign week numbers: prefer each file's own detected week if free, else next free number.
    parsed.sort(key=lambda p: (p["internal_week"] is None, p["internal_week"]))
    next_free = (max(used) + 1) if used else 1
    batch = []
    for p in parsed:
        week_number = p["internal_week"]
        if week_number is None or week_number in used:
            while next_free in used:
                next_free += 1
            week_number = next_free
        used.add(week_number)
        next_free = max(next_free, week_number + 1)
        batch.append(
            {
                "filename": p["filename"],
                "internal_week": p["internal_week"],
                "week_number": week_number,
                "shop_count": p["shop_count"],
                "overwrite": week_number in existing_weeks,
                "rows": p["rows"],
            }
        )

    # Auto-assignment always steers clear of collisions (see loop above), so a per-file
    # "overwrite" flag is only ever true here in the degenerate case where two source files
    # detected the exact same week and neither could be bumped — the live case that actually
    # matters is the user *editing* the week number in the confirm step back onto an existing
    # week, which the frontend detects itself by checking the edited number against this list.
    return {"failed_files": failed, "batch": batch, "existing_weeks": sorted(existing_weeks)}


class VswtCommitFile(SQLModel):
    filename: str
    week_number: int
    rows: list[dict[str, Any]]


class VswtCommitRequest(SQLModel):
    batch: list[VswtCommitFile]


@router.post("/commit")
def commit_vswt_batch(
    payload: VswtCommitRequest,
    auth: AuthContext = Depends(require_manager_or_above),
    session: Session = Depends(get_session),
):
    if not payload.batch:
        raise HTTPException(status_code=400, detail="Nothing to commit.")
    week_numbers = [item.week_number for item in payload.batch]
    if len(set(week_numbers)) != len(week_numbers):
        raise HTTPException(status_code=400, detail="Duplicate week numbers in this batch.")

    metric_fields = [name for name, _ in COLUMN_MAP]
    now = datetime.now(timezone.utc)
    saved = []
    for item in payload.batch:
        session.exec(
            sa_delete(VswtWeeklyShopMetric).where(VswtWeeklyShopMetric.week_seq == item.week_number)
        )
        count = 0
        for row in item.rows:
            if not row.get("shop_number"):
                continue
            fields = {name: row.get(name) for name in metric_fields}
            session.add(
                VswtWeeklyShopMetric(
                    week_seq=item.week_number,
                    source_filename=item.filename,
                    uploaded_by_tenant_id=auth.tenant_id,
                    uploaded_by_user_id=auth.user_id,
                    uploaded_at=now,
                    **fields,
                )
            )
            count += 1
        saved.append({"week_number": item.week_number, "shop_count": count})
    session.commit()
    return {"saved": saved}


@router.get("/weeks")
def get_vswt_weeks(
    auth: AuthContext = Depends(require_manager_or_above),
    session: Session = Depends(get_session),
):
    weeks = _all_weeks(session)
    out = []
    for w in weeks:
        rows = _week_rows(session, w)
        source_filenames = sorted({r.source_filename for r in rows if r.source_filename})
        uploaded_at = max((r.uploaded_at for r in rows), default=None)
        out.append(
            {
                "week": w,
                "shop_count": len(rows),
                "source_filenames": source_filenames,
                "uploaded_at": uploaded_at,
            }
        )
    return {"weeks": out}


@router.get("/export")
def export_vswt_csv(
    week: Optional[int] = Query(None, description="Export one week; omit to export every uploaded week."),
    shop_number: Optional[str] = Query(None, description="Limit export to one shop."),
    auth: AuthContext = Depends(get_auth_context),
    session: Session = Depends(get_session),
):
    """Export the regional KPI history for analysis outside the app."""
    if _shop_number_for(auth, session) is None:
        raise HTTPException(status_code=403, detail="A linked Minit shop is required for regional exports.")
    weeks = _all_weeks(session)
    if week is not None:
        weeks = [w for w in weeks if w == week]
    if not weeks:
        raise HTTPException(status_code=404, detail="No regional data is available for export.")

    output = io.StringIO()
    fieldnames = ["week", "shop_number", "shop_name", "area_name", "store_format", "comp_status"] + [k.key for k in KPI_DEFS]
    writer = csv.DictWriter(output, fieldnames=fieldnames)
    writer.writeheader()
    for current_week in weeks:
        for row in _week_rows(session, current_week):
            if shop_number and row.shop_number != shop_number:
                continue
            record = {"week": current_week, "shop_number": row.shop_number, "shop_name": row.shop_name,
                      "area_name": row.area_name, "store_format": row.store_format, "comp_status": row.comp_status}
            record.update({k.key: getattr(row, k.key) for k in KPI_DEFS})
            writer.writerow(record)
    return Response(
        content=output.getvalue(),
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=regional-report.csv"},
    )


@router.delete("/weeks/{week_seq}")
def delete_vswt_week(
    week_seq: int,
    auth: AuthContext = Depends(require_manager_or_above),
    session: Session = Depends(get_session),
):
    session.exec(sa_delete(VswtWeeklyShopMetric).where(VswtWeeklyShopMetric.week_seq == week_seq))
    session.commit()
    return {"deleted_week": week_seq}


# ── Read endpoints ───────────────────────────────────────────────────────────────────────

@router.get("/summary")
def get_vswt_summary(
    auth: AuthContext = Depends(get_auth_context),
    session: Session = Depends(get_session),
):
    shop_number = _shop_number_for(auth, session)
    if shop_number is None:
        return {"available": False, "reason": "no_shop_number"}

    weeks = _all_weeks(session)
    if not weeks:
        return {"available": False, "reason": "no_data"}

    latest = weeks[-1]
    prev = weeks[-2] if len(weeks) > 1 else None
    latest_rows = _week_rows(session, latest)
    my_row = _find_shop(latest_rows, shop_number)
    if my_row is None:
        return {"available": False, "reason": "shop_not_found", "latest_week": latest}

    prev_row = _find_shop(_week_rows(session, prev), shop_number) if prev is not None else None
    prev_rows = _week_rows(session, prev) if prev is not None else []
    peers = _peer_rows(latest_rows)
    area_rows = [r for r in latest_rows if my_row.area_name and r.area_name == my_row.area_name]

    return {
        "available": True,
        "shop_number": shop_number,
        "shop_name": my_row.shop_name,
        "area_name": my_row.area_name,
        "latest_week": latest,
        "weeks_tracked": len(weeks),
        "region_size": len(latest_rows),
        "peer_size": len(peers),
        "area_size": len(area_rows),
        "sales": {
            "value": my_row.sales_ty,
            "prev_value": prev_row.sales_ty if prev_row else None,
            "region_rank": _rank_of(latest_rows, "sales_ty", my_row.sales_ty),
            "prev_region_rank": _rank_of(prev_rows, "sales_ty", prev_row.sales_ty) if prev_row else None,
            "peer_rank": _rank_of(peers, "sales_ty", my_row.sales_ty),
            "area_rank": _rank_of(area_rows, "sales_ty", my_row.sales_ty) if area_rows else None,
        },
        "customers": {
            "value": my_row.customer_ty,
            "prev_value": prev_row.customer_ty if prev_row else None,
            "region_rank": _rank_of(latest_rows, "customer_ty", my_row.customer_ty),
            "prev_region_rank": _rank_of(prev_rows, "customer_ty", prev_row.customer_ty) if prev_row else None,
        },
        "jobs": {
            "value": my_row.jobs_ty,
            "prev_value": prev_row.jobs_ty if prev_row else None,
            "region_rank": _rank_of(latest_rows, "jobs_ty", my_row.jobs_ty),
            "prev_region_rank": _rank_of(prev_rows, "jobs_ty", prev_row.jobs_ty) if prev_row else None,
        },
    }


@router.get("/cockpit")
def get_vswt_cockpit(
    week: Optional[int] = Query(None),
    comparison: Literal["previous", "4w", "13w", "52w", "last_year"] = Query("previous"),
    shop_number: Optional[str] = Query(None),
    auth: AuthContext = Depends(get_auth_context),
    session: Session = Depends(get_session),
):
    """A single comparison contract used by the management cockpit.

    It deliberately returns every KPI with the same current/baseline/rolling/rank shape so the
    UI cannot drift into using different period definitions in different sections.
    """
    own_shop_number = _shop_number_for(auth, session)
    if own_shop_number is None:
        return {"available": False, "reason": "no_shop_number"}
    return _build_cockpit_data(
        session,
        auth=auth,
        target_shop_number=shop_number or own_shop_number,
        selected_week=week,
        comparison=comparison,
    )


class VswtTargetsUpdate(SQLModel):
    targets: dict[str, Optional[float]]


@router.get("/targets")
def get_vswt_targets(
    auth: AuthContext = Depends(get_auth_context),
    session: Session = Depends(get_session),
):
    shop_number = _shop_number_for(auth, session)
    if shop_number is None:
        return {"available": False, "reason": "no_shop_number"}
    return {"available": True, "shop_number": shop_number, "targets": _target_value_map(session, auth.tenant_id, shop_number)}


@router.put("/targets")
def put_vswt_targets(
    payload: VswtTargetsUpdate,
    auth: AuthContext = Depends(require_manager_or_above),
    session: Session = Depends(get_session),
):
    shop_number = _shop_number_for(auth, session)
    if shop_number is None:
        raise HTTPException(status_code=400, detail="A linked Minit shop is required.")
    allowed_keys = set(KPI_BY_KEY) | {"avg_sale", "jobs_per_customer"}
    invalid = [key for key in payload.targets if key not in allowed_keys]
    if invalid:
        raise HTTPException(status_code=400, detail=f"Unknown target metric: {invalid[0]}")
    now = datetime.now(timezone.utc)
    for metric_key, target_value in payload.targets.items():
        existing = session.exec(
            select(VswtReportTarget)
            .where(VswtReportTarget.tenant_id == auth.tenant_id)
            .where(VswtReportTarget.shop_number == shop_number)
            .where(VswtReportTarget.metric_key == metric_key)
        ).first()
        if target_value is None:
            if existing:
                session.delete(existing)
            continue
        if target_value < 0:
            raise HTTPException(status_code=400, detail="Targets cannot be negative.")
        if existing:
            existing.target_value = target_value
            existing.updated_at = now
            session.add(existing)
        else:
            session.add(
                VswtReportTarget(
                    tenant_id=auth.tenant_id,
                    shop_number=shop_number,
                    metric_key=metric_key,
                    target_value=target_value,
                    created_by_user_id=auth.user_id,
                    created_at=now,
                    updated_at=now,
                )
            )
    session.commit()
    return {"available": True, "shop_number": shop_number, "targets": _target_value_map(session, auth.tenant_id, shop_number)}


class VswtAnnotationUpdate(SQLModel):
    week: int
    event_type: str = "other"
    note: str


@router.get("/annotations")
def get_vswt_annotations(
    auth: AuthContext = Depends(get_auth_context),
    session: Session = Depends(get_session),
):
    shop_number = _shop_number_for(auth, session)
    if shop_number is None:
        return {"available": False, "reason": "no_shop_number"}
    return {
        "available": True,
        "shop_number": shop_number,
        "annotations": [_annotation_dict(row) for row in _annotation_rows(session, auth.tenant_id, shop_number)],
    }


@router.put("/annotations")
def put_vswt_annotation(
    payload: VswtAnnotationUpdate,
    auth: AuthContext = Depends(require_manager_or_above),
    session: Session = Depends(get_session),
):
    shop_number = _shop_number_for(auth, session)
    if shop_number is None:
        raise HTTPException(status_code=400, detail="A linked Minit shop is required.")
    if payload.week not in _all_weeks(session):
        raise HTTPException(status_code=400, detail="That reporting week is not available.")
    note = payload.note.strip()
    if not note or len(note) > 500:
        raise HTTPException(status_code=400, detail="Week note must be between 1 and 500 characters.")
    event_type = payload.event_type.strip().lower().replace(" ", "_")[:32] or "other"
    now = datetime.now(timezone.utc)
    row = session.exec(
        select(VswtWeekAnnotation)
        .where(VswtWeekAnnotation.tenant_id == auth.tenant_id)
        .where(VswtWeekAnnotation.shop_number == shop_number)
        .where(VswtWeekAnnotation.week_seq == payload.week)
    ).first()
    if row:
        row.note = note
        row.event_type = event_type
        row.updated_at = now
    else:
        row = VswtWeekAnnotation(
            tenant_id=auth.tenant_id,
            shop_number=shop_number,
            week_seq=payload.week,
            event_type=event_type,
            note=note,
            created_by_user_id=auth.user_id,
            created_at=now,
            updated_at=now,
        )
    session.add(row)
    session.commit()
    session.refresh(row)
    return _annotation_dict(row)


@router.delete("/annotations/{annotation_id}")
def delete_vswt_annotation(
    annotation_id: UUID,
    auth: AuthContext = Depends(require_manager_or_above),
    session: Session = Depends(get_session),
):
    row = session.get(VswtWeekAnnotation, annotation_id)
    if not row or row.tenant_id != auth.tenant_id:
        raise HTTPException(status_code=404, detail="Week note not found.")
    session.delete(row)
    session.commit()
    return {"deleted": str(annotation_id)}


class VswtEmailPreferenceUpdate(SQLModel):
    enabled: bool


def _get_or_create_notification_pref(session: Session, auth: AuthContext) -> UserNotificationPreference:
    row = session.exec(
        select(UserNotificationPreference)
        .where(UserNotificationPreference.tenant_id == auth.tenant_id)
        .where(UserNotificationPreference.user_id == auth.user_id)
    ).first()
    if row:
        return row
    row = UserNotificationPreference(tenant_id=auth.tenant_id, user_id=auth.user_id)
    session.add(row)
    session.flush()
    return row


@router.get("/email-preference")
def get_vswt_email_preference(
    auth: AuthContext = Depends(get_auth_context),
    session: Session = Depends(get_session),
):
    pref = _get_or_create_notification_pref(session, auth)
    session.commit()
    return {
        "enabled": pref.email_weekly_regional_report,
        "last_sent_at": pref.last_weekly_regional_report_sent_at,
    }


@router.put("/email-preference")
def put_vswt_email_preference(
    payload: VswtEmailPreferenceUpdate,
    auth: AuthContext = Depends(get_auth_context),
    session: Session = Depends(get_session),
):
    if _shop_number_for(auth, session) is None:
        raise HTTPException(status_code=400, detail="A linked Minit shop is required.")
    pref = _get_or_create_notification_pref(session, auth)
    pref.email_weekly_regional_report = payload.enabled
    pref.updated_at = datetime.now(timezone.utc)
    session.add(pref)
    session.commit()
    session.refresh(pref)
    return {"enabled": pref.email_weekly_regional_report, "last_sent_at": pref.last_weekly_regional_report_sent_at}


@router.post("/email-preference/send-now")
def send_vswt_email_now(
    auth: AuthContext = Depends(get_auth_context),
    session: Session = Depends(get_session),
):
    from ..services.regional_report_email import send_regional_report_for_user

    sent = send_regional_report_for_user(session, tenant_id=auth.tenant_id, user_id=auth.user_id)
    return {"sent": sent}


@router.get("/scorecard")
def get_vswt_scorecard(
    shop_number: Optional[str] = Query(
        None, description="View another Minit shop's scorecard instead of your own (you must be a Minit shop yourself)."
    ),
    auth: AuthContext = Depends(get_auth_context),
    session: Session = Depends(get_session),
):
    my_shop_number = _shop_number_for(auth, session)
    if my_shop_number is None:
        return {"available": False, "reason": "no_shop_number"}
    target_shop_number = shop_number or my_shop_number
    weeks = _all_weeks(session)
    if not weeks:
        return {"available": False, "reason": "no_data"}

    matrix = []
    found_any = False
    target_name = None
    target_area = None
    for w in weeks:
        week_rows = _week_rows(session, w)
        target_row = _find_shop(week_rows, target_shop_number)
        if target_row is not None:
            found_any = True
            target_name = target_row.shop_name
            target_area = target_row.area_name
        cells = {}
        for kpi in KPI_DEFS:
            value = getattr(target_row, kpi.key) if target_row else None
            cells[kpi.key] = {"value": value, "rank": _rank_of(week_rows, kpi.key, value)}
        matrix.append({"week": w, "region_size": len(week_rows), "cells": cells})

    if not found_any:
        return {"available": False, "reason": "shop_not_found"}

    return {
        "available": True,
        "shop_number": target_shop_number,
        "shop_name": target_name,
        "area_name": target_area,
        "viewing_own_shop": target_shop_number == my_shop_number,
        "weeks": weeks,
        "groups": KPI_GROUPS,
        "kpis": [{"key": k.key, "label": k.label, "group": k.group, "type": k.type} for k in KPI_DEFS],
        "matrix": matrix,
    }


@router.get("/rankings")
def get_vswt_rankings(
    week: Optional[int] = Query(None),
    shop_number: Optional[str] = Query(
        None, description="View another Minit shop's rankings instead of your own (you must be a Minit shop yourself)."
    ),
    auth: AuthContext = Depends(get_auth_context),
    session: Session = Depends(get_session),
):
    my_shop_number = _shop_number_for(auth, session)
    if my_shop_number is None:
        return {"available": False, "reason": "no_shop_number"}
    target_shop_number = shop_number or my_shop_number
    weeks = _all_weeks(session)
    if not weeks:
        return {"available": False, "reason": "no_data"}
    target_week = week if week in weeks else weeks[-1]

    week_rows = _week_rows(session, target_week)
    target_row = _find_shop(week_rows, target_shop_number)
    if target_row is None:
        return {"available": False, "reason": "shop_not_found", "week": target_week}

    peers = _peer_rows(week_rows)
    rows = []
    for kpi in KPI_DEFS:
        value = getattr(target_row, kpi.key)
        region_rank = _rank_of(week_rows, kpi.key, value)
        percentile = (
            (len(week_rows) - region_rank) / (len(week_rows) - 1)
            if region_rank is not None and len(week_rows) > 1
            else None
        )
        rows.append(
            {
                "key": kpi.key,
                "label": kpi.label,
                "group": kpi.group,
                "type": kpi.type,
                "value": value,
                "region_avg": _average([getattr(r, kpi.key) for r in week_rows]),
                "region_rank": region_rank,
                "percentile": percentile,
                "peer_avg": _average([getattr(r, kpi.key) for r in peers]),
                "peer_rank": _rank_of(peers, kpi.key, value),
            }
        )

    return {
        "available": True,
        "shop_number": target_shop_number,
        "shop_name": target_row.shop_name,
        "area_name": target_row.area_name,
        "viewing_own_shop": target_shop_number == my_shop_number,
        "week": target_week,
        "weeks": weeks,
        "region_size": len(week_rows),
        "peer_size": len(peers),
        "rows": rows,
    }


@router.get("/directory")
def get_vswt_directory(
    week: Optional[int] = Query(None),
    search: Optional[str] = Query(None, description="Filter by shop name, shop number, or area (case-insensitive)."),
    group: Optional[str] = Query(None, description="KPI group to include as columns; defaults to Headline."),
    peer_only: bool = Query(False, description="Only franchise + comparable stores."),
    auth: AuthContext = Depends(get_auth_context),
    session: Session = Depends(get_session),
):
    """Every shop in the region for one week, searchable — the entry point for browsing/looking
    up any other Minit shop's numbers, not just your own. Gated the same as the rest of this
    feature: you must be a Minit shop yourself to browse the network."""
    my_shop_number = _shop_number_for(auth, session)
    if my_shop_number is None:
        return {"available": False, "reason": "no_shop_number"}
    weeks = _all_weeks(session)
    if not weeks:
        return {"available": False, "reason": "no_data"}
    target_week = week if week in weeks else weeks[-1]

    week_rows = _week_rows(session, target_week)
    peer_numbers = {r.shop_number for r in _peer_rows(week_rows)}

    kpi_group = group if group in KPI_GROUPS else "Headline"
    kpis = [k for k in KPI_DEFS if k.group == kpi_group]

    rows = week_rows
    if peer_only:
        rows = [r for r in rows if r.shop_number in peer_numbers]
    if search and search.strip():
        q = search.strip().lower()
        rows = [
            r for r in rows
            if q in (r.shop_name or "").lower()
            or q in (r.shop_number or "").lower()
            or q in (r.area_name or "").lower()
        ]

    out_rows = [
        {
            "shop_number": r.shop_number,
            "shop_name": r.shop_name,
            "area_name": r.area_name,
            "store_format": r.store_format,
            "comp_status": r.comp_status,
            "is_peer": r.shop_number in peer_numbers,
            "is_me": r.shop_number == my_shop_number,
            "values": {k.key: getattr(r, k.key) for k in kpis},
        }
        for r in rows
    ]

    return {
        "available": True,
        "week": target_week,
        "weeks": weeks,
        "region_size": len(week_rows),
        "peer_size": len(peer_numbers),
        "result_size": len(out_rows),
        "group": kpi_group,
        "groups": KPI_GROUPS,
        "kpis": [{"key": k.key, "label": k.label, "group": k.group, "type": k.type} for k in kpis],
        "rows": out_rows,
    }


@router.get("/shop-report")
def get_vswt_shop_report(
    shop_number: Optional[str] = Query(
        None, description="View another Minit shop's report instead of your own (you must be a Minit shop yourself)."
    ),
    group: Optional[str] = Query(None, description="KPI group to include as rows; defaults to Headline."),
    auth: AuthContext = Depends(get_auth_context),
    session: Session = Depends(get_session),
):
    """One shop's Week / Month / Year numbers, each ranked against the rest of the region — the
    Directory's per-shop drill-down. "Month" is a rolling trailing-4-week average; "Year" averages
    every week on file (there's no calendar date on this data, only a sequence of weekly uploads,
    so "Year" grows into a real year as more weeks accumulate). Averaging over many weeks — rather
    than only ever showing the latest week — is what surfaces a shop that's consistently strong or
    weak, instead of one that just had a single standout or disastrous week.
    """
    my_shop_number = _shop_number_for(auth, session)
    if my_shop_number is None:
        return {"available": False, "reason": "no_shop_number"}
    target_shop_number = shop_number or my_shop_number
    weeks = _all_weeks(session)
    if not weeks:
        return {"available": False, "reason": "no_data"}

    rows_by_week = {w: _week_rows(session, w) for w in weeks}
    latest_week = weeks[-1]
    latest_rows = rows_by_week[latest_week]
    target_latest = _find_shop(latest_rows, target_shop_number)
    if target_latest is None:
        return {"available": False, "reason": "shop_not_found"}

    month_weeks = set(weeks[-4:])
    kpi_group = group if group in KPI_GROUPS else "Headline"
    kpis = [k for k in KPI_DEFS if k.group == kpi_group]

    # Single pass over every week: accumulate each shop's raw values for the Month window and for
    # all-time ("Year"), and record the target shop's own rank each week it appears (used below
    # for the Year consistency stats — best/worst rank and how much it's varied).
    month_raw: dict[str, dict[str, list[float]]] = {}  # shop_number -> kpi.key -> values
    year_raw: dict[str, dict[str, list[float]]] = {}
    target_week_ranks: dict[str, list[int]] = {k.key: [] for k in kpis}
    for w in weeks:
        week_rows = rows_by_week[w]
        target_row = _find_shop(week_rows, target_shop_number)
        if target_row is not None:
            for kpi in kpis:
                rank = _rank_of(week_rows, kpi.key, getattr(target_row, kpi.key))
                if rank is not None:
                    target_week_ranks[kpi.key].append(rank)
        in_month = w in month_weeks
        for r in week_rows:
            for kpi in kpis:
                v = getattr(r, kpi.key)
                if v is None:
                    continue
                year_raw.setdefault(r.shop_number, {}).setdefault(kpi.key, []).append(v)
                if in_month:
                    month_raw.setdefault(r.shop_number, {}).setdefault(kpi.key, []).append(v)

    # Region-wide average-per-shop, per KPI — used to rank the target's Month/Year average against
    # everyone else's, the same way `_rank_of` ranks a single week's value.
    month_avgs = {
        kpi.key: {sn: _average(vals[kpi.key]) for sn, vals in month_raw.items() if vals.get(kpi.key)}
        for kpi in kpis
    }
    year_avgs = {
        kpi.key: {sn: _average(vals[kpi.key]) for sn, vals in year_raw.items() if vals.get(kpi.key)}
        for kpi in kpis
    }

    rows = []
    for kpi in kpis:
        week_value = getattr(target_latest, kpi.key)
        month_weeks_counted = len(month_raw.get(target_shop_number, {}).get(kpi.key, []))
        year_weeks_counted = len(year_raw.get(target_shop_number, {}).get(kpi.key, []))
        week_ranks = target_week_ranks[kpi.key]
        rows.append(
            {
                "key": kpi.key, "label": kpi.label, "group": kpi.group, "type": kpi.type,
                "week": {"value": week_value, "rank": _rank_of(latest_rows, kpi.key, week_value)},
                "month": {
                    "value": month_avgs[kpi.key].get(target_shop_number),
                    "rank": _rank_in_averages(month_avgs[kpi.key], target_shop_number),
                    "weeks_counted": month_weeks_counted,
                },
                "year": {
                    "value": year_avgs[kpi.key].get(target_shop_number),
                    "rank": _rank_in_averages(year_avgs[kpi.key], target_shop_number),
                    "weeks_counted": year_weeks_counted,
                    "best_rank": min(week_ranks) if week_ranks else None,
                    "worst_rank": max(week_ranks) if week_ranks else None,
                    "rank_stdev": statistics.pstdev(week_ranks) if len(week_ranks) > 1 else None,
                },
            }
        )

    return {
        "available": True,
        "shop_number": target_shop_number,
        "shop_name": target_latest.shop_name,
        "area_name": target_latest.area_name,
        "viewing_own_shop": target_shop_number == my_shop_number,
        "weeks_tracked": len(weeks),
        "region_size": len(latest_rows),
        "group": kpi_group,
        "groups": KPI_GROUPS,
        "kpis": [{"key": k.key, "label": k.label, "group": k.group, "type": k.type} for k in kpis],
        "rows": rows,
    }


def _consistency_boards(
    session: Session, weeks: list[int], kpis: list[KpiDef], shop_number: Optional[str]
) -> list[dict[str, Any]]:
    """Top/bottom leaderboards ranked by average rank across every week on file, instead of one
    week's value — rewards a shop that's reliably strong over a shop that just had one great week.
    Mirrors the shape of the "latest" leaderboards below exactly, so the frontend can render both
    with the same component."""
    rank_lists: dict[str, dict[str, list[int]]] = {}
    shop_meta: dict[str, tuple[Optional[str], Optional[str]]] = {}
    for w in weeks:
        week_rows = _week_rows(session, w)
        for r in week_rows:
            shop_meta[r.shop_number] = (r.shop_name, r.area_name)
        for kpi in kpis:
            for sn, rank in _ranks_for_week(week_rows, kpi.key).items():
                rank_lists.setdefault(sn, {}).setdefault(kpi.key, []).append(rank)

    # A shop needs at least a handful of weeks on file before its average rank means anything —
    # otherwise one lucky week could pass for "consistency". Caps at 3 so this doesn't lock the
    # feature out entirely while only a few weeks have been uploaded so far.
    min_weeks = min(3, len(weeks))

    boards = []
    for kpi in kpis:
        entries = [
            (sn, sum(ranks) / len(ranks), len(ranks))
            for sn, by_kpi in rank_lists.items()
            for ranks in [by_kpi.get(kpi.key, [])]
            if len(ranks) >= min_weeks
        ]
        entries.sort(key=lambda e: e[1])  # ascending average rank = most consistently good first
        total = len(entries)
        my_index = next((i for i, e in enumerate(entries) if e[0] == shop_number), None)

        def _entry(rank_pos: int, entry: tuple[str, float, int]) -> dict[str, Any]:
            sn, avg_rank, weeks_counted = entry
            is_me = sn == shop_number
            name, _area = shop_meta.get(sn, (None, None))
            return {
                "rank": rank_pos,
                "shop_number": sn,
                "shop_name": name,
                "value": round(avg_rank, 2),
                "weeks_counted": weeks_counted,
                "is_me": is_me,
            }

        top = [_entry(i + 1, e) for i, e in enumerate(entries[:5])]
        bottom_slice = entries[-5:] if total > 5 else []
        bottom_start = total - len(bottom_slice)
        bottom = [_entry(bottom_start + i + 1, e) for i, e in enumerate(bottom_slice)]

        boards.append(
            {
                "key": kpi.key, "label": kpi.label, "group": kpi.group, "type": "ratio",
                "top": top, "bottom": bottom,
                "my_rank": (my_index + 1) if my_index is not None else None,
                "total": total,
            }
        )
    return boards


@router.get("/leaderboards")
def get_vswt_leaderboards(
    week: Optional[int] = Query(None),
    group: Optional[str] = Query(None),
    mode: Literal["latest", "consistency"] = Query(
        "latest", description="'latest' = this week's values; 'consistency' = average rank across every week on file."
    ),
    auth: AuthContext = Depends(get_auth_context),
    session: Session = Depends(get_session),
):
    # Leaderboards don't require the logged-in shop to have a shop_number — matches the
    # reference app, where leaderboards are visible even before "my shop" is known.
    shop_number = _shop_number_for(auth, session)
    weeks = _all_weeks(session)
    if not weeks:
        return {"available": False, "reason": "no_data"}
    kpis = KPI_DEFS if not group or group == "All" else [k for k in KPI_DEFS if k.group == group]

    if mode == "consistency":
        return {
            "available": True,
            "mode": "consistency",
            "week": weeks[-1],
            "weeks": weeks,
            "groups": ["All"] + list(KPI_GROUPS),
            "boards": _consistency_boards(session, weeks, kpis, shop_number),
        }

    target_week = week if week in weeks else weeks[-1]
    week_rows = _week_rows(session, target_week)

    boards = []
    for kpi in kpis:
        ranked = sorted(
            (r for r in week_rows if getattr(r, kpi.key) is not None),
            key=lambda r: getattr(r, kpi.key),
            reverse=True,
        )
        top = ranked[:5]
        bottom = ranked[-5:] if len(ranked) > 5 else []
        bottom_start = len(ranked) - len(bottom)
        my_index = (
            next((i for i, r in enumerate(ranked) if r.shop_number == shop_number), None)
            if shop_number
            else None
        )
        boards.append(
            {
                "key": kpi.key,
                "label": kpi.label,
                "group": kpi.group,
                "type": kpi.type,
                "top": [
                    {
                        "rank": i + 1, "shop_number": r.shop_number, "shop_name": r.shop_name,
                        "value": getattr(r, kpi.key), "is_me": r.shop_number == shop_number,
                    }
                    for i, r in enumerate(top)
                ],
                "bottom": [
                    {
                        "rank": bottom_start + i + 1,
                        "shop_number": r.shop_number,
                        "shop_name": r.shop_name,
                        "value": getattr(r, kpi.key), "is_me": r.shop_number == shop_number,
                    }
                    for i, r in enumerate(bottom)
                ],
                "my_rank": (my_index + 1) if my_index is not None else None,
                "total": len(ranked),
            }
        )

    return {
        "available": True,
        "mode": "latest",
        "week": target_week,
        "weeks": weeks,
        "groups": ["All"] + list(KPI_GROUPS),
        "boards": boards,
    }


@router.get("/trends")
def get_vswt_trends(
    weeks_back: int = Query(8, ge=1, le=104),
    shop_number: Optional[str] = Query(
        None, description="View another Minit shop's trends instead of your own (you must be a Minit shop yourself)."
    ),
    auth: AuthContext = Depends(get_auth_context),
    session: Session = Depends(get_session),
):
    my_shop_number = _shop_number_for(auth, session)
    if my_shop_number is None:
        return {"available": False, "reason": "no_shop_number"}
    target_shop_number = shop_number or my_shop_number
    all_weeks = _all_weeks(session)
    if not all_weeks:
        return {"available": False, "reason": "no_data"}
    weeks = all_weeks[-weeks_back:]

    sales_series = []
    customers_series = []
    jobs_series = []
    rank_series = []
    found_any = False
    target_name = None
    target_area = None
    for w in weeks:
        week_rows = _week_rows(session, w)
        target_row = _find_shop(week_rows, target_shop_number)
        peers = _peer_rows(week_rows)
        if target_row is not None:
            found_any = True
            target_name = target_row.shop_name
            target_area = target_row.area_name
        sales_series.append(
            {
                "week": w,
                "shop": target_row.sales_ty if target_row else None,
                "region_avg": _average([r.sales_ty for r in week_rows]),
                "peer_avg": _average([r.sales_ty for r in peers]),
            }
        )
        customers_series.append(
            {
                "week": w,
                "shop": target_row.customer_ty if target_row else None,
                "region_avg": _average([r.customer_ty for r in week_rows]),
                "peer_avg": _average([r.customer_ty for r in peers]),
            }
        )
        jobs_series.append(
            {
                "week": w,
                "shop": target_row.jobs_ty if target_row else None,
                "region_avg": _average([r.jobs_ty for r in week_rows]),
                "peer_avg": _average([r.jobs_ty for r in peers]),
            }
        )
        rank_series.append(
            {"week": w, "rank": _rank_of(week_rows, "sales_ty", target_row.sales_ty) if target_row else None}
        )

    if not found_any:
        return {"available": False, "reason": "shop_not_found"}

    latest = weeks[-1]
    latest_rows = _week_rows(session, latest)
    latest_target_row = _find_shop(latest_rows, target_shop_number)
    category_series = [
        {
            "name": label,
            "shop": getattr(latest_target_row, key) if latest_target_row else None,
            "region_avg": _average([getattr(r, key) for r in latest_rows]),
        }
        for key, label in CATEGORY_SALES_KEYS
    ]
    annotations = (
        [_annotation_dict(row) for row in _annotation_rows(session, auth.tenant_id, target_shop_number)]
        if target_shop_number == my_shop_number
        else []
    )

    return {
        "available": True,
        "shop_number": target_shop_number,
        "shop_name": target_name,
        "area_name": target_area,
        "viewing_own_shop": target_shop_number == my_shop_number,
        "weeks": weeks,
        "latest_week": latest,
        "sales_series": sales_series,
        "customers_series": customers_series,
        "jobs_series": jobs_series,
        "rank_series": rank_series,
        "category_series": category_series,
        "region_size": len(latest_rows),
        "annotations": annotations,
    }


# ── Weekly report builder ────────────────────────────────────────────────────────────────
# Lets a shop hand-pick a handful of other shops (e.g. their own franchisee group) and get one
# week's numbers for just those shops laid out together — for pasting into a group chat, not for
# browsing the whole region like the Directory does.

def _parse_shop_numbers(shop_numbers: str) -> list[str]:
    # De-dupe while preserving the order the caller picked them in, so the report reads the same
    # order the user built it in rather than region sort order.
    seen: set[str] = set()
    out: list[str] = []
    for sn in shop_numbers.split(","):
        sn = sn.strip()
        if sn and sn not in seen:
            seen.add(sn)
            out.append(sn)
    return out


def _weekly_report_data(
    week_rows: list[VswtWeeklyShopMetric],
    shop_numbers: list[str],
    my_shop_number: Optional[str],
    compare_within_selection: bool = False,
) -> dict[str, Any]:
    """Shared by the JSON preview and the PDF export below, so both always show the same numbers.
    Comprehensive by design: every KPI HQ tracks gets a value *and* a rank for every selected
    shop, not just the Headline group — the report is meant to stand on its own without anyone
    needing to flip back to Rankings for the rest of the picture.

    `compare_within_selection` swaps what ranks are computed against: normally (False) every rank
    is the shop's position in the *whole region* — same numbers as the rest of the VSWT tabs. Set
    True to rank shops only against each other (e.g. "who's top of our own franchisee group this
    week"), which needs the selected shops resolved first so the ranking pool is just them."""
    by_number = {r.shop_number: r for r in week_rows}
    selected_rows: list[VswtWeeklyShopMetric] = []
    missing: list[str] = []
    for sn in shop_numbers:
        r = by_number.get(sn)
        if r is None:
            missing.append(sn)
        else:
            selected_rows.append(r)

    rank_pool = selected_rows if compare_within_selection else week_rows

    shops: list[dict[str, Any]] = []
    for r in selected_rows:
        values: dict[str, Optional[float]] = {}
        ranks: dict[str, Optional[int]] = {}
        for kpi in KPI_DEFS:
            v = getattr(r, kpi.key)
            values[kpi.key] = v
            ranks[kpi.key] = _rank_of(rank_pool, kpi.key, v)
        ranked = [rk for rk in ranks.values() if rk is not None]
        shops.append(
            {
                "shop_number": r.shop_number,
                "shop_name": r.shop_name,
                "area_name": r.area_name,
                "is_me": r.shop_number == my_shop_number,
                "sales_value": r.sales_ty,
                "sales_rank": ranks.get("sales_ty"),
                "customer_value": r.customer_ty,
                "jobs_value": r.jobs_ty,
                # Average rank across every tracked KPI — a single composite "how's this shop
                # doing overall" number alongside the headline sales rank.
                "overall_avg_rank": (sum(ranked) / len(ranked)) if ranked else None,
                "values": values,
                "ranks": ranks,
            }
        )
    # Best sales first — reads like a mini leaderboard for the group, nulls sink to the bottom.
    shops.sort(key=lambda s: (s["sales_value"] is None, -(s["sales_value"] or 0)))

    sales_vals = [s["sales_value"] for s in shops if s["sales_value"] is not None]
    customer_vals = [s["customer_value"] for s in shops if s["customer_value"] is not None]
    jobs_vals = [s["jobs_value"] for s in shops if s["jobs_value"] is not None]
    sales_ranks = [s["sales_rank"] for s in shops if s["sales_rank"] is not None]
    totals = {
        "sales": sum(sales_vals) if sales_vals else None,
        "customers": sum(customer_vals) if customer_vals else None,
        "jobs": sum(jobs_vals) if jobs_vals else None,
        "avg_sales_rank": (sum(sales_ranks) / len(sales_ranks)) if sales_ranks else None,
    }
    return {
        "shops": shops,
        "missing_shop_numbers": missing,
        "totals": totals,
        "rank_pool_size": len(rank_pool),
    }


@router.get("/weekly-report")
def get_vswt_weekly_report(
    week: Optional[int] = Query(None),
    shop_numbers: str = Query(..., description="Comma-separated shop numbers to include, in the order picked."),
    compare_within_selection: bool = Query(
        False, description="Rank shops only against each other instead of the whole region."
    ),
    auth: AuthContext = Depends(get_auth_context),
    session: Session = Depends(get_session),
):
    my_shop_number = _shop_number_for(auth, session)
    if my_shop_number is None:
        return {"available": False, "reason": "no_shop_number"}
    weeks = _all_weeks(session)
    if not weeks:
        return {"available": False, "reason": "no_data"}
    target_week = week if week in weeks else weeks[-1]

    numbers = _parse_shop_numbers(shop_numbers)
    if not numbers:
        raise HTTPException(status_code=400, detail="Pick at least one shop for the report.")

    week_rows = _week_rows(session, target_week)
    data = _weekly_report_data(week_rows, numbers, my_shop_number, compare_within_selection)
    if not data["shops"]:
        return {"available": False, "reason": "shop_not_found", "week": target_week}

    return {
        "available": True,
        "week": target_week,
        "weeks": weeks,
        "region_size": len(week_rows),
        "compare_within_selection": compare_within_selection,
        "groups": KPI_GROUPS,
        "kpis": [{"key": k.key, "label": k.label, "group": k.group, "type": k.type} for k in KPI_DEFS],
        **data,
    }


@router.get("/weekly-report/pdf")
def get_vswt_weekly_report_pdf(
    week: Optional[int] = Query(None),
    shop_numbers: str = Query(..., description="Comma-separated shop numbers to include, in the order picked."),
    title: str = Query("Weekly Regional Report", description="Report title, e.g. your franchisee group's name."),
    compare_within_selection: bool = Query(
        False, description="Rank shops only against each other instead of the whole region."
    ),
    auth: AuthContext = Depends(get_auth_context),
    session: Session = Depends(get_session),
):
    my_shop_number = _shop_number_for(auth, session)
    if my_shop_number is None:
        raise HTTPException(status_code=404, detail="This shop isn't linked to a VSWT shop number yet.")
    weeks = _all_weeks(session)
    if not weeks:
        raise HTTPException(status_code=404, detail="No regional data has been uploaded yet.")
    target_week = week if week in weeks else weeks[-1]

    numbers = _parse_shop_numbers(shop_numbers)
    if not numbers:
        raise HTTPException(status_code=400, detail="Pick at least one shop for the report.")

    week_rows = _week_rows(session, target_week)
    data = _weekly_report_data(week_rows, numbers, my_shop_number, compare_within_selection)
    if not data["shops"]:
        raise HTTPException(status_code=404, detail="None of the selected shops were found in this week's data.")

    pdf_bytes = build_weekly_report_pdf(
        title=title.strip() or "Weekly Regional Report",
        week=target_week,
        region_size=len(week_rows),
        compare_within_selection=compare_within_selection,
        rank_pool_size=data["rank_pool_size"],
        groups=KPI_GROUPS,
        kpis=KPI_DEFS,
        shops=data["shops"],
        totals=data["totals"],
        generated_on=date.today(),
    )
    filename = f"weekly-report-week-{target_week}.pdf"
    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )
