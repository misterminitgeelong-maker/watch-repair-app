"""Characterisation tests for the ``shoe`` and ``mobile`` CSV import targets.

``tests/test_csv_import_safety.py`` never passes ``import_target``, so it only
exercises the default ``watch`` branch of ``_import_csv_sync``. These tests pin
the observable behaviour of the other two branches -- which rows land, the job
numbers they get, the skip reasons and the summary counts -- so the importer can
be restructured without changing what a franchisee sees.

They assert on database state and the HTTP response only, never on the shape of
the code, so they must keep passing across a refactor of the function body.
"""
import io
from datetime import date, datetime, timezone
from uuid import UUID, uuid4

import pytest
from fastapi.testclient import TestClient
from sqlmodel import Session, select

from app.config import settings
from app.database import engine
from app.limiter import limiter
from app.models import (
    AutoKeyJob,
    AutoKeyQuote,
    AutoKeyQuoteLineItem,
    Customer,
    ImportLog,
    ImportLogDetail,
    RepairJob,
    Shoe,
    ShoeJobStatusHistory,
    ShoeRepairJob,
    Watch,
)

IMPORT_URL = "/v1/import/csv"


# ── Fixtures and helpers ───────────────────────────────────────────────────────


@pytest.fixture(scope="module", autouse=True)
def _lift_import_rate_limit():
    """The endpoint allows 5 imports a minute per client; this module makes many more."""
    previous = settings.rate_limit_import_csv
    settings.rate_limit_import_csv = "1000/minute"
    limiter.reset()
    yield
    settings.rate_limit_import_csv = previous
    limiter.reset()


def _bootstrap_tenant(client: TestClient, plan_code: str | None = None) -> tuple[dict[str, str], UUID]:
    """Bootstrap a tenant and log its owner in: ``(headers, tenant_id)``.

    Mirrors ``test_csv_import_safety.py``; the conftest fixture returns only the
    token and these tests need the tenant id to scope their database assertions.
    """
    suffix = uuid4().hex[:8]
    slug = f"import-{suffix}"
    email = f"owner-{suffix}@example.test"
    password = "Admin123!"
    payload = {
        "tenant_name": f"Tenant {slug}",
        "tenant_slug": slug,
        "owner_email": email,
        "owner_full_name": "Owner",
        "owner_password": password,
    }
    if plan_code:
        payload["plan_code"] = plan_code
    bootstrap = client.post("/v1/auth/bootstrap", json=payload)
    assert bootstrap.status_code == 200, bootstrap.text
    login = client.post("/v1/auth/login", json={"tenant_slug": slug, "email": email, "password": password})
    assert login.status_code == 200, login.text
    return {"Authorization": f"Bearer {login.json()['access_token']}"}, UUID(bootstrap.json()["tenant_id"])


@pytest.fixture
def tenant(client: TestClient):
    """A fresh tenant on a plan with every tab enabled: ``(headers, tenant_id)``.

    Bootstrap defaults to ``basic_watch``, which would 403 both targets under test
    before the import code runs.
    """
    return _bootstrap_tenant(client, plan_code="basic_all_tabs")


def _csv_file(content: str):
    return {"file": ("import.csv", io.BytesIO(content.encode("utf-8")), "text/csv")}


def _import(client: TestClient, headers: dict[str, str], target: str, csv_text: str, **params):
    res = client.post(
        IMPORT_URL,
        headers=headers,
        params={"import_target": target, **params},
        files=_csv_file(csv_text),
    )
    assert res.status_code == 200, res.text
    return res.json()


def _rows(session: Session, model, tenant_id: UUID) -> list:
    return session.exec(select(model).where(model.tenant_id == tenant_id)).all()


def _tenant_counts(session: Session, tenant_id: UUID) -> dict[str, int]:
    """Row counts for every table an import can touch, so 'nothing changed' is one comparison."""
    tables = {
        "customers": Customer,
        "watches": Watch,
        "repair_jobs": RepairJob,
        "shoes": Shoe,
        "shoe_jobs": ShoeRepairJob,
        "shoe_history": ShoeJobStatusHistory,
        "auto_key_jobs": AutoKeyJob,
        "auto_key_quotes": AutoKeyQuote,
        "auto_key_line_items": AutoKeyQuoteLineItem,
        "import_logs": ImportLog,
    }
    return {name: len(_rows(session, model, tenant_id)) for name, model in tables.items()}


def _seed_customer(session: Session, tenant_id: UUID, name: str, phone: str) -> Customer:
    customer = Customer(tenant_id=tenant_id, full_name=name, phone=phone)
    session.add(customer)
    session.flush()
    return customer


def _seed_watch_job(session: Session, tenant_id: UUID, customer: Customer, job_number: str) -> RepairJob:
    watch = Watch(tenant_id=tenant_id, customer_id=customer.id, brand="Seiko")
    session.add(watch)
    session.flush()
    job = RepairJob(tenant_id=tenant_id, watch_id=watch.id, job_number=job_number, title="Battery")
    session.add(job)
    session.flush()
    return job


def _seed_shoe_job(session: Session, tenant_id: UUID, customer: Customer, job_number: str) -> ShoeRepairJob:
    shoe = Shoe(tenant_id=tenant_id, customer_id=customer.id, brand="RM Williams")
    session.add(shoe)
    session.flush()
    job = ShoeRepairJob(tenant_id=tenant_id, shoe_id=shoe.id, job_number=job_number, title="Resole")
    session.add(job)
    session.flush()
    session.add(
        ShoeJobStatusHistory(
            tenant_id=tenant_id, shoe_repair_job_id=job.id, new_status=job.status, change_note="seed"
        )
    )
    return job


def _seed_auto_key_job(session: Session, tenant_id: UUID, customer: Customer, job_number: str) -> AutoKeyJob:
    job = AutoKeyJob(tenant_id=tenant_id, customer_id=customer.id, job_number=job_number, title="Spare key")
    session.add(job)
    session.flush()
    quote = AutoKeyQuote(tenant_id=tenant_id, auto_key_job_id=job.id, total_cents=1000)
    session.add(quote)
    session.flush()
    session.add(
        AutoKeyQuoteLineItem(
            tenant_id=tenant_id,
            auto_key_quote_id=quote.id,
            description="seed",
            unit_price_cents=1000,
            total_price_cents=1000,
        )
    )
    return job


def _seed_every_vertical(session: Session, tenant_id: UUID) -> None:
    """One job in each of the three tabs, sharing one customer, so tab-scoped clearing is testable."""
    customer = _seed_customer(session, tenant_id, "Existing Person", "0400000001")
    _seed_watch_job(session, tenant_id, customer, "W-EXISTING")
    _seed_shoe_job(session, tenant_id, customer, "SH-EXISTING")
    _seed_auto_key_job(session, tenant_id, customer, "AK-EXISTING")
    session.commit()


# ── Plan gating ────────────────────────────────────────────────────────────────


@pytest.mark.parametrize(
    ("target", "plan_without_it"),
    [("shoe", "basic_watch"), ("mobile", "basic_watch_shoe")],
)
def test_import_target_is_refused_without_the_plan_feature(client: TestClient, target: str, plan_without_it: str):
    headers, _tenant_id = _bootstrap_tenant(client, plan_code=plan_without_it)
    res = client.post(
        IMPORT_URL,
        headers=headers,
        params={"import_target": target, "dry_run": "true"},
        files=_csv_file("customer_name,phone\nSomeone,0412000000\n"),
    )
    assert res.status_code == 403, res.text


# ── Shoe ───────────────────────────────────────────────────────────────────────

SHOE_HEADER = "ticket_number,customer_name,phone,date_in,shoe_brand,shoe_type,color,quote,cost,status,notes,title\n"


def test_shoe_dry_run_writes_and_deletes_nothing(client: TestClient, tenant):
    headers, tenant_id = tenant
    with Session(engine) as session:
        _seed_every_vertical(session, tenant_id)
        before = _tenant_counts(session, tenant_id)

    body = _import(
        client,
        headers,
        "shoe",
        SHOE_HEADER + "6000101,Alice Shoe,0412 345 678,2024-03-05,Blundstone,boots,brown,149.95,60,ready,heel worn,\n",
        dry_run="true",
        replace_existing="true",
    )
    assert body["dry_run"] is True
    assert body["imported"] == 1
    assert body["skipped"] == 0
    assert body["import_target"] == "shoe"

    with Session(engine) as session:
        assert _tenant_counts(session, tenant_id) == before


def test_shoe_normal_run_creates_customer_shoe_job_and_history(client: TestClient, tenant):
    headers, tenant_id = tenant
    started = datetime.now(timezone.utc)
    body = _import(
        client,
        headers,
        "shoe",
        SHOE_HEADER
        + "6000101,Alice Shoe,0412 345 678,2024-03-05,Blundstone,boots,brown,149.95,60,ready,heel worn,\n"
        + "6000102,Bob Boot,0413 000 111,,Ecco,,,120,,in repair,,Stretch and clean\n"
        + "6000103,Cara Clog,0414 000 222,,Birkenstock,sandals,,,,,cork resealed,\n",
    )
    assert body["dry_run"] is False
    assert body["imported"] == 3
    assert body["skipped"] == 0
    assert body["customers_created"] == 3

    with Session(engine) as session:
        customers = {c.full_name: c for c in _rows(session, Customer, tenant_id)}
        assert set(customers) == {"Alice Shoe", "Bob Boot", "Cara Clog"}
        assert customers["Alice Shoe"].phone == "0412345678"

        jobs = {j.job_number: j for j in _rows(session, ShoeRepairJob, tenant_id)}
        assert set(jobs) == {"IMP-SH6000101", "IMP-SH6000102", "IMP-SH6000103"}
        assert _rows(session, RepairJob, tenant_id) == []
        assert _rows(session, AutoKeyJob, tenant_id) == []

        alice = jobs["IMP-SH6000101"]
        assert alice.title == "Shoe repair: Blundstone"
        assert alice.description == "heel worn"
        assert alice.status == "awaiting_collection"  # "ready"
        assert alice.quote_status == "approved"  # quoted and already awaiting collection
        assert alice.cost_cents == 6000  # explicit cost wins over the quote
        assert alice.created_at.date() == date(2024, 3, 5)
        shoe = session.get(Shoe, alice.shoe_id)
        assert (shoe.brand, shoe.shoe_type, shoe.color, shoe.description_notes) == (
            "Blundstone", "boots", "brown", "heel worn"
        )
        assert shoe.customer_id == customers["Alice Shoe"].id

        bob = jobs["IMP-SH6000102"]
        assert bob.title == "Stretch and clean"  # explicit title beats the generated one
        assert bob.status == "working_on"  # "in repair"
        assert bob.quote_status == "sent"  # quoted, still in progress
        assert bob.cost_cents == 12000  # no cost column, falls back to the quote
        assert started.date() <= bob.created_at.date() <= datetime.now(timezone.utc).date()  # no date_in: now

        cara = jobs["IMP-SH6000103"]
        assert cara.status == "awaiting_go_ahead"  # blank status
        assert cara.quote_status == "none"
        assert cara.cost_cents == 0

        history = _rows(session, ShoeJobStatusHistory, tenant_id)
        assert {(h.shoe_repair_job_id, h.old_status, h.new_status, h.change_note) for h in history} == {
            (alice.id, None, "awaiting_collection", "Imported"),
            (bob.id, None, "working_on", "Imported"),
            (cara.id, None, "awaiting_go_ahead", "Imported"),
        }


def test_shoe_invalid_rows_are_reported_not_fatal(client: TestClient, tenant):
    headers, tenant_id = tenant
    body = _import(
        client,
        headers,
        "shoe",
        SHOE_HEADER
        + ",,,,,,,,,,,\n"  # nothing at all
        + ",,,,,,,10,,ready,,\n"  # a price but nobody and no shoe
        + ",Name Only,,,,,,,,,,\n"  # a customer but no phone, brand or notes
        + ",Valid Person,0412 111 222,,Dr Martens,,,,,,scuffed,\n",
    )
    assert body["imported"] == 1
    assert body["skipped"] == 3
    assert body["skipped_reasons"] == {"empty_row": 1, "missing_core_fields": 2}

    with Session(engine) as session:
        jobs = _rows(session, ShoeRepairJob, tenant_id)
        assert [j.job_number for j in jobs] == ["IMP-00001"]  # skipped rows do not consume a sequence slot
        assert [c.full_name for c in _rows(session, Customer, tenant_id)] == ["Valid Person"]
        details = session.exec(
            select(ImportLogDetail).where(ImportLogDetail.import_log_id == UUID(body["import_id"]))
        ).all()
        assert sorted((d.row_number, d.skip_reason) for d in details) == [
            (1, "empty_row"),
            (2, "missing_core_fields"),
            (3, "missing_core_fields"),
            (4, None),
        ]


def test_shoe_duplicate_ticket_numbers_in_file_get_unique_job_numbers(client: TestClient, tenant):
    headers, tenant_id = tenant
    body = _import(
        client,
        headers,
        "shoe",
        SHOE_HEADER
        + "6000827,Alice,0411111111,,Blundstone,,,,,collected,left boot,\n"
        + "6000827,Bob,0412222222,,Ecco,,,,,collected,right boot,\n"
        + "6000827,Cara,0413333333,,Ecco,,,,,collected,both,\n",
    )
    assert body["imported"] == 3
    with Session(engine) as session:
        nums = sorted(j.job_number for j in _rows(session, ShoeRepairJob, tenant_id))
    assert nums == ["IMP-SH6000827", "IMP-SH6000827-2", "IMP-SH6000827-3"]


def test_shoe_ticket_already_in_database_is_suffixed_not_collided(client: TestClient, tenant):
    headers, tenant_id = tenant
    row = "7000001,Pat,0412000000,,Ecco,,,,,collected,first import,\n"
    first = _import(client, headers, "shoe", SHOE_HEADER + row)
    assert first["imported"] == 1
    second = _import(client, headers, "shoe", SHOE_HEADER + row.replace("Pat", "Alex"))
    assert second["imported"] == 1

    with Session(engine) as session:
        nums = sorted(j.job_number for j in _rows(session, ShoeRepairJob, tenant_id))
    assert nums == ["IMP-SH7000001", "IMP-SH7000001-2"]


def test_shoe_replace_existing_clears_only_the_shoe_tab(client: TestClient, tenant):
    headers, tenant_id = tenant
    with Session(engine) as session:
        _seed_every_vertical(session, tenant_id)

    body = _import(
        client,
        headers,
        "shoe",
        SHOE_HEADER + "6000201,Imported Shoe,0411999000,,Ecco,,,,,,,\n",
        replace_existing="true",
    )
    assert body["imported"] == 1

    with Session(engine) as session:
        assert [j.job_number for j in _rows(session, ShoeRepairJob, tenant_id)] == ["IMP-SH6000201"]
        assert len(_rows(session, Shoe, tenant_id)) == 1
        assert {h.change_note for h in _rows(session, ShoeJobStatusHistory, tenant_id)} == {"Imported"}
        # The other two tabs, and the customers they share, are untouched.
        assert [j.job_number for j in _rows(session, RepairJob, tenant_id)] == ["W-EXISTING"]
        assert [j.job_number for j in _rows(session, AutoKeyJob, tenant_id)] == ["AK-EXISTING"]
        assert len(_rows(session, AutoKeyQuote, tenant_id)) == 1
        assert {c.full_name for c in _rows(session, Customer, tenant_id)} == {"Existing Person", "Imported Shoe"}


def test_shoe_summary_counts_match_what_landed(client: TestClient, tenant):
    headers, tenant_id = tenant
    body = _import(
        client,
        headers,
        "shoe",
        SHOE_HEADER
        + "6000301,Alice Repeat,0412 345 678,,Blundstone,,,,,,left,\n"
        + "6000302,Alice Repeat,0412 345 678,,Ecco,,,,,,right,\n"  # same customer, second pair
        + ",,,,,,,,,,,\n",
    )
    assert body == {
        "import_id": body["import_id"],
        "imported": 2,
        "skipped": 1,
        "customers_created": 1,
        "total_rows": 3,
        "skipped_reasons": {"empty_row": 1},
        "dry_run": False,
        "duplicate_customer_rows_in_file": 1,
        "source_sheet": None,
        "import_target": "shoe",
    }

    with Session(engine) as session:
        customers = _rows(session, Customer, tenant_id)
        assert len(customers) == 1
        assert len(_rows(session, ShoeRepairJob, tenant_id)) == 2
        assert len(_rows(session, Shoe, tenant_id)) == 2

        log = session.get(ImportLog, UUID(body["import_id"]))
        assert log is not None and log.tenant_id == tenant_id
        assert (log.status, log.total_rows, log.imported_count, log.skipped_count, log.customers_created_count) == (
            "completed", 3, 2, 1, 1
        )
        details = session.exec(select(ImportLogDetail).where(ImportLogDetail.import_log_id == log.id)).all()
        assert sorted((d.row_number, d.skip_reason, d.created_customer_id) for d in details) == [
            (1, None, customers[0].id),
            (2, None, None),  # customer reused from row 1
            (3, "empty_row", None),
        ]


# ── Mobile (auto key) ──────────────────────────────────────────────────────────

MOBILE_HEADER = (
    "ticket_number,customer_name,phone,date_in,quote,cost,status,notes,address,"
    "vehicle_make,vehicle_model,vehicle_year,rego,job_type,title,work_required\n"
)


def test_mobile_dry_run_writes_and_deletes_nothing(client: TestClient, tenant):
    headers, tenant_id = tenant
    with Session(engine) as session:
        _seed_every_vertical(session, tenant_id)
        before = _tenant_counts(session, tenant_id)

    body = _import(
        client,
        headers,
        "mobile",
        MOBILE_HEADER + "8000101,Alice Key,0412 345 678,2024-03-05,250,90,booked,lost key,1 Main St,Toyota,Corolla,2019,ABC123,Lockout,,\n",
        dry_run="true",
        replace_existing="true",
    )
    assert body["dry_run"] is True
    assert body["imported"] == 1
    assert body["skipped"] == 0
    assert body["import_target"] == "mobile"

    with Session(engine) as session:
        assert _tenant_counts(session, tenant_id) == before


def test_mobile_normal_run_creates_customer_job_and_quote(client: TestClient, tenant):
    headers, tenant_id = tenant
    started = datetime.now(timezone.utc)
    body = _import(
        client,
        headers,
        "mobile",
        MOBILE_HEADER
        + "8000101,Alice Key,0412 345 678,2024-03-05,250,90,booked,lost key,1 Main St,Toyota,Corolla,2019,ABC123,Lockout,,\n"
        + "8000102,Bob Fob,0413 000 111,,180,,collected,,,Mazda,3,abc,,,Programmed fob,\n"
        + "8000103,Cara Car,0414 000 222,,,,,,,Holden,Astra,1900,,,,Cut and program a spare key for a 2004 Astra sedan while on site at the customer's workplace in Geelong West near the station\n",
    )
    assert body["dry_run"] is False
    assert body["imported"] == 3
    assert body["skipped"] == 0
    assert body["customers_created"] == 3

    with Session(engine) as session:
        customers = {c.full_name: c for c in _rows(session, Customer, tenant_id)}
        assert set(customers) == {"Alice Key", "Bob Fob", "Cara Car"}
        assert customers["Alice Key"].phone == "0412345678"
        assert customers["Alice Key"].address == "1 Main St"

        jobs = {j.job_number: j for j in _rows(session, AutoKeyJob, tenant_id)}
        assert set(jobs) == {"IMP-M8000101", "IMP-M8000102", "IMP-M8000103"}
        assert _rows(session, RepairJob, tenant_id) == []
        assert _rows(session, ShoeRepairJob, tenant_id) == []

        alice = jobs["IMP-M8000101"]
        assert alice.customer_id == customers["Alice Key"].id
        assert alice.title == "Mobile service"  # no title and no work line
        assert alice.status == "booked"
        assert alice.description == "lost key"
        assert alice.tech_notes == "lost key"
        assert alice.job_address == "1 Main St"
        assert (alice.vehicle_make, alice.vehicle_model, alice.vehicle_year, alice.registration_plate) == (
            "Toyota", "Corolla", 2019, "ABC123"
        )
        assert alice.job_type == "Lockout"
        assert alice.cost_cents == 9000  # explicit cost wins over the quote
        assert alice.created_at.date() == date(2024, 3, 5)

        bob = jobs["IMP-M8000102"]
        assert bob.title == "Programmed fob"
        assert bob.status == "invoice_paid"
        assert bob.work_completed_at == bob.created_at
        assert bob.vehicle_year is None  # "abc" is not a year
        assert bob.cost_cents == 18000  # no cost column, falls back to the quote
        assert started.date() <= bob.created_at.date() <= datetime.now(timezone.utc).date()  # no date_in: now

        cara = jobs["IMP-M8000103"]
        assert cara.status == "awaiting_quote"  # blank status on a mobile job
        assert cara.vehicle_year is None  # 1900 is out of range
        assert cara.cost_cents == 0
        assert cara.title.endswith("…") and len(cara.title) == 121  # work line truncated to 120 + ellipsis
        assert cara.title.startswith("Cut and program a spare key")

        quotes = {q.auto_key_job_id: q for q in _rows(session, AutoKeyQuote, tenant_id)}
        assert set(quotes) == {alice.id, bob.id}  # Cara had no quote
        assert (quotes[alice.id].status, quotes[alice.id].total_cents, quotes[alice.id].subtotal_cents) == (
            "sent", 25000, 25000
        )
        assert quotes[bob.id].status == "approved"  # already collected
        assert quotes[bob.id].currency == "AUD"
        assert quotes[alice.id].created_at.date() == date(2024, 3, 5)

        line_items = _rows(session, AutoKeyQuoteLineItem, tenant_id)
        assert sorted(
            (li.auto_key_quote_id, li.description, li.quantity, li.unit_price_cents, li.total_price_cents)
            for li in line_items
        ) == sorted([
            (quotes[alice.id].id, "Imported quote total", 1, 25000, 25000),
            (quotes[bob.id].id, "Imported quote total", 1, 18000, 18000),
        ])


def test_mobile_invalid_rows_are_reported_not_fatal(client: TestClient, tenant):
    headers, tenant_id = tenant
    body = _import(
        client,
        headers,
        "mobile",
        MOBILE_HEADER
        + ",,,,,,,,,,,,,,,\n"  # nothing at all
        + ",,,,10,,booked,,,,,,,,,\n"  # a price and status but nobody, nowhere, nothing to do
        + ",Name Only,,,,,,,,,,,,,,\n"  # a customer but no phone, address or work line
        + ",Valid Person,0412 111 222,,,,,,,,,,,,,\n",
    )
    assert body["imported"] == 1
    assert body["skipped"] == 3
    assert body["skipped_reasons"] == {"empty_row": 1, "missing_core_fields": 2}

    with Session(engine) as session:
        jobs = _rows(session, AutoKeyJob, tenant_id)
        assert [j.job_number for j in jobs] == ["IMP-00001"]  # skipped rows do not consume a sequence slot
        assert [c.full_name for c in _rows(session, Customer, tenant_id)] == ["Valid Person"]
        details = session.exec(
            select(ImportLogDetail).where(ImportLogDetail.import_log_id == UUID(body["import_id"]))
        ).all()
        assert sorted((d.row_number, d.skip_reason) for d in details) == [
            (1, "empty_row"),
            (2, "missing_core_fields"),
            (3, "missing_core_fields"),
            (4, None),
        ]


def test_mobile_duplicate_ticket_numbers_in_file_get_unique_job_numbers(client: TestClient, tenant):
    headers, tenant_id = tenant
    body = _import(
        client,
        headers,
        "mobile",
        MOBILE_HEADER
        + "8000827,Alice,0411111111,,,,collected,,,,,,,,,first\n"
        + "8000827,Bob,0412222222,,,,collected,,,,,,,,,second\n"
        + "8000827,Cara,0413333333,,,,collected,,,,,,,,,third\n",
    )
    assert body["imported"] == 3
    with Session(engine) as session:
        nums = sorted(j.job_number for j in _rows(session, AutoKeyJob, tenant_id))
    assert nums == ["IMP-M8000827", "IMP-M8000827-2", "IMP-M8000827-3"]


def test_mobile_ticket_already_in_database_is_suffixed_not_collided(client: TestClient, tenant):
    """AutoKeyJob has a real (tenant_id, job_number) unique constraint, so a collision would 400."""
    headers, tenant_id = tenant
    row = "9000001,Pat,0412000000,,,,collected,,,,,,,,,first import\n"
    first = _import(client, headers, "mobile", MOBILE_HEADER + row)
    assert first["imported"] == 1
    second = _import(client, headers, "mobile", MOBILE_HEADER + row.replace("Pat", "Alex"))
    assert second["imported"] == 1

    with Session(engine) as session:
        nums = sorted(j.job_number for j in _rows(session, AutoKeyJob, tenant_id))
    assert nums == ["IMP-M9000001", "IMP-M9000001-2"]


def test_mobile_replace_existing_clears_only_the_auto_key_tab(client: TestClient, tenant):
    headers, tenant_id = tenant
    with Session(engine) as session:
        _seed_every_vertical(session, tenant_id)

    body = _import(
        client,
        headers,
        "mobile",
        MOBILE_HEADER + "8000201,Imported Key,0411999000,,300,,,,,,,,,,,\n",
        replace_existing="true",
    )
    assert body["imported"] == 1

    with Session(engine) as session:
        assert [j.job_number for j in _rows(session, AutoKeyJob, tenant_id)] == ["IMP-M8000201"]
        quotes = _rows(session, AutoKeyQuote, tenant_id)
        assert [q.total_cents for q in quotes] == [30000]  # the seeded $10 quote is gone
        assert [li.description for li in _rows(session, AutoKeyQuoteLineItem, tenant_id)] == ["Imported quote total"]
        # The other two tabs, and the customers they share, are untouched.
        assert [j.job_number for j in _rows(session, RepairJob, tenant_id)] == ["W-EXISTING"]
        assert [j.job_number for j in _rows(session, ShoeRepairJob, tenant_id)] == ["SH-EXISTING"]
        assert len(_rows(session, Shoe, tenant_id)) == 1
        assert {c.full_name for c in _rows(session, Customer, tenant_id)} == {"Existing Person", "Imported Key"}


def test_mobile_summary_counts_match_what_landed(client: TestClient, tenant):
    headers, tenant_id = tenant
    body = _import(
        client,
        headers,
        "mobile",
        MOBILE_HEADER
        + "8000301,Alice Repeat,0412 345 678,,120,,,,,Toyota,,,,,,Spare key\n"
        + "8000302,Alice Repeat,0412 345 678,,,,,,,Toyota,,,,,,Lockout\n"  # same customer, second job
        + ",,,,,,,,,,,,,,,\n",
    )
    assert body == {
        "import_id": body["import_id"],
        "imported": 2,
        "skipped": 1,
        "customers_created": 1,
        "total_rows": 3,
        "skipped_reasons": {"empty_row": 1},
        "dry_run": False,
        "duplicate_customer_rows_in_file": 1,
        "source_sheet": None,
        "import_target": "mobile",
    }

    with Session(engine) as session:
        customers = _rows(session, Customer, tenant_id)
        assert len(customers) == 1
        assert len(_rows(session, AutoKeyJob, tenant_id)) == 2
        assert len(_rows(session, AutoKeyQuote, tenant_id)) == 1  # only the first row was quoted

        log = session.get(ImportLog, UUID(body["import_id"]))
        assert log is not None and log.tenant_id == tenant_id
        assert (log.status, log.total_rows, log.imported_count, log.skipped_count, log.customers_created_count) == (
            "completed", 3, 2, 1, 1
        )
        details = session.exec(select(ImportLogDetail).where(ImportLogDetail.import_log_id == log.id)).all()
        assert sorted((d.row_number, d.skip_reason, d.created_customer_id) for d in details) == [
            (1, None, customers[0].id),
            (2, None, None),  # customer reused from row 1
            (3, "empty_row", None),
        ]
