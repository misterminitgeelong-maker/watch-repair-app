import io
import os
from pathlib import Path
from uuid import UUID, uuid4

from fastapi.testclient import TestClient
from sqlmodel import Session, select

_TEST_DB = Path(__file__).with_name(f"test_csv_import_{uuid4().hex}.db")
os.environ["DATABASE_URL"] = f"sqlite:///{_TEST_DB.as_posix()}"
os.environ.setdefault("JWT_SECRET", "test-secret-not-for-production")
os.environ.setdefault("APP_ENV", "test")

from app.config import settings
from app.database import create_db_and_tables, engine
from app.limiter import limiter
from app.main import app
from app.models import (
    AutoKeyJob,
    Customer,
    CustomerAccount,
    CustomerAccountMembership,
    ImportLog,
    RepairJob,
)

create_db_and_tables()
client = TestClient(app)


def _bootstrap_and_login(tenant_slug: str, email: str, password: str) -> str:
    _token, _tid = _bootstrap_login_and_tenant(tenant_slug, email, password)
    return _token


def _bootstrap_login_and_tenant(tenant_slug: str, email: str, password: str) -> tuple[str, UUID]:
    bootstrap = client.post(
        "/v1/auth/bootstrap",
        json={
            "tenant_name": f"Tenant {tenant_slug}",
            "tenant_slug": tenant_slug,
            "owner_email": email,
            "owner_full_name": "Owner",
            "owner_password": password,
        },
    )
    assert bootstrap.status_code == 200
    tenant_id = UUID(bootstrap.json()["tenant_id"])
    login = client.post(
        "/v1/auth/login",
        json={"tenant_slug": tenant_slug, "email": email, "password": password},
    )
    assert login.status_code == 200
    return login.json()["access_token"], tenant_id


def _csv_file(content: str):
    return {"file": ("import.csv", io.BytesIO(content.encode("utf-8")), "text/csv")}


def test_csv_import_dry_run_does_not_write_data():
    token = _bootstrap_and_login("csv-safe-a", "csva@example.com", "Admin123!")
    headers = {"Authorization": f"Bearer {token}"}
    csv_text = (
        "customer_name,phone,brand,quote,status,notes\n"
        "Alice,0412345678,Omega,120,ready,ok\n"
    )
    with Session(engine) as session:
        before_jobs = len(session.exec(select(RepairJob)).all())
        before_customers = len(session.exec(select(Customer)).all())
        before_import_logs = len(session.exec(select(ImportLog)).all())

    res = client.post("/v1/import/csv", headers=headers, params={"dry_run": "true"}, files=_csv_file(csv_text))
    assert res.status_code == 200
    body = res.json()
    assert body["dry_run"] is True
    assert body["imported"] == 1
    assert body["skipped"] == 0

    with Session(engine) as session:
        after_jobs = len(session.exec(select(RepairJob)).all())
        after_customers = len(session.exec(select(Customer)).all())
        after_import_logs = len(session.exec(select(ImportLog)).all())
    assert after_jobs == before_jobs
    assert after_customers == before_customers
    assert after_import_logs == before_import_logs


def test_csv_import_normal_run_writes_data():
    token = _bootstrap_and_login("csv-safe-b", "csvb@example.com", "Admin123!")
    headers = {"Authorization": f"Bearer {token}"}
    csv_text = (
        "customer_name,phone,brand,quote,status,notes\n"
        "Bob,0412000000,Seiko,200,ready,all good\n"
    )
    with Session(engine) as session:
        before_jobs = len(session.exec(select(RepairJob)).all())
        before_customers = len(session.exec(select(Customer)).all())
        before_import_logs = len(session.exec(select(ImportLog)).all())

    res = client.post("/v1/import/csv", headers=headers, files=_csv_file(csv_text))
    assert res.status_code == 200
    body = res.json()
    assert body["dry_run"] is False
    assert body["imported"] == 1

    with Session(engine) as session:
        after_jobs = len(session.exec(select(RepairJob)).all())
        after_customers = len(session.exec(select(Customer)).all())
        after_import_logs = len(session.exec(select(ImportLog)).all())
    assert after_jobs > before_jobs
    assert after_customers > before_customers
    assert after_import_logs > before_import_logs


def test_csv_import_invalid_rows_reported():
    token = _bootstrap_and_login("csv-safe-c", "csvc@example.com", "Admin123!")
    headers = {"Authorization": f"Bearer {token}"}
    csv_text = (
        "customer_name,phone,brand,quote,status,notes\n"
        ",,,,,\n"
        ",,,10,ready,\n"
        "Valid Name,0412111222,Rolex,300,ready,ok\n"
    )
    res = client.post("/v1/import/csv", headers=headers, params={"dry_run": "true"}, files=_csv_file(csv_text))
    assert res.status_code == 200
    body = res.json()
    assert body["skipped"] == 2
    assert body["imported"] == 1
    assert body["skipped_reasons"].get("empty_row", 0) == 1
    assert body["skipped_reasons"].get("missing_core_fields", 0) == 1


def test_csv_import_duplicate_like_rows_summarized():
    token = _bootstrap_and_login("csv-safe-d", "csvd@example.com", "Admin123!")
    headers = {"Authorization": f"Bearer {token}"}
    csv_text = (
        "customer_name,phone,brand,quote,status,notes\n"
        "Same Person,0412333444,Omega,100,ready,job1\n"
        "Same Person,0412333444,Tissot,150,ready,job2\n"
    )
    res = client.post("/v1/import/csv", headers=headers, params={"dry_run": "true"}, files=_csv_file(csv_text))
    assert res.status_code == 200
    body = res.json()
    assert body["imported"] == 2
    assert body["customers_created"] == 1
    assert body["duplicate_customer_rows_in_file"] == 1


def test_csv_import_duplicate_ticket_numbers_get_unique_job_numbers():
    """Same docket/ticket twice in a file must not abort the import (unique job_number)."""
    token = _bootstrap_and_login("csv-safe-dup-tix", "csvdup@example.com", "Admin123!")
    headers = {"Authorization": f"Bearer {token}"}
    csv_text = (
        "ticket_number,customer_name,phone,brand,quote,status,notes\n"
        "6000827,Alice,0411111111,Omega,100,collected,first\n"
        "6000827,Bob,0412222222,Seiko,200,collected,second\n"
    )
    res = client.post("/v1/import/csv", headers=headers, files=_csv_file(csv_text))
    assert res.status_code == 200
    body = res.json()
    assert body["imported"] == 2
    assert body["source_sheet"] is None
    with Session(engine) as session:
        jobs = session.exec(select(RepairJob)).all()
        nums = sorted(j.job_number for j in jobs if j.job_number.startswith("IMP-6000827"))
    assert nums == ["IMP-6000827", "IMP-6000827-2"]


def test_csv_import_reuses_no_job_number_when_ticket_exists_in_db():
    """Second import with same ticket as an existing job must suffix, not UniqueViolation."""
    limiter.reset()
    old_rl = settings.rate_limit_import_csv
    settings.rate_limit_import_csv = "100/minute"
    try:
        token = _bootstrap_and_login("csv-safe-redo", "csvredo@example.com", "Admin123!")
        headers = {"Authorization": f"Bearer {token}"}
        first = (
            "ticket_number,customer_name,phone,brand,quote,status,notes\n"
            "9999999,Pat,0412000000,Seiko,49.95,collected,first import row\n"
        )
        r1 = client.post("/v1/import/csv", headers=headers, files=_csv_file(first))
        assert r1.status_code == 200
        second = (
            "ticket_number,customer_name,phone,brand,quote,status,notes\n"
            "9999999,Alex,0413111222,Omega,120,collected,re-import same ticket\n"
        )
        r2 = client.post("/v1/import/csv", headers=headers, files=_csv_file(second))
        assert r2.status_code == 200
        assert r2.json()["imported"] == 1
        with Session(engine) as session:
            jobs = session.exec(select(RepairJob)).all()
            nums = sorted(j.job_number for j in jobs if j.job_number.startswith("IMP-9999999"))
        assert nums == ["IMP-9999999", "IMP-9999999-2"]
    finally:
        settings.rate_limit_import_csv = old_rl
        limiter.reset()


def test_csv_import_replace_watch_only_preserves_mobile_customers():
    """Watch-tab replace clears watch data only; customers linked to mobile jobs are kept."""
    token, tenant_id = _bootstrap_login_and_tenant(
        "csv-replace-fk", "csvrepfk@example.com", "Admin123!"
    )
    headers = {"Authorization": f"Bearer {token}"}
    with Session(engine) as session:
        cust = Customer(tenant_id=tenant_id, full_name="Fleet Person", phone="0411888777")
        session.add(cust)
        acc = CustomerAccount(tenant_id=tenant_id, name="Fleet Co")
        session.add(acc)
        session.flush()
        session.add(
            CustomerAccountMembership(
                tenant_id=tenant_id,
                customer_account_id=acc.id,
                customer_id=cust.id,
            )
        )
        session.add(
            AutoKeyJob(
                tenant_id=tenant_id,
                customer_id=cust.id,
                job_number="AK-100",
                title="Spare key",
            )
        )
        session.commit()

    csv_text = (
        "customer_name,phone,brand,quote,status,notes\n"
        "Imported,0411999000,Omega,50,ready,ok\n"
    )
    res = client.post(
        "/v1/import/csv",
        headers=headers,
        params={"replace_existing": "true"},
        files=_csv_file(csv_text),
    )
    assert res.status_code == 200, res.text
    assert res.json()["imported"] == 1

    with Session(engine) as session:
        customers = session.exec(select(Customer).where(Customer.tenant_id == tenant_id)).all()
        assert len(customers) == 2
        names = {c.full_name for c in customers}
        assert "Fleet Person" in names and "Imported" in names
        mems = session.exec(
            select(CustomerAccountMembership).where(CustomerAccountMembership.tenant_id == tenant_id)
        ).all()
        assert len(mems) == 1
        ajobs = session.exec(select(AutoKeyJob).where(AutoKeyJob.tenant_id == tenant_id)).all()
        assert len(ajobs) == 1
        jobs = session.exec(select(RepairJob).where(RepairJob.tenant_id == tenant_id)).all()
        assert len(jobs) == 1
