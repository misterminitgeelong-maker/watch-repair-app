import io
import os
from pathlib import Path
from uuid import uuid4

from fastapi.testclient import TestClient

_TEST_DB = Path(__file__).with_name(f"test_attachments_{uuid4().hex}.db")
os.environ["DATABASE_URL"] = f"sqlite:///{_TEST_DB.as_posix()}"
os.environ.setdefault("JWT_SECRET", "test-secret-not-for-production")
os.environ.setdefault("APP_ENV", "test")

from app.database import create_db_and_tables
from app.main import app

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


def _create_repair_job(headers: dict[str, str]) -> str:
    customer = client.post(
        "/v1/customers",
        headers=headers,
        json={"full_name": "Attachment Customer", "email": "attach@example.com"},
    )
    assert customer.status_code == 201
    watch = client.post(
        "/v1/watches",
        headers=headers,
        json={"customer_id": customer.json()["id"], "brand": "Rolex", "model": "Explorer"},
    )
    assert watch.status_code == 201
    job = client.post(
        "/v1/repair-jobs",
        headers=headers,
        json={"watch_id": watch.json()["id"], "title": "Attachment job", "priority": "normal"},
    )
    assert job.status_code == 201
    return job.json()["id"]


def test_attachment_valid_upload():
    token = _bootstrap_and_login("attach-tenant-a", "ownera@example.com", "Admin123!")
    headers = {"Authorization": f"Bearer {token}"}
    repair_job_id = _create_repair_job(headers)

    files = {"file": ("note.txt", io.BytesIO(b"hello attachment"), "text/plain")}
    res = client.post("/v1/attachments", headers=headers, params={"repair_job_id": repair_job_id}, files=files)

    assert res.status_code == 201
    body = res.json()
    assert body["repair_job_id"] == repair_job_id
    assert body["content_type"] == "text/plain"
    assert body["file_size_bytes"] > 0


def test_attachment_reject_content_type():
    token = _bootstrap_and_login("attach-tenant-b", "ownerb@example.com", "Admin123!")
    headers = {"Authorization": f"Bearer {token}"}
    repair_job_id = _create_repair_job(headers)

    files = {"file": ("bad.exe", io.BytesIO(b"MZ"), "application/x-msdownload")}
    res = client.post("/v1/attachments", headers=headers, params={"repair_job_id": repair_job_id}, files=files)

    assert res.status_code == 415
    assert res.json()["detail"] == "Unsupported file type"


def test_attachment_reject_oversized(monkeypatch):
    token = _bootstrap_and_login("attach-tenant-c", "ownerc@example.com", "Admin123!")
    headers = {"Authorization": f"Bearer {token}"}
    repair_job_id = _create_repair_job(headers)

    monkeypatch.setattr("app.routes.attachments.settings.attachment_max_upload_bytes", 5)
    files = {"file": ("big.txt", io.BytesIO(b"this is too large"), "text/plain")}
    res = client.post("/v1/attachments", headers=headers, params={"repair_job_id": repair_job_id}, files=files)

    assert res.status_code == 413
    assert res.json()["detail"] == "File too large"


def test_attachment_tenant_isolation_download_and_list():
    token_a = _bootstrap_and_login("attach-tenant-d1", "ownerd1@example.com", "Admin123!")
    headers_a = {"Authorization": f"Bearer {token_a}"}
    repair_job_id_a = _create_repair_job(headers_a)

    upload = client.post(
        "/v1/attachments",
        headers=headers_a,
        params={"repair_job_id": repair_job_id_a},
        files={"file": ("a.txt", io.BytesIO(b"tenant-a"), "text/plain")},
    )
    assert upload.status_code == 201
    storage_key = upload.json()["storage_key"]

    token_b = _bootstrap_and_login("attach-tenant-d2", "ownerd2@example.com", "Admin123!")
    headers_b = {"Authorization": f"Bearer {token_b}"}

    list_b = client.get("/v1/attachments", headers=headers_b)
    assert list_b.status_code == 200
    assert all(item["storage_key"] != storage_key for item in list_b.json())

    download_b = client.get(f"/v1/attachments/download/{storage_key}", headers=headers_b)
    assert download_b.status_code == 404
