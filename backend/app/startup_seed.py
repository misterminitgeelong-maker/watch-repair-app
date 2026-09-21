import csv
import io
import re
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from random import randint
from uuid import uuid4
from zoneinfo import ZoneInfo

import httpx
from sqlmodel import Session, col, func, select

from .config import settings
from .models import PARENT_ROLE_HQ_ADMIN, AutoKeyJob, Customer, CustomerAccount, Invoice, InvoiceNumberCounter, MobileSuburbRoute, ParentAccount, Payment, Quote, RepairJob, ShoeRepairJob, ShoeRepairJobItem, Suburb, Tenant, User, Watch
from .parent_network import grant_parent_role, link_site
from .minit_provision import ensure_minit_pilot_account
from .security import hash_password

# Victorian B2B demo accounts (used at startup and by demo-seed)
DEMO_B2B_ACCOUNT_SPECS: list[dict] = [
    {"name": "Pickles Auto Group", "account_code": "PKL-VIC", "account_type": "Car Auctions", "fleet_size": 450,
     "contact_name": "Jason Mercer", "contact_phone": "0398765432", "contact_email": "jason.mercer@pickles.com.au",
     "billing_address": "211 Boundary Rd, Mordialloc VIC 3195", "payment_terms_days": 30, "billing_cycle": "Monthly", "credit_limit": 15000},
    {"name": "SG Fleet Victoria", "account_code": "SGF-VIC", "account_type": "Corporate Fleet", "fleet_size": 280,
     "contact_name": "Michelle Tan", "contact_phone": "0392001234", "contact_email": "michelle.tan@sgfleet.com",
     "billing_address": "565 Bourke St, Melbourne VIC 3000", "payment_terms_days": 30, "billing_cycle": "Monthly", "credit_limit": 20000},
    {"name": "Hertz Australia", "account_code": "HTZ-AUS", "account_type": "Rental Fleet", "fleet_size": 620,
     "contact_name": "David Nguyen", "contact_phone": "0396541200", "contact_email": "david.nguyen@hertz.com.au",
     "billing_address": "97 Franklin St, Melbourne VIC 3000", "payment_terms_days": 14, "billing_cycle": "Fortnightly", "credit_limit": 25000},
    {"name": "Manheim Auctions", "account_code": "MNH-001", "account_type": "Car Auctions", "fleet_size": 310,
     "contact_name": "Sarah O'Brien", "contact_phone": "0387652100", "contact_email": "sarah.obrien@manheim.com.au",
     "billing_address": "211 Boundary Rd, Mordialloc VIC 3195", "payment_terms_days": 30, "billing_cycle": "Monthly", "credit_limit": 12000},
    {"name": "FleetPartners", "account_code": "FLP-VIC", "account_type": "Corporate Fleet", "fleet_size": 195,
     "contact_name": "Tom Ridley", "contact_phone": "0394321800", "contact_email": "tom.ridley@fleetpartners.com.au",
     "billing_address": "10 Dorcas St, South Melbourne VIC 3205", "payment_terms_days": 30, "billing_cycle": "Monthly", "credit_limit": 18000},
    {"name": "Budget Rent a Car Melbourne", "account_code": "BDG-VIC", "account_type": "Rental Fleet", "fleet_size": 420,
     "contact_name": "Lisa Chen", "contact_phone": "0398765400", "contact_email": "lisa.chen@budget.com.au",
     "billing_address": "115 Elizabeth St, Melbourne VIC 3000", "payment_terms_days": 14, "billing_cycle": "Fortnightly", "credit_limit": 22000},
    {"name": "Toyota Fleet Sales Melbourne", "account_code": "TFS-MEL", "account_type": "Dealership", "fleet_size": 85,
     "contact_name": "Andrew Walsh", "contact_phone": "0398761234", "contact_email": "andrew.walsh@toyotafleet.com.au",
     "billing_address": "350 Warrigal Rd, Cheltenham VIC 3192", "payment_terms_days": 30, "billing_cycle": "Monthly", "credit_limit": 14000},
    {"name": "Apex Auctions Melbourne", "account_code": "APX-VIC", "account_type": "Car Auctions", "fleet_size": 180,
     "contact_name": "Emma Foster", "contact_phone": "0392456789", "contact_email": "emma.foster@apexauctions.com.au",
     "billing_address": "50 Hammond Rd, Dandenong South VIC 3175", "payment_terms_days": 30, "billing_cycle": "Monthly", "credit_limit": 9500},
    {"name": "Novated Lease Co Melbourne", "account_code": "NVL-VIC", "account_type": "Corporate Fleet", "fleet_size": 520,
     "contact_name": "James Park", "contact_phone": "0391234567", "contact_email": "james.park@novatedlease.com.au",
     "billing_address": "200 Collins St, Melbourne VIC 3000", "payment_terms_days": 30, "billing_cycle": "Monthly", "credit_limit": 28000},
    {"name": "Europcar Melbourne", "account_code": "EUR-VIC", "account_type": "Rental Fleet", "fleet_size": 340,
     "contact_name": "Nina Sharma", "contact_phone": "0392345678", "contact_email": "nina.sharma@europcar.com.au",
     "billing_address": "144 Bourke St, Melbourne VIC 3000", "payment_terms_days": 14, "billing_cycle": "Fortnightly", "credit_limit": 19000},
    {"name": "Melbourne City Council Fleet", "account_code": "MCC-FLT", "account_type": "Government Fleet", "fleet_size": 210,
     "contact_name": "Robert Kim", "contact_phone": "0396555555", "contact_email": "r.kim@melbourne.vic.gov.au",
     "billing_address": "200 Little Collins St, Melbourne VIC 3000", "payment_terms_days": 30, "billing_cycle": "Monthly", "credit_limit": 16000},
    {"name": "BMW Group Melbourne", "account_code": "BMW-VIC", "account_type": "Corporate Fleet", "fleet_size": 155,
     "contact_name": "Claire Bennett", "contact_phone": "0398001234", "contact_email": "claire.bennett@bmw.com.au",
     "billing_address": "101 Collins St, Melbourne VIC 3000", "payment_terms_days": 30, "billing_cycle": "Monthly", "credit_limit": 24000},
    {"name": "Grays Online Auctions Melbourne", "account_code": "GRY-VIC", "account_type": "Car Auctions", "fleet_size": 290,
     "contact_name": "Michael Torres", "contact_phone": "0398765432", "contact_email": "michael.torres@grays.com.au",
     "billing_address": "88 Eastern Rd, South Melbourne VIC 3205", "payment_terms_days": 30, "billing_cycle": "Monthly", "credit_limit": 13500},
    {"name": "Redspot Car Rentals Melbourne", "account_code": "RSP-VIC", "account_type": "Rental Fleet", "fleet_size": 380,
     "contact_name": "Daniel Lee", "contact_phone": "0391234567", "contact_email": "daniel.lee@redspot.com.au",
     "billing_address": "230 Spencer St, Melbourne VIC 3000", "payment_terms_days": 14, "billing_cycle": "Fortnightly", "credit_limit": 17500},
    {"name": "Lexus Fleet Melbourne", "account_code": "LEX-VIC", "account_type": "Dealership", "fleet_size": 72,
     "contact_name": "Sophie Adams", "contact_phone": "0395666777", "contact_email": "sophie.adams@lexusmelbourne.com.au",
     "billing_address": "620 Springvale Rd, Glen Waverley VIC 3150", "payment_terms_days": 30, "billing_cycle": "Monthly", "credit_limit": 11000},
    {"name": "Thrifty Car Rental Melbourne", "account_code": "THF-VIC", "account_type": "Rental Fleet", "fleet_size": 510,
     "contact_name": "Kate Morrison", "contact_phone": "0398765432", "contact_email": "kate.morrison@thrifty.com.au",
     "billing_address": "40 Grant St, Port Melbourne VIC 3207", "payment_terms_days": 14, "billing_cycle": "Fortnightly", "credit_limit": 23000},
    {"name": "Suncorp Fleet Melbourne", "account_code": "SUN-VIC", "account_type": "Corporate Fleet", "fleet_size": 165,
     "contact_name": "Paul Williams", "contact_phone": "0393123456", "contact_email": "paul.williams@suncorp.com.au",
     "billing_address": "36 Exhibition St, Melbourne VIC 3000", "payment_terms_days": 30, "billing_cycle": "Monthly", "credit_limit": 15000},
    {"name": "Ross Auctions Geelong", "account_code": "RSS-VIC", "account_type": "Car Auctions", "fleet_size": 125,
     "contact_name": "Amy Johnston", "contact_phone": "0398765432", "contact_email": "amy.johnston@rossauctions.com.au",
     "billing_address": "125 Boundary Rd, North Geelong VIC 3215", "payment_terms_days": 30, "billing_cycle": "Monthly", "credit_limit": 8500},
    {"name": "ANZ Bank Fleet", "account_code": "ANZ-FLT", "account_type": "Corporate Fleet", "fleet_size": 430,
     "contact_name": "Rachel Green", "contact_phone": "0396543210", "contact_email": "rachel.green@anz.com",
     "billing_address": "833 Collins St, Docklands VIC 3008", "payment_terms_days": 30, "billing_cycle": "Monthly", "credit_limit": 32000},
    {"name": "Sixt Rent a Car", "account_code": "SXT-MEL", "account_type": "Rental Fleet", "fleet_size": 275,
     "contact_name": "Oliver Schmidt", "contact_phone": "0398123456", "contact_email": "oliver.schmidt@sixt.com.au",
     "billing_address": "278 Flinders St, Melbourne VIC 3000", "payment_terms_days": 14, "billing_cycle": "Fortnightly", "credit_limit": 18500},
    {"name": "Victorian Government Fleet", "account_code": "VIC-GOV", "account_type": "Government Fleet", "fleet_size": 680,
     "contact_name": "Helen Zhang", "contact_phone": "0396012345", "contact_email": "helen.zhang@vicroads.vic.gov.au",
     "billing_address": "60 Denmark St, Kew VIC 3101", "payment_terms_days": 30, "billing_cycle": "Monthly", "credit_limit": 35000},
    {"name": "Ford Dealer Network VIC", "account_code": "FND-VIC", "account_type": "Dealership", "fleet_size": 95,
     "contact_name": "Mark Thompson", "contact_phone": "0394332211", "contact_email": "mark.thompson@forddealer.net",
     "billing_address": "450 High St, Kew VIC 3101", "payment_terms_days": 30, "billing_cycle": "Monthly", "credit_limit": 12500},
]


_seed_status: dict[str, object] = {
    "enabled": settings.startup_seed_enabled,
    "ran": False,
    "seeded": False,
    "reason": "not_started",
    "csv_path": settings.startup_seed_csv_path,
    "total_rows": 0,
    "imported_rows": 0,
    "skipped_rows": 0,
    "finished_at": None,
}


def get_seed_status() -> dict[str, object]:
    return dict(_seed_status)


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
    "at 3rd party repairer": "at_third_party_repairer",
    "at third party repairer": "at_third_party_repairer",
    "at 3rd party repairer for quoting": "at_third_party_for_quoting",
    "at third party repairer for quoting": "at_third_party_for_quoting",
    "3rd party repairer approved quote": "third_party_quote_approved",
    "third party repairer approved quote": "third_party_quote_approved",
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

    if "original_job_id" not in normalized and row.get(""):
        normalized["original_job_id"] = (row.get("") or "").strip()
    return normalized


def ensure_demo_tenant(session: Session) -> Tenant:
    """Always-on: creates the demo/bootstrap tenant + owner user if absent."""
    return _ensure_tenant_owner(session)


def ensure_testing_tenant(session: Session) -> Tenant | None:
    """Creates a testing tenant + owner if TESTING_* env vars are set. No demo prompts."""
    slug = (settings.testing_tenant_slug or "").strip().lower()
    email = (settings.testing_owner_email or "").strip().lower()
    password = settings.testing_owner_password or ""
    if not slug or "@" not in email or len(password) < 4:
        return None

    tenant = session.exec(select(Tenant).where(Tenant.slug == slug)).first()
    if tenant:
        # Tenant exists: ensure user exists and password matches current env
        owner = session.exec(
            select(User).where(User.tenant_id == tenant.id).where(User.email == email)
        ).first()
        if owner:
            owner.password_hash = hash_password(password)
            owner.is_active = True
            session.add(owner)
        else:
            session.add(
                User(
                    tenant_id=tenant.id,
                    email=email,
                    full_name="Testing",
                    role="owner",
                    password_hash=hash_password(password),
                    is_active=True,
                )
            )
        session.commit()
        session.refresh(tenant)
        return tenant

    tenant = Tenant(
        name=(settings.testing_tenant_name or "Testing").strip() or "Testing",
        slug=slug,
    )
    session.add(tenant)
    session.flush()

    owner = User(
        tenant_id=tenant.id,
        email=email,
        full_name="Testing",
        role="owner",
        password_hash=hash_password(password),
        is_active=True,
    )
    session.add(owner)
    session.commit()
    session.refresh(tenant)
    return tenant


def _ensure_tenant_owner(session: Session) -> Tenant:
    tenant = session.exec(select(Tenant).where(Tenant.slug == settings.startup_seed_tenant_slug)).first()
    if tenant:
        # Ensure demo tenant always has pro plan (full features including customer_accounts)
        if tenant.plan_code != "pro":
            tenant.plan_code = "pro"
            session.add(tenant)
            session.commit()
        return tenant

    tenant = Tenant(
        name=settings.startup_seed_tenant_name,
        slug=settings.startup_seed_tenant_slug,
        plan_code="pro",
    )
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


# Melbourne addresses for demo auto_key_jobs K-1001..K-1018
DEMO_AUTO_KEY_ADDRESSES: dict[str, str] = {
    "K-1001": "45 Glenferrie Rd, Malvern VIC 3144",
    "K-1002": "12 Chapel St, Prahran VIC 3181",
    "K-1003": "8 Bay St, Port Melbourne VIC 3207",
    "K-1004": "231 Punt Rd, Richmond VIC 3121",
    "K-1005": "67 Burke Rd, Camberwell VIC 3124",
    "K-1006": "15 Lygon St, Carlton VIC 3053",
    "K-1007": "88 Sydney Rd, Brunswick VIC 3056",
    "K-1008": "120 Collins St, Melbourne VIC 3000",
    "K-1009": "42 Smith St, Collingwood VIC 3066",
    "K-1010": "99 Bridge Rd, Richmond VIC 3121",
    "K-1011": "55 Swan St, Richmond VIC 3121",
    "K-1012": "78 Victoria St, Abbotsford VIC 3067",
    "K-1013": "200 Gertrude St, Fitzroy VIC 3065",
    "K-1014": "31 Flinders St, Melbourne VIC 3000",
    "K-1015": "400 Victoria Parade, East Melbourne VIC 3002",
    "K-1016": "150 Bridge Rd, Richmond VIC 3121",
    "K-1017": "18 Grey St, St Kilda VIC 3182",
    "K-1018": "900 Dandenong Rd, Malvern East VIC 3145",
}

# Demo-seed mobile jobs: stages for dashboard kanban + dispatch/map (scheduled same shop-local day).
DEMO_MOBILE_DISPATCH_STATUSES: tuple[str, ...] = (
    "awaiting_customer_details",
    "awaiting_customer_details",
    "awaiting_customer_details",
    "pending_booking",
    "pending_booking",
    "booked",
    "booked",
    "booked",
    "booked",
    "booked",
    "en_route",
    "en_route",
    "on_site",
    "go_ahead",
    "working_on",
    "awaiting_quote",
    "working_on",
    "awaiting_go_ahead",
)


def _naive_utc_for_shop_clock(cal_tz: str, y: int, mo: int, d: int, hour: int, minute: int) -> datetime:
    local = datetime(y, mo, d, hour, minute, 0, tzinfo=ZoneInfo(cal_tz))
    return local.astimezone(timezone.utc).replace(tzinfo=None)


def apply_demo_auto_key_dispatch_calendar(session: Session, tenant_id) -> int:
    """
    Align demo job numbers K-1001.. with today's date in schedule_calendar_timezone so Dispatch/Map
    default to today's date; populate confirmed-booking (booked) and field-work statuses for demos.
    """
    cal_tz = settings.schedule_calendar_timezone
    now_local = datetime.now(ZoneInfo(cal_tz))
    y, mo, d = now_local.year, now_local.month, now_local.day
    demo_keys = sorted(DEMO_AUTO_KEY_ADDRESSES.keys(), key=lambda k: int(k.split("-")[1]))
    updated = 0
    for idx, job_number in enumerate(demo_keys):
        job = session.exec(
            select(AutoKeyJob).where(AutoKeyJob.tenant_id == tenant_id, AutoKeyJob.job_number == job_number)
        ).first()
        if not job:
            continue
        address = DEMO_AUTO_KEY_ADDRESSES.get(job_number)
        if address:
            job.job_address = address
        status = (
            DEMO_MOBILE_DISPATCH_STATUSES[idx]
            if idx < len(DEMO_MOBILE_DISPATCH_STATUSES)
            else "awaiting_quote"
        )
        job.status = status
        job.job_type = "All Keys Lost"
        job.visit_order = idx + 1
        start_min = 8 * 60 + idx * 38
        hour, minute = divmod(start_min, 60)
        if hour > 18:
            hour, minute = 18, min(minute, 45)
        job.scheduled_at = _naive_utc_for_shop_clock(cal_tz, y, mo, d, hour, minute)
        session.add(job)
        updated += 1
    return updated


def ensure_demo_auto_key_addresses(session: Session, tenant_id) -> int:
    """Update existing demo auto_key_jobs (K-1001..K-1018) with Melbourne addresses and scheduled_at. Returns count updated."""
    cal_tz = settings.schedule_calendar_timezone
    now_local = datetime.now(ZoneInfo(cal_tz))
    y, mo, d = now_local.year, now_local.month, now_local.day
    updated = 0
    for job_number, address in DEMO_AUTO_KEY_ADDRESSES.items():
        job = session.exec(
            select(AutoKeyJob)
            .where(AutoKeyJob.tenant_id == tenant_id)
            .where(AutoKeyJob.job_number == job_number)
        ).first()
        if job and (not job.job_address or not job.scheduled_at):
            job.job_address = address
            idx = int(job_number.split("-")[1]) - 1001
            start_min = 8 * 60 + idx * 38
            hour, minute = divmod(start_min, 60)
            if hour > 18:
                hour, minute = 18, min(minute, 45)
            job.scheduled_at = _naive_utc_for_shop_clock(cal_tz, y, mo, d, hour, minute)
            session.add(job)
            updated += 1
    return updated


def ensure_demo_b2b_accounts(session: Session, tenant: Tenant, *, commit: bool = True) -> int:
    """Seed Victorian B2B customer accounts for demo tenant. Returns number created. Set commit=False when called from a larger transaction."""
    account_count = int(
        session.exec(
            select(func.count()).select_from(CustomerAccount).where(CustomerAccount.tenant_id == tenant.id)
        ).one()
    )
    created = 0
    if account_count < 20:
        for idx in range(account_count, min(20, account_count + len(DEMO_B2B_ACCOUNT_SPECS))):
            spec = DEMO_B2B_ACCOUNT_SPECS[idx - account_count]
            account = CustomerAccount(
                tenant_id=tenant.id,
                name=spec["name"],
                account_code=spec["account_code"],
                account_type=spec["account_type"],
                fleet_size=spec["fleet_size"],
                contact_name=spec["contact_name"],
                primary_contact_name=spec["contact_name"],
                contact_phone=spec["contact_phone"],
                primary_contact_phone=spec["contact_phone"],
                contact_email=spec["contact_email"],
                billing_address=spec["billing_address"],
                payment_terms_days=spec["payment_terms_days"],
                billing_cycle=spec["billing_cycle"],
                credit_limit=spec["credit_limit"],
                created_at=datetime.now(timezone.utc) - timedelta(days=randint(30, 180)),
            )
            session.add(account)
            created += 1
    else:
        existing_accounts = session.exec(
            select(CustomerAccount)
            .where(CustomerAccount.tenant_id == tenant.id)
            .order_by(CustomerAccount.created_at)
        ).all()
        for i, account in enumerate(existing_accounts[:20]):
            if i < len(DEMO_B2B_ACCOUNT_SPECS):
                spec = DEMO_B2B_ACCOUNT_SPECS[i]
                account.name = spec["name"]
                account.account_code = spec["account_code"]
                account.account_type = spec["account_type"]
                account.fleet_size = spec["fleet_size"]
                account.contact_name = spec["contact_name"]
                account.primary_contact_name = spec["contact_name"]
                account.contact_phone = spec["contact_phone"]
                account.primary_contact_phone = spec["contact_phone"]
                account.contact_email = spec["contact_email"]
                account.billing_address = spec["billing_address"]
                account.payment_terms_days = spec["payment_terms_days"]
                account.billing_cycle = spec["billing_cycle"]
                account.credit_limit = spec["credit_limit"]
                session.add(account)
    if commit:
        session.commit()
    return created


def ensure_platform_admin_account(session: Session) -> None:
    if not settings.platform_admin_enabled:
        return

    email = (settings.platform_admin_email or "").strip().lower()
    password = settings.platform_admin_password or ""
    full_name = (settings.platform_admin_full_name or "Platform Admin").strip() or "Platform Admin"
    tenant_slug = (settings.platform_admin_tenant_slug or "platform").strip().lower() or "platform"
    tenant_name = (settings.platform_admin_tenant_name or "Platform").strip() or "Platform"

    if not email or "@" not in email:
        return
    if len(password) < 8:
        return

    tenant = session.exec(select(Tenant).where(Tenant.slug == tenant_slug)).first()
    if not tenant:
        tenant = Tenant(name=tenant_name, slug=tenant_slug)
        session.add(tenant)
        session.flush()

    user = session.exec(select(User).where(User.email == email)).first()
    if user:
        user.tenant_id = tenant.id
        user.role = "platform_admin"
        user.is_active = True
        user.password_hash = hash_password(password)
        user.full_name = full_name
        session.add(user)
    else:
        session.add(
            User(
                tenant_id=tenant.id,
                email=email,
                full_name=full_name,
                role="platform_admin",
                password_hash=hash_password(password),
                is_active=True,
            )
        )

    session.commit()


def ensure_minit_pilot_if_enabled(session: Session) -> dict[str, object] | None:
    """Create Mister Minit HQ + pilot shops when MINIT_SEED_ENABLED=true."""
    if not settings.minit_seed_enabled:
        return None
    password = settings.minit_hq_owner_password or ""
    if len(password) < 8:
        return {"ok": False, "reason": "minit_hq_owner_password_too_short"}
    result = ensure_minit_pilot_account(
        session,
        parent_name=settings.minit_parent_account_name,
        hq_tenant_slug=settings.minit_hq_tenant_slug.strip().lower(),
        hq_tenant_name=settings.minit_hq_tenant_name,
        hq_owner_email=settings.minit_hq_owner_email,
        hq_owner_password=password,
    )
    return {
        "ok": True,
        "parent_account_id": str(result.parent_account_id),
        "parent_account_name": result.parent_account_name,
        "hq_tenant_slug": result.hq_tenant_slug,
        "hq_owner_email": result.hq_owner_email,
        "created_tenant_slugs": result.created_tenant_slugs,
        "skipped_shop_numbers": result.skipped_shop_numbers,
    }


def ensure_demo_parent_account(session: Session, demo_tenant: Tenant) -> None:
    """Create two extra demo shop tenants and a parent account linking all three.

    All extra tenants share the demo owner email so the standard site-switcher
    works out of the box — no extra credentials needed.
    """
    owner_email = settings.startup_seed_owner_email
    owner_password = settings.startup_seed_owner_password

    extra_sites = [
        ("Mainspring North", "mainspring-north"),
        ("Mainspring South", "mainspring-south"),
    ]

    extra_tenants: list[Tenant] = []
    for name, slug in extra_sites:
        tenant = session.exec(select(Tenant).where(Tenant.slug == slug)).first()
        if not tenant:
            tenant = Tenant(name=name, slug=slug, plan_code="pro")
            session.add(tenant)
            session.flush()
        extra_tenants.append(tenant)

        # Ensure an owner user with the same email as the demo owner exists
        owner = session.exec(
            select(User).where(User.tenant_id == tenant.id).where(User.email == owner_email)
        ).first()
        if not owner:
            session.add(User(
                tenant_id=tenant.id,
                email=owner_email,
                full_name="Demo Owner",
                role="owner",
                password_hash=hash_password(owner_password),
                is_active=True,
            ))
            session.flush()

    session.commit()

    # Create (or find) parent account for the demo owner
    parent = session.exec(
        select(ParentAccount)
        .where(ParentAccount.owner_email == owner_email)
        .order_by(col(ParentAccount.created_at).asc())
    ).first()
    if not parent:
        parent = ParentAccount(name="Mainspring Group", owner_email=owner_email)
        session.add(parent)
        session.flush()

    # Link all three tenants as sites; the demo owner's logins run the network.
    for tenant in [demo_tenant] + extra_tenants:
        owner = session.exec(
            select(User).where(User.tenant_id == tenant.id).where(User.email == owner_email)
        ).first()
        if not owner:
            continue
        link_site(session, parent_id=parent.id, tenant=tenant)
        grant_parent_role(session, parent_id=parent.id, user_id=owner.id, role=PARENT_ROLE_HQ_ADMIN)

    session.flush()

    # Seed demo suburb routes
    north_id = extra_tenants[0].id
    south_id = extra_tenants[1].id
    demo_routes = [
        ("VIC", "richmond", demo_tenant.id),
        ("VIC", "fitzroy", demo_tenant.id),
        ("VIC", "collingwood", demo_tenant.id),
        ("VIC", "bendigo", north_id),
        ("VIC", "ballarat", north_id),
        ("VIC", "frankston", south_id),
        ("VIC", "dandenong", south_id),
    ]
    for state, suburb, target_id in demo_routes:
        exists = session.exec(
            select(MobileSuburbRoute)
            .where(MobileSuburbRoute.parent_account_id == parent.id)
            .where(MobileSuburbRoute.state_code == state)
            .where(MobileSuburbRoute.suburb_normalized == suburb)
        ).first()
        if not exists:
            session.add(MobileSuburbRoute(
                parent_account_id=parent.id,
                state_code=state,
                suburb_normalized=suburb,
                target_tenant_id=target_id,
            ))

    session.commit()


AU_STATE_CODES = {"ACT", "NSW", "NT", "QLD", "SA", "TAS", "VIC", "WA"}
SUBURBS_CSV_URL = "https://raw.githubusercontent.com/matthewproctor/australianpostcodes/master/australian_postcodes.csv"


def ensure_suburbs_seeded(session: Session) -> None:
    """Populate suburbs table from public Australian localities data (matthewproctor/australianpostcodes) if empty."""
    count = session.exec(select(func.count()).select_from(Suburb)).one()
    if int(count) > 0:
        return

    try:
        with httpx.Client(timeout=30.0) as client:
            resp = client.get(SUBURBS_CSV_URL)
            resp.raise_for_status()
            content = resp.text
    except Exception:
        return

    seen: set[tuple[str, str]] = set()
    rows = list(csv.DictReader(io.StringIO(content)))
    for row in rows:
        locality = (row.get("locality") or "").strip()
        state = (row.get("state") or "").strip().upper()
        if not locality or state not in AU_STATE_CODES:
            continue
        name = locality.strip().title() if locality else ""
        if not name or len(name) < 2:
            continue
        key = (name, state)
        if key in seen:
            continue
        seen.add(key)
        session.add(Suburb(name=name, state_code=state))
    session.commit()


def seed_from_csv_if_empty(session: Session) -> None:
    _seed_status["enabled"] = settings.startup_seed_enabled
    _seed_status["csv_path"] = settings.startup_seed_csv_path

    if not settings.startup_seed_enabled:
        _seed_status["ran"] = True
        _seed_status["seeded"] = False
        _seed_status["reason"] = "disabled"
        _seed_status["finished_at"] = datetime.now(timezone.utc).isoformat()
        return

    existing_jobs = session.exec(select(func.count()).select_from(RepairJob)).one()
    if int(existing_jobs) > 0:
        _seed_status["ran"] = True
        _seed_status["seeded"] = False
        _seed_status["reason"] = "database_not_empty"
        _seed_status["finished_at"] = datetime.now(timezone.utc).isoformat()
        return

    csv_path = Path(settings.startup_seed_csv_path)
    if not csv_path.is_file():
        _seed_status["ran"] = True
        _seed_status["seeded"] = False
        _seed_status["reason"] = "csv_not_found"
        _seed_status["finished_at"] = datetime.now(timezone.utc).isoformat()
        return

    with csv_path.open(newline="", encoding="utf-8-sig") as f:
        rows = list(csv.DictReader(f))
    _seed_status["total_rows"] = len(rows)

    if not rows:
        _seed_status["ran"] = True
        _seed_status["seeded"] = False
        _seed_status["reason"] = "csv_empty"
        _seed_status["finished_at"] = datetime.now(timezone.utc).isoformat()
        return

    tenant = _ensure_tenant_owner(session)
    tenant_id = tenant.id

    customer_cache: dict[tuple[str, str | None], Customer] = {}
    job_seq = 0
    imported = 0
    skipped = 0

    # The CSV is a real historical book whose newest entry is fixed in the past,
    # so importing it verbatim leaves every dashboard window empty however long
    # ago that was. Shift the whole book forward by a single offset instead: the
    # newest job lands today and every earlier job keeps its true spacing, so the
    # trends keep the shape of the real history and the demo reads as current
    # whenever it is run. Rows with no usable date are spread over the recent
    # weeks rather than all being stamped with the moment of import.
    parsed_dates = [
        parsed
        for parsed in (_parse_date(_get_first(_normalize_row_keys(dict(r)), ["date_in", "created_at", "created", "intake_date", "date"])) for r in rows)
        if parsed is not None
    ]
    today = datetime.now(timezone.utc).date()
    date_offset = timedelta(days=0)
    if parsed_dates:
        # Anchor on the newest date that is not already in the future: the book
        # contains a few mistyped years, and anchoring on one of those would
        # cancel the shift and leave the rest of the history stale.
        past_dates = [d for d in parsed_dates if d <= today]
        anchor = max(past_dates) if past_dates else min(parsed_dates)
        if anchor < today:
            date_offset = timedelta(days=(today - anchor).days)
    undated_seq = 0
    used_job_numbers: set[str] = set()

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
        # Only a clean ticket number becomes the job number. Ragged rows in the
        # source book spill note text into this column, and a prefix match would
        # happily turn a whole paragraph into "IMP-<paragraph>".
        ticket = (original_job_id or "").strip()
        if re.fullmatch(r"\d{2,12}", ticket):
            job_number = f"IMP-{ticket}"
        else:
            job_number = f"IMP-{job_seq:05d}"
        # The source book reuses a handful of ticket numbers, and job_number is
        # unique per tenant, so a repeat would abort the whole import.
        if job_number in used_job_numbers:
            suffix = 2
            while f"{job_number}-{suffix}" in used_job_numbers:
                suffix += 1
            job_number = f"{job_number}-{suffix}"
        used_job_numbers.add(job_number)

        title = f"Repair: {brand_case}" if brand_case else "Watch Repair"
        if date_in:
            created_at = datetime(date_in.year, date_in.month, date_in.day, tzinfo=timezone.utc) + date_offset
            # A mistyped year must not produce a job created in the future.
            created_at = min(created_at, datetime.now(timezone.utc))
        else:
            # No usable date on the row: place it in the recent past so it still
            # counts as activity without clustering on the import timestamp.
            undated_seq += 1
            created_at = datetime.now(timezone.utc) - timedelta(days=undated_seq % 90, hours=undated_seq % 24)

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
    _seed_status["ran"] = True
    _seed_status["seeded"] = True
    _seed_status["reason"] = "seed_completed"
    _seed_status["imported_rows"] = imported
    _seed_status["skipped_rows"] = skipped
    _seed_status["finished_at"] = datetime.now(timezone.utc).isoformat()


# ---------------------------------------------------------------------------
# Demo financials — invoices, payments and quoted values
#
# Operational demo data (jobs, customers, vehicles) seeded richly, but the money
# did not: three flat $99.99 invoices, no payment rows at all, and no quoted
# value on open jobs. The dashboard therefore opened on a negative gross profit,
# an empty receivables tile and a $0.00 average job, which is the first thing
# anyone sees. These helpers build a coherent ledger instead, anchored to the
# current date so it stays current however long after seeding the demo is shown.
# ---------------------------------------------------------------------------

#: Australian GST. Applied two ways, matching how the amount was set: added on
#: top of a figure quoted ex-GST, or recorded as the component already inside a
#: counter price. Either way the GST report finally has something to total.
_DEMO_GST_RATE_PERCENT = 10

#: Realistic ex-GST watch service prices, used only to give an open job a quoted
#: value when it has none, so "outstanding work value" is not $0.00 beside a
#: count of jobs awaiting approval.
_DEMO_WATCH_PRICE_CENTS = (18500, 24500, 32000, 15000, 45000, 28500, 21000, 38000, 19500, 26000)

#: Counter trade is settled on collection, so most invoices are paid and a small
#: tail is still owed — enough for receivables and the open-invoice count to show
#: something real without implying the shop cannot collect. Only "paid" and
#: "unpaid" exist in the UI, so no other status is used here.
_DEMO_INVOICE_PAID_CYCLE = (True,) * 9 + (False,)

#: Parts and materials as a share of the price. The source book records almost no
#: cost, which would otherwise report a ~98% margin — an artefact of the missing
#: column rather than a real one. This keeps gross profit in the range a service
#: business actually runs at; it is demo data, not a claim about the shop.
_DEMO_COST_SHARE_PERCENT = (32, 28, 35, 25, 38, 30, 27, 34, 29, 36)

#: Ceiling on the demo ledger. The dashboard derives its open-invoice tile from
#: the newest 500 invoices it can fetch, so a larger ledger makes that tile
#: disagree with the unpaid count beside it. Staying under that window keeps
#: every figure on the opening screen consistent with every other.
_DEMO_INVOICE_MAX_TOTAL = 450

#: Upper bound on invoices raised in one pass, so a large imported book cannot
#: turn a startup into a long write. Anything left over is picked up next run.
_DEMO_INVOICE_LIMIT = 450


def _as_utc(value: datetime) -> datetime:
    """Treat a stored timestamp as UTC. SQLite hands back naive datetimes."""
    return value if value.tzinfo is not None else value.replace(tzinfo=timezone.utc)


def _demo_gst_split(subtotal_cents: int) -> tuple[int, int, int]:
    """Return (subtotal, gst, total) for a GST-exclusive amount."""
    tax = int(round(subtotal_cents * _DEMO_GST_RATE_PERCENT / 100))
    return subtotal_cents, tax, subtotal_cents + tax


def _sync_invoice_number_counter(session: Session, tenant_id) -> None:
    """Point the invoice counter past every number already on disk.

    Seeded invoices are written with explicit ``INV-000NN`` numbers but the
    counter that ``/v1/invoices`` allocates from is a separate row. Left alone it
    still starts at 1, so the first invoice raised from the UI collides with a
    seeded number and the request fails on the unique constraint — during a live
    demo, on the "Raise an invoice" step of the launch checklist.
    """
    numbers = session.exec(select(Invoice.invoice_number).where(Invoice.tenant_id == tenant_id)).all()
    highest = 0
    for number in numbers:
        match = re.search(r"(\d+)\s*$", number or "")
        if match:
            highest = max(highest, int(match.group(1)))
    if highest <= 0:
        return

    counter = session.exec(
        select(InvoiceNumberCounter).where(InvoiceNumberCounter.tenant_id == tenant_id)
    ).first()
    if counter is None:
        session.add(InvoiceNumberCounter(tenant_id=tenant_id, next_number=highest + 1))
    elif int(counter.next_number) <= highest:
        counter.next_number = highest + 1
        session.add(counter)
    session.flush()


def ensure_demo_shoe_items(session: Session, tenant_id) -> int:
    """Give every shoe job its catalogue service items. Returns rows created.

    A shoe job with no items shows "0 services · $0.00" on the board, and shoe
    revenue is summed from these rows, so any job left without them is invisible
    to both the board and the reports. Idempotent per job, because the shoe jobs
    themselves are created by a later seeding pass than the startup refresh.
    """
    shoe_jobs = session.exec(
        select(ShoeRepairJob).where(ShoeRepairJob.tenant_id == tenant_id)
    ).all()
    if not shoe_jobs:
        return 0

    already = set(
        session.exec(
            select(ShoeRepairJobItem.shoe_repair_job_id).where(ShoeRepairJobItem.tenant_id == tenant_id)
        ).all()
    )
    created = 0
    for idx, job in enumerate(shoe_jobs):
        if job.id in already:
            continue
        # 1–3 services per job, rotating the catalogue so the mix varies.
        for k in range((idx % 3) + 1):
            item_def = _DEMO_SHOE_ITEMS[(idx + k) % len(_DEMO_SHOE_ITEMS)]
            session.add(ShoeRepairJobItem(
                tenant_id=tenant_id,
                shoe_repair_job_id=job.id,
                catalogue_key=item_def["catalogue_key"],
                catalogue_group=item_def["catalogue_group"],
                item_name=item_def["item_name"],
                pricing_type=item_def["pricing_type"],
                unit_price_cents=item_def["unit_price_cents"],
                quantity=1.0,
            ))
            created += 1
    if created:
        session.flush()
    return created


def ensure_demo_financials(session: Session, tenant: Tenant, *, commit: bool = True) -> dict[str, int]:
    """Build the demo tenant a believable invoice and payment ledger.

    Idempotent: it only invoices approved quotes that have none yet and leaves
    existing rows alone, so it is safe on every startup and every demo login.
    Returns what it created.
    """
    tenant_id = tenant.id
    now = datetime.now(timezone.utc)
    created_invoices = 0
    created_payments = 0
    quoted_jobs = 0

    # ── 1. Quoted value on open jobs ─────────────────────────────────────────
    # "Outstanding work value" and the approval funnel read the quoted figure on
    # jobs still awaiting a decision. Imported jobs carry none, which is why the
    # tile read $0.00 next to a count of jobs waiting.
    open_jobs = session.exec(
        select(RepairJob)
        .where(RepairJob.tenant_id == tenant_id)
        .where(col(RepairJob.status).in_(["awaiting_quote", "awaiting_go_ahead", "awaiting_parts"]))
        .limit(60)
    ).all()
    for idx, job in enumerate(open_jobs):
        if not job.pre_quote_cents:
            job.pre_quote_cents = _DEMO_WATCH_PRICE_CENTS[idx % len(_DEMO_WATCH_PRICE_CENTS)]
            session.add(job)
            quoted_jobs += 1
    if quoted_jobs:
        session.flush()

    # ── 2. Invoice + payment ledger ──────────────────────────────────────────
    # Built from the approved quotes the imported book already carries, which is
    # the product's own path: quote → approved → invoiced → paid. That keeps the
    # money consistent with the work on screen and sized to the real price list,
    # instead of a handful of invented invoices sitting next to 900-odd jobs.
    existing_invoices = int(
        session.exec(select(func.count()).select_from(Invoice).where(Invoice.tenant_id == tenant_id)).one()
    )
    room = max(_DEMO_INVOICE_MAX_TOTAL - existing_invoices, 0)
    quotes_to_invoice = session.exec(
        select(Quote)
        .where(Quote.tenant_id == tenant_id)
        .where(Quote.status == "approved")
        .where(col(Quote.id).not_in(select(Invoice.quote_id).where(col(Invoice.quote_id).is_not(None))))
        .order_by(col(Quote.created_at).desc())
        .limit(min(_DEMO_INVOICE_LIMIT, room))
    ).all() if room else []

    if quotes_to_invoice:
        next_seq = 1
        for number in session.exec(
            select(Invoice.invoice_number).where(Invoice.tenant_id == tenant_id)
        ).all():
            match = re.search(r"(\d+)\s*$", number or "")
            if match:
                next_seq = max(next_seq, int(match.group(1)) + 1)

        for idx, quote in enumerate(quotes_to_invoice):
            total = int(quote.total_cents or 0)
            if total <= 0:
                continue
            # The book's prices are counter prices, so GST sits inside them.
            # Recording the included component keeps the GST report truthful
            # without inflating what the customer was actually charged.
            gst_component = total - int(round(total / (1 + _DEMO_GST_RATE_PERCENT / 100)))
            issued_at = min(_as_utc(quote.created_at) + timedelta(days=1 + (idx % 5)), now)
            is_paid = _DEMO_INVOICE_PAID_CYCLE[idx % len(_DEMO_INVOICE_PAID_CYCLE)]

            # The book has no usable cost column, so a plausible parts cost is
            # derived from the price. Only filled where the job has none.
            job = session.get(RepairJob, quote.repair_job_id)
            if job is not None and not job.cost_cents:
                share = _DEMO_COST_SHARE_PERCENT[idx % len(_DEMO_COST_SHARE_PERCENT)]
                job.cost_cents = int(round(total * share / 100))
                session.add(job)

            invoice = Invoice(
                tenant_id=tenant_id,
                repair_job_id=quote.repair_job_id,
                quote_id=quote.id,
                invoice_number=f"INV-{next_seq + idx:05d}",
                status="paid" if is_paid else "unpaid",
                subtotal_cents=total,
                tax_cents=gst_component,
                gst_enabled=True,
                gst_inclusive=True,
                total_cents=total,
                currency="AUD",
                created_at=issued_at,
            )
            session.add(invoice)
            session.flush()
            created_invoices += 1

            if is_paid:
                # A real payment row, not just a "paid" flag: revenue reporting
                # counts payments first and only falls back to flagged invoices.
                session.add(
                    Payment(
                        tenant_id=tenant_id,
                        invoice_id=invoice.id,
                        amount_cents=total,
                        currency="AUD",
                        status="succeeded",
                        provider="manual",
                        provider_reference=f"DEMO-{invoice.invoice_number}",
                        created_at=min(issued_at + timedelta(days=2 + (idx % 6)), now),
                    )
                )
                created_payments += 1
        session.flush()

    # ── 3. Keep live invoice creation working ────────────────────────────────
    _sync_invoice_number_counter(session, tenant_id)

    if commit:
        session.commit()
    return {
        "invoices": created_invoices,
        "payments": created_payments,
        "quoted_jobs": quoted_jobs,
    }


# ---------------------------------------------------------------------------
# Demo data top-up — runs on every startup, idempotent
# Fixes demo-data gaps without wiping existing tenant data:
#   1. Quote Status Distribution chart empty  → seed demo quotes
#   2. Mobile Services "This Month" = 0       → refresh AutoKeyJob dates
#   3. Shoe board "0 services · $0.00"        → seed ShoeRepairJobItem rows
#   4. Revenue, margin and receivables empty  → build the invoice/payment ledger
# ---------------------------------------------------------------------------

_DEMO_SHOE_ITEMS = [
    {
        "catalogue_key": "heels__block_heels",
        "catalogue_group": "Heels",
        "item_name": "Block Heels",
        "pricing_type": "pair",
        "unit_price_cents": 3500,
    },
    {
        "catalogue_key": "soles__half_sole_leather",
        "catalogue_group": "Soles",
        "item_name": "Half Sole — Leather",
        "pricing_type": "pair",
        "unit_price_cents": 5500,
    },
    {
        "catalogue_key": "cleaning__full_clean_condition",
        "catalogue_group": "Cleaning",
        "item_name": "Full Clean & Condition",
        "pricing_type": "fixed",
        "unit_price_cents": 2500,
    },
    {
        "catalogue_key": "stitching__stitch_resole",
        "catalogue_group": "Stitching",
        "item_name": "Stitch & Resole",
        "pricing_type": "pair",
        "unit_price_cents": 6500,
    },
    {
        "catalogue_key": "heels__stiletto_tip_replacement",
        "catalogue_group": "Heels",
        "item_name": "Stiletto Tip Replacement",
        "pricing_type": "pair",
        "unit_price_cents": 2000,
    },
]

_DEMO_QUOTE_AMOUNTS_CENTS = [18500, 25000, 9500, 14000, 32000, 8500, 21000, 11500, 16000, 27500]
_DEMO_QUOTE_STATUSES = ["sent", "approved", "approved", "declined", "approved", "sent", "approved", "sent", "approved", "declined"]


def ensure_demo_supplemental_data(session: Session) -> None:
    """Idempotently top-up demo data so dashboards look realistic on every startup."""
    tenant = session.exec(select(Tenant).where(Tenant.slug == settings.startup_seed_tenant_slug)).first()
    if not tenant:
        return
    tenant_id = tenant.id

    # ── 1. Demo quotes ────────────────────────────────────────────────────────
    quote_count = int(session.exec(select(func.count()).select_from(Quote).where(Quote.tenant_id == tenant_id)).one())
    if quote_count == 0:
        # Pick up to 10 existing repair jobs to attach demo quotes to
        sample_jobs = session.exec(
            select(RepairJob)
            .where(RepairJob.tenant_id == tenant_id)
            .limit(10)
        ).all()
        now = datetime.now(timezone.utc)
        for i, job in enumerate(sample_jobs):
            amount = _DEMO_QUOTE_AMOUNTS_CENTS[i % len(_DEMO_QUOTE_AMOUNTS_CENTS)]
            status = _DEMO_QUOTE_STATUSES[i % len(_DEMO_QUOTE_STATUSES)]
            created_at = now - timedelta(days=30 - i * 3)
            subtotal, tax, total = _demo_gst_split(amount)
            session.add(Quote(
                tenant_id=tenant_id,
                repair_job_id=job.id,
                status=status,
                subtotal_cents=subtotal,
                tax_cents=tax,
                gst_enabled=True,
                gst_inclusive=False,
                total_cents=total,
                currency="AUD",
                created_at=created_at,
            ))
        session.flush()

    # ── 2. Refresh stale AutoKeyJob dates ────────────────────────────────────
    ak_jobs = session.exec(
        select(AutoKeyJob)
        .where(AutoKeyJob.tenant_id == tenant_id)
        .order_by(AutoKeyJob.created_at.desc())  # type: ignore[arg-type]
        .limit(5)
    ).all()
    if ak_jobs:
        cutoff = datetime.now(timezone.utc) - timedelta(days=45)
        newest_date = max(j.created_at for j in ak_jobs)
        if newest_date.replace(tzinfo=None) < cutoff.replace(tzinfo=None):
            # Spread the 5 most recent demo jobs across the last 28 days
            now = datetime.now(timezone.utc)
            for i, job in enumerate(ak_jobs):
                job.created_at = now - timedelta(days=i * 6)
                session.add(job)
            session.flush()

    # ── 3. Seed ShoeRepairJobItem rows for shoe job board cards ──────────────
    ensure_demo_shoe_items(session, tenant_id)

    # ── 4. Invoices, payments, quoted values and the invoice counter ─────────
    ensure_demo_financials(session, tenant, commit=False)

    session.commit()
