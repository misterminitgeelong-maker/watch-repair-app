"""Tests for the Mister Minit BCC email-lead parser (backend/app/minit_email_lead_parser.py).

Fixture bodies below mirror the real field layout observed in production
inbound emails (label:value line dump from powerfulform.com), with the
customer's own PII swapped for synthetic values — never commit real
customer data into test fixtures.
"""

import os
from pathlib import Path
from uuid import uuid4

_TEST_DB = Path(__file__).with_name(f"test_minit_email_lead_parser_{uuid4().hex}.db")
os.environ["DATABASE_URL"] = f"sqlite:///{_TEST_DB.as_posix()}"
os.environ.setdefault("JWT_SECRET", "test-secret-not-for-production")
os.environ.setdefault("APP_ENV", "test")

from fastapi.testclient import TestClient
from sqlmodel import Session, select

from app.database import create_db_and_tables, engine
from app.main import app
from app.minit_email_lead_parser import (
    match_operator_for_lead,
    parse_powerfulform_body,
)
from app.models import ParentAccount, Tenant

create_db_and_tables()
client = TestClient(app)

# --- Fixture bodies -----------------------------------------------------
# "Other" service with a wrapped free-text details field, no vehicle info —
# mirrors a real garage-remote enquiry.
BODY_GARAGE_REMOTE = """Mister Minit

A customer has just submitted a form!
Go to the app admin page to check details.

More information

Please Select Your Location: NSW
Nearest Provider NSW: Mister Minit Mobile Services Burwood
First Name: Jamie
Last Name: Example
Email: jamie.example@example.com
Phone: 0400 000 001

Service Required: Other
Please Provide Details: Garage remote replacement, buttons have stopped working
and the strata manager has already been notified.
How would you like to be contacted: Phone

If you have any questions, reply to this email or contact us at orders@misterminit.co

Click here to unsubscribe"""

# Key-cutting service with vehicle fields, no free-text details field.
BODY_KEY_CUTTING = """Mister Minit

A customer has just submitted a form!
Go to the app admin page to check details.

More information

Please Select Your Location: QLD
Nearest Provider QLD: Mister Minit Mobile Services Smithfield / Cairns
First Name: Alex
Last Name: Sample
Email: alex.sample@example.com
Phone: 0411 000 002

Service Required: Key Cutting and Programming
Make: MG
Model: MG3
Year: 2023
How would you like to be contacted: Email

If you have any questions, reply to this email or contact us at orders@misterminit.co

Click here to unsubscribe"""

# Observed in production for some NZ-region leads (e.g. Auckland, Wellington):
# no field data in text_body at all, just the generic notice.
BODY_NO_FIELDS = """Mister Minit

A customer has just submitted a form!
Go to the app admin page to check details.

More information

If you have any questions, reply to this email or contact us at orders@misterminit.co

Click here to unsubscribe"""


def test_parse_garage_remote_body_extracts_all_fields():
    parsed = parse_powerfulform_body(BODY_GARAGE_REMOTE)
    assert parsed.fields_found is True
    assert parsed.location_state_raw == "NSW"
    assert parsed.nearest_provider_raw == "Mister Minit Mobile Services Burwood"
    assert parsed.nearest_provider_clean == "Mobile Services Burwood"
    assert parsed.customer_name == "Jamie Example"
    assert parsed.email == "jamie.example@example.com"
    assert parsed.phone == "0400 000 001"
    assert parsed.service_required == "Other"
    assert parsed.contact_preference == "Phone"
    # Wrapped continuation line folded into the details field.
    assert parsed.details == (
        "Garage remote replacement, buttons have stopped working "
        "and the strata manager has already been notified."
    )
    assert parsed.vehicle_make is None


def test_parse_key_cutting_body_extracts_vehicle_fields():
    parsed = parse_powerfulform_body(BODY_KEY_CUTTING)
    assert parsed.fields_found is True
    assert parsed.nearest_provider_clean == "Mobile Services Smithfield / Cairns"
    assert parsed.service_required == "Key Cutting and Programming"
    assert parsed.vehicle_make == "MG"
    assert parsed.vehicle_model == "MG3"
    assert parsed.vehicle_year == "2023"
    assert parsed.contact_preference == "Email"
    # No "Please Provide Details" line in this template.
    assert parsed.details is None


def test_parse_body_with_no_fields_flags_fields_found_false():
    parsed = parse_powerfulform_body(BODY_NO_FIELDS)
    assert parsed.fields_found is False
    assert parsed.nearest_provider_clean is None
    assert parsed.customer_name is None


def test_parse_none_and_empty_body():
    assert parse_powerfulform_body(None).fields_found is False
    assert parse_powerfulform_body("").fields_found is False


# --- Operator matching ---------------------------------------------------


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


def _setup_parent_with_operator(operator_label: str) -> tuple[uuid4, uuid4]:
    """Bootstrap an HQ parent account with one linked operator tenant.

    Returns (parent_account_id, operator_tenant_id).
    """
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
        session.refresh(tenant)
        parent = session.exec(select(ParentAccount).where(ParentAccount.owner_email == hq_email)).one()
        return parent.id, tenant.id


def test_match_operator_exact_name():
    parent_id, operator_id = _setup_parent_with_operator("Mobile Services Burwood")
    parsed = parse_powerfulform_body(BODY_GARAGE_REMOTE)
    with Session(engine) as session:
        match = match_operator_for_lead(session, parent_id=parent_id, parsed=parsed)
    assert match.confidence == "matched"
    assert match.tenant.id == operator_id


def test_match_operator_loose_punctuation_variant():
    # Tenant name has different slash spacing than the email's provider line.
    parent_id, operator_id = _setup_parent_with_operator("Mobile Services Smithfield/Cairns")
    parsed = parse_powerfulform_body(BODY_KEY_CUTTING)  # "Smithfield / Cairns"
    with Session(engine) as session:
        match = match_operator_for_lead(session, parent_id=parent_id, parsed=parsed)
    assert match.confidence == "matched_loose"
    assert match.tenant.id == operator_id


def test_match_operator_unmatched_when_no_operator_named_that():
    parent_id, _operator_id = _setup_parent_with_operator("Mobile Services Some Other Suburb")
    parsed = parse_powerfulform_body(BODY_GARAGE_REMOTE)  # wants "Burwood"
    with Session(engine) as session:
        match = match_operator_for_lead(session, parent_id=parent_id, parsed=parsed)
    assert match.confidence == "unmatched"
    assert match.tenant is None


def test_match_operator_no_provider_field():
    parent_id, _operator_id = _setup_parent_with_operator("Mobile Services Burwood")
    parsed = parse_powerfulform_body(BODY_NO_FIELDS)
    with Session(engine) as session:
        match = match_operator_for_lead(session, parent_id=parent_id, parsed=parsed)
    assert match.confidence == "no_provider_field"
    assert match.tenant is None
