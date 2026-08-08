"""Tests for the "email leads by shop" report (backend/app/routes/parent_operations.py).

Answers "which shops' enquiries are actually getting actioned" by bucketing
captured InboundEmail rows by matched operator and new/processed/dismissed
counts — used to power the Mobile jobs page's shop-enquiry breakdown.
"""

import os
from pathlib import Path
from uuid import uuid4

_TEST_DB = Path(__file__).with_name(f"test_email_leads_by_shop_{uuid4().hex}.db")
os.environ["DATABASE_URL"] = f"sqlite:///{_TEST_DB.as_posix()}"
os.environ.setdefault("JWT_SECRET", "test-secret-not-for-production")
os.environ.setdefault("APP_ENV", "test")

from fastapi.testclient import TestClient
from sqlmodel import Session, select

from app.database import create_db_and_tables, engine
from app.main import app
from app.minit_provision import ensure_minit_pilot_account
from app.models import InboundEmail, ParentAccount, Tenant

create_db_and_tables()
client = TestClient(app)

HQ_EMAIL = "hq-owner@test.mainspring.au"
HQ_PASSWORD = "MinitPilot2026!"

BODY_MATCHED = """Mister Minit

A customer has just submitted a form!

More information

Please Select Your Location: NSW
Nearest Provider NSW: Mister Minit Mobile Services Burwood
First Name: Jamie
Last Name: Example
Phone: 0400 000 001

Service Required: Key Cutting and Programming
How would you like to be contacted: Phone

Click here to unsubscribe"""

BODY_NO_FIELDS = """Mister Minit

A customer has just submitted a form!
Go to the app admin page to check details.

More information

Click here to unsubscribe"""


def _ensure_hq() -> tuple[str, str]:
    """Idempotent HQ bootstrap — returns (token, parent_owner_email)."""
    with Session(engine) as session:
        ensure_minit_pilot_account(
            session,
            parent_name="Mister Minit",
            hq_tenant_slug="mmsupport",
            hq_tenant_name="Mister Minit HQ",
            hq_owner_email=HQ_EMAIL,
            hq_owner_password=HQ_PASSWORD,
        )
    login = client.post(
        "/v1/auth/login",
        json={"tenant_slug": "mmsupport", "email": HQ_EMAIL, "password": HQ_PASSWORD},
    )
    assert login.status_code == 200, login.text
    return login.json()["access_token"], HQ_EMAIL


def _link_operator(headers: dict, operator_label: str) -> str:
    suffix = uuid4().hex[:8]
    slug, email = f"op-{suffix}", f"op-{suffix}@test.local"
    res = client.post(
        "/v1/auth/bootstrap",
        json={
            "tenant_name": f"Tenant {slug}",
            "tenant_slug": slug,
            "owner_email": email,
            "owner_full_name": "Owner",
            "owner_password": "pass123456",
            "plan_code": "basic_auto_key",
        },
    )
    assert res.status_code == 200, res.text
    link = client.post("/v1/parent-accounts/me/link-tenant", headers=headers, json={"tenant_slug": slug, "owner_email": email})
    assert link.status_code == 200, link.text
    with Session(engine) as session:
        tenant = session.exec(select(Tenant).where(Tenant.slug == slug)).one()
        tenant.name = operator_label
        session.add(tenant)
        session.commit()
        return str(tenant.id)


def _insert_email(text_body: str, status: str = "new") -> None:
    with Session(engine) as session:
        parent = session.exec(select(ParentAccount).where(ParentAccount.owner_email == HQ_EMAIL)).one()
        session.add(
            InboundEmail(
                parent_account_id=parent.id,
                subject="new booking enquiry",
                from_email="no-reply@powerfulform.com",
                text_body=text_body,
                status=status,
            )
        )
        session.commit()


def test_report_buckets_by_matched_operator_and_status():
    token, _ = _ensure_hq()
    headers = {"Authorization": f"Bearer {token}"}
    operator_id = _link_operator(headers, "Mobile Services Burwood")

    _insert_email(BODY_MATCHED, status="new")
    _insert_email(BODY_MATCHED, status="new")
    _insert_email(BODY_MATCHED, status="processed")
    _insert_email(BODY_NO_FIELDS, status="new")

    res = client.get("/v1/parent-accounts/me/operations/email-leads-by-shop", headers=headers)
    assert res.status_code == 200, res.text
    data = res.json()

    burwood = next(s for s in data["shops"] if s["operator_tenant_id"] == operator_id)
    assert burwood["operator_name"] == "Mobile Services Burwood"
    assert burwood["total_count"] == 3
    assert burwood["new_count"] == 2
    assert burwood["processed_count"] == 1
    assert burwood["oldest_new_at"] is not None

    no_fields_bucket = next(s for s in data["shops"] if s["operator_tenant_id"] is None and "No fields" in s["operator_name"])
    assert no_fields_bucket["total_count"] == 1
    assert no_fields_bucket["new_count"] == 1

    # Most-unactioned bucket sorts first.
    assert data["shops"][0]["new_count"] >= data["shops"][-1]["new_count"]


def test_report_unmatched_operator_name_bucket():
    token, _ = _ensure_hq()
    headers = {"Authorization": f"Bearer {token}"}
    # No operator named "Mobile Services Burwood" linked this time — every prior
    # test's data is still in the shared DB, so just confirm a fresh unmatched
    # email lands in an "(no matching operator)" bucket distinct from real matches.
    body_other_suburb = BODY_MATCHED.replace("Burwood", "Nowhere Special")
    _insert_email(body_other_suburb, status="new")

    res = client.get("/v1/parent-accounts/me/operations/email-leads-by-shop", headers=headers)
    assert res.status_code == 200, res.text
    data = res.json()
    unmatched = [s for s in data["shops"] if s["operator_tenant_id"] is None and "no matching operator" in s["operator_name"]]
    assert any("Nowhere Special" in s["operator_name"] for s in unmatched)


def test_report_requires_minit_hq():
    # A generic (non-Minit) multi-site tenant must not be able to call this report.
    suffix = uuid4().hex[:8]
    slug, email = f"generic-{suffix}", f"generic-{suffix}@test.local"
    res = client.post(
        "/v1/auth/bootstrap",
        json={
            "tenant_name": "Generic HQ", "tenant_slug": slug, "owner_email": email,
            "owner_full_name": "Owner", "owner_password": "pass123456", "plan_code": "enterprise",
        },
    )
    assert res.status_code == 200, res.text
    login = client.post("/v1/auth/login", json={"tenant_slug": slug, "email": email, "password": "pass123456"})
    token = login.json()["access_token"]
    res = client.get(
        "/v1/parent-accounts/me/operations/email-leads-by-shop",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert res.status_code == 403
