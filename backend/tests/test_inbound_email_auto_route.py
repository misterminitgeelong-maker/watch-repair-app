"""Auto-routing BCC'd Mister Minit form emails to the matched operator's Lead Inbox.

Off by default. When on, only a clean match is routed: the form's "Nearest Provider"
names one of the network's operators and the customer left a phone or email. Anything
else — and any failure while routing — stays in HQ triage, as it did before.
"""

import os
from pathlib import Path
from uuid import UUID, uuid4

_TEST_DB = Path(__file__).with_name(f"test_inbound_email_auto_route_{uuid4().hex}.db")
os.environ.setdefault("DATABASE_URL", f"sqlite:///{_TEST_DB.as_posix()}")
os.environ.setdefault("JWT_SECRET", "test-secret-not-for-production")
os.environ.setdefault("APP_ENV", "test")

from fastapi.testclient import TestClient
from sqlmodel import Session, select

from app.database import create_db_and_tables, engine
from app.main import app
from app.models import InboundEmail, ProspectLead, Tenant
from app.routes import inbound_email as inbound_email_routes
from network_link_helpers import link_and_accept

create_db_and_tables()
client = TestClient(app)

INBOUND_SECRET = "inbound-email-secret-for-tests-123"

FORM_BODY = """Mister Minit

A customer has just submitted a form!

Please Select Your Location: Victoria
Nearest Provider VIC: Mister Minit Mobile Services Chadstone
First Name: Jamie
Last Name: Example
Email: jamie.example@example.com
Phone: 0400 000 001

Service Required: Key Cutting and Programming
Make: Toyota
Model: Corolla
Year: 2021
Please Provide Details: Lost my only key
at the shops.
How would you like to be contacted: Phone
"""

NO_FIELDS_BODY = """Mister Minit

A customer has just submitted a form!
Go to the app admin page to check details.
"""


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


def _login(slug: str, email: str) -> dict[str, str]:
    res = client.post("/v1/auth/login", json={"tenant_slug": slug, "email": email, "password": "pass123456"})
    assert res.status_code == 200, res.text
    return {"Authorization": f"Bearer {res.json()['access_token']}"}


def _setup(*, auto_route: bool, force_hq: bool = False) -> dict:
    suffix = uuid4().hex[:8]
    hq_slug, hq_email = f"hq-{suffix}", f"hq-{suffix}@test.local"
    op_slug, op_email = f"op-{suffix}", f"op-{suffix}@test.local"
    hq = _bootstrap(hq_slug, hq_email, "enterprise")
    _bootstrap(op_slug, op_email, "basic_auto_key")
    headers = _login(hq_slug, hq_email)

    link = link_and_accept(
        client,
        "/v1/parent-accounts/me/link-tenant",
        headers=headers,
        json={"tenant_slug": op_slug, "owner_email": op_email},
    )
    assert link.status_code == 200, link.text
    with Session(engine) as session:
        operator = session.exec(select(Tenant).where(Tenant.slug == op_slug)).one()
        operator.name = "Mobile Services Chadstone"
        session.add(operator)
        session.commit()
        operator_id = operator.id

    enable = client.post("/v1/parent-accounts/me/mobile-lead-ingest/enable", headers=headers)
    assert enable.status_code == 200, enable.text
    secret = client.put(
        "/v1/parent-accounts/me/inbound-email/secret", headers=headers, json={"webhook_secret": INBOUND_SECRET}
    )
    assert secret.status_code == 200, secret.text
    default = client.put(
        "/v1/parent-accounts/me/mobile-lead-ingest/default-tenant",
        headers=headers,
        json={"tenant_id": hq["tenant_id"]},
    )
    assert default.status_code == 200, default.text

    settings = client.put(
        "/v1/parent-accounts/me/mobile-lead-ingest/dispatch-settings",
        headers=headers,
        json={"inbound_email_auto_route": auto_route, "force_hq_dispatch": force_hq},
    )
    assert settings.status_code == 200, settings.text
    assert settings.json()["inbound_email_auto_route"] is auto_route

    return {
        "headers": headers,
        "ingest_id": enable.json()["mobile_lead_ingest_public_id"],
        "operator_id": operator_id,
        "hq_tenant_id": UUID(hq["tenant_id"]),
    }


def _post(ctx: dict, text: str):
    return client.post(
        f"/v1/public/inbound-email/{ctx['ingest_id']}",
        headers={"X-Inbound-Email-Secret": INBOUND_SECRET},
        data={
            "from": "no-reply@powerfulform.com",
            "to": "autokey@leads.mainspring.test",
            "subject": "New booking enquiry",
            "text": text,
            "headers": f"Message-ID: <{uuid4().hex}@powerfulform.com>",
        },
    )


def _leads_for(tenant_id: UUID) -> list[ProspectLead]:
    with Session(engine) as session:
        return list(session.exec(select(ProspectLead).where(ProspectLead.tenant_id == tenant_id)).all())


def _email(email_id: str) -> InboundEmail:
    with Session(engine) as session:
        return session.get(InboundEmail, UUID(email_id))


def test_matched_email_routes_to_operator_lead_inbox():
    ctx = _setup(auto_route=True)
    res = _post(ctx, FORM_BODY)
    assert res.status_code == 200, res.text
    body = res.json()
    assert body["status"] == "routed"
    assert body["routed_tenant_id"] == str(ctx["operator_id"])

    leads = _leads_for(ctx["operator_id"])
    assert len(leads) == 1
    lead = leads[0]
    assert lead.source == "website_lead"
    assert lead.name == "Jamie Example"
    assert lead.phone == "0400 000 001"
    assert lead.contact_email == "jamie.example@example.com"
    assert lead.state_code == "VIC"
    assert "Service required: Key Cutting and Programming" in lead.notes
    assert "Lost my only key at the shops." in lead.notes
    assert "Vehicle: Toyota Corolla" in lead.notes

    row = _email(body["inbound_email_id"])
    assert row.status == "processed"
    assert row.prospect_lead_id == lead.id
    assert row.routed_tenant_id == ctx["operator_id"]

    listed = client.get("/v1/parent-accounts/me/inbound-emails", headers=ctx["headers"]).json()
    assert listed[0]["routed_tenant_id"] == str(ctx["operator_id"])
    assert listed[0]["prospect_lead_id"] == str(lead.id)
    assert listed[0]["routed_tenant_name"] == "Mobile Services Chadstone"


def test_auto_route_off_by_default_leaves_email_in_hq_triage():
    ctx = _setup(auto_route=False)
    res = _post(ctx, FORM_BODY)
    assert res.status_code == 200, res.text
    assert res.json()["status"] == "received"
    assert _leads_for(ctx["operator_id"]) == []
    assert _email(res.json()["inbound_email_id"]).status == "new"


def test_unmatched_provider_stays_in_hq_triage():
    ctx = _setup(auto_route=True)
    res = _post(ctx, FORM_BODY.replace("Mobile Services Chadstone", "Mobile Services Nowhere"))
    assert res.json()["status"] == "received"
    assert _leads_for(ctx["operator_id"]) == []
    assert _email(res.json()["inbound_email_id"]).status == "new"


def test_email_without_fields_stays_in_hq_triage():
    ctx = _setup(auto_route=True)
    res = _post(ctx, NO_FIELDS_BODY)
    assert res.json()["status"] == "received"
    assert _email(res.json()["inbound_email_id"]).status == "new"


def test_email_without_customer_contact_stays_in_hq_triage():
    ctx = _setup(auto_route=True)
    body = FORM_BODY.replace("Email: jamie.example@example.com\n", "").replace("Phone: 0400 000 001\n", "")
    res = _post(ctx, body)
    assert res.json()["status"] == "received"
    assert _leads_for(ctx["operator_id"]) == []


def test_hq_testing_mode_overrides_auto_route():
    ctx = _setup(auto_route=True, force_hq=True)
    res = _post(ctx, FORM_BODY)
    assert res.json()["status"] == "received"
    assert _leads_for(ctx["operator_id"]) == []


def test_routing_failure_still_captures_email_for_hq(monkeypatch):
    ctx = _setup(auto_route=True)

    def _boom(*_args, **_kwargs):
        raise RuntimeError("sms provider down")

    monkeypatch.setattr(inbound_email_routes, "deliver_website_lead", _boom)
    res = _post(ctx, FORM_BODY)
    assert res.status_code == 200, res.text
    assert res.json()["status"] == "received"
    row = _email(res.json()["inbound_email_id"])
    assert row.status == "new"
    assert row.prospect_lead_id is None
    assert _leads_for(ctx["operator_id"]) == []
