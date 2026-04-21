"""Demo-seed helper extracted from routes/auth.py.

This single function (~480 lines) creates the demo customers/watches/shoes/
auto-key jobs/invoices that populate a freshly-bootstrapped tenant so the
UI has realistic data on first login.

It's kept separate because it has no reason to sit next to signup/login/
refresh logic and inflates the surface area of auth.py's diff history
disproportionately.

Usage: `from .demo_seed import seed_demo_data_for_tenant`.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from random import randint

from sqlmodel import Session, func, select

from ..startup_seed import (
    DEMO_AUTO_KEY_ADDRESSES,
    apply_demo_auto_key_dispatch_calendar,
    ensure_demo_b2b_accounts,
)
from ..models import (
    AutoKeyJob,
    Customer,
    Invoice,
    RepairJob,
    Shoe,
    ShoeRepairJob,
    Tenant,
    TenantEventLog,
    User,
    Watch,
)


def seed_demo_data_for_tenant(session: Session, tenant: Tenant, actor: User) -> dict[str, int]:
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

