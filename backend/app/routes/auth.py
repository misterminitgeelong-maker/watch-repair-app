from datetime import datetime, timedelta, timezone
from random import randint
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlmodel import Session, func, select

from ..config import settings
from ..database import get_session
from ..dependencies import (
    AuthContext,
    PLAN_FEATURES,
    VALID_PLAN_CODES,
    get_auth_context,
    normalize_plan_code,
    require_owner,
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
    CustomerAccount,
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
    return AuthSessionResponse(
        user=_build_public_user(user),
        tenant_id=tenant.id,
        tenant_slug=tenant.slug,
        plan_code=normalized_plan,
        enabled_features=enabled,
        active_site_tenant_id=tenant.id,
        available_sites=available_sites,
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
    if len(watches) < 8 and customers:
        watch_specs = [
            ("Omega", "Seamaster", "automatic"),
            ("Rolex", "Datejust", "automatic"),
            ("Seiko", "Prospex", "automatic"),
            ("Longines", "HydroConquest", "automatic"),
            ("Tissot", "PRX", "quartz"),
            ("Hamilton", "Khaki", "automatic"),
            ("Citizen", "Eco-Drive", "solar"),
            ("TAG Heuer", "Carrera", "automatic"),
        ]
        for idx in range(len(watches), 8):
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
    created_repair_jobs = 0
    if repair_job_count < 10 and watches:
        statuses = [
            "awaiting_quote",
            "awaiting_go_ahead",
            "working_on",
            "awaiting_parts",
            "completed",
            "awaiting_collection",
        ]
        priorities = ["low", "normal", "high", "urgent"]
        for idx in range(repair_job_count, 10):
            watch = watches[idx % len(watches)]
            job = RepairJob(
                tenant_id=tenant.id,
                watch_id=watch.id,
                assigned_user_id=actor.id,
                job_number=f"W-{idx + 1001:04d}",
                title=f"{watch.brand or 'Watch'} service and regulation",
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
    if len(shoes) < 6 and customers:
        shoe_specs = [
            ("boots", "RM Williams", "chestnut"),
            ("sneakers", "Nike", "white"),
            ("dress", "Loake", "black"),
            ("heels", "Nine West", "tan"),
            ("sandals", "Birkenstock", "brown"),
            ("work", "Blundstone", "black"),
        ]
        for idx in range(len(shoes), 6):
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
    created_shoe_jobs = 0
    if shoe_job_count < 6 and shoes:
        shoe_statuses = ["awaiting_quote", "working_on", "completed", "awaiting_collection"]
        for idx in range(shoe_job_count, 6):
            shoe = shoes[idx % len(shoes)]
            job = ShoeRepairJob(
                tenant_id=tenant.id,
                shoe_id=shoe.id,
                assigned_user_id=actor.id,
                job_number=f"S-{idx + 1001:04d}",
                title=f"{shoe.brand or 'Shoe'} restoration",
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
    if auto_key_count < 5 and customers:
        vehicle_specs = [
            ("Toyota", "Hilux", "TRX-001"),
            ("Ford", "Ranger", "FRD-202"),
            ("Mazda", "CX-5", "MZD-303"),
            ("Hyundai", "i30", "HYU-404"),
            ("Kia", "Sportage", "KIA-505"),
        ]
        programming = ["pending", "in_progress", "programmed"]
        for idx in range(auto_key_count, 5):
            make, model, plate = vehicle_specs[idx % len(vehicle_specs)]
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
                status="working_on" if idx % 2 else "awaiting_quote",
                priority="normal",
                salesperson=actor.full_name,
                deposit_cents=2000 + (idx * 450),
                cost_cents=2500 + (idx * 500),
                created_at=datetime.now(timezone.utc) - timedelta(days=randint(1, 70)),
            )
            session.add(job)
            created_auto_key_jobs += 1

    # Seed customer accounts (B2B / fleet / dealer) for demo
    account_count = int(
        session.exec(
            select(func.count()).select_from(CustomerAccount).where(CustomerAccount.tenant_id == tenant.id)
        ).one()
    )
    created_customer_accounts = 0
    if account_count < 20:
        account_specs = [
            {
                "name": "Pickles Auto Group",
                "account_code": "PKL-VIC",
                "account_type": "Car Auctions",
                "fleet_size": 450,
                "contact_name": "Jason Mercer",
                "contact_phone": "0398765432",
                "contact_email": "jason.mercer@pickles.com.au",
                "billing_address": "211 Boundary Rd, Mordialloc VIC 3195",
                "payment_terms_days": 30,
                "billing_cycle": "Monthly",
                "credit_limit": 15000,
            },
            {
                "name": "SG Fleet Victoria",
                "account_code": "SGF-VIC",
                "account_type": "Corporate Fleet",
                "fleet_size": 280,
                "contact_name": "Michelle Tan",
                "contact_phone": "0392001234",
                "contact_email": "michelle.tan@sgfleet.com",
                "billing_address": "565 Bourke St, Melbourne VIC 3000",
                "payment_terms_days": 30,
                "billing_cycle": "Monthly",
                "credit_limit": 20000,
            },
            {
                "name": "Hertz Australia",
                "account_code": "HTZ-AUS",
                "account_type": "Rental Fleet",
                "fleet_size": 620,
                "contact_name": "David Nguyen",
                "contact_phone": "0396541200",
                "contact_email": "david.nguyen@hertz.com.au",
                "billing_address": "97 Franklin St, Melbourne VIC 3000",
                "payment_terms_days": 14,
                "billing_cycle": "Fortnightly",
                "credit_limit": 25000,
            },
            {
                "name": "Manheim Auctions",
                "account_code": "MNH-001",
                "account_type": "Car Auctions",
                "fleet_size": 310,
                "contact_name": "Sarah O'Brien",
                "contact_phone": "0387652100",
                "contact_email": "sarah.obrien@manheim.com.au",
                "billing_address": "211 Boundary Rd, Mordialloc VIC 3195",
                "payment_terms_days": 30,
                "billing_cycle": "Monthly",
                "credit_limit": 12000,
            },
            {
                "name": "FleetPartners",
                "account_code": "FLP-VIC",
                "account_type": "Corporate Fleet",
                "fleet_size": 195,
                "contact_name": "Tom Ridley",
                "contact_phone": "0394321800",
                "contact_email": "tom.ridley@fleetpartners.com.au",
                "billing_address": "10 Dorcas St, South Melbourne VIC 3205",
                "payment_terms_days": 30,
                "billing_cycle": "Monthly",
                "credit_limit": 18000,
            },
            {
                "name": "Budget Rent a Car Melbourne",
                "account_code": "BDG-VIC",
                "account_type": "Rental Fleet",
                "fleet_size": 420,
                "contact_name": "Lisa Chen",
                "contact_phone": "0398765400",
                "contact_email": "lisa.chen@budget.com.au",
                "billing_address": "115 Elizabeth St, Melbourne VIC 3000",
                "payment_terms_days": 14,
                "billing_cycle": "Fortnightly",
                "credit_limit": 22000,
            },
            {
                "name": "Toyota Fleet Sales Melbourne",
                "account_code": "TFS-MEL",
                "account_type": "Dealership",
                "fleet_size": 85,
                "contact_name": "Andrew Walsh",
                "contact_phone": "0398761234",
                "contact_email": "andrew.walsh@toyotafleet.com.au",
                "billing_address": "350 Warrigal Rd, Cheltenham VIC 3192",
                "payment_terms_days": 30,
                "billing_cycle": "Monthly",
                "credit_limit": 14000,
            },
            {
                "name": "Apex Auctions Melbourne",
                "account_code": "APX-VIC",
                "account_type": "Car Auctions",
                "fleet_size": 180,
                "contact_name": "Emma Foster",
                "contact_phone": "0392456789",
                "contact_email": "emma.foster@apexauctions.com.au",
                "billing_address": "50 Hammond Rd, Dandenong South VIC 3175",
                "payment_terms_days": 30,
                "billing_cycle": "Monthly",
                "credit_limit": 9500,
            },
            {
                "name": "Novated Lease Co Melbourne",
                "account_code": "NVL-VIC",
                "account_type": "Corporate Fleet",
                "fleet_size": 520,
                "contact_name": "James Park",
                "contact_phone": "0391234567",
                "contact_email": "james.park@novatedlease.com.au",
                "billing_address": "200 Collins St, Melbourne VIC 3000",
                "payment_terms_days": 30,
                "billing_cycle": "Monthly",
                "credit_limit": 28000,
            },
            {
                "name": "Europcar Melbourne",
                "account_code": "EUR-VIC",
                "account_type": "Rental Fleet",
                "fleet_size": 340,
                "contact_name": "Nina Sharma",
                "contact_phone": "0392345678",
                "contact_email": "nina.sharma@europcar.com.au",
                "billing_address": "144 Bourke St, Melbourne VIC 3000",
                "payment_terms_days": 14,
                "billing_cycle": "Fortnightly",
                "credit_limit": 19000,
            },
            {
                "name": "Melbourne City Council Fleet",
                "account_code": "MCC-FLT",
                "account_type": "Government Fleet",
                "fleet_size": 210,
                "contact_name": "Robert Kim",
                "contact_phone": "0396555555",
                "contact_email": "r.kim@melbourne.vic.gov.au",
                "billing_address": "200 Little Collins St, Melbourne VIC 3000",
                "payment_terms_days": 30,
                "billing_cycle": "Monthly",
                "credit_limit": 16000,
            },
            {
                "name": "BMW Group Melbourne",
                "account_code": "BMW-VIC",
                "account_type": "Corporate Fleet",
                "fleet_size": 155,
                "contact_name": "Claire Bennett",
                "contact_phone": "0398001234",
                "contact_email": "claire.bennett@bmw.com.au",
                "billing_address": "101 Collins St, Melbourne VIC 3000",
                "payment_terms_days": 30,
                "billing_cycle": "Monthly",
                "credit_limit": 24000,
            },
            {
                "name": "Grays Online Auctions Melbourne",
                "account_code": "GRY-VIC",
                "account_type": "Car Auctions",
                "fleet_size": 290,
                "contact_name": "Michael Torres",
                "contact_phone": "0398765432",
                "contact_email": "michael.torres@grays.com.au",
                "billing_address": "88 Eastern Rd, South Melbourne VIC 3205",
                "payment_terms_days": 30,
                "billing_cycle": "Monthly",
                "credit_limit": 13500,
            },
            {
                "name": "Redspot Car Rentals Melbourne",
                "account_code": "RSP-VIC",
                "account_type": "Rental Fleet",
                "fleet_size": 380,
                "contact_name": "Daniel Lee",
                "contact_phone": "0391234567",
                "contact_email": "daniel.lee@redspot.com.au",
                "billing_address": "230 Spencer St, Melbourne VIC 3000",
                "payment_terms_days": 14,
                "billing_cycle": "Fortnightly",
                "credit_limit": 17500,
            },
            {
                "name": "Lexus Fleet Melbourne",
                "account_code": "LEX-VIC",
                "account_type": "Dealership",
                "fleet_size": 72,
                "contact_name": "Sophie Adams",
                "contact_phone": "0395666777",
                "contact_email": "sophie.adams@lexusmelbourne.com.au",
                "billing_address": "620 Springvale Rd, Glen Waverley VIC 3150",
                "payment_terms_days": 30,
                "billing_cycle": "Monthly",
                "credit_limit": 11000,
            },
            {
                "name": "Thrifty Car Rental Melbourne",
                "account_code": "THF-VIC",
                "account_type": "Rental Fleet",
                "fleet_size": 510,
                "contact_name": "Kate Morrison",
                "contact_phone": "0398765432",
                "contact_email": "kate.morrison@thrifty.com.au",
                "billing_address": "40 Grant St, Port Melbourne VIC 3207",
                "payment_terms_days": 14,
                "billing_cycle": "Fortnightly",
                "credit_limit": 23000,
            },
            {
                "name": "Suncorp Fleet Melbourne",
                "account_code": "SUN-VIC",
                "account_type": "Corporate Fleet",
                "fleet_size": 165,
                "contact_name": "Paul Williams",
                "contact_phone": "0393123456",
                "contact_email": "paul.williams@suncorp.com.au",
                "billing_address": "36 Exhibition St, Melbourne VIC 3000",
                "payment_terms_days": 30,
                "billing_cycle": "Monthly",
                "credit_limit": 15000,
            },
            {
                "name": "Ross Auctions Geelong",
                "account_code": "RSS-VIC",
                "account_type": "Car Auctions",
                "fleet_size": 125,
                "contact_name": "Amy Johnston",
                "contact_phone": "0398765432",
                "contact_email": "amy.johnston@rossauctions.com.au",
                "billing_address": "125 Boundary Rd, North Geelong VIC 3215",
                "payment_terms_days": 30,
                "billing_cycle": "Monthly",
                "credit_limit": 8500,
            },
            {
                "name": "ANZ Bank Fleet",
                "account_code": "ANZ-FLT",
                "account_type": "Corporate Fleet",
                "fleet_size": 430,
                "contact_name": "Rachel Green",
                "contact_phone": "0396543210",
                "contact_email": "rachel.green@anz.com",
                "billing_address": "833 Collins St, Docklands VIC 3008",
                "payment_terms_days": 30,
                "billing_cycle": "Monthly",
                "credit_limit": 32000,
            },
            {
                "name": "Sixt Rent a Car",
                "account_code": "SXT-MEL",
                "account_type": "Rental Fleet",
                "fleet_size": 275,
                "contact_name": "Oliver Schmidt",
                "contact_phone": "0398123456",
                "contact_email": "oliver.schmidt@sixt.com.au",
                "billing_address": "278 Flinders St, Melbourne VIC 3000",
                "payment_terms_days": 14,
                "billing_cycle": "Fortnightly",
                "credit_limit": 18500,
            },
            {
                "name": "Victorian Government Fleet",
                "account_code": "VIC-GOV",
                "account_type": "Government Fleet",
                "fleet_size": 680,
                "contact_name": "Helen Zhang",
                "contact_phone": "0396012345",
                "contact_email": "helen.zhang@vicroads.vic.gov.au",
                "billing_address": "60 Denmark St, Kew VIC 3101",
                "payment_terms_days": 30,
                "billing_cycle": "Monthly",
                "credit_limit": 35000,
            },
            {
                "name": "Ford Dealer Network VIC",
                "account_code": "FND-VIC",
                "account_type": "Dealership",
                "fleet_size": 95,
                "contact_name": "Mark Thompson",
                "contact_phone": "0394332211",
                "contact_email": "mark.thompson@forddealer.net",
                "billing_address": "450 High St, Kew VIC 3101",
                "payment_terms_days": 30,
                "billing_cycle": "Monthly",
                "credit_limit": 12500,
            },
        ]
        for idx in range(account_count, min(20, account_count + len(account_specs))):
            spec = account_specs[idx - account_count]
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
            created_customer_accounts += 1

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

    tenant = Tenant(name=tenant_name, slug=tenant_slug, plan_code=plan_code)
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

    token_subject = f"{tenant.id}:{owner.id}:{owner.role}"
    token, expires = create_access_token(token_subject)
    refresh_token, refresh_expires = create_refresh_token(token_subject)
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
    return "1000/minute" if settings.app_env == "test" else "20/minute"

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

    token_subject = f"{tenant.id}:{user.id}:{user.role}"
    token, expires = create_access_token(token_subject)
    refresh_token, refresh_expires = create_refresh_token(token_subject)
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

    token_subject = f"{selected.tenant_id}:{selected.user_id}:{selected.role}"
    token, expires = create_access_token(token_subject)
    refresh_token, refresh_expires = create_refresh_token(token_subject)
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
        token_subject = f"{tenant.id}:{user.id}:{user.role}"
        token, expires = create_access_token(token_subject)
        refresh_token, refresh_expires = create_refresh_token(token_subject)
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

    token_subject = f"{selected_tenant.id}:{user.id}:{user.role}"
    token, expires = create_access_token(token_subject)
    refresh_token, refresh_expires = create_refresh_token(token_subject)
    return TokenResponse(
        access_token=token,
        expires_in_seconds=expires,
        refresh_token=refresh_token,
        refresh_expires_in_seconds=refresh_expires,
    )


@router.post("/refresh", response_model=TokenResponse)
def refresh_tokens(payload: RefreshRequest, session: Session = Depends(get_session)):
    try:
        subject = decode_refresh_token(payload.refresh_token)
    except ValueError:
        raise HTTPException(status_code=401, detail="Invalid or expired refresh token")

    parts = subject.split(":", maxsplit=2)
    if len(parts) < 2:
        raise HTTPException(status_code=401, detail="Invalid refresh token")
    tenant_id = UUID(parts[0])
    user_id = UUID(parts[1])

    user = session.get(User, user_id)
    if not user or user.tenant_id != tenant_id or not user.is_active:
        raise HTTPException(status_code=401, detail="Invalid refresh token")

    tenant = session.get(Tenant, tenant_id)
    if not tenant:
        raise HTTPException(status_code=401, detail="Invalid refresh token")

    token_subject = f"{tenant_id}:{user_id}:{user.role}"
    token, expires = create_access_token(token_subject)
    refresh_token, refresh_expires = create_refresh_token(token_subject)
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


@router.get("/sessions", summary="List active sessions (stub: returns empty until refresh tokens are stored)")
def list_sessions(auth: AuthContext = Depends(get_auth_context)):
    """Return list of sessions for the current user. Currently a stub; returns empty until refresh tokens are persisted."""
    return {"sessions": []}


@router.post("/sessions/revoke-others", summary="Revoke all other sessions (stub: no-op until refresh tokens are stored)")
def revoke_other_sessions(auth: AuthContext = Depends(get_auth_context)):
    """Revoke every session except the current one. Currently a stub; no-op until refresh tokens are persisted."""
    return {"revoked": 0}


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

    token_subject = f"{target.tenant_id}:{target.user_id}:{target.role}"
    token, expires = create_access_token(token_subject)
    refresh_token, refresh_expires = create_refresh_token(token_subject)
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
