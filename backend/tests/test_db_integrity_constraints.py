import os
from pathlib import Path
from uuid import uuid4

import pytest
from sqlalchemy.exc import IntegrityError
from sqlmodel import Session

_TEST_DB = Path(__file__).with_name(f"test_db_integrity_{uuid4().hex}.db")
os.environ["DATABASE_URL"] = f"sqlite:///{_TEST_DB.as_posix()}"
os.environ.setdefault("JWT_SECRET", "test-secret-not-for-production")
os.environ.setdefault("APP_ENV", "test")

from app.database import create_db_and_tables, engine
from app.models import (
    Attachment,
    Customer,
    Invoice,
    Payment,
    RepairJob,
    Tenant,
    User,
    Watch,
    WorkLog,
)
from app.security import hash_password

create_db_and_tables()


def _seed_tenant_with_watch():
    with Session(engine) as session:
        tenant = Tenant(name=f"T-{uuid4().hex[:6]}", slug=f"slug-{uuid4().hex[:8]}")
        session.add(tenant)
        session.flush()
        customer = Customer(tenant_id=tenant.id, full_name="Customer")
        session.add(customer)
        session.flush()
        watch = Watch(tenant_id=tenant.id, customer_id=customer.id, brand="Omega")
        session.add(watch)
        session.commit()
        return tenant.id, watch.id


def test_duplicate_user_email_in_same_tenant_rejected():
    with Session(engine) as session:
        tenant = Tenant(name=f"T-{uuid4().hex[:6]}", slug=f"same-tenant-{uuid4().hex[:8]}")
        session.add(tenant)
        session.flush()
        session.add(
            User(
                tenant_id=tenant.id,
                email="owner@example.com",
                full_name="Owner One",
                password_hash=hash_password("pass123456"),
            )
        )
        session.commit()

        session.add(
            User(
                tenant_id=tenant.id,
                email="owner@example.com",
                full_name="Owner Two",
                password_hash=hash_password("pass123456"),
            )
        )
        with pytest.raises(IntegrityError):
            session.commit()


def test_same_user_email_across_tenants_allowed():
    with Session(engine) as session:
        tenant_a = Tenant(name=f"A-{uuid4().hex[:6]}", slug=f"a-{uuid4().hex[:8]}")
        tenant_b = Tenant(name=f"B-{uuid4().hex[:6]}", slug=f"b-{uuid4().hex[:8]}")
        session.add(tenant_a)
        session.add(tenant_b)
        session.flush()
        session.add(
            User(
                tenant_id=tenant_a.id,
                email="shared@example.com",
                full_name="Shared A",
                password_hash=hash_password("pass123456"),
            )
        )
        session.add(
            User(
                tenant_id=tenant_b.id,
                email="shared@example.com",
                full_name="Shared B",
                password_hash=hash_password("pass123456"),
            )
        )
        session.commit()


def test_negative_cents_fields_rejected():
    tenant_id, watch_id = _seed_tenant_with_watch()
    with Session(engine) as session:
        job = RepairJob(
            tenant_id=tenant_id,
            watch_id=watch_id,
            job_number=f"JOB-{uuid4().hex[:5]}",
            title="Bad money",
            deposit_cents=-1,
        )
        session.add(job)
        with pytest.raises(IntegrityError):
            session.commit()
        session.rollback()

        tenant_id_obj = tenant_id
        watch = session.get(Watch, watch_id)
        valid_job = RepairJob(
            tenant_id=tenant_id_obj,
            watch_id=watch.id,
            job_number=f"JOB-{uuid4().hex[:5]}",
            title="Valid job",
            deposit_cents=0,
        )
        session.add(valid_job)
        session.flush()

        invoice = Invoice(
            tenant_id=tenant_id_obj,
            repair_job_id=valid_job.id,
            invoice_number=f"INV-{uuid4().hex[:5]}",
            subtotal_cents=-10,
            tax_cents=0,
            total_cents=0,
        )
        session.add(invoice)
        with pytest.raises(IntegrityError):
            session.commit()


def test_negative_minutes_and_file_size_rejected():
    tenant_id, watch_id = _seed_tenant_with_watch()
    with Session(engine) as session:
        tenant_id_obj = tenant_id
        watch = session.get(Watch, watch_id)
        job = RepairJob(
            tenant_id=tenant_id_obj,
            watch_id=watch.id,
            job_number=f"JOB-{uuid4().hex[:5]}",
            title="Integrity",
            deposit_cents=0,
        )
        session.add(job)
        session.flush()

        session.add(
            WorkLog(
                tenant_id=tenant_id_obj,
                repair_job_id=job.id,
                note="bad minutes",
                minutes_spent=-5,
            )
        )
        with pytest.raises(IntegrityError):
            session.commit()
        session.rollback()

        session.add(
            Attachment(
                tenant_id=tenant_id_obj,
                repair_job_id=job.id,
                storage_key=f"key-{uuid4().hex}",
                file_name="photo.jpg",
                content_type="image/jpeg",
                file_size_bytes=-1,
            )
        )
        with pytest.raises(IntegrityError):
            session.commit()
        session.rollback()

        invoice = Invoice(
            tenant_id=tenant_id_obj,
            repair_job_id=job.id,
            invoice_number=f"INV-{uuid4().hex[:5]}",
            subtotal_cents=100,
            tax_cents=0,
            total_cents=100,
        )
        session.add(invoice)
        session.flush()
        session.add(
            Payment(
                tenant_id=tenant_id_obj,
                invoice_id=invoice.id,
                amount_cents=-1,
            )
        )
        with pytest.raises(IntegrityError):
            session.commit()
