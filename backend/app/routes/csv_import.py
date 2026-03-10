"""
CSV import endpoint – accepts an uploaded CSV file and imports
customers, watches, repair jobs, and quotes into the database.
"""

import csv
import io
import re
from datetime import date, datetime, timezone
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException, UploadFile, File
from sqlmodel import Session, select

from ..database import get_session
from ..dependencies import AuthContext, get_auth_context
from ..models import Customer, Quote, RepairJob, Watch

router = APIRouter(prefix="/v1/import", tags=["import"])


# ── Helpers (ported from import_csv.py) ────────────────────────────────────────

def _parse_date(raw: str) -> date | None:
    if not raw or not raw.strip():
        return None
    raw = raw.strip()

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
        return int(round(total * 100))

    numbers = [float(n) for n in re.findall(r"\d+(?:\.\d+)?", s)]
    if not numbers:
        return 0
    return int(round(numbers[0] * 100))


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

    # The true source file has a blank first header containing original job IDs.
    if "original_job_id" not in normalized and row.get(""):
        normalized["original_job_id"] = (row.get("") or "").strip()
    return normalized


_STATUS_MAP = {
    "collected": "collected",
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


# ── Endpoint ───────────────────────────────────────────────────────────────────

@router.post("/csv")
async def import_csv(
    file: UploadFile = File(...),
    auth: AuthContext = Depends(get_auth_context),
    session: Session = Depends(get_session),
):
    if not file.filename or not file.filename.lower().endswith(".csv"):
        raise HTTPException(status_code=400, detail="Only .csv files are accepted.")

    raw_bytes = await file.read()
    try:
        text = raw_bytes.decode("utf-8-sig")
    except UnicodeDecodeError:
        text = raw_bytes.decode("latin-1")

    reader = csv.DictReader(io.StringIO(text))
    rows = list(reader)
    if not rows:
        raise HTTPException(status_code=400, detail="CSV file is empty.")

    tenant_id = auth.tenant_id
    customer_cache: dict[tuple[str, str | None], Customer] = {}
    imported = 0
    skipped = 0
    job_seq = 0

    for row in rows:
        row = _normalize_row_keys(row)
        original_job_id = _get_first(row, ["original_job_id", "job_id", "ticket", "ticket_number", "job_number"])
        team_member = _get_first(row, ["team_member", "salesperson", "staff", "assignee"])
        customer_name_raw = _get_first(row, ["customer_name", "customer", "client", "name"])
        date_in_raw = _get_first(row, ["date_in", "created_at", "created", "intake_date", "date"])
        brand_case = _get_first(row, ["brand_case_numbers", "brand", "watch_brand", "make_model", "model"])
        phone_raw = _get_first(row, ["phone_number", "phone", "mobile", "contact_phone", "number"])
        quote_raw = _get_first(row, ["quote_price", "quote", "estimate", "amount", "total"])
        cost_raw = _get_first(row, ["cost_to_business", "cost", "job_cost", "internal_cost"])
        status_raw = _get_first(row, ["status", "job_status", "repair_status", "state", "ga_ng_collected"])
        notes_raw = _get_first(row, ["repair_notes", "notes", "description", "job_notes"])

        customer_name = _clean_name(customer_name_raw)
        if not customer_name:
            customer_name = _clean_name(original_job_id)
            if not customer_name:
                has_meaningful_data = any([brand_case, phone_raw, quote_raw, status_raw, notes_raw, original_job_id])
                if not has_meaningful_data:
                    skipped += 1
                    continue
                customer_name = f"Unknown Customer {original_job_id or uuid4().hex[:8]}"

        phone = _normalize_phone(phone_raw)
        date_in = _parse_date(date_in_raw)
        status = _infer_job_status(status_raw, notes_raw)
        quote_cents = _dollars_to_cents(quote_raw)
        cost_cents = _dollars_to_cents(cost_raw)

        # Customer dedup
        cache_key = (customer_name.lower(), phone)
        if cache_key in customer_cache:
            customer = customer_cache[cache_key]
        else:
            customer = Customer(tenant_id=tenant_id, full_name=customer_name, phone=phone)
            session.add(customer)
            session.flush()
            customer_cache[cache_key] = customer

        # Watch
        watch = Watch(tenant_id=tenant_id, customer_id=customer.id, brand=brand_case or None)
        session.add(watch)
        session.flush()

        # Job
        job_seq += 1
        if original_job_id and re.match(r"^\d+", original_job_id):
            job_number = f"IMP-{original_job_id}"
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
                currency="AUD",
                created_at=created_at,
            ))

        imported += 1

    session.commit()

    return {
        "imported": imported,
        "skipped": skipped,
        "customers_created": len(customer_cache),
        "total_rows": len(rows),
    }
