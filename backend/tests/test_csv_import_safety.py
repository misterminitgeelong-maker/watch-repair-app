import io
import os
from pathlib import Path
from uuid import uuid4

from fastapi.testclient import TestClient
from sqlmodel import Session, select

_TEST_DB = Path(__file__).with_name(f"test_csv_import_{uuid4().hex}.db")
os.environ["DATABASE_URL"] = f"sqlite:///{_TEST_DB.as_posix()}"
os.environ.setdefault("JWT_SECRET", "test-secret-not-for-production")
os.environ.setdefault("APP_ENV", "test")

from app.database import create_db_and_tables, engine
from app.main import app
from app.models import Customer, ImportLog, RepairJob

create_db_and_tables()
client = TestClient(app)


def _bootstrap_and_login(tenant_slug: str, email: str, password: str) -> str:
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
    login = client.post(
        "/v1/auth/login",
        json={"tenant_slug": tenant_slug, "email": email, "password": password},
    )
    assert login.status_code == 200
    return login.json()["access_token"]


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
