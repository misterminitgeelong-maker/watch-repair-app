r"""
Import historical repair records from repairs_import.csv into the database.

Usage:
    cd backend
    python import_csv.py "C:\Users\samme\Downloads\repairs_import.csv"
"""

import csv
import re
import sys
from datetime import date, datetime, timezone
from pathlib import Path
from uuid import uuid4

from sqlmodel import Session, select

# Ensure the app package is importable
sys.path.insert(0, str(Path(__file__).resolve().parent))

from app.database import create_db_and_tables, engine
from app.models import (
    Customer,
    Quote,
    RepairJob,
    Tenant,
    Watch,
)


def parse_date(raw: str) -> date | None:
    """Parse the messy date formats in the CSV. Returns None on failure."""
    if not raw or not raw.strip():
        return None
    raw = raw.strip()

    # DD/MM/YY  e.g. 14/11/23
    m = re.match(r"^(\d{1,2})/(\d{1,2})/(\d{2})$", raw)
    if m:
        d, mo, y = int(m.group(1)), int(m.group(2)), int(m.group(3))
        y += 2000
        if 1 <= mo <= 12 and 1 <= d <= 31:
            try:
                return date(y, mo, d)
            except ValueError:
                return None

    # DD/MM/YYYY
    m = re.match(r"^(\d{1,2})/(\d{1,2})/(\d{4})$", raw)
    if m:
        d, mo, y = int(m.group(1)), int(m.group(2)), int(m.group(3))
        if 1 <= mo <= 12 and 1 <= d <= 31:
            try:
                return date(y, mo, d)
            except ValueError:
                return None

    # YYYY-MM-DD  e.g. 2023-04-11
    m = re.match(r"^(\d{4})-(\d{1,2})-(\d{1,2})$", raw)
    if m:
        y, mo, d = int(m.group(1)), int(m.group(2)), int(m.group(3))
        if 1 <= mo <= 12 and 1 <= d <= 31:
            try:
                return date(y, mo, d)
            except ValueError:
                return None

    # DD.MM.YY or DD.M.YY  e.g. 12.1.24
    m = re.match(r"^(\d{1,2})\.(\d{1,2})\.(\d{2,4})$", raw)
    if m:
        d, mo, y = int(m.group(1)), int(m.group(2)), int(m.group(3))
        if y < 100:
            y += 2000
        if 1 <= mo <= 12 and 1 <= d <= 31:
            try:
                return date(y, mo, d)
            except ValueError:
                return None

    # DD/M/YY with extra slashes  e.g. "08//04/24"
    m = re.match(r"^(\d{1,2})/+(\d{1,2})/+(\d{2,4})$", raw)
    if m:
        d, mo, y = int(m.group(1)), int(m.group(2)), int(m.group(3))
        if y < 100:
            y += 2000
        if 1 <= mo <= 12 and 1 <= d <= 31:
            try:
                return date(y, mo, d)
            except ValueError:
                return None

    return None


def normalize_phone(raw: str) -> str | None:
    """Normalize Australian phone numbers."""
    if not raw or not raw.strip():
        return None
    digits = re.sub(r"\D", "", raw.strip())
    # If multiple numbers concatenated (very long), take first 10 digits
    if len(digits) > 12:
        digits = digits[:10]
    # Prefix with 0 if 9-digit mobile
    if len(digits) == 9 and digits[0] in ("4", "3"):
        digits = "0" + digits
    if len(digits) < 8:
        return None
    return digits


def dollars_to_cents(raw: str) -> int:
    """Parse a dollar amount string to integer cents."""
    if not raw or not raw.strip():
        return 0
    try:
        return int(round(float(raw.strip()) * 100))
    except ValueError:
        return 0


def clean_name(raw: str) -> str | None:
    """Return a cleaned customer name or None if garbage."""
    if not raw or not raw.strip():
        return None
    name = raw.strip()
    # Skip purely numeric or very short garbage entries
    if re.match(r"^\d+$", name):
        return None
    # Skip entries that look like dates
    if re.match(r"^\d{1,2}/\d{1,2}/\d{2,4}", name):
        return None
    if len(name) < 2:
        return None
    return name


def map_status(raw: str) -> str:
    """Map CSV status to our JobStatus literal."""
    s = (raw or "").strip().lower()
    mapping = {
        "delivered": "delivered",
        "in_repair": "in_repair",
        "in repair": "in_repair",
        "ready": "ready",
        "intake": "intake",
        "approved": "awaiting_approval",
        "cancelled": "cancelled",
    }
    return mapping.get(s, "delivered")


def run_import(csv_path: str) -> None:
    create_db_and_tables()

    with Session(engine) as session:
        # Find the tenant (must be bootstrapped first)
        tenant = session.exec(select(Tenant).where(Tenant.slug == "myshop")).first()
        if not tenant:
            print("ERROR: Tenant 'myshop' not found. Bootstrap the app first:")
            print('  curl -X POST http://localhost:8000/v1/auth/bootstrap -H "Content-Type: application/json" \\')
            print('    -d \'{"tenant_name":"My Shop","tenant_slug":"myshop","owner_email":"admin@myshop.com","owner_full_name":"Admin","owner_password":"watchrepair123"}\'')
            sys.exit(1)

        tenant_id = tenant.id

        # Customer dedup cache: (lower_name, phone) -> Customer
        customer_cache: dict[tuple[str, str | None], Customer] = {}

        imported = 0
        skipped = 0
        job_seq = 0  # sequence counter for job numbers

        with open(csv_path, newline="", encoding="utf-8-sig") as f:
            reader = csv.DictReader(f)
            rows = list(reader)

        print(f"Read {len(rows)} rows from CSV")

        for i, row in enumerate(rows, start=2):
            original_job_id = (row.get("original_job_id") or "").strip()
            team_member = (row.get("team_member") or "").strip()
            customer_name_raw = (row.get("customer_name") or "").strip()
            date_in_raw = (row.get("date_in") or "").strip()
            brand_case = (row.get("brand_case_numbers") or "").strip()
            phone_raw = (row.get("phone_number") or "").strip()
            cost_raw = (row.get("cost_to_business") or "").strip()
            quote_raw = (row.get("quote_price") or "").strip()
            status_raw = (row.get("status") or "").strip()
            notes_raw = (row.get("repair_notes") or "").strip()

            # Clean the customer name
            customer_name = clean_name(customer_name_raw)
            if not customer_name:
                # Try to salvage from original_job_id field (some rows have data there)
                customer_name = clean_name(original_job_id)
                if not customer_name:
                    skipped += 1
                    continue

            phone = normalize_phone(phone_raw)
            date_in = parse_date(date_in_raw)
            status = map_status(status_raw)
            quote_cents = dollars_to_cents(quote_raw)
            cost_cents = dollars_to_cents(cost_raw)

            # --- Customer dedup ---
            cache_key = (customer_name.lower(), phone)
            if cache_key in customer_cache:
                customer = customer_cache[cache_key]
            else:
                customer = Customer(
                    tenant_id=tenant_id,
                    full_name=customer_name,
                    phone=phone,
                )
                session.add(customer)
                session.flush()
                customer_cache[cache_key] = customer

            # --- Watch ---
            watch = Watch(
                tenant_id=tenant_id,
                customer_id=customer.id,
                brand=brand_case if brand_case else None,
            )
            session.add(watch)
            session.flush()

            # --- Repair Job ---
            job_seq += 1
            # Use original ticket number if available, otherwise generate
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
                description=notes_raw if notes_raw else None,
                priority="normal",
                status=status,
                salesperson=team_member if team_member else None,
                deposit_cents=0,
                created_at=created_at,
            )
            session.add(job)
            session.flush()

            # --- Quote (if quote_price provided) ---
            if quote_cents > 0:
                quote = Quote(
                    tenant_id=tenant_id,
                    repair_job_id=job.id,
                    status="approved" if status == "delivered" else "sent",
                    subtotal_cents=quote_cents,
                    tax_cents=0,
                    total_cents=quote_cents,
                    currency="AUD",
                    created_at=created_at,
                )
                session.add(quote)

            imported += 1
            if imported % 100 == 0:
                print(f"  ...imported {imported} records")

        session.commit()
        print(f"\nDone! Imported {imported} records, skipped {skipped} rows.")
        print(f"  Unique customers: {len(customer_cache)}")


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print(f"Usage: python {sys.argv[0]} <path_to_csv>")
        sys.exit(1)
    run_import(sys.argv[1])
