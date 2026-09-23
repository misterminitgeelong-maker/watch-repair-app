import base64
import io
import os
from pathlib import Path
from uuid import UUID, uuid4

from PIL import Image

_TEST_DB = Path(__file__).with_name(f"test_ak_intake_{uuid4().hex}.db")
os.environ.setdefault("DATABASE_URL", f"sqlite:///{_TEST_DB.as_posix()}")

from fastapi.testclient import TestClient
from sqlmodel import Session, select

from app.database import create_db_and_tables, engine
from app.main import app
from app.models import Attachment, AutoKeyJob

create_db_and_tables()
client = TestClient(app)


def _bootstrap_token():
    suffix = uuid4().hex[:8]
    slug = f"akin-{suffix}"
    assert (
        client.post(
            "/v1/auth/bootstrap",
            json={
                "tenant_name": "AK Intake",
                "tenant_slug": slug,
                "owner_email": f"o{suffix}@in.test",
                "owner_full_name": "Owner",
                "owner_password": "pass123456",
                "plan_code": "enterprise",
            },
        ).status_code
        == 200
    )
    login = client.post(
        "/v1/auth/login",
        json={"tenant_slug": slug, "email": f"o{suffix}@in.test", "password": "pass123456"},
    )
    assert login.status_code == 200
    return {"Authorization": f"Bearer {login.json()['access_token']}"}


def test_quick_intake_public_flow():
    h = _bootstrap_token()
    r = client.post(
        "/v1/auto-key-jobs/quick-intake",
        headers=h,
        json={"full_name": "Sam Taylor", "phone": "0412777999"},
    )
    assert r.status_code == 201
    job = r.json()
    assert job["status"] == "awaiting_customer_details"
    # Quick intake titles the job with the customer's first name.
    assert "Sam" in job["title"]

    with Session(engine) as s:
        row = s.get(AutoKeyJob, UUID(job["id"]))
        assert row is not None
        assert row.customer_intake_token
        tok = row.customer_intake_token

    pub = client.get(f"/v1/public/auto-key-intake/{tok}")
    assert pub.status_code == 200
    body = pub.json()
    assert body["job_number"] == job["job_number"]
    assert body["customer_first_name_hint"] == "Sam"

    sub = client.post(
        f"/v1/public/auto-key-intake/{tok}/submit",
        json={
            "vehicle_make": "Toyota",
            "vehicle_model": "Hilux",
            "vehicle_year": 2020,
            "job_type": "Key cut – basic",
            "additional_services": [{"custom": "Spare remote"}],
            "key_quantity": 2,
        },
    )
    assert sub.status_code == 200
    assert sub.json()["ok"] is True

    job2 = client.get(f"/v1/auto-key-jobs/{job['id']}", headers=h)
    assert job2.status_code == 200
    j2 = job2.json()
    assert j2["status"] == "awaiting_quote"
    assert "Sam" in j2["title"] and "Toyota" in j2["title"]
    assert j2["vehicle_year"] == 2020
    assert j2["key_quantity"] == 2
    assert j2.get("additional_services_json")

    with Session(engine) as s:
        row = s.get(AutoKeyJob, UUID(job["id"]))
        assert row is not None
        assert row.status == "awaiting_quote"
        token = row.customer_intake_token

    # Reopening the link afterwards says it's done rather than "invalid".
    again = client.get(f"/v1/public/auto-key-intake/{token}")
    assert again.status_code == 410
    assert again.json()["detail"] == "already_submitted"
    resubmit = client.post(f"/v1/public/auto-key-intake/{token}/submit", json={"description": "again"})
    assert resubmit.status_code == 404


def test_public_intake_requires_details():
    h = _bootstrap_token()
    r = client.post(
        "/v1/auto-key-jobs/quick-intake",
        headers=h,
        json={"full_name": "Pat Lee", "phone": "0499000111"},
    )
    assert r.status_code == 201
    jid = r.json()["id"]
    with Session(engine) as s:
        row = s.get(AutoKeyJob, UUID(jid))
        assert row is not None
        tok = row.customer_intake_token
    bad = client.post(
        f"/v1/public/auto-key-intake/{tok}/submit",
        json={"key_quantity": 1},
    )
    assert bad.status_code == 400


def _tiny_jpeg() -> bytes:
    buf = io.BytesIO()
    Image.new("RGB", (12, 12), (200, 40, 40)).save(buf, format="JPEG")
    return buf.getvalue()


def test_public_intake_key_photo_attaches_to_job():
    h = _bootstrap_token()
    r = client.post(
        "/v1/auto-key-jobs/quick-intake",
        headers=h,
        json={"full_name": "Key Photo", "phone": "0412000999"},
    )
    assert r.status_code == 201
    job_id = r.json()["id"]
    with Session(engine) as s:
        row = s.get(AutoKeyJob, UUID(job_id))
        assert row is not None
        tok = row.customer_intake_token

    missing = client.post(
        "/v1/public/auto-key-intake/not-a-token/photos",
        files=[("files", ("car-key.jpg", io.BytesIO(_tiny_jpeg()), "image/jpeg"))],
    )
    assert missing.status_code == 404

    photo = client.post(
        f"/v1/public/auto-key-intake/{tok}/photos",
        files=[("files", ("car-key.jpg", io.BytesIO(_tiny_jpeg()), "image/jpeg"))],
    )
    assert photo.status_code == 200
    body = photo.json()
    assert body["ok"] is True
    assert body["count"] == 1
    assert len(body["attachment_ids"]) == 1

    listed = client.get("/v1/attachments", headers=h, params={"auto_key_job_id": job_id})
    assert listed.status_code == 200
    items = listed.json()
    assert len(items) == 1
    assert items[0]["auto_key_job_id"] == job_id
    assert items[0]["label"] == "customer_key_photo"
    assert items[0]["content_type"] == "image/jpeg"
    assert items[0]["storage_key"].startswith(f"auto-key-photos/{job_id}/")

    sub = client.post(
        f"/v1/public/auto-key-intake/{tok}/submit",
        json={"vehicle_make": "Mazda", "description": "Lost spare"},
    )
    assert sub.status_code == 200

    with Session(engine) as s:
        att = s.exec(select(Attachment).where(Attachment.auto_key_job_id == UUID(job_id))).first()
        assert att is not None
        assert att.label == "customer_key_photo"

    after = client.post(
        f"/v1/public/auto-key-intake/{tok}/photos",
        files=[("files", ("car-key.jpg", io.BytesIO(_tiny_jpeg()), "image/jpeg"))],
    )
    assert after.status_code == 404


def test_public_intake_submit_attaches_key_photo():
    h = _bootstrap_token()
    r = client.post(
        "/v1/auto-key-jobs/quick-intake",
        headers=h,
        json={"full_name": "Submit Photo", "phone": "0412333444"},
    )
    assert r.status_code == 201
    job_id = r.json()["id"]
    with Session(engine) as s:
        row = s.get(AutoKeyJob, UUID(job_id))
        assert row is not None
        tok = row.customer_intake_token

    photo_b64 = base64.b64encode(_tiny_jpeg()).decode("ascii")
    sub = client.post(
        f"/v1/public/auto-key-intake/{tok}/submit",
        json={
            "vehicle_make": "Honda",
            "description": "Spare key",
            "key_photo_data": photo_b64,
        },
    )
    assert sub.status_code == 200

    listed = client.get("/v1/attachments", headers=h, params={"auto_key_job_id": job_id})
    assert listed.status_code == 200
    items = listed.json()
    assert len(items) == 1
    assert items[0]["auto_key_job_id"] == job_id
    assert items[0]["label"] == "customer_key_photo"
    assert items[0]["storage_key"].startswith(f"auto-key-photos/{job_id}/")


def test_public_intake_key_photo_rejects_non_image():
    h = _bootstrap_token()
    r = client.post(
        "/v1/auto-key-jobs/quick-intake",
        headers=h,
        json={"full_name": "No File", "phone": "0412111222"},
    )
    assert r.status_code == 201
    with Session(engine) as s:
        row = s.get(AutoKeyJob, UUID(r.json()["id"]))
        assert row is not None
        tok = row.customer_intake_token

    bad = client.post(
        f"/v1/public/auto-key-intake/{tok}/photos",
        files=[("files", ("notes.txt", io.BytesIO(b"not a photo"), "text/plain"))],
    )
    assert bad.status_code == 415
