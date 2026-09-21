"""Closed public-demo seed for the interactive walkthrough.

`POST /v1/auth/demo-seed` wipes operational junk/PII on the demo tenant and
replants a connected story: one named customer with a watch job awaiting quote,
a shoe job with services, a key job with programming, quotes in the Quotes
workspace, and a readable unpaid invoice.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from uuid import UUID

from sqlalchemy import delete as sa_delete
from sqlalchemy import update as sa_update
from sqlalchemy import func
from sqlmodel import Session, select

from .config import settings
from .gst import compute_gst_amounts
from .models import (
    Approval,
    Attachment,
    AutoKeyInvoice,
    AutoKeyJob,
    AutoKeyQuote,
    AutoKeyQuoteLineItem,
    Customer,
    CustomerAccount,
    CustomerAccountInvoice,
    CustomerAccountInvoiceLine,
    CustomerAccountMembership,
    CustomerLoyalty,
    CustomerOrder,
    CustomerPortalSession,
    EmailLog,
    ImportLog,
    ImportLogDetail,
    InboundEmail,
    IntakeJob,
    Invoice,
    InvoiceNumberCounter,
    JobMessage,
    JobStatusHistory,
    MobileLeadDispatch,
    Payment,
    PointsLedger,
    Quote,
    QuoteLineItem,
    RepairJob,
    RepairJobNumberCounter,
    RepairQueueDayState,
    Shoe,
    ShoeJobStatusHistory,
    ShoeRepairJob,
    ShoeRepairJobItem,
    ShoeRepairJobNumberCounter,
    ShoeRepairJobShoe,
    ShopMobileBookingRequest,
    SmsLog,
    Tenant,
    TenantEventLog,
    User,
    Watch,
    WorkLog,
)
from .startup_seed import DEMO_AUTO_KEY_ADDRESSES, apply_demo_auto_key_dispatch_calendar

DEMO_STAFF_NAME = "Alex Chen"
STORY_CUSTOMER_EMAIL = "elena.rossi@example.com"
STORY_CUSTOMER_NAME = "Elena Rossi"
STORY_WATCH_JOB_NUMBER = "JOB-10001"
STORY_SHOE_JOB_NUMBER = "SHO-10001"
STORY_KEY_JOB_NUMBER = "K-1001"
STORY_INVOICE_NUMBER = "INV-10001"

_DEMO_CUSTOMERS: list[dict[str, str]] = [
    {
        "full_name": STORY_CUSTOMER_NAME,
        "email": STORY_CUSTOMER_EMAIL,
        "phone": "0400111001",
        "address": "18 High St, Prahran VIC 3181",
        "notes": "Demo story customer — watch, shoe, and mobile work on file.",
    },
    {"full_name": "Marcus Hale", "email": "marcus.hale@example.com", "phone": "0400111002", "address": "44 Chapel St, Windsor VIC 3181", "notes": "Seeded demo customer"},
    {"full_name": "Priya Nair", "email": "priya.nair@example.com", "phone": "0400111003", "address": "9 Bay St, Brighton VIC 3186", "notes": "Seeded demo customer"},
    {"full_name": "Tom Brennan", "email": "tom.brennan@example.com", "phone": "0400111004", "address": "72 Swan St, Richmond VIC 3121", "notes": "Seeded demo customer"},
    {"full_name": "Sophie Nguyen", "email": "sophie.nguyen@example.com", "phone": "0400111005", "address": "15 Lygon St, Carlton VIC 3053", "notes": "Seeded demo customer"},
    {"full_name": "James Okonkwo", "email": "james.okonkwo@example.com", "phone": "0400111006", "address": "201 Bridge Rd, Richmond VIC 3121", "notes": "Seeded demo customer"},
    {"full_name": "Hannah Blake", "email": "hannah.blake@example.com", "phone": "0400111007", "address": "6 Glenferrie Rd, Malvern VIC 3144", "notes": "Seeded demo customer"},
    {"full_name": "Daniel Rossi", "email": "daniel.rossi@example.com", "phone": "0400111008", "address": "88 Smith St, Collingwood VIC 3066", "notes": "Seeded demo customer"},
    {"full_name": "Amelia Chen", "email": "amelia.chen@example.com", "phone": "0400111009", "address": "12 Punt Rd, South Yarra VIC 3141", "notes": "Seeded demo customer"},
    {"full_name": "Noah Patel", "email": "noah.patel@example.com", "phone": "0400111010", "address": "55 Burke Rd, Camberwell VIC 3124", "notes": "Seeded demo customer"},
    {"full_name": "Olivia Carter", "email": "olivia.carter@example.com", "phone": "0400111011", "address": "30 Acland St, St Kilda VIC 3182", "notes": "Seeded demo customer"},
    {"full_name": "Liam Fraser", "email": "liam.fraser@example.com", "phone": "0400111012", "address": "4 Church St, Hawthorn VIC 3122", "notes": "Seeded demo customer"},
]


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _days_ago(days: int, hours: int = 0) -> datetime:
    return _now() - timedelta(days=days, hours=hours)


def _wipe_operational_data(session: Session, tenant_id: UUID) -> None:
    """Remove shop records so the public demo cannot leak junk or live PII.

    Keeps the tenant, users, refresh sessions, and parent-account links.
    """
    auto_key_ids = select(AutoKeyJob.id).where(AutoKeyJob.tenant_id == tenant_id)
    session.execute(sa_update(IntakeJob).where(IntakeJob.resulting_job_id.in_(auto_key_ids)).values(resulting_job_id=None))
    session.execute(sa_update(IntakeJob).where(IntakeJob.claimed_by_tenant_id == tenant_id).values(claimed_by_tenant_id=None, resulting_job_id=None))
    session.execute(
        sa_update(ShopMobileBookingRequest)
        .where(ShopMobileBookingRequest.resulting_auto_key_job_id.in_(auto_key_ids))
        .values(resulting_auto_key_job_id=None)
    )
    session.execute(sa_update(MobileLeadDispatch).where(MobileLeadDispatch.auto_key_job_id.in_(auto_key_ids)).values(auto_key_job_id=None))
    session.execute(sa_update(InboundEmail).where(InboundEmail.auto_key_job_id.in_(auto_key_ids)).values(auto_key_job_id=None))

    import_log_ids = session.exec(select(ImportLog.id).where(ImportLog.tenant_id == tenant_id)).all()
    if import_log_ids:
        session.exec(sa_delete(ImportLogDetail).where(ImportLogDetail.import_log_id.in_(import_log_ids)))
        session.exec(sa_delete(ImportLog).where(ImportLog.id.in_(import_log_ids)))

    session.exec(sa_delete(CustomerPortalSession).where(CustomerPortalSession.tenant_id == tenant_id))
    session.exec(sa_delete(EmailLog).where(EmailLog.tenant_id == tenant_id))
    session.exec(sa_delete(RepairQueueDayState).where(RepairQueueDayState.tenant_id == tenant_id))
    session.exec(sa_delete(ShoeRepairJobNumberCounter).where(ShoeRepairJobNumberCounter.tenant_id == tenant_id))
    session.exec(sa_delete(JobMessage).where(JobMessage.tenant_id == tenant_id))
    session.exec(sa_delete(SmsLog).where(SmsLog.tenant_id == tenant_id))
    session.exec(sa_delete(PointsLedger).where(PointsLedger.tenant_id == tenant_id))
    session.exec(sa_delete(CustomerLoyalty).where(CustomerLoyalty.tenant_id == tenant_id))
    session.exec(sa_delete(CustomerOrder).where(CustomerOrder.tenant_id == tenant_id))
    session.exec(sa_delete(CustomerAccountInvoiceLine).where(CustomerAccountInvoiceLine.tenant_id == tenant_id))
    session.exec(sa_delete(CustomerAccountInvoice).where(CustomerAccountInvoice.tenant_id == tenant_id))
    session.exec(sa_delete(CustomerAccountMembership).where(CustomerAccountMembership.tenant_id == tenant_id))
    session.exec(sa_delete(CustomerAccount).where(CustomerAccount.tenant_id == tenant_id))

    session.exec(sa_delete(Attachment).where(Attachment.tenant_id == tenant_id))
    session.exec(sa_delete(WorkLog).where(WorkLog.tenant_id == tenant_id))
    session.exec(sa_delete(JobStatusHistory).where(JobStatusHistory.tenant_id == tenant_id))
    session.exec(sa_delete(Payment).where(Payment.tenant_id == tenant_id))
    session.exec(sa_delete(QuoteLineItem).where(QuoteLineItem.tenant_id == tenant_id))
    session.exec(sa_delete(Approval).where(Approval.tenant_id == tenant_id))
    session.exec(sa_delete(Invoice).where(Invoice.tenant_id == tenant_id))
    session.exec(sa_delete(Quote).where(Quote.tenant_id == tenant_id))
    session.exec(sa_delete(InvoiceNumberCounter).where(InvoiceNumberCounter.tenant_id == tenant_id))
    session.exec(sa_delete(RepairJobNumberCounter).where(RepairJobNumberCounter.tenant_id == tenant_id))

    session.exec(sa_delete(ShoeJobStatusHistory).where(ShoeJobStatusHistory.tenant_id == tenant_id))
    session.exec(sa_delete(ShoeRepairJobItem).where(ShoeRepairJobItem.tenant_id == tenant_id))
    session.exec(sa_delete(ShoeRepairJobShoe).where(ShoeRepairJobShoe.tenant_id == tenant_id))
    session.exec(sa_delete(ShoeRepairJob).where(ShoeRepairJob.tenant_id == tenant_id))
    session.exec(sa_delete(Shoe).where(Shoe.tenant_id == tenant_id))

    session.exec(sa_delete(AutoKeyQuoteLineItem).where(AutoKeyQuoteLineItem.tenant_id == tenant_id))
    session.exec(sa_delete(AutoKeyInvoice).where(AutoKeyInvoice.tenant_id == tenant_id))
    session.exec(sa_delete(AutoKeyQuote).where(AutoKeyQuote.tenant_id == tenant_id))
    session.exec(sa_delete(AutoKeyJob).where(AutoKeyJob.tenant_id == tenant_id))

    session.exec(sa_delete(RepairJob).where(RepairJob.tenant_id == tenant_id))
    session.exec(sa_delete(Watch).where(Watch.tenant_id == tenant_id))
    session.exec(sa_delete(Customer).where(Customer.tenant_id == tenant_id))
    session.exec(sa_delete(TenantEventLog).where(TenantEventLog.tenant_id == tenant_id))
    session.flush()


def _add_status(session: Session, tenant_id: UUID, job: RepairJob, actor: User, note: str) -> None:
    session.add(
        JobStatusHistory(
            tenant_id=tenant_id,
            repair_job_id=job.id,
            old_status=None,
            new_status=job.status,
            changed_by_user_id=actor.id,
            change_note=note,
            created_at=job.created_at,
        )
    )


def _add_work_log(session: Session, tenant_id: UUID, job: RepairJob, actor: User, note: str, minutes: int, hours_after: int) -> None:
    started = job.created_at + timedelta(hours=hours_after)
    session.add(
        WorkLog(
            tenant_id=tenant_id,
            repair_job_id=job.id,
            user_id=actor.id,
            note=note,
            minutes_spent=minutes,
            started_at=started,
            ended_at=started + timedelta(minutes=minutes),
            created_at=started + timedelta(minutes=minutes),
        )
    )


def _make_quote(
    session: Session,
    *,
    tenant_id: UUID,
    job: RepairJob,
    status: str,
    lines: list[tuple[str, str, int]],
    sent_days_ago: int,
) -> Quote:
    subtotal = sum(cents for _kind, _desc, cents in lines)
    gst_sub, gst_tax, gst_total = compute_gst_amounts(subtotal, True, True)
    sent_at = _days_ago(sent_days_ago, 2) if status != "draft" else None
    quote = Quote(
        tenant_id=tenant_id,
        repair_job_id=job.id,
        status=status,
        subtotal_cents=gst_sub,
        tax_cents=gst_tax,
        gst_enabled=True,
        gst_inclusive=True,
        total_cents=gst_total,
        currency="AUD",
        sent_at=sent_at,
        created_at=_days_ago(sent_days_ago, 3),
    )
    session.add(quote)
    session.flush()
    for kind, desc, cents in lines:
        session.add(
            QuoteLineItem(
                tenant_id=tenant_id,
                quote_id=quote.id,
                item_type=kind,
                description=desc,
                quantity=1,
                unit_price_cents=cents,
                total_price_cents=cents,
            )
        )
    if status == "approved":
        session.add(
            Approval(
                tenant_id=tenant_id,
                quote_id=quote.id,
                decision="approved",
                decided_at=_days_ago(max(sent_days_ago - 1, 0), 4),
            )
        )
    return quote


def _make_invoice(
    session: Session,
    *,
    tenant_id: UUID,
    job: RepairJob,
    quote: Quote | None,
    invoice_number: str,
    status: str,
    days_ago: int,
) -> Invoice:
    if quote is not None:
        sub, tax, total = quote.subtotal_cents, quote.tax_cents, quote.total_cents
        quote_id = quote.id
        currency = quote.currency
    else:
        sub, tax, total = compute_gst_amounts(job.pre_quote_cents or 18500, True, True)
        quote_id = None
        currency = "AUD"
    invoice = Invoice(
        tenant_id=tenant_id,
        repair_job_id=job.id,
        quote_id=quote_id,
        invoice_number=invoice_number,
        status=status,
        subtotal_cents=sub,
        tax_cents=tax,
        gst_enabled=True,
        gst_inclusive=True,
        total_cents=total,
        currency=currency,
        created_at=_days_ago(days_ago),
    )
    session.add(invoice)
    return invoice


def _demo_shop_is_pristine(session: Session, tenant_id: UUID) -> bool:
    """True when the demo already holds exactly the story this function plants
    and nothing has been added to it.

    The demo tenant is shared, so two people starting a walkthrough at the same
    time both ask for a reseed — and the second one wipes the first one's shop
    out from under them mid-demo. When the shop is already the untouched story
    there is nothing to rebuild, so the second visitor leaves it alone."""
    customer_count = int(
        session.exec(select(func.count()).select_from(Customer).where(Customer.tenant_id == tenant_id)).one()
    )
    if customer_count != len(_DEMO_CUSTOMERS):
        return False
    # The story job carries a fixed number, so its presence says the seed ran;
    # the counts above say nobody has added to it since.
    story_job = session.exec(
        select(RepairJob)
        .where(RepairJob.tenant_id == tenant_id)
        .where(RepairJob.job_number == STORY_WATCH_JOB_NUMBER)
    ).first()
    return story_job is not None


def reset_and_seed_demo_shop(session: Session, tenant: Tenant, actor: User) -> dict[str, int]:
    """Wipe operational demo data and plant the connected walkthrough story."""
    if _demo_shop_is_pristine(session, tenant.id):
        return {"skipped": 1}
    _wipe_operational_data(session, tenant.id)
    now = _now()

    tenant.name = "Mainspring Demo"
    tenant.shop_email = "hello@example.com"
    tenant.shop_phone = "03 9000 1000"
    tenant.shop_number = None
    session.add(tenant)

    customers: list[Customer] = []
    for idx, spec in enumerate(_DEMO_CUSTOMERS):
        customer = Customer(
            tenant_id=tenant.id,
            full_name=spec["full_name"],
            email=spec["email"],
            phone=spec["phone"],
            address=spec["address"],
            notes=spec["notes"],
            created_at=_days_ago(0 if idx == 0 else idx + 2),
        )
        session.add(customer)
        customers.append(customer)
    session.flush()
    elena = customers[0]
    supporting = customers[1:]

    # --- Watches + jobs (recent dates, modest cost vs quote) ---
    story_watch = Watch(
        tenant_id=tenant.id,
        customer_id=elena.id,
        brand="Omega",
        model="Seamaster",
        movement_type="automatic",
        serial_number="DEMO-W-10001",
        condition_notes="Crystal scuffed; running 12s/day fast. Customer wants a hand refit after service.",
        created_at=_days_ago(4),
    )
    session.add(story_watch)
    session.flush()

    story_watch_job = RepairJob(
        tenant_id=tenant.id,
        watch_id=story_watch.id,
        assigned_user_id=actor.id,
        job_number=STORY_WATCH_JOB_NUMBER,
        title="Omega Seamaster hand refit",
        description="Intake complete. Quote the hand set and pressure test, then wait for go-ahead.",
        priority="normal",
        status="awaiting_quote",
        salesperson=DEMO_STAFF_NAME,
        deposit_cents=0,
        pre_quote_cents=29500,
        cost_cents=8200,
        created_at=_days_ago(3, 4),
    )
    session.add(story_watch_job)
    session.flush()
    _add_status(session, tenant.id, story_watch_job, actor, "Job created (demo seed)")
    _add_work_log(session, tenant.id, story_watch_job, actor, "Intake photos and condition notes.", 20, 1)

    extra_watch_specs = [
        ("Rolex", "Datejust", "automatic", "Full service and regulation", "awaiting_go_ahead", 2, 38500, 14000),
        ("Seiko", "Prospex", "automatic", "Crystal replacement", "working_on", 5, 16500, 5200),
        ("Tissot", "PRX", "quartz", "Battery replacement", "completed", 8, 8900, 1800),
        ("Longines", "HydroConquest", "automatic", "Waterproof reseal", "awaiting_collection", 6, 21000, 6400),
        ("Hamilton", "Khaki", "automatic", "Crown and tube replacement", "awaiting_quote", 1, 14500, 4100),
        ("Citizen", "Eco-Drive", "solar", "Strap replacement", "go_ahead", 4, 7200, 1900),
        ("TAG Heuer", "Carrera", "automatic", "Chronograph service", "working_on", 7, 42000, 16800),
        ("Orient", "Bambino", "automatic", "Mainspring replacement", "completed", 10, 19500, 6100),
        ("Grand Seiko", "Snowflake", "automatic", "Timing adjustment", "awaiting_parts", 3, 24000, 7800),
    ]
    extra_watch_jobs: list[RepairJob] = []
    for idx, (brand, model, movement, title, status, age, quote_cents, cost_cents) in enumerate(extra_watch_specs):
        owner = supporting[idx % len(supporting)]
        watch = Watch(
            tenant_id=tenant.id,
            customer_id=owner.id,
            brand=brand,
            model=model,
            movement_type=movement,
            serial_number=f"DEMO-W-{1010 + idx}",
            condition_notes="General service requested",
            created_at=_days_ago(age + 1),
        )
        session.add(watch)
        session.flush()
        job = RepairJob(
            tenant_id=tenant.id,
            watch_id=watch.id,
            assigned_user_id=actor.id,
            job_number=f"JOB-{10002 + idx:05d}",
            title=f"{brand} {title}",
            description="Amplitude check, gasket refresh, and pressure test.",
            priority="normal" if idx % 4 else "high",
            status=status,
            salesperson=DEMO_STAFF_NAME,
            deposit_cents=2500 if status != "awaiting_quote" else 0,
            pre_quote_cents=quote_cents,
            cost_cents=cost_cents,
            created_at=_days_ago(age),
        )
        session.add(job)
        extra_watch_jobs.append(job)
    session.flush()
    for job in extra_watch_jobs:
        _add_status(session, tenant.id, job, actor, "Job created (demo seed)")
        _add_work_log(session, tenant.id, job, actor, "Initial assessment and intake.", 15, 1)
        if job.status not in {"awaiting_quote"}:
            _add_work_log(session, tenant.id, job, actor, "Movement inspection on the bench.", 35, 3)

    # Elena also has a completed billed job so the invoice has a real customer.
    billed_watch = Watch(
        tenant_id=tenant.id,
        customer_id=elena.id,
        brand="Tissot",
        model="Gentleman",
        movement_type="automatic",
        serial_number="DEMO-W-1099",
        condition_notes="Collected after service.",
        created_at=_days_ago(12),
    )
    session.add(billed_watch)
    session.flush()
    billed_job = RepairJob(
        tenant_id=tenant.id,
        watch_id=billed_watch.id,
        assigned_user_id=actor.id,
        job_number="JOB-10020",
        title="Tissot Gentleman full service",
        description="Service complete. Invoice ready for payment.",
        priority="normal",
        status="awaiting_collection",
        salesperson=DEMO_STAFF_NAME,
        deposit_cents=5000,
        pre_quote_cents=38500,
        cost_cents=14200,
        created_at=_days_ago(11),
    )
    session.add(billed_job)
    session.flush()
    _add_status(session, tenant.id, billed_job, actor, "Job created (demo seed)")
    _add_work_log(session, tenant.id, billed_job, actor, "Full service complete and timed.", 90, 20)

    # --- Quotes (visible on /quotes) ---
    sent_story_quote = _make_quote(
        session,
        tenant_id=tenant.id,
        job=story_watch_job,
        status="sent",
        lines=[
            ("labor", "Hand set refit and regulation", 18500),
            ("part", "Gasket set", 4500),
            ("fee", "Pressure test", 6500),
        ],
        sent_days_ago=1,
    )
    approved_invoice_quote = _make_quote(
        session,
        tenant_id=tenant.id,
        job=billed_job,
        status="approved",
        lines=[
            ("labor", "Full service and regulation", 28000),
            ("part", "Gasket and oil set", 6500),
            ("fee", "Timing and pressure test", 4000),
        ],
        sent_days_ago=8,
    )
    extra_quote_jobs = [
        extra_watch_jobs[0],  # awaiting_go_ahead — sent
        extra_watch_jobs[2],  # completed — approved
        extra_watch_jobs[5],  # go_ahead — approved
        extra_watch_jobs[4],  # awaiting_quote — sent
        extra_watch_jobs[7],  # completed — declined
    ]
    _make_quote(
        session, tenant_id=tenant.id, job=extra_quote_jobs[0], status="sent",
        lines=[("labor", "Full service", 32000), ("part", "Crystal", 6500)], sent_days_ago=2,
    )
    paid_quote_a = _make_quote(
        session, tenant_id=tenant.id, job=extra_quote_jobs[1], status="approved",
        lines=[("labor", "Battery and gasket", 6500), ("part", "Strap", 2400)], sent_days_ago=7,
    )
    paid_quote_b = _make_quote(
        session, tenant_id=tenant.id, job=extra_quote_jobs[2], status="approved",
        lines=[("labor", "Strap replacement", 4800), ("part", "Spring bars", 900)], sent_days_ago=5,
    )
    _make_quote(
        session, tenant_id=tenant.id, job=extra_quote_jobs[3], status="sent",
        lines=[("labor", "Crown and tube", 9800), ("part", "Tube", 2200)], sent_days_ago=3,
    )
    declined = _make_quote(
        session, tenant_id=tenant.id, job=extra_quote_jobs[4], status="declined",
        lines=[("labor", "Mainspring replacement", 14500)], sent_days_ago=6,
    )
    declined.status = "declined"
    session.add(declined)

    # --- Invoices: one readable unpaid (tour) plus paid ones for modest profit ---
    story_invoice = _make_invoice(
        session,
        tenant_id=tenant.id,
        job=billed_job,
        quote=approved_invoice_quote,
        invoice_number=STORY_INVOICE_NUMBER,
        status="unpaid",
        days_ago=2,
    )
    paid_a = _make_invoice(
        session, tenant_id=tenant.id, job=extra_quote_jobs[1], quote=paid_quote_a,
        invoice_number="INV-10002", status="paid", days_ago=6,
    )
    paid_b = _make_invoice(
        session, tenant_id=tenant.id, job=extra_quote_jobs[2], quote=paid_quote_b,
        invoice_number="INV-10003", status="paid", days_ago=4,
    )
    session.add(InvoiceNumberCounter(tenant_id=tenant.id, next_number=4, created_at=now, updated_at=now))

    # --- Shoes ---
    story_shoe = Shoe(
        tenant_id=tenant.id,
        customer_id=elena.id,
        shoe_type="boots",
        brand="R.M. Williams",
        color="chestnut",
        description_notes="Worn heels, still structurally sound.",
        created_at=_days_ago(5),
    )
    story_shoe_pair_two = Shoe(
        tenant_id=tenant.id,
        customer_id=elena.id,
        shoe_type="riding boots",
        brand="R.M. Williams",
        color="black",
        description_notes="Second pair on the same ticket.",
        created_at=_days_ago(5),
    )
    session.add(story_shoe)
    session.add(story_shoe_pair_two)
    session.flush()
    story_shoe_job = ShoeRepairJob(
        tenant_id=tenant.id,
        shoe_id=story_shoe.id,
        assigned_user_id=actor.id,
        job_number=STORY_SHOE_JOB_NUMBER,
        title="Heel replacement",
        description="Two pairs: chestnut dress boots and black riding boots. Heels on both.",
        priority="normal",
        status="go_ahead",
        salesperson=DEMO_STAFF_NAME,
        deposit_cents=4000,
        cost_cents=5800,
        quote_status="approved",
        created_at=_days_ago(4),
    )
    session.add(story_shoe_job)
    session.flush()
    session.add(
        ShoeRepairJobShoe(
            tenant_id=tenant.id,
            shoe_repair_job_id=story_shoe_job.id,
            shoe_id=story_shoe_pair_two.id,
            sort_order=1,
        )
    )
    session.add(
        ShoeRepairJobItem(
            tenant_id=tenant.id,
            shoe_repair_job_id=story_shoe_job.id,
            catalogue_key="heels__all_pegged_pin_heels",
            catalogue_group="heels",
            item_name="Heel replacement",
            pricing_type="pair",
            unit_price_cents=6500,
            quantity=1,
            notes="Chestnut dress boots",
        )
    )
    session.add(
        ShoeRepairJobItem(
            tenant_id=tenant.id,
            shoe_repair_job_id=story_shoe_job.id,
            catalogue_key="soles__half_soles",
            catalogue_group="soles",
            item_name="Half soles",
            pricing_type="pair",
            unit_price_cents=8900,
            quantity=1,
            notes="Chestnut dress boots",
        )
    )
    session.add(
        ShoeRepairJobItem(
            tenant_id=tenant.id,
            shoe_repair_job_id=story_shoe_job.id,
            catalogue_key="heels__all_pegged_pin_heels",
            catalogue_group="heels",
            item_name="Heel replacement",
            pricing_type="pair",
            unit_price_cents=6500,
            quantity=1,
            notes="Black riding boots",
        )
    )
    session.add(
        ShoeJobStatusHistory(
            tenant_id=tenant.id,
            shoe_repair_job_id=story_shoe_job.id,
            old_status=None,
            new_status="go_ahead",
            changed_by_user_id=actor.id,
            change_note="Job created (demo seed)",
            created_at=story_shoe_job.created_at,
        )
    )

    extra_shoe_specs = [
        ("sneakers", "Nike", "white", "Full sole replacement", "awaiting_quote", 2, 2200),
        ("dress", "Loake", "black", "Resole and heel", "working_on", 3, 4100),
        ("work", "Blundstone", "black", "Stitching repair", "awaiting_collection", 6, 1800),
        ("loafers", "Clarks", "brown", "Clean and polish", "completed", 8, 900),
        ("ankle boots", "Dr. Martens", "black", "Welt repair", "go_ahead", 4, 2700),
        ("oxfords", "Church's", "black", "Heel tip replacement", "working_on", 1, 1500),
    ]
    for idx, (shoe_type, brand, color, title, status, age, cost) in enumerate(extra_shoe_specs):
        owner = supporting[(idx + 1) % len(supporting)]
        shoe = Shoe(
            tenant_id=tenant.id,
            customer_id=owner.id,
            shoe_type=shoe_type,
            brand=brand,
            color=color,
            description_notes="General wear",
            created_at=_days_ago(age + 1),
        )
        session.add(shoe)
        session.flush()
        job = ShoeRepairJob(
            tenant_id=tenant.id,
            shoe_id=shoe.id,
            assigned_user_id=actor.id,
            job_number=f"SHO-{10002 + idx:05d}",
            title=title,
            description="Sole edge clean, polish, and heel/sole repair.",
            priority="normal",
            status=status,
            salesperson=DEMO_STAFF_NAME,
            deposit_cents=1500,
            cost_cents=cost,
            quote_status="sent" if status == "awaiting_quote" else "approved",
            created_at=_days_ago(age),
        )
        session.add(job)
        session.flush()
        session.add(
            ShoeRepairJobItem(
                tenant_id=tenant.id,
                shoe_repair_job_id=job.id,
                catalogue_key="heels__standard",
                catalogue_group="heels",
                item_name=title,
                pricing_type="pair",
                unit_price_cents=cost + 4000,
                quantity=1,
            )
        )

    # --- Mobile / auto-key ---
    story_key = AutoKeyJob(
        tenant_id=tenant.id,
        customer_id=elena.id,
        assigned_user_id=actor.id,
        job_number=STORY_KEY_JOB_NUMBER,
        title="Honda Civic duplicate key",
        description="Program a spare transponder and verify immobilizer sync.",
        vehicle_make="Honda",
        vehicle_model="Civic",
        vehicle_year=2018,
        registration_plate="ELENA1",
        key_type="transponder",
        job_type="Duplicate key",
        key_quantity=1,
        programming_status="in_progress",
        status="booked",
        priority="normal",
        salesperson=DEMO_STAFF_NAME,
        deposit_cents=0,
        cost_cents=3200,
        created_at=_days_ago(1, 3),
        job_address="18 High St, Prahran VIC 3181",
        tech_notes="2018 Civic — standard transponder, not an all-keys-lost job.",
    )
    session.add(story_key)

    extra_key_specs = [
        ("Toyota", "Hilux", "K-1002", 2019, "transponder", "booked"),
        ("Ford", "Ranger", "K-1003", 2020, "transponder", "en_route"),
        ("Mazda", "CX-5", "K-1004", 2017, "proximity", "on_site"),
        ("Hyundai", "i30", "K-1005", 2021, "transponder", "work_completed"),
        ("Kia", "Sportage", "K-1006", 2018, "transponder", "quote_sent"),
        ("Volkswagen", "Golf", "K-1007", 2016, "transponder", "booking_confirmed"),
        ("Subaru", "Outback", "K-1008", 2022, "proximity", "awaiting_quote"),
    ]
    extra_keys: list[AutoKeyJob] = []
    for idx, (make, model, number, year, key_type, status) in enumerate(extra_key_specs):
        owner = supporting[idx % len(supporting)]
        address = DEMO_AUTO_KEY_ADDRESSES.get(number, owner.address or "Melbourne VIC")
        job = AutoKeyJob(
            tenant_id=tenant.id,
            customer_id=owner.id,
            assigned_user_id=actor.id,
            job_number=number,
            title=f"{make} {model} key replacement",
            description="Program spare key and verify immobilizer sync.",
            vehicle_make=make,
            vehicle_model=model,
            vehicle_year=year,
            registration_plate=f"DEMO-{100 + idx}",
            key_type=key_type,
            job_type="Duplicate key",
            key_quantity=1,
            programming_status="pending" if status != "work_completed" else "programmed",
            status=status,
            priority="normal",
            salesperson=DEMO_STAFF_NAME,
            deposit_cents=2000,
            cost_cents=2800 + idx * 200,
            created_at=_days_ago(min(idx + 1, 6)),
            job_address=address,
        )
        session.add(job)
        extra_keys.append(job)
    session.flush()

    apply_demo_auto_key_dispatch_calendar(session, tenant.id)
    # Re-assert the story key after the calendar pass, which overwrites K-1001.
    story_key.customer_id = elena.id
    story_key.title = "Honda Civic duplicate key"
    story_key.vehicle_make = "Honda"
    story_key.vehicle_model = "Civic"
    story_key.vehicle_year = 2018
    story_key.job_type = "Duplicate key"
    story_key.programming_status = "in_progress"
    story_key.status = "booked"
    story_key.salesperson = DEMO_STAFF_NAME
    story_key.tech_notes = "2018 Civic — standard transponder, not an all-keys-lost job."
    story_key.job_address = "18 High St, Prahran VIC 3181"
    session.add(story_key)

    key_quote = AutoKeyQuote(
        tenant_id=tenant.id,
        auto_key_job_id=story_key.id,
        status="approved",
        subtotal_cents=8091,
        tax_cents=809,
        gst_enabled=True,
        gst_inclusive=True,
        total_cents=8900,
        currency="AUD",
        sent_at=_days_ago(1),
        created_at=_days_ago(1, 2),
    )
    session.add(key_quote)
    session.flush()
    session.add(
        AutoKeyQuoteLineItem(
            tenant_id=tenant.id,
            auto_key_quote_id=key_quote.id,
            description="Duplicate transponder key + programming",
            quantity=1,
            unit_price_cents=8900,
            total_price_cents=8900,
        )
    )

    # A recent paid mobile invoice so Today overdue does not include "Invoice Paid".
    completed_key = extra_keys[3]
    completed_key.status = "invoice_paid"
    completed_key.programming_status = "programmed"
    session.add(completed_key)
    paid_key_inv = AutoKeyInvoice(
        tenant_id=tenant.id,
        auto_key_job_id=completed_key.id,
        invoice_number="MINV-10001",
        status="paid",
        subtotal_cents=16182,
        tax_cents=1618,
        gst_enabled=True,
        gst_inclusive=True,
        total_cents=17800,
        currency="AUD",
        created_at=_days_ago(2),
        paid_at=_days_ago(1),
    )
    session.add(paid_key_inv)

    session.add(
        TenantEventLog(
            tenant_id=tenant.id,
            actor_user_id=actor.id,
            actor_email=actor.email,
            entity_type="tenant",
            event_type="demo_seeded",
            event_summary=(
                f"Closed demo seed by {actor.email}: "
                f"story={STORY_CUSTOMER_EMAIL}, watch={STORY_WATCH_JOB_NUMBER}, "
                f"shoe={STORY_SHOE_JOB_NUMBER}, key={STORY_KEY_JOB_NUMBER}, "
                f"invoice={STORY_INVOICE_NUMBER}"
            ),
        )
    )
    session.commit()
    return {
        "customers": len(customers),
        "watches": 2 + len(extra_watch_specs),
        "repair_jobs": 2 + len(extra_watch_jobs),
        "shoe_jobs": 1 + len(extra_shoe_specs),
        "auto_key_jobs": 1 + len(extra_keys),
        "quotes": 7,
        "invoices": 3,
        "story_customer": STORY_CUSTOMER_EMAIL,
        "story_watch_job": STORY_WATCH_JOB_NUMBER,
        "story_shoe_job": STORY_SHOE_JOB_NUMBER,
        "story_key_job": STORY_KEY_JOB_NUMBER,
        "story_invoice": story_invoice.invoice_number,
    }
