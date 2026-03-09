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
    try:
        return int(round(float(raw.strip()) * 100))
    except ValueError:
        return 0


def _clean_name(raw: str) -> str | None:
    if not raw or not raw.strip():
        return None
    name = raw.strip()
    if re.match(r"^\d+$", name):
        return None
    if re.match(r"^\d{1,2}/\d{1,2}/\d{2,4}", name):
        return None
    if len(name) < 2:
        return None
    return name


_STATUS_MAP = {
    "delivered": "delivered",
    "in_repair": "in_repair",
    "in repair": "in_repair",
    "ready": "ready",
    "intake": "intake",
    "approved": "awaiting_approval",
    "cancelled": "cancelled",
}


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
        original_job_id = (row.get("original_job_id") or "").strip()
        team_member = (row.get("team_member") or "").strip()
        customer_name_raw = (row.get("customer_name") or "").strip()
        date_in_raw = (row.get("date_in") or "").strip()
        brand_case = (row.get("brand_case_numbers") or "").strip()
        phone_raw = (row.get("phone_number") or "").strip()
        quote_raw = (row.get("quote_price") or "").strip()
        status_raw = (row.get("status") or "").strip()
        notes_raw = (row.get("repair_notes") or "").strip()

        customer_name = _clean_name(customer_name_raw)
        if not customer_name:
            customer_name = _clean_name(original_job_id)
            if not customer_name:
                skipped += 1
                continue

        phone = _normalize_phone(phone_raw)
        date_in = _parse_date(date_in_raw)
        status = _STATUS_MAP.get((status_raw or "").lower(), "delivered")
        quote_cents = _dollars_to_cents(quote_raw)

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
            created_at=created_at,
        )
        session.add(job)
        session.flush()

        if quote_cents > 0:
            session.add(Quote(
                tenant_id=tenant_id,
                repair_job_id=job.id,
                status="approved" if status == "delivered" else "sent",
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
