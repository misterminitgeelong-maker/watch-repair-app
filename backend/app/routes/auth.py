from datetime import datetime, timedelta, timezone
from random import randint
from uuid import UUID
from zoneinfo import ZoneInfo

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlmodel import Session, func, select

from ..config import settings
from ..database import get_session
from ..startup_seed import DEMO_AUTO_KEY_ADDRESSES, apply_demo_auto_key_dispatch_calendar, ensure_demo_b2b_accounts
from ..dependencies import (
    AuthContext,
    PLAN_FEATURES,
    VALID_PLAN_CODES,
    get_auth_context,
    normalize_plan_code,
    require_owner,
    stripe_billing_configured,
)
from ..limiter import limiter
from ..models import (
    AuthSessionResponse,
    AuthSessionSiteOption,
    ActiveSiteSwitchRequest,
    ActiveSiteSwitchResponse,
    AutoKeyJob,
    BootstrapResponse,
    Customer,
    Invoice,
    LoginRequest,
    MultiSiteLoginRequest,
    MultiSiteLoginResponse,
    ParentAccount,
    RefreshRequest,
    ParentAccountEventLog,
    ParentAccountMembership,
    PublicUser,
    RepairJob,
    Shoe,
    ShoeRepairJob,
    TenantEventLog,
    TenantSignupRequest,
    TenantPlanUpdateRequest,
    TenantSignupResponse,
    Tenant,
    TenantBootstrap,
    TokenResponse,
    User,
    Watch,
)
from ..security import create_access_token, create_refresh_token, decode_refresh_token, hash_password, verify_password

router = APIRouter(prefix="/v1/auth", tags=["auth"])

def _normalize_email(value: str) -> str:
    return value.strip().lower()


def _normalize_slug(value: str) -> str:
    return value.strip().lower()


def _normalize_plan_code(value: str | None, default_if_empty: str = "pro") -> str:
    plan_code = normalize_plan_code(value, default_if_empty=default_if_empty)
    if plan_code not in VALID_PLAN_CODES:
        raise HTTPException(status_code=400, detail=f"Unsupported plan code '{value}'")
    return plan_code


def _validate_password_strength(value: str) -> None:
    password = value or ""
    min_len = settings.password_min_length
    if len(password) < min_len:
        raise HTTPException(
            status_code=400,
            detail=f"Password must be at least {min_len} characters",
        )
    if settings.password_require_number and not any(c.isdigit() for c in password):
        raise HTTPException(
            status_code=400,
            detail="Password must contain at least one number",
        )
    if settings.password_require_special:
        special = set("!@#$%^&*()_+-=[]{}|;':\",./<>?")
        if not any(c in special for c in password):
            raise HTTPException(
                status_code=400,
                detail="Password must contain at least one special character (!@#$%^&* etc.)",
            )


def _build_public_user(user: User) -> PublicUser:
    return PublicUser(
        id=user.id,
        tenant_id=user.tenant_id,
        email=user.email,
        full_name=user.full_name,
        role=user.role,
        is_active=user.is_active,
        mobile_commission_rules_json=getattr(user, "mobile_commission_rules_json", None),
    )


def _get_or_create_parent_account(session: Session, owner_email: str, owner_name: str) -> ParentAccount:
    parent = session.exec(
        select(ParentAccount).where(ParentAccount.owner_email == owner_email)
    ).first()
    if parent:
        return parent
    parent = ParentAccount(name=f"{owner_name} Group", owner_email=owner_email)
    session.add(parent)
    session.flush()
    return parent


def _ensure_parent_membership(session: Session, parent: ParentAccount, user: User) -> None:
    existing = session.exec(
        select(ParentAccountMembership)
        .where(ParentAccountMembership.parent_account_id == parent.id)
        .where(ParentAccountMembership.user_id == user.id)
    ).first()
    if existing:
        return
    session.add(
        ParentAccountMembership(
            parent_account_id=parent.id,
            tenant_id=user.tenant_id,
            user_id=user.id,
        )
    )


def _build_available_sites_for_email(session: Session, email: str) -> list[AuthSessionSiteOption]:
    parents = session.exec(select(ParentAccount).where(ParentAccount.owner_email == email)).all()
    if not parents:
        return []

    parent_ids = [p.id for p in parents]
    memberships = session.exec(
        select(ParentAccountMembership)
        .where(ParentAccountMembership.parent_account_id.in_(parent_ids))
        .order_by(ParentAccountMembership.created_at)
    ).all()

    sites: list[AuthSessionSiteOption] = []
    seen: set[UUID] = set()
    for membership in memberships:
        user = session.get(User, membership.user_id)
        if not user or not user.is_active or user.email != email:
            continue
        tenant = session.get(Tenant, membership.tenant_id)
        if not tenant:
            continue
        if tenant.id in seen:
            continue
        seen.add(tenant.id)
        sites.append(
            AuthSessionSiteOption(
                tenant_id=tenant.id,
                tenant_slug=tenant.slug,
                tenant_name=tenant.name,
                user_id=user.id,
                role=user.role,
            )
        )

    return sorted(sites, key=lambda s: (s.tenant_name.lower(), s.tenant_slug.lower()))


def _create_default_owner(session: Session, tenant: Tenant) -> User:
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
    session.refresh(owner)
    return owner


def _build_auth_session_response(session: Session, tenant: Tenant, user: User) -> AuthSessionResponse:
    normalized_plan = _normalize_plan_code(tenant.plan_code)
    enabled = sorted(PLAN_FEATURES.get(normalized_plan, PLAN_FEATURES["pro"]))
    available_sites = _build_available_sites_for_email(session, user.email)
    if not available_sites:
        available_sites = [
            AuthSessionSiteOption(
                tenant_id=tenant.id,
                tenant_slug=tenant.slug,
                tenant_name=tenant.name,
                user_id=user.id,
                role=user.role,
            )
        ]
    cal_tz = settings.schedule_calendar_timezone
    now_shop = datetime.now(ZoneInfo(cal_tz))
    shop_today = now_shop.strftime("%Y-%m-%d")
    return AuthSessionResponse(
        user=_build_public_user(user),
        tenant_id=tenant.id,
        tenant_slug=tenant.slug,
        plan_code=normalized_plan,
        enabled_features=enabled,
        active_site_tenant_id=tenant.id,
        available_sites=available_sites,
        schedule_calendar_timezone=cal_tz,
        shop_calendar_today_ymd=shop_today,
        signup_payment_pending=bool(getattr(tenant, "signup_payment_pending", False)),
    )


def _seed_demo_data_for_tenant(session: Session, tenant: Tenant, actor: User) -> dict[str, int]:
    customer_count = int(
        session.exec(
            select(func.count()).select_from(Customer).where(Customer.tenant_id == tenant.id)
        ).one()
    )

    created_customers = 0
    if customer_count < 8:
        names = [
            "Olivia Carter",
            "Ethan Brooks",
            "Mia Nguyen",
            "Noah Patel",
            "Ava Thompson",
            "Liam O'Connor",
            "Zoe Campbell",
            "Lucas Rivera",
        ]
        for idx in range(customer_count, 8):
            name = names[idx % len(names)]
            customer = Customer(
                tenant_id=tenant.id,
                full_name=name,
                email=f"{name.lower().replace(' ', '.').replace("'", '')}@example.com",
                phone=f"+61400{idx:04d}",
                notes="Seeded demo customer",
                created_at=datetime.now(timezone.utc) - timedelta(days=randint(15, 160)),
            )
            session.add(customer)
            created_customers += 1

    session.flush()

    customers = session.exec(
        select(Customer).where(Customer.tenant_id == tenant.id).order_by(Customer.created_at)
    ).all()

    watches = session.exec(
        select(Watch).where(Watch.tenant_id == tenant.id).order_by(Watch.created_at)
    ).all()
    created_watches = 0
    if len(watches) < 26 and customers:
        watch_specs = [
            ("Omega", "Seamaster", "automatic"),
            ("Rolex", "Datejust", "automatic"),
            ("Seiko", "Prospex", "automatic"),
            ("Longines", "HydroConquest", "automatic"),
            ("Tissot", "PRX", "quartz"),
            ("Hamilton", "Khaki", "automatic"),
            ("Citizen", "Eco-Drive", "solar"),
            ("TAG Heuer", "Carrera", "automatic"),
            ("Orient", "Bambino", "automatic"),
            ("Breitling", "Navitimer", "automatic"),
            ("Grand Seiko", "Snowflake", "automatic"),
            ("Nomos", "Tangente", "automatic"),
            ("Junghans", "Max Bill", "automatic"),
            ("Mido", "Multifort", "automatic"),
            ("Rado", "DiaStar", "automatic"),
            ("Certina", "DS Action", "automatic"),
            ("Christopher Ward", "C63", "automatic"),
            ("Sinn", "556", "automatic"),
            ("Ball", "Engineer", "automatic"),
            ("Frederique Constant", "Classics", "automatic"),
            ("Raymond Weil", "Parsifal", "quartz"),
            ("Movado", "Museum", "quartz"),
            ("Baume & Mercier", "Clifton", "automatic"),
            ("Montblanc", "1858", "automatic"),
            ("Panerai", "Luminor", "automatic"),
        ]
        for idx in range(len(watches), 26):
            brand, model, movement = watch_specs[idx % len(watch_specs)]
            customer = customers[idx % len(customers)]
            watch = Watch(
                tenant_id=tenant.id,
                customer_id=customer.id,
                brand=brand,
                model=model,
                movement_type=movement,
                serial_number=f"DEMO-W-{idx + 1000}",
                condition_notes="General service requested",
                created_at=datetime.now(timezone.utc) - timedelta(days=randint(10, 140)),
            )
            session.add(watch)
            created_watches += 1

    session.flush()

    watches = session.exec(
        select(Watch).where(Watch.tenant_id == tenant.id).order_by(Watch.created_at)
    ).all()

    repair_job_count = int(
        session.exec(
            select(func.count()).select_from(RepairJob).where(RepairJob.tenant_id == tenant.id)
        ).one()
    )
    watch_repair_titles = [
        "Full service and regulation",
        "Crystal replacement",
        "Crown and tube replacement",
        "Movement overhaul",
        "Bracelet resizing",
        "Battery replacement",
        "Waterproof reseal",
        "Dial refinish",
        "Hand replacement",
        "Mainspring replacement",
        "Escapement service",
        "Chronograph service",
        "Date mechanism repair",
        "Case polishing",
        "Gasket replacement",
        "Quartz movement swap",
        "Strap replacement",
        "Timing adjustment",
        "Rotor bearing service",
        "Keyless works repair",
        "Jewelling replacement",
        "Hairspring adjustment",
        "Balance staff replacement",
        "Automatic module service",
        "Shock absorber repair",
        "Complication service",
    ]
    created_repair_jobs = 0
    if repair_job_count < 26 and watches:
        statuses = [
            "awaiting_quote",
            "awaiting_go_ahead",
            "working_on",
            "awaiting_parts",
            "completed",
            "awaiting_collection",
        ]
        priorities = ["low", "normal", "high", "urgent"]
        for idx in range(repair_job_count, 26):
            watch = watches[idx % len(watches)]
            title = watch_repair_titles[idx % len(watch_repair_titles)]
            job = RepairJob(
                tenant_id=tenant.id,
                watch_id=watch.id,
                assigned_user_id=actor.id,
                job_number=f"W-{idx + 1001:04d}",
                title=f"{watch.brand or 'Watch'} {title}",
                description="Amplitude check, gasket refresh, and pressure test.",
                priority=priorities[idx % len(priorities)],
                status=statuses[idx % len(statuses)],
                salesperson=actor.full_name,
                deposit_cents=2500 + (idx * 500),
                pre_quote_cents=9000 + (idx * 1300),
                cost_cents=3500 + (idx * 600),
                created_at=datetime.now(timezone.utc) - timedelta(days=randint(1, 120)),
            )
            session.add(job)
            created_repair_jobs += 1

    # Add demo WorkLog entries for each demo watch RepairJob
    session.flush()
    demo_jobs = session.exec(
        select(RepairJob).where(RepairJob.tenant_id == tenant.id).order_by(RepairJob.created_at)
    ).all()
    from ..models import WorkLog
    for job in demo_jobs:
        # Only add if not already present (guard for idempotency)
        existing_logs = session.exec(
            select(WorkLog).where(WorkLog.tenant_id == tenant.id, WorkLog.repair_job_id == job.id)
        ).all()
        if len(existing_logs) == 0:
            now = datetime.now(timezone.utc)
            wl1 = WorkLog(
                tenant_id=tenant.id,
                repair_job_id=job.id,
                user_id=actor.id,
                note="Initial assessment and intake.",
                minutes_spent=15,
                started_at=job.created_at + timedelta(hours=1),
                ended_at=job.created_at + timedelta(hours=1, minutes=15),
                created_at=job.created_at + timedelta(hours=1, minutes=15),
            )
            wl2 = WorkLog(
                tenant_id=tenant.id,
                repair_job_id=job.id,
                user_id=actor.id,
                note="Movement disassembly and cleaning.",
                minutes_spent=45,
                started_at=job.created_at + timedelta(hours=2),
                ended_at=job.created_at + timedelta(hours=2, minutes=45),
                created_at=job.created_at + timedelta(hours=2, minutes=45),
            )
            session.add(wl1)
            session.add(wl2)

    # Add demo JobStatusHistory entries for each demo watch RepairJob
    from ..models import JobStatusHistory
    for job in demo_jobs:
        # Only add if not already present (guard for idempotency)
        existing_status = session.exec(
            select(JobStatusHistory).where(JobStatusHistory.tenant_id == tenant.id, JobStatusHistory.repair_job_id == job.id)
        ).all()
        if len(existing_status) == 0:
            history = JobStatusHistory(
                tenant_id=tenant.id,
                repair_job_id=job.id,
                old_status=None,
                new_status=job.status,
                changed_by_user_id=actor.id,
                change_note="Job created (demo seed)",
                created_at=job.created_at,
            )
            session.add(history)

    shoes = session.exec(
        select(Shoe).where(Shoe.tenant_id == tenant.id).order_by(Shoe.created_at)
    ).all()
    created_shoes = 0
    if len(shoes) < 24 and customers:
        shoe_specs = [
            ("boots", "RM Williams", "chestnut"),
            ("sneakers", "Nike", "white"),
            ("dress", "Loake", "black"),
            ("heels", "Nine West", "tan"),
            ("sandals", "Birkenstock", "brown"),
            ("work", "Blundstone", "black"),
            ("loafers", "Clarks", "brown"),
            ("oxfords", "Church's", "black"),
            ("ankle boots", "Dr. Martens", "black"),
            ("running", "Asics", "blue"),
            ("slip-on", "Vans", "checkered"),
            ("mules", "Maje", "black"),
            ("derby", "Grenson", "tan"),
            ("chelsea", "Solovair", "black"),
            ("espadrille", "Castaner", "natural"),
            ("riding", "Ariat", "brown"),
            ("trail", "Merrell", "grey"),
            ("ballet flat", "Repetto", "red"),
            ("wedge", "Toms", "navy"),
            ("brogue", "Barker", "brown"),
            ("monk strap", "Meermin", "burgundy"),
            ("driving", "Tod's", "burgundy"),
            ("hiking", "Salomon", "green"),
            ("casual", "Ecco", "grey"),
        ]
        for idx in range(len(shoes), 24):
            shoe_type, brand, color = shoe_specs[idx % len(shoe_specs)]
            customer = customers[idx % len(customers)]
            shoe = Shoe(
                tenant_id=tenant.id,
                customer_id=customer.id,
                shoe_type=shoe_type,
                brand=brand,
                color=color,
                description_notes="General wear and heel replacement needed",
                created_at=datetime.now(timezone.utc) - timedelta(days=randint(5, 90)),
            )
            session.add(shoe)
            created_shoes += 1

    session.flush()

    shoes = session.exec(
        select(Shoe).where(Shoe.tenant_id == tenant.id).order_by(Shoe.created_at)
    ).all()

    shoe_job_count = int(
        session.exec(
            select(func.count()).select_from(ShoeRepairJob).where(ShoeRepairJob.tenant_id == tenant.id)
        ).one()
    )
    shoe_repair_titles = [
        "Heel replacement",
        "Full sole replacement",
        "Resole and heel",
        "Stretch and soften",
        "Clean and polish",
        "Stitching repair",
        "Zip replacement",
        "Insole replacement",
        "Toe cap repair",
        "Welt repair",
        "Upper refurbish",
        "Waterproofing",
        "Dye refresh",
        "Lining repair",
        "Tread replacement",
        "Heel tip replacement",
        "Elastic repair",
        "Buckle replacement",
        "Sole edge repair",
        "Scuff removal",
        "Full restoration",
    ]
    created_shoe_jobs = 0
    if shoe_job_count < 24 and shoes:
        shoe_statuses = ["awaiting_quote", "working_on", "completed", "awaiting_collection"]
        for idx in range(shoe_job_count, 24):
            shoe = shoes[idx % len(shoes)]
            title = shoe_repair_titles[idx % len(shoe_repair_titles)]
            job = ShoeRepairJob(
                tenant_id=tenant.id,
                shoe_id=shoe.id,
                assigned_user_id=actor.id,
                job_number=f"S-{idx + 1001:04d}",
                title=f"{shoe.brand or 'Shoe'} {title}",
                description="Sole edge clean, polish, and heel/sole repair.",
                priority="normal",
                status=shoe_statuses[idx % len(shoe_statuses)],
                salesperson=actor.full_name,
                deposit_cents=1500 + (idx * 300),
                cost_cents=1800 + (idx * 250),
                created_at=datetime.now(timezone.utc) - timedelta(days=randint(1, 80)),
            )
            session.add(job)
            created_shoe_jobs += 1

    auto_key_count = int(
        session.exec(
            select(func.count()).select_from(AutoKeyJob).where(AutoKeyJob.tenant_id == tenant.id)
        ).one()
    )
    created_auto_key_jobs = 0
    if auto_key_count < 18 and customers:
        vehicle_specs = [
            ("Toyota", "Hilux", "TRX-001", "45 Glenferrie Rd, Malvern VIC 3144"),
            ("Ford", "Ranger", "FRD-202", "12 Chapel St, Prahran VIC 3181"),
            ("Mazda", "CX-5", "MZD-303", "8 Bay St, Port Melbourne VIC 3207"),
            ("Hyundai", "i30", "HYU-404", "231 Punt Rd, Richmond VIC 3121"),
            ("Kia", "Sportage", "KIA-505", "67 Burke Rd, Camberwell VIC 3124"),
            ("Honda", "CR-V", "HND-606", "15 Lygon St, Carlton VIC 3053"),
            ("Volkswagen", "Golf", "VW-707", "88 Sydney Rd, Brunswick VIC 3056"),
            ("Subaru", "Outback", "SUB-808", "120 Collins St, Melbourne VIC 3000"),
            ("Nissan", "X-Trail", "NSN-909", "42 Smith St, Collingwood VIC 3066"),
            ("Toyota", "Camry", "TRX-110", "99 Bridge Rd, Richmond VIC 3121"),
            ("Ford", "Focus", "FRD-211", "55 Swan St, Richmond VIC 3121"),
            ("Holden", "Commodore", "HLD-312", "78 Victoria St, Abbotsford VIC 3067"),
        ]
        programming = ["pending", "in_progress", "programmed"]
        for idx in range(auto_key_count, 18):
            make, model, plate, address = vehicle_specs[idx % len(vehicle_specs)]
            customer = customers[idx % len(customers)]
            job = AutoKeyJob(
                tenant_id=tenant.id,
                customer_id=customer.id,
                assigned_user_id=actor.id,
                job_number=f"K-{idx + 1001:04d}",
                title=f"{make} {model} key replacement",
                description="Program spare key and verify immobilizer sync.",
                vehicle_make=make,
                vehicle_model=model,
                vehicle_year=2018 + (idx % 7),
                registration_plate=plate,
                key_type="transponder",
                key_quantity=1 + (idx % 2),
                programming_status=programming[idx % len(programming)],
                status="awaiting_quote",
                priority="normal",
                salesperson=actor.full_name,
                deposit_cents=2000 + (idx * 450),
                cost_cents=2500 + (idx * 500),
                created_at=datetime.now(timezone.utc) - timedelta(days=randint(1, 70)),
                job_address=address,
                scheduled_at=None,
            )
            session.add(job)
            created_auto_key_jobs += 1

    session.flush()

    # Same shop-local day as schedule_calendar_timezone: dispatch + map default date; booked / en_route / on_site for demos
    apply_demo_auto_key_dispatch_calendar(session, tenant.id)

    # Backfill job_address for existing auto key jobs that don't have it (e.g. from before migration)
    existing_auto = session.exec(select(AutoKeyJob).where(AutoKeyJob.tenant_id == tenant.id)).all()
    for job in existing_auto:
        if not job.job_address and job.job_number in DEMO_AUTO_KEY_ADDRESSES:
            job.job_address = DEMO_AUTO_KEY_ADDRESSES[job.job_number]
            session.add(job)

    # Seed customer accounts (B2B / fleet / dealer) for demo — uses shared startup logic
    created_customer_accounts = ensure_demo_b2b_accounts(session, tenant, commit=False)

    session.flush()

    # Seed up to 3 paid invoices linked to demo watch repair jobs (for guided tour step 10+)
    existing_invoice_count = int(
        session.exec(select(func.count()).select_from(Invoice).where(Invoice.tenant_id == tenant.id)).one()
    )
    created_invoices = 0
    if existing_invoice_count < 3:
        repair_jobs_for_invoices = session.exec(
            select(RepairJob).where(RepairJob.tenant_id == tenant.id).order_by(RepairJob.job_number).limit(3)
        ).all()
        to_create = 3 - existing_invoice_count
        for i in range(to_create):
            if i >= len(repair_jobs_for_invoices):
                break
            job = repair_jobs_for_invoices[i]
            total_cents = job.cost_cents or job.pre_quote_cents or 9999
            inv = Invoice(
                tenant_id=tenant.id,
                repair_job_id=job.id,
                quote_id=None,
                invoice_number=f"INV-{existing_invoice_count + i + 1:05d}",
                status="paid",
                subtotal_cents=total_cents,
                tax_cents=0,
                total_cents=total_cents,
                currency="AUD",
                created_at=datetime.now(timezone.utc) - timedelta(days=randint(1, 60)),
            )
            session.add(inv)
            created_invoices += 1

    if any([created_customers, created_watches, created_repair_jobs, created_shoe_jobs, created_auto_key_jobs, created_customer_accounts, created_invoices]):
        session.add(
            TenantEventLog(
                tenant_id=tenant.id,
                actor_user_id=actor.id,
                actor_email=actor.email,
                entity_type="tenant",
                event_type="demo_seeded",
                event_summary=(
                    f"Demo data seeded by {actor.email}: "
                    f"customers={created_customers}, watches={created_watches}, "
                    f"watch_jobs={created_repair_jobs}, shoe_jobs={created_shoe_jobs}, auto_key_jobs={created_auto_key_jobs}, "
                    f"customer_accounts={created_customer_accounts}, invoices={created_invoices}"
                ),
            )
        )

    # Seed fake Inbox messages (quote approvals/declines) for demo
    inbox_count = int(
        session.exec(
            select(func.count())
            .select_from(TenantEventLog)
            .where(TenantEventLog.tenant_id == tenant.id)
            .where(TenantEventLog.event_type.in_(["quote_approved", "quote_declined"]))
        ).one()
    )
    if inbox_count < 6:
        repair_jobs_for_inbox = session.exec(
            select(RepairJob)
            .where(RepairJob.tenant_id == tenant.id)
            .order_by(RepairJob.job_number)
            .limit(8)
        ).all()
        fake_inbox_events = [
            ("quote_approved", "Customer approved quote for job #{job_number}"),
            ("quote_approved", "Customer approved quote for job #{job_number}"),
            ("quote_declined", "Customer declined quote for job #{job_number} — return watch"),
            ("quote_approved", "Customer approved quote for job #{job_number}"),
            ("quote_declined", "Customer declined quote for job #{job_number} — return watch"),
            ("quote_approved", "Customer approved quote for job #{job_number}"),
        ]
        for i, (event_type, template) in enumerate(fake_inbox_events):
            if i >= len(repair_jobs_for_inbox):
                break
            job = repair_jobs_for_inbox[i]
            session.add(
                TenantEventLog(
                    tenant_id=tenant.id,
                    actor_user_id=None,
                    entity_type="repair_job",
                    entity_id=job.id,
                    event_type=event_type,
                    event_summary=template.format(job_number=job.job_number),
                    created_at=datetime.now(timezone.utc) - timedelta(hours=randint(2, 72)),
                )
            )

    session.commit()

    return {
        "customers": created_customers,
        "watches": created_watches,
        "repair_jobs": created_repair_jobs,
        "shoe_jobs": created_shoe_jobs,
        "auto_key_jobs": created_auto_key_jobs,
        "customer_accounts": created_customer_accounts,
        "invoices": created_invoices,
    }


@router.post("/signup", response_model=TenantSignupResponse)
@limiter.limit("10/minute")
def signup(request: Request, payload: TenantSignupRequest, session: Session = Depends(get_session)):
    tenant_slug = _normalize_slug(payload.tenant_slug)
    owner_email = _normalize_email(payload.email)
    owner_name = payload.full_name.strip()
    tenant_name = payload.tenant_name.strip()

    if not tenant_slug:
        raise HTTPException(status_code=400, detail="Tenant slug is required")
    if not tenant_name:
        raise HTTPException(status_code=400, detail="Tenant name is required")
    if not owner_name:
        raise HTTPException(status_code=400, detail="Full name is required")
    if not owner_email or "@" not in owner_email:
        raise HTTPException(status_code=400, detail="A valid email is required")

    _validate_password_strength(payload.password)

    existing_tenant = session.exec(select(Tenant).where(Tenant.slug == tenant_slug)).first()
    if existing_tenant:
        raise HTTPException(status_code=409, detail="Tenant slug already exists")

    plan_code = _normalize_plan_code(payload.plan_code, default_if_empty="basic_watch")

    tenant = Tenant(
        name=tenant_name,
        slug=tenant_slug,
        plan_code=plan_code,
        signup_payment_pending=stripe_billing_configured(),
    )
    session.add(tenant)
    session.flush()

    owner = User(
        tenant_id=tenant.id,
        email=owner_email,
        full_name=owner_name,
        role="owner",
        password_hash=hash_password(payload.password),
    )
    session.add(owner)
    session.commit()
    session.refresh(owner)

    parent = _get_or_create_parent_account(session, owner_email, owner_name)
    _ensure_parent_membership(session, parent, owner)
    session.commit()

    token, expires = create_access_token(tenant.id, owner.id, owner.role)
    refresh_token, refresh_expires = create_refresh_token(tenant.id, owner.id, owner.role)
    return TenantSignupResponse(
        tenant_id=tenant.id,
        user=_build_public_user(owner),
        access_token=token,
        expires_in_seconds=expires,
        refresh_token=refresh_token,
        refresh_expires_in_seconds=refresh_expires,
    )


@router.post("/bootstrap", response_model=BootstrapResponse)
def bootstrap_tenant(payload: TenantBootstrap, session: Session = Depends(get_session)):
    if not settings.allow_public_bootstrap:
        raise HTTPException(status_code=403, detail="Bootstrap is disabled")

    tenant_slug = _normalize_slug(payload.tenant_slug)
    owner_email = _normalize_email(payload.owner_email)
    _validate_password_strength(payload.owner_password)

    existing_tenant = session.exec(select(Tenant).where(Tenant.slug == tenant_slug)).first()
    if existing_tenant:
        raise HTTPException(status_code=409, detail="Tenant slug already exists")

    plan_code = _normalize_plan_code(payload.plan_code, default_if_empty="basic_watch")

    tenant = Tenant(name=payload.tenant_name.strip(), slug=tenant_slug, plan_code=plan_code)
    session.add(tenant)
    session.flush()

    owner = User(
        tenant_id=tenant.id,
        email=owner_email,
        full_name=payload.owner_full_name.strip(),
        role="owner",
        password_hash=hash_password(payload.owner_password),
    )
    session.add(owner)
    session.commit()
    session.refresh(owner)

    parent = _get_or_create_parent_account(session, owner_email, payload.owner_full_name.strip())
    _ensure_parent_membership(session, parent, owner)
    session.commit()

    return BootstrapResponse(tenant_id=tenant.id, owner_user=_build_public_user(owner))



# Dynamically set rate limit based on environment
def get_login_rate_limit():
    return settings.rate_limit_auth_login_test if settings.app_env == "test" else settings.rate_limit_auth_login

@router.post("/login", response_model=TokenResponse)
@limiter.limit(get_login_rate_limit)
def login(request: Request, payload: LoginRequest, session: Session = Depends(get_session)):
    return _login_impl(request, payload, session)

def _login_impl(request: Request, payload: LoginRequest, session: Session = Depends(get_session)):
    tenant = session.exec(select(Tenant).where(Tenant.slug == _normalize_slug(payload.tenant_slug))).first()
    if not tenant:
        raise HTTPException(status_code=401, detail="Invalid credentials")

    user = session.exec(
        select(User).where(User.tenant_id == tenant.id).where(User.email == _normalize_email(payload.email))
    ).first()

    if not user or not user.is_active or not verify_password(payload.password, user.password_hash):
        raise HTTPException(status_code=401, detail="Invalid credentials")

    session.add(
        TenantEventLog(
            tenant_id=tenant.id,
            actor_user_id=user.id,
            actor_email=user.email,
            entity_type="session",
            event_type="login",
            event_summary=f"{user.email} logged in",
        )
    )
    session.commit()

    token, expires = create_access_token(tenant.id, user.id, user.role)
    refresh_token, refresh_expires = create_refresh_token(tenant.id, user.id, user.role)
    return TokenResponse(
        access_token=token,
        expires_in_seconds=expires,
        refresh_token=refresh_token,
        refresh_expires_in_seconds=refresh_expires,
    )


@router.post("/multi-site-login", response_model=MultiSiteLoginResponse)
@limiter.limit("20/minute")
def multi_site_login(request: Request, payload: MultiSiteLoginRequest, session: Session = Depends(get_session)):
    email = _normalize_email(payload.email)
    if not email or "@" not in email:
        raise HTTPException(status_code=400, detail="A valid email is required")

    sites = _build_available_sites_for_email(session, email)
    if not sites:
        raise HTTPException(status_code=401, detail="Invalid credentials")

    valid_sites: list[AuthSessionSiteOption] = []
    for site in sites:
        user = session.get(User, site.user_id)
        if user and verify_password(payload.password, user.password_hash):
            valid_sites.append(site)

    if not valid_sites:
        raise HTTPException(status_code=401, detail="Invalid credentials")

    selected = valid_sites[0]
    # Log login event for the active site
    session.add(
        TenantEventLog(
            tenant_id=selected.tenant_id,
            actor_user_id=selected.user_id,
            actor_email=email,
            entity_type="session",
            event_type="login",
            event_summary=f"{email} logged in via multi-site login",
        )
    )
    session.commit()

    token, expires = create_access_token(selected.tenant_id, selected.user_id, selected.role)
    refresh_token, refresh_expires = create_refresh_token(selected.tenant_id, selected.user_id, selected.role)
    return MultiSiteLoginResponse(
        access_token=token,
        expires_in_seconds=expires,
        refresh_token=refresh_token,
        refresh_expires_in_seconds=refresh_expires,
        active_site_tenant_id=selected.tenant_id,
        available_sites=valid_sites,
    )


@router.post("/demo-seed")
def seed_demo_data(
    auth: AuthContext = Depends(require_owner),
    session: Session = Depends(get_session),
):
    tenant = session.get(Tenant, auth.tenant_id)
    user = session.get(User, auth.user_id)
    if not tenant or not user or user.tenant_id != tenant.id:
        raise HTTPException(status_code=401, detail="Invalid token")

    if settings.app_env.lower() == "production":
        allowed = [
            _normalize_slug(settings.startup_seed_tenant_slug),
            *([_normalize_slug(s) for s in [settings.testing_tenant_slug] if (s or "").strip()]),
        ]
        if tenant.slug not in [a for a in allowed if a]:
            raise HTTPException(status_code=403, detail="Demo seeding is only available for the configured demo or testing tenant")

    created = _seed_demo_data_for_tenant(session, tenant, user)
    return {"ok": True, "created": created}


@router.post("/ensure-testing-tenant")
def ensure_testing_tenant_endpoint(session: Session = Depends(get_session)):
    """Force-create/update the testing tenant from env vars. Use when login fails with 'Invalid credentials'.
    Enable with ALLOW_ENSURE_TESTING_TENANT=true or when APP_ENV is not production."""
    if settings.app_env.lower() == "production" and not settings.allow_ensure_testing_tenant:
        raise HTTPException(status_code=403, detail="Set ALLOW_ENSURE_TESTING_TENANT=true in .env to enable")
    from ..startup_seed import ensure_testing_tenant

    result = ensure_testing_tenant(session)
    if not result:
        return {
            "ok": False,
            "detail": "Testing tenant not configured. Set TESTING_TENANT_SLUG, TESTING_OWNER_EMAIL, TESTING_OWNER_PASSWORD in .env",
        }
    return {"ok": True, "tenant_slug": result.slug, "detail": "Testing tenant ready. Try signing in."}


@router.post("/dev-auto-login", response_model=TokenResponse)
def dev_auto_login(session: Session = Depends(get_session)):
    if settings.app_env.lower() == "production" or not settings.allow_dev_auto_login:
        raise HTTPException(status_code=403, detail="Dev auto-login is disabled")

    tenants = session.exec(select(Tenant)).all()
    if not tenants:
        tenant = Tenant(name=settings.startup_seed_tenant_name, slug=settings.startup_seed_tenant_slug)
        session.add(tenant)
        session.flush()
        user = _create_default_owner(session, tenant)
        token, expires = create_access_token(tenant.id, user.id, user.role)
        refresh_token, refresh_expires = create_refresh_token(tenant.id, user.id, user.role)
        return TokenResponse(
            access_token=token,
            expires_in_seconds=expires,
            refresh_token=refresh_token,
            refresh_expires_in_seconds=refresh_expires,
        )

    selected_tenant = tenants[0]
    selected_count = -1
    for tenant in tenants:
        tenant_job_count = session.exec(
            select(func.count()).select_from(RepairJob).where(RepairJob.tenant_id == tenant.id)
        ).one()
        count = int(tenant_job_count)
        if count > selected_count:
            selected_count = count
            selected_tenant = tenant

    user = session.exec(
        select(User)
        .where(User.tenant_id == selected_tenant.id)
        .where(User.email == settings.startup_seed_owner_email)
        .where(User.is_active)
    ).first()

    if not user:
        user = session.exec(
            select(User)
            .where(User.tenant_id == selected_tenant.id)
            .where(User.is_active)
            .order_by(User.created_at)
        ).first()

    if not user:
        user = _create_default_owner(session, selected_tenant)

    token, expires = create_access_token(selected_tenant.id, user.id, user.role)
    refresh_token, refresh_expires = create_refresh_token(selected_tenant.id, user.id, user.role)
    return TokenResponse(
        access_token=token,
        expires_in_seconds=expires,
        refresh_token=refresh_token,
        refresh_expires_in_seconds=refresh_expires,
    )


@router.post("/refresh", response_model=TokenResponse)
def refresh_tokens(payload: RefreshRequest, session: Session = Depends(get_session)):
    try:
        claims = decode_refresh_token(payload.refresh_token)
    except ValueError:
        raise HTTPException(status_code=401, detail="Invalid or expired refresh token")
    tenant_id = claims.tenant_id
    user_id = claims.user_id

    user = session.get(User, user_id)
    if not user or user.tenant_id != tenant_id or not user.is_active:
        raise HTTPException(status_code=401, detail="Invalid refresh token")

    tenant = session.get(Tenant, tenant_id)
    if not tenant:
        raise HTTPException(status_code=401, detail="Invalid refresh token")

    token, expires = create_access_token(tenant_id, user_id, user.role)
    refresh_token, refresh_expires = create_refresh_token(tenant_id, user_id, user.role)
    return TokenResponse(
        access_token=token,
        expires_in_seconds=expires,
        refresh_token=refresh_token,
        refresh_expires_in_seconds=refresh_expires,
    )


@router.get("/export-my-data", summary="Export tenant data for portability (GDPR-style)")
def export_my_data(
    auth: AuthContext = Depends(get_auth_context),
    session: Session = Depends(get_session),
):
    """Returns a JSON snapshot of the tenant's data (customers, watches, jobs, quotes, invoices) for backup or portability."""
    customers = session.exec(select(Customer).where(Customer.tenant_id == auth.tenant_id)).all()
    watches = session.exec(select(Watch).where(Watch.tenant_id == auth.tenant_id)).all()
    jobs = session.exec(select(RepairJob).where(RepairJob.tenant_id == auth.tenant_id)).all()
    from ..models import Quote, Invoice
    quotes = session.exec(select(Quote).where(Quote.tenant_id == auth.tenant_id)).all()
    invoices = session.exec(select(Invoice).where(Invoice.tenant_id == auth.tenant_id)).all()
    return {
        "exported_at": datetime.now(timezone.utc).isoformat(),
        "customers": [{"id": str(c.id), "full_name": c.full_name, "email": c.email, "phone": c.phone, "created_at": c.created_at.isoformat() if c.created_at else None} for c in customers],
        "watches": [{"id": str(w.id), "customer_id": str(w.customer_id), "brand": w.brand, "model": w.model, "created_at": w.created_at.isoformat() if w.created_at else None} for w in watches],
        "repair_jobs": [{"id": str(j.id), "job_number": j.job_number, "watch_id": str(j.watch_id), "title": j.title, "status": j.status, "created_at": j.created_at.isoformat() if j.created_at else None} for j in jobs],
        "quotes": [{"id": str(q.id), "repair_job_id": str(q.repair_job_id), "status": q.status, "total_cents": q.total_cents, "created_at": q.created_at.isoformat() if q.created_at else None} for q in quotes],
        "invoices": [{"id": str(i.id), "invoice_number": i.invoice_number, "status": i.status, "total_cents": i.total_cents, "created_at": i.created_at.isoformat() if i.created_at else None} for i in invoices],
    }


@router.get("/session", response_model=AuthSessionResponse)
def get_session_info(
    auth: AuthContext = Depends(get_auth_context),
    session: Session = Depends(get_session),
):
    tenant = session.get(Tenant, auth.tenant_id)
    user = session.get(User, auth.user_id)
    if not tenant or not user or user.tenant_id != tenant.id:
        raise HTTPException(status_code=401, detail="Invalid token")

    return _build_auth_session_response(session, tenant, user)


@router.get("/sessions", summary="List known sessions for current user")
def list_sessions(
    auth: AuthContext = Depends(get_auth_context),
    session: Session = Depends(get_session),
):
    """
    Return the currently authenticated session shape.
    Until refresh-token persistence is introduced, we can only reliably surface
    the active token context rather than a full device/session inventory.
    """
    tenant = session.get(Tenant, auth.tenant_id)
    user = session.get(User, auth.user_id)
    if not tenant or not user or user.tenant_id != tenant.id:
        raise HTTPException(status_code=401, detail="Invalid token")

    return {
        "sessions": [
            {
                "session_id": f"active:{auth.tenant_id}:{auth.user_id}",
                "tenant_id": str(auth.tenant_id),
                "user_id": str(auth.user_id),
                "role": auth.role,
                "email": user.email,
                "is_current": True,
            }
        ]
    }


@router.post("/sessions/revoke-others", summary="Revoke all other sessions for current user")
def revoke_other_sessions(auth: AuthContext = Depends(get_auth_context)):
    """
    Refresh tokens are not persisted yet, so there are currently no server-tracked
    "other sessions" to revoke. Returning a deterministic result avoids a silent stub.
    """
    return {"revoked": 0, "message": "No persisted secondary sessions found"}


@router.patch("/session/site", response_model=ActiveSiteSwitchResponse)
def switch_active_site(
    payload: ActiveSiteSwitchRequest,
    auth: AuthContext = Depends(get_auth_context),
    session: Session = Depends(get_session),
):
    current_user = session.get(User, auth.user_id)
    if not current_user or not current_user.is_active:
        raise HTTPException(status_code=401, detail="Invalid token")

    sites = _build_available_sites_for_email(session, current_user.email)
    target = next((s for s in sites if s.tenant_id == payload.tenant_id), None)
    if not target:
        raise HTTPException(status_code=403, detail="Target site is not available for this login")

    parent = session.exec(
        select(ParentAccount).where(ParentAccount.owner_email == current_user.email)
    ).first()
    if parent:
        source_tenant = session.get(Tenant, auth.tenant_id)
        target_tenant = session.get(Tenant, target.tenant_id)
        source_label = source_tenant.slug if source_tenant else str(auth.tenant_id)
        target_label = target_tenant.slug if target_tenant else str(target.tenant_id)
        session.add(
            ParentAccountEventLog(
                parent_account_id=parent.id,
                tenant_id=target.tenant_id,
                actor_user_id=current_user.id,
                actor_email=current_user.email,
                event_type="switch_site",
                event_summary=f"Switched active site from '{source_label}' to '{target_label}'",
            )
        )
        session.commit()

    token, expires = create_access_token(target.tenant_id, target.user_id, target.role)
    refresh_token, refresh_expires = create_refresh_token(target.tenant_id, target.user_id, target.role)
    return ActiveSiteSwitchResponse(
        access_token=token,
        expires_in_seconds=expires,
        refresh_token=refresh_token,
        refresh_expires_in_seconds=refresh_expires,
        active_site_tenant_id=target.tenant_id,
        available_sites=sites,
    )


@router.patch("/session/plan", response_model=AuthSessionResponse)
def update_session_plan(
    payload: TenantPlanUpdateRequest,
    auth: AuthContext = Depends(require_owner),
    session: Session = Depends(get_session),
):
    tenant = session.get(Tenant, auth.tenant_id)
    user = session.get(User, auth.user_id)
    if not tenant or not user or user.tenant_id != tenant.id:
        raise HTTPException(status_code=401, detail="Invalid token")

    old_plan = tenant.plan_code
    tenant.plan_code = _normalize_plan_code(payload.plan_code)
    session.add(
        TenantEventLog(
            tenant_id=tenant.id,
            actor_user_id=user.id,
            actor_email=user.email,
            entity_type="tenant",
            event_type="plan_changed",
            event_summary=f"Plan changed from '{old_plan}' to '{tenant.plan_code}' by {user.email}",
        )
    )
    session.add(tenant)
    session.commit()
    session.refresh(tenant)

    return _build_auth_session_response(session, tenant, user)
