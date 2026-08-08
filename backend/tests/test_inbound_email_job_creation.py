"""Tests for the inbound-email "parsed preview" + "create job" review-form flow.

Staff review the parser's output in the HQ inbox and confirm before a job is
created — nothing is created automatically, and the job never auto-lands on
the matched operator tenant (see backend/app/routes/inbound_email.py).
"""

import os
from pathlib import Path
from uuid import uuid4

_TEST_DB = Path(__file__).with_name(f"test_inbound_email_job_creation_{uuid4().hex}.db")
os.environ["DATABASE_URL"] = f"sqlite:///{_TEST_DB.as_posix()}"
os.environ.setdefault("JWT_SECRET", "test-secret-not-for-production")
os.environ.setdefault("APP_ENV", "test")

from fastapi.testclient import TestClient
from sqlmodel import Session, select

from app.database import create_db_and_tables, engine
from app.main import app
from app.models import AutoKeyJob, InboundEmail, ParentAccount, Tenant

create_db_and_tables()
client = TestClient(app)

BODY_WITH_FIELDS = """Mister Minit

A customer has just submitted a form!

More information

Please Select Your Location: NSW
Nearest Provider NSW: Mister Minit Mobile Services Burwood
First Name: Jamie
Last Name: Example
Email: jamie.example@example.com
Phone: 0400 000 001

Service Required: Key Cutting and Programming
Make: Toyota
Model: Corolla
Year: 2021
How would you like to be contacted: Phone

If you have any questions, reply to this email.
Click here to unsubscribe"""

BODY_NO_FIELDS = """Mister Minit

A customer has just submitted a form!
Go to the app admin page to check details.

More information

Click here to unsubscribe"""


def _bootstrap(slug: str, email: str, plan_code: str) -> dict:
    res = client.post(
        "/v1/auth/bootstrap",
        json={
            "tenant_name": f"Tenant {slug}",
            "tenant_slug": slug,
            "owner_email": email,
            "owner_full_name": "Owner",
            "owner_password": "pass123456",
            "plan_code": plan_code,
        },
    )
    assert res.status_code == 200, res.text
    return res.json()


def _login(slug: str, email: str) -> str:
    res = client.post(
        "/v1/auth/login",
        json={"tenant_slug": slug, "email": email, "password": "pass123456"},
    )
    assert res.status_code == 200, res.text
    return res.json()["access_token"]


def _setup_hq_with_operator(operator_label: str = "Mobile Services Burwood") -> tuple[str, "uuid4", str]:
    suffix = uuid4().hex[:8]
    hq_slug, hq_email = f"hq-{suffix}", f"hq-{suffix}@test.local"
    op_slug, op_email = f"op-{suffix}", f"op-{suffix}@test.local"

    _bootstrap(hq_slug, hq_email, "enterprise")
    _bootstrap(op_slug, op_email, "basic_auto_key")

    hq_token = _login(hq_slug, hq_email)
    headers = {"Authorization": f"Bearer {hq_token}"}
    link = client.post(
        "/v1/parent-accounts/me/link-tenant",
        headers=headers,
        json={"tenant_slug": op_slug, "owner_email": op_email},
    )
    assert link.status_code == 200, link.text

    with Session(engine) as session:
        tenant = session.exec(select(Tenant).where(Tenant.slug == op_slug)).one()
        tenant.name = operator_label
        session.add(tenant)
        session.commit()

    # HQ's own tenant is the escalation target for jobs created from this flow.
    hq_sites = client.get("/v1/parent-accounts/me/sites?limit=10", headers=headers).json()["sites"]
    hq_tenant_id = next(s["tenant_id"] for s in hq_sites if s["tenant_slug"] == hq_slug)
    esc = client.put(
        "/v1/parent-accounts/me/mobile-lead-ingest/escalation-tenant",
        headers=headers,
        json={"tenant_id": hq_tenant_id},
    )
    assert esc.status_code == 200, esc.text

    return hq_token, hq_tenant_id, hq_email


def _insert_inbound_email(text_body: str, hq_email: str) -> tuple["uuid4", "uuid4"]:
    with Session(engine) as session:
        parent = session.exec(select(ParentAccount).where(ParentAccount.owner_email == hq_email)).one()
        row = InboundEmail(
            parent_account_id=parent.id,
            subject="new booking enquiry for Mister Minit Mobile Services Burwood",
            from_email="no-reply@powerfulform.com",
            text_body=text_body,
        )
        session.add(row)
        session.commit()
        session.refresh(row)
        return row.id, parent.id


def test_parsed_preview_is_read_only_and_matches_operator():
    hq_token, _hq_tenant_id, hq_email = _setup_hq_with_operator()
    headers = {"Authorization": f"Bearer {hq_token}"}
    email_id, _parent_id = _insert_inbound_email(BODY_WITH_FIELDS, hq_email)

    res = client.get(f"/v1/parent-accounts/me/inbound-emails/{email_id}/parsed", headers=headers)
    assert res.status_code == 200, res.text
    data = res.json()
    assert data["fields_found"] is True
    assert data["customer_name"] == "Jamie Example"
    assert data["match_confidence"] == "matched"
    assert data["suggested_operator_name"] == "Mobile Services Burwood"

    # Preview must not have created anything.
    with Session(engine) as session:
        row = session.get(InboundEmail, email_id)
        assert row.status == "new"
        assert row.auto_key_job_id is None
        assert session.exec(select(AutoKeyJob)).first() is None


def test_parsed_preview_no_fields_found():
    hq_token, _hq_tenant_id, hq_email = _setup_hq_with_operator()
    headers = {"Authorization": f"Bearer {hq_token}"}
    email_id, _ = _insert_inbound_email(BODY_NO_FIELDS, hq_email)

    res = client.get(f"/v1/parent-accounts/me/inbound-emails/{email_id}/parsed", headers=headers)
    assert res.status_code == 200, res.text
    data = res.json()
    assert data["fields_found"] is False
    assert data["match_confidence"] == "no_fields_found"
    assert data["customer_name"] is None


def test_create_job_lands_on_hq_tenant_not_matched_operator():
    hq_token, hq_tenant_id, hq_email = _setup_hq_with_operator()
    headers = {"Authorization": f"Bearer {hq_token}"}
    email_id, _ = _insert_inbound_email(BODY_WITH_FIELDS, hq_email)

    res = client.post(
        f"/v1/parent-accounts/me/inbound-emails/{email_id}/create-job",
        headers=headers,
        json={
            "customer_name": "Jamie Example",
            "phone": "0400 000 001",
            "email": "jamie.example@example.com",
            "suburb": "Burwood",
            "state_code": "NSW",
            "service_required": "Key Cutting and Programming",
            "vehicle_make": "Toyota",
            "vehicle_model": "Corolla",
            "vehicle_year": "2021",
            "details": "Lost key, needs a spare cut and programmed.",
            "contact_preference": "Phone",
        },
    )
    assert res.status_code == 201, res.text
    result = res.json()
    assert result["tenant_id"] == str(hq_tenant_id)
    assert result["job_number"].startswith("AK-")

    with Session(engine) as session:
        email_row = session.get(InboundEmail, email_id)
        assert email_row.status == "processed"
        assert str(email_row.auto_key_job_id) == result["auto_key_job_id"]

        job = session.get(AutoKeyJob, email_row.auto_key_job_id)
        assert str(job.tenant_id) == hq_tenant_id
        assert job.vehicle_make == "Toyota"
        assert job.vehicle_year == 2021
        assert "Key Cutting and Programming" in job.description
        assert "Lost key" in job.description


def test_create_job_twice_fails():
    hq_token, _hq_tenant_id, hq_email = _setup_hq_with_operator()
    headers = {"Authorization": f"Bearer {hq_token}"}
    email_id, _ = _insert_inbound_email(BODY_WITH_FIELDS, hq_email)

    body = {"customer_name": "Jamie Example", "phone": "0400 000 001"}
    first = client.post(
        f"/v1/parent-accounts/me/inbound-emails/{email_id}/create-job", headers=headers, json=body
    )
    assert first.status_code == 201, first.text

    second = client.post(
        f"/v1/parent-accounts/me/inbound-emails/{email_id}/create-job", headers=headers, json=body
    )
    assert second.status_code == 409


def test_create_job_can_explicitly_target_operator_tenant():
    hq_token, hq_tenant_id, hq_email = _setup_hq_with_operator()
    headers = {"Authorization": f"Bearer {hq_token}"}
    email_id, _ = _insert_inbound_email(BODY_WITH_FIELDS, hq_email)

    preview = client.get(f"/v1/parent-accounts/me/inbound-emails/{email_id}/parsed", headers=headers).json()
    operator_tenant_id = preview["suggested_operator_tenant_id"]
    assert operator_tenant_id is not None

    res = client.post(
        f"/v1/parent-accounts/me/inbound-emails/{email_id}/create-job",
        headers=headers,
        json={
            "customer_name": "Jamie Example",
            "phone": "0400 000 001",
            "target_tenant_id": operator_tenant_id,
        },
    )
    assert res.status_code == 201, res.text
    result = res.json()
    assert result["tenant_id"] == operator_tenant_id
    assert result["tenant_id"] != str(hq_tenant_id)
