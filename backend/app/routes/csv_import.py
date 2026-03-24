"""
CSV import endpoint – accepts an uploaded CSV file and imports
customers, watches, repair jobs, and quotes into the database.
"""

import csv
import io
import re
from datetime import date, datetime, timezone
from pathlib import Path
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Request
from sqlalchemy import delete as sa_delete
from sqlmodel import Session, select
import openpyxl
import xlrd

from ..database import get_session
from ..dependencies import AuthContext, get_auth_context
from ..config import settings
from ..limiter import limiter
from ..models import (
    Approval,
    Attachment,
    AutoKeyInvoice,
    AutoKeyJob,
    AutoKeyQuote,
    AutoKeyQuoteLineItem,
    Customer,
    ImportLog,
    ImportLogDetail,
    ImportSummaryResponse,
    Invoice,
    JobStatusHistory,
    Payment,
    Quote,
    QuoteLineItem,
    RepairJob,
    SmsLog,
    Watch,
    WorkLog,
    Shoe,
    ShoeRepairJob,
    ShoeRepairJobItem,
    ShoeRepairJobShoe,
    Tenant,
)

router = APIRouter(prefix="/v1/import", tags=["import"])


def get_import_csv_rate_limit() -> str:
    return settings.rate_limit_import_csv


# ── Helpers (ported from import_csv.py) ────────────────────────────────────────

def _parse_date(raw: str) -> date | None:
    if not raw or not raw.strip():
        return None
    raw = raw.strip()

    # Excel date serial (e.g. 44927 or 44927.0)
    try:
        n = float(raw)
        if 1000 < n < 100000 and n == int(n):
            from datetime import timedelta
            d = date(1899, 12, 30) + timedelta(days=int(n))
            return d
    except (ValueError, TypeError):
        pass

    for pattern, groups in [
        (r"^(\d{1,2})/(\d{1,2})/(\d{2})$", "dmy2"),
        (r"^(\d{1,2})/(\d{1,2})/(\d{4})$", "dmy4"),
        (r"^(\d{4})-(\d{1,2})-(\d{1,2})$", "ymd"),
        (r"^(\d{1,2})\.(\d{1,2})\.(\d{2,4})$", "dmy_dot"),
        (r"^(\d{1,2})/+(\d{1,2})/+(\d{2,4})$", "dmy_slash"),
    ]:
        m = re.match(pattern, raw)
        if not m:
            continue
        if groups == "ymd":
            y, mo, d = int(m.group(1)), int(m.group(2)), int(m.group(3))
        else:
            d, mo, y = int(m.group(1)), int(m.group(2)), int(m.group(3))
        if y < 100:
            y += 2000
        if 1 <= mo <= 12 and 1 <= d <= 31:
            try:
                return date(y, mo, d)
            except ValueError:
                continue
    return None


def _normalize_phone(raw: str) -> str | None:
    if not raw or not raw.strip():
        return None
    digits = re.sub(r"\D", "", raw.strip())
    if len(digits) > 12:
        digits = digits[:10]
    if len(digits) == 9 and digits[0] in ("4", "3"):
        digits = "0" + digits
    if len(digits) < 8:
        return None
    return digits


# PostgreSQL INTEGER max; clamp to avoid overflow from corrupted Excel values
_MAX_CENTS = 2_147_483_647


def _dollars_to_cents(raw: str) -> int:
    if not raw or not raw.strip():
        return 0
    s = raw.strip().lower()
    if any(token in s for token in ["n/c", "nc", "quote"]):
        return 0

    # Handles values like "2x69.95" or "2 x $49.95 - 10%"
    m = re.search(r"(\d+)\s*x\s*\$?\s*(\d+(?:\.\d+)?)", s)
    if m:
        qty = int(m.group(1))
        unit = float(m.group(2))
        total = qty * unit
        discount = re.search(r"-\s*(\d+(?:\.\d+)?)\s*%", s)
        if discount:
            total *= 1 - (float(discount.group(1)) / 100)
        return min(int(round(total * 100)), _MAX_CENTS)

    numbers = [float(n) for n in re.findall(r"\d+(?:\.\d+)?", s)]
    if not numbers:
        return 0
    return min(int(round(numbers[0] * 100)), _MAX_CENTS)


def _clean_name(raw: str) -> str | None:
    if not raw or not raw.strip():
        return None
    name = re.sub(r"\s+", " ", raw.strip())
    lower_name = name.lower()

    # Common placeholders/comments that are not valid customer names.
    invalid_name_fragments = [
        "already collected",
        "has been collected",
        "picked up",
        "cancelled",
        "unknown",
    ]
    if any(fragment in lower_name for fragment in invalid_name_fragments):
        return None

    if re.match(r"^\d+$", name):
        return None
    if re.match(r"^\d{1,2}/\d{1,2}/\d{2,4}", name):
        return None
    if len(name) < 2:
        return None
    return name


def _get_first(row: dict[str, str], keys: list[str]) -> str:
    """Return the first non-empty value found in the provided column keys."""
    for key in keys:
        value = row.get(key)
        if value is not None and str(value).strip():
            return str(value).strip()
    return ""


def _normalize_key(key: str) -> str:
    k = (key or "").strip().lower()
    k = re.sub(r"[^a-z0-9]+", "_", k)
    return k.strip("_")


def _normalize_row_keys(row: dict[str, str]) -> dict[str, str]:
    normalized: dict[str, str] = {}
    for key, value in row.items():
        normalized[_normalize_key(key)] = (value or "").strip()

    # First column with no header (Excel: _col0→col0, CSV: "") often contains ticket/job numbers.
    for blank_key in ("", "_col0", "col0"):
        val = (row.get(blank_key) or "").strip()
        if val and "original_job_id" not in normalized:
            try:
                if re.match(r"^[\d.]+$", val):
                    normalized["original_job_id"] = val
                    break
            except Exception:
                pass
    return normalized


def _to_text(value: object) -> str:
    if value is None:
        return ""
    if isinstance(value, datetime):
        return value.strftime("%Y-%m-%d")
    if isinstance(value, date):
        return value.isoformat()
    return str(value).strip()


def _load_csv_rows(raw_bytes: bytes) -> list[dict[str, str]]:
    text = ""
    for encoding in ("utf-8-sig", "utf-16", "latin-1"):
        try:
            text = raw_bytes.decode(encoding)
            break
        except UnicodeDecodeError:
            continue

    if not text:
        raise HTTPException(status_code=400, detail="Unable to decode CSV file. Please export as UTF-8 CSV.")

    sample = text[:8192]
    try:
        dialect = csv.Sniffer().sniff(sample, delimiters=",;\t|")
        reader = csv.DictReader(io.StringIO(text), dialect=dialect)
    except csv.Error:
        reader = csv.DictReader(io.StringIO(text))

    rows = list(reader)
    if not reader.fieldnames:
        raise HTTPException(status_code=400, detail="CSV header row could not be read. Ensure the first row contains column names.")
    return rows


def _load_xlsx_rows(raw_bytes: bytes) -> list[dict[str, str]]:
    try:
        workbook = openpyxl.load_workbook(io.BytesIO(raw_bytes), data_only=True)
        sheet = workbook.active
        if sheet is None:
            raise HTTPException(status_code=400, detail="Excel file has no worksheets.")
        all_rows = list(sheet.iter_rows(values_only=True))
    except Exception as exc:
        raise HTTPException(
            status_code=400,
            detail=f"Could not read Excel file. Try saving as CSV (UTF-8) or a fresh .xlsx. Error: {exc}",
        ) from exc

    if not all_rows:
        return []

    header_row = all_rows[0]
    header = [_to_text(v) or f"_col{i}" for i, v in enumerate(header_row)]
    # Ensure unique header keys (Excel often has blank columns)
    seen: set[str] = set()
    for i, h in enumerate(header):
        if h in seen:
            header[i] = f"{h}_{i}"
        seen.add(header[i])

    result: list[dict[str, str]] = []
    for row in all_rows[1:]:
        if not any(_to_text(c) for c in row):
            continue
        row_len = len(row)
        hdr_len = len(header)
        cells = [_to_text(row[idx]) if idx < row_len else "" for idx in range(hdr_len)]
        result.append({header[i]: cells[i] for i in range(hdr_len)})
    return result


def _load_xls_rows(raw_bytes: bytes) -> list[dict[str, str]]:
    workbook = xlrd.open_workbook(file_contents=raw_bytes)
    sheet = workbook.sheet_by_index(0)
    if sheet.nrows == 0:
        return []

    header = [_to_text(sheet.cell_value(0, col)) for col in range(sheet.ncols)]
    output: list[dict[str, str]] = []
    for row_idx in range(1, sheet.nrows):
        row_values = [_to_text(sheet.cell_value(row_idx, col)) for col in range(sheet.ncols)]
        if not any(row_values):
            continue
        output.append({header[idx]: value for idx, value in enumerate(row_values)})
    return output


def _load_rows(filename: str, raw_bytes: bytes) -> tuple[list[dict[str, str]], str]:
    ext = Path(filename).suffix.lower()
    if ext == ".csv":
        return _load_csv_rows(raw_bytes), "csv"
    if ext in {".xlsx", ".xlsm"}:
        return _load_xlsx_rows(raw_bytes), "xlsx"
    if ext == ".xls":
        return _load_xls_rows(raw_bytes), "xls"

    # Be tolerant of renamed/missing extensions by sniffing common formats.
    if raw_bytes.startswith(b"PK"):
        return _load_xlsx_rows(raw_bytes), "xlsx"
    if raw_bytes.startswith(b"\xD0\xCF\x11\xE0\xA1\xB1\x1A\xE1"):
        return _load_xls_rows(raw_bytes), "xls"

    try:
        return _load_csv_rows(raw_bytes), "csv"
    except Exception as exc:
        raise HTTPException(
            status_code=400,
            detail="Only .csv, .xlsx, .xls, and .xlsm files are accepted. If this is CSV, re-save as UTF-8 CSV.",
        ) from exc


_STATUS_MAP = {
    "collected": "collected",
    "ga": "completed",  # Good as New
    "ng": "no_go",     # No Good
    "in_repair": "working_on",
    "in repair": "working_on",
    "working on": "working_on",
    "ready": "awaiting_collection",
    "awaiting collection": "awaiting_collection",
    "intake": "awaiting_go_ahead",
    "awaiting go ahead": "awaiting_go_ahead",
    "go ahead": "go_ahead",
    "no go": "no_go",
    "completed": "completed",
    "awaiting parts": "awaiting_parts",
    "parts to be ordered": "parts_to_order",
    "sent to labanda": "sent_to_labanda",
    "service": "service",
    "cancelled": "no_go",
    "approved": "go_ahead",
}


def _infer_job_status(status_raw: str, notes_raw: str) -> str:
    status = (status_raw or "").strip().lower()
    notes = (notes_raw or "").strip().lower()

    if status in _STATUS_MAP:
        return _STATUS_MAP[status]

    if status == "delivered":
        if any(token in notes for token in ["collected", "picked up", "has been collected", "watch collect"]):
            return "collected"
        if any(token in notes for token in ["awaiting collection", "ready for collection", "ready in drawer", "messaged for collection"]):
            return "awaiting_collection"
        return "completed"

    return "awaiting_go_ahead"


def _clear_tenant_importable_data(session: Session, tenant_id, clear_tabs: list[str]) -> None:
    """Delete tenant-scoped operational data before replacement import, for selected tabs."""
    import_log_ids = session.exec(select(ImportLog.id).where(ImportLog.tenant_id == tenant_id)).all()
    if import_log_ids:
        session.exec(sa_delete(ImportLogDetail).where(ImportLogDetail.import_log_id.in_(import_log_ids)))
        session.exec(sa_delete(ImportLog).where(ImportLog.id.in_(import_log_ids)))

    # --- SHOE REPAIR TABLES ---
    if "shoe" in clear_tabs:
        session.exec(sa_delete(ShoeRepairJobItem).where(ShoeRepairJobItem.tenant_id == tenant_id))
        session.exec(sa_delete(ShoeRepairJobShoe).where(ShoeRepairJobShoe.tenant_id == tenant_id))
        session.exec(sa_delete(ShoeRepairJob).where(ShoeRepairJob.tenant_id == tenant_id))
        session.exec(sa_delete(Shoe).where(Shoe.tenant_id == tenant_id))

    # --- WATCH REPAIR TABLES ---
    if "watch" in clear_tabs:
        session.exec(sa_delete(Attachment).where(Attachment.tenant_id == tenant_id))
        session.exec(sa_delete(WorkLog).where(WorkLog.tenant_id == tenant_id))
        session.exec(sa_delete(JobStatusHistory).where(JobStatusHistory.tenant_id == tenant_id))
        session.exec(sa_delete(SmsLog).where(SmsLog.tenant_id == tenant_id))
        session.exec(sa_delete(QuoteLineItem).where(QuoteLineItem.tenant_id == tenant_id))
        session.exec(sa_delete(Approval).where(Approval.tenant_id == tenant_id))
        session.exec(sa_delete(Payment).where(Payment.tenant_id == tenant_id))
        session.exec(sa_delete(Invoice).where(Invoice.tenant_id == tenant_id))
        session.exec(sa_delete(Quote).where(Quote.tenant_id == tenant_id))
        session.exec(sa_delete(RepairJob).where(RepairJob.tenant_id == tenant_id))
        session.exec(sa_delete(Watch).where(Watch.tenant_id == tenant_id))
        session.exec(sa_delete(Customer).where(Customer.tenant_id == tenant_id))

    # --- AUTO KEY TABLES ---
    if "auto_key" in clear_tabs:
        session.exec(sa_delete(AutoKeyInvoice).where(AutoKeyInvoice.tenant_id == tenant_id))
        session.exec(sa_delete(AutoKeyQuoteLineItem).where(AutoKeyQuoteLineItem.tenant_id == tenant_id))
        session.exec(sa_delete(AutoKeyQuote).where(AutoKeyQuote.tenant_id == tenant_id))
        session.exec(sa_delete(AutoKeyJob).where(AutoKeyJob.tenant_id == tenant_id))


# ── Endpoint ───────────────────────────────────────────────────────────────────

from fastapi import Query

@router.post("/csv", response_model=ImportSummaryResponse)
@limiter.limit(get_import_csv_rate_limit)
async def import_csv(
    request: Request,
    file: UploadFile = File(...),
    replace_existing: bool = False,
    dry_run: bool = False,
    clear_tabs: list[str] = Query(["watch", "shoe", "auto_key"], description="Tabs to clear: watch, shoe, auto_key"),
    auth: AuthContext = Depends(get_auth_context),
    session: Session = Depends(get_session),
):
    if not file.filename:
        raise HTTPException(status_code=400, detail="File name is required")

    raw_bytes = await file.read()
    rows, file_type = _load_rows(file.filename, raw_bytes)
    if not rows:
        raise HTTPException(status_code=400, detail="Import file is empty.")

    tenant_id = auth.tenant_id
    tenant = session.get(Tenant, tenant_id)
    tenant_currency = (tenant.default_currency if tenant and tenant.default_currency else "AUD").upper()
    if replace_existing and not dry_run:
        _clear_tenant_importable_data(session, tenant_id, clear_tabs)
        session.commit()

    import_log = None
    if not dry_run:
        import_log = ImportLog(
            tenant_id=tenant_id,
            uploaded_by_user_id=auth.user_id,
            file_name=file.filename,
            file_type=file_type,
            total_rows=len(rows),
        )
        session.add(import_log)
        session.commit()
        session.refresh(import_log)

    customer_cache: dict[tuple[str, str | None], Customer] = {}
    imported = 0
    skipped = 0
    job_seq = 0
    skipped_reasons: dict[str, int] = {}
    duplicate_customer_rows_in_file = 0

    def log_skip(row_number: int, reason: str) -> None:
        nonlocal skipped
        skipped += 1
        skipped_reasons[reason] = skipped_reasons.get(reason, 0) + 1
        if import_log is not None:
            session.add(ImportLogDetail(import_log_id=import_log.id, row_number=row_number, skip_reason=reason))

    try:
        for idx, row in enumerate(rows, start=1):
            row = _normalize_row_keys(row)
            # Ticket: check unnamed first col (col0/_col0) first, then common headers. Omit "number" (often phone).
            original_job_id = _get_first(row, [
                "col0", "_col0", "original_job_id", "job_id", "ticket", "ticket_number", "job_number",
                "ticket_", "job_", "ref", "job_no", "ticket_no", "case_no", "no",
            ])
            team_member = _get_first(row, ["team_member", "salesperson", "staff", "assignee"])
            customer_name_raw = _get_first(row, ["customer_name", "customer", "client", "name"])
            date_in_raw = _get_first(row, ["date_in", "created_at", "created", "intake_date", "date"])
            brand_case = _get_first(row, ["brand_case_numbers", "brand", "watch_brand", "make_model", "model"])
            phone_raw = _get_first(row, ["phone_number", "phone", "mobile", "contact_phone", "number"])
            quote_raw = _get_first(row, ["quote_price", "quote", "estimate", "amount", "total"])
            cost_raw = _get_first(row, ["cost_to_business", "cost", "job_cost", "internal_cost"])
            status_raw = _get_first(row, ["status", "job_status", "repair_status", "state", "ga_ng_collected"])
            notes_raw = _get_first(row, ["repair_notes", "notes", "description", "job_notes", "being_done"])

            customer_name = _clean_name(customer_name_raw)
            if not customer_name:
                customer_name = _clean_name(original_job_id)
                if not customer_name:
                    has_meaningful_data = any([brand_case, phone_raw, quote_raw, status_raw, notes_raw, original_job_id])
                    if not has_meaningful_data:
                        log_skip(idx, "empty_row")
                        continue
                    if not brand_case and not phone_raw:
                        log_skip(idx, "missing_core_fields")
                        continue
                    customer_name = f"Unknown Customer {original_job_id or uuid4().hex[:8]}"

            phone = _normalize_phone(phone_raw)
            date_in = _parse_date(date_in_raw)
            status = _infer_job_status(status_raw, notes_raw)
            quote_cents = _dollars_to_cents(quote_raw)
            cost_cents = _dollars_to_cents(cost_raw)

            cache_key = (customer_name.lower(), phone)
            created_customer_id = None
            if cache_key in customer_cache:
                customer = customer_cache[cache_key]
                duplicate_customer_rows_in_file += 1
            else:
                customer = Customer(tenant_id=tenant_id, full_name=customer_name, phone=phone)
                session.add(customer)
                session.flush()
                customer_cache[cache_key] = customer
                created_customer_id = customer.id

            watch = Watch(tenant_id=tenant_id, customer_id=customer.id, brand=brand_case or None)
            session.add(watch)
            session.flush()

            job_seq += 1
            # Use ticket from file when present; strip Excel .0 suffix from numeric cells
            if original_job_id:
                ticket = original_job_id.strip()
                if re.match(r"^[\d.]+$", ticket) and ticket.endswith(".0"):
                    ticket = ticket[:-2]  # "29120.0" -> "29120"
                if ticket:
                    job_number = f"IMP-{ticket}"
                else:
                    job_number = f"IMP-{job_seq:05d}"
            else:
                job_number = f"IMP-{job_seq:05d}"

            title = f"Repair: {brand_case}" if brand_case else "Watch Repair"
            created_at = (
                datetime(date_in.year, date_in.month, date_in.day, tzinfo=timezone.utc)
                if date_in
                else datetime.now(timezone.utc)
            )

            job = RepairJob(
                tenant_id=tenant_id,
                watch_id=watch.id,
                job_number=job_number,
                title=title,
                description=notes_raw or None,
                priority="normal",
                status=status,
                salesperson=team_member or None,
                deposit_cents=0,
                pre_quote_cents=quote_cents or cost_cents,
                cost_cents=cost_cents,
                created_at=created_at,
            )
            session.add(job)
            session.flush()

            if quote_cents > 0:
                quote_status = "approved" if status in {"completed", "awaiting_collection", "collected"} else "sent"
                session.add(Quote(
                    tenant_id=tenant_id,
                    repair_job_id=job.id,
                    status=quote_status,
                    subtotal_cents=quote_cents,
                    tax_cents=0,
                    total_cents=quote_cents,
                    currency=tenant_currency,
                    created_at=created_at,
                ))

            if import_log is not None:
                session.add(
                    ImportLogDetail(
                        import_log_id=import_log.id,
                        row_number=idx,
                        created_repair_job_id=job.id,
                        created_customer_id=created_customer_id,
                    )
                )

            imported += 1

        if dry_run:
            session.rollback()
            return ImportSummaryResponse(
                import_id=uuid4(),
                imported=imported,
                skipped=skipped,
                customers_created=len(customer_cache),
                total_rows=len(rows),
                skipped_reasons=skipped_reasons,
                dry_run=True,
                duplicate_customer_rows_in_file=duplicate_customer_rows_in_file,
            )

        import_log.imported_count = imported
        import_log.skipped_count = skipped
        import_log.customers_created_count = len(customer_cache)
        import_log.status = "completed"
        session.add(import_log)
        session.commit()
    except Exception as exc:
        session.rollback()
        if import_log is not None:
            import_log.status = "failed"
            import_log.error_message = str(exc)
            import_log.imported_count = imported
            import_log.skipped_count = skipped
            import_log.customers_created_count = len(customer_cache)
            session.add(import_log)
            session.commit()
        raise HTTPException(status_code=400, detail=f"Import failed: {exc}") from exc

    return ImportSummaryResponse(
        import_id=import_log.id,
        imported=imported,
        skipped=skipped,
        customers_created=len(customer_cache),
        total_rows=len(rows),
        skipped_reasons=skipped_reasons,
        dry_run=False,
        duplicate_customer_rows_in_file=duplicate_customer_rows_in_file,
    )
