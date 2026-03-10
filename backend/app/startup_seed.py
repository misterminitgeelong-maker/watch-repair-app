import csv
import re
from datetime import date, datetime, timezone
from pathlib import Path
from uuid import uuid4

from sqlmodel import Session, func, select

from .config import settings
from .models import Customer, Quote, RepairJob, Tenant, User, Watch
from .security import hash_password


_STATUS_MAP = {
    "delivered": "collected",
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


def _parse_date(raw: str) -> date | None:
    if not raw or not raw.strip():
        return None
    raw = raw.strip()

    for pattern, groups in [
        (r"^(\\d{1,2})/(\\d{1,2})/(\\d{2})$", "dmy2"),
        (r"^(\\d{1,2})/(\\d{1,2})/(\\d{4})$", "dmy4"),
        (r"^(\\d{4})-(\\d{1,2})-(\\d{1,2})$", "ymd"),
        (r"^(\\d{1,2})\\.(\\d{1,2})\\.(\\d{2,4})$", "dmy_dot"),
        (r"^(\\d{1,2})/+(\\d{1,2})/+(\\d{2,4})$", "dmy_slash"),
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
    digits = re.sub(r"\\D", "", raw.strip())
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
    name = re.sub(r"\\s+", " ", raw.strip())
    lower_name = name.lower()
    invalid_name_fragments = [
        "already collected",
        "has been collected",
        "picked up",
        "cancelled",
        "unknown",
    ]
    if any(fragment in lower_name for fragment in invalid_name_fragments):
        return None
    if re.match(r"^\\d+$", name):
        return None
    if re.match(r"^\\d{1,2}/\\d{1,2}/\\d{2,4}", name):
        return None
    if len(name) < 2:
        return None
    return name


def _get_first(row: dict[str, str], keys: list[str]) -> str:
    for key in keys:
        value = row.get(key)
        if value is not None and str(value).strip():
            return str(value).strip()
    return ""


def _ensure_tenant_owner(session: Session) -> Tenant:
    tenant = session.exec(select(Tenant).where(Tenant.slug == settings.startup_seed_tenant_slug)).first()
    if tenant:
        return tenant

    tenant = Tenant(name=settings.startup_seed_tenant_name, slug=settings.startup_seed_tenant_slug)
    session.add(tenant)
    session.flush()

    owner = User(
        tenant_id=tenant.id,
        email=settings.startup_seed_owner_email,
        full_name="Admin",
        role="owner",
        password_hash=hash_password(settings.startup_seed_owner_password),
        is_active=True,
    )
    session.add(owner)
    session.commit()
    session.refresh(tenant)
    return tenant


def seed_from_csv_if_empty(session: Session) -> None:
    if not settings.startup_seed_enabled:
        return

    existing_jobs = session.exec(select(func.count()).select_from(RepairJob)).one()
    if int(existing_jobs) > 0:
        return

    csv_path = Path(settings.startup_seed_csv_path)
    if not csv_path.is_file():
        return

    with csv_path.open(newline="", encoding="utf-8-sig") as f:
        rows = list(csv.DictReader(f))

    if not rows:
        return

    tenant = _ensure_tenant_owner(session)
    tenant_id = tenant.id

    customer_cache: dict[tuple[str, str | None], Customer] = {}
    job_seq = 0

    for row in rows:
        original_job_id = _get_first(row, ["original_job_id", "job_id", "ticket", "ticket_number", "job_number"])
        team_member = _get_first(row, ["team_member", "salesperson", "staff", "assignee"])
        customer_name_raw = _get_first(row, ["customer_name", "customer", "client", "name"])
        date_in_raw = _get_first(row, ["date_in", "created_at", "created", "intake_date", "date"])
        brand_case = _get_first(row, ["brand_case_numbers", "brand", "watch_brand", "make_model", "model"])
        phone_raw = _get_first(row, ["phone_number", "phone", "mobile", "contact_phone"])
        quote_raw = _get_first(row, ["quote_price", "quote", "estimate", "amount", "total"])
        status_raw = _get_first(row, ["status", "job_status", "repair_status", "state"])
        notes_raw = _get_first(row, ["repair_notes", "notes", "description", "job_notes"])

        customer_name = _clean_name(customer_name_raw)
        if not customer_name:
            customer_name = _clean_name(original_job_id)
            if not customer_name:
                has_meaningful_data = any([brand_case, phone_raw, quote_raw, status_raw, notes_raw, original_job_id])
                if not has_meaningful_data:
                    continue
                customer_name = f"Unknown Customer {original_job_id or uuid4().hex[:8]}"

        phone = _normalize_phone(phone_raw)
        date_in = _parse_date(date_in_raw)
        status = _STATUS_MAP.get((status_raw or "").lower(), "awaiting_go_ahead")
        quote_cents = _dollars_to_cents(quote_raw)

        cache_key = (customer_name.lower(), phone)
        if cache_key in customer_cache:
            customer = customer_cache[cache_key]
        else:
            customer = Customer(tenant_id=tenant_id, full_name=customer_name, phone=phone)
            session.add(customer)
            session.flush()
            customer_cache[cache_key] = customer

        watch = Watch(tenant_id=tenant_id, customer_id=customer.id, brand=brand_case or None)
        session.add(watch)
        session.flush()

        job_seq += 1
        if original_job_id and re.match(r"^\\d+", original_job_id):
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

    session.commit()
