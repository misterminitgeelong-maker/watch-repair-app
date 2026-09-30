"""Tests for the daily/weekly/monthly lead volume report."""

import os
from pathlib import Path
from uuid import uuid4

_TEST_DB = Path(__file__).with_name(f"test_lead_volume_{uuid4().hex}.db")
os.environ.setdefault("DATABASE_URL", f"sqlite:///{_TEST_DB.as_posix()}")
os.environ.setdefault("JWT_SECRET", "test-secret-not-for-production")
os.environ.setdefault("APP_ENV", "test")

from fastapi.testclient import TestClient
from sqlmodel import Session, select

from app.database import create_db_and_tables, engine
from app.main import app
from app.minit_provision import ensure_minit_pilot_account
from datetime import datetime, timedelta, timezone

from app.models import InboundEmail, MobileLeadDispatch, ParentAccount

create_db_and_tables()
client = TestClient(app)

HQ_EMAIL = "hq-owner@test.mainspring.au"
HQ_PASSWORD = "MinitPilot2026!"

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



def test_lead_volume_counts_website_and_email_leads():
    token, _ = _ensure_hq()
    headers = {"Authorization": f"Bearer {token}"}
    url = "/v1/parent-accounts/me/operations/lead-volume"
    before = client.get(url, headers=headers).json()

    now = datetime.now(timezone.utc)
    with Session(engine) as session:
        parent = session.exec(select(ParentAccount).where(ParentAccount.owner_email == HQ_EMAIL)).one()
        session.add(InboundEmail(parent_account_id=parent.id, subject="x", created_at=now))
        session.add(InboundEmail(parent_account_id=parent.id, subject="old", created_at=now - timedelta(days=90)))
        session.add(
            MobileLeadDispatch(
                parent_account_id=parent.id, suburb="Burwood", state_code="NSW",
                suburb_normalized="burwood", payload_json="{}", candidate_operator_ids_json="[]",
                created_at=now,
            )
        )
        session.commit()

    data = client.get(url, headers=headers).json()
    assert (len(data["daily"]), len(data["weekly"]), len(data["monthly"])) == (30, 12, 12)
    for key in ("daily", "weekly", "monthly"):
        assert data[key][-1]["total"] - before[key][-1]["total"] == 2
        assert data[key][-1]["website_leads"] - before[key][-1]["website_leads"] == 1
        assert data[key][-1]["email_leads"] - before[key][-1]["email_leads"] == 1
    # The 90-day-old email shows up in the monthly view only.
    assert sum(b["email_leads"] for b in data["daily"]) - sum(b["email_leads"] for b in before["daily"]) == 1
    assert sum(b["email_leads"] for b in data["monthly"]) - sum(b["email_leads"] for b in before["monthly"]) == 2
