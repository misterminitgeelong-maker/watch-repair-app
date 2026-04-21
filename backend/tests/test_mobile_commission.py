"""Mobile Services technician commission report and rules."""
import json
import os
from datetime import date
from pathlib import Path
from uuid import uuid4

_TEST_DB = Path(__file__).with_name(f"test_mc_{uuid4().hex}.db")
os.environ["DATABASE_URL"] = f"sqlite:///{_TEST_DB.as_posix()}"

from fastapi.testclient import TestClient

from app.database import create_db_and_tables
from app.main import app

create_db_and_tables()
client = TestClient(app)


def _bootstrap() -> tuple[str, str]:
    suffix = uuid4().hex[:8]
    slug = f"mc-{suffix}"
    assert client.post(
        "/v1/auth/bootstrap",
        json={
            "tenant_name": "MC Test",
            "tenant_slug": slug,
            "owner_email": f"owner-{suffix}@test.com",
            "owner_full_name": "Owner",
            "owner_password": "pass123456",
            "plan_code": "enterprise",
        },
    ).status_code == 200
    login = client.post(
        "/v1/auth/login",
        json={"tenant_slug": slug, "email": f"owner-{suffix}@test.com", "password": "pass123456"},
    )
    assert login.status_code == 200
    return login.json()["access_token"], slug


def _customer(h: dict) -> str:
    r = client.post("/v1/customers", headers=h, json={"full_name": "C", "phone": "0411000222"})
    assert r.status_code == 201
    return r.json()["id"]


def _tech_with_commission(h: dict, suffix: str, shop_bp: int = 3000, self_bp: int = 5000, retainer: int = 36000) -> str:
    rules = {
        "enabled": True,
        "retainer_cents_per_period": retainer,
        "revenue_basis": "invoice_total",
        "eligible_job_statuses": ["work_completed", "invoice_paid"],
        "rates_bp": {"shop_referred": shop_bp, "tech_sourced": self_bp},
        "labels": {"shop_referred": "Shop", "tech_sourced": "Self"},
    }
    r = client.post(
        "/v1/users",
        headers=h,
        json={
            "full_name": f"Tech {suffix}",
            "email": f"tech-{suffix}@test.com",
            "password": "pass123456",
            "role": "tech",
            "mobile_commission_rules_json": json.dumps(rules),
        },
    )
    assert r.status_code == 201, r.text
    return r.json()["id"]


def test_commission_rate_minit_sourced_in_defaults():
    from app.mobile_commission import default_mobile_commission_rules_json, parse_mobile_commission_rules, rate_for_lead_source

    rules = parse_mobile_commission_rules(default_mobile_commission_rules_json())
    assert rules is not None
    assert rate_for_lead_source(rules, "minit_sourced") == 4000
    assert rate_for_lead_source(rules, "shop_referred") == 3000


def test_commission_report_retainer_and_rates():
    token, _ = _bootstrap()
    h = {"Authorization": f"Bearer {token}"}
    tid = _tech_with_commission(h, "a", retainer=36000)
    cid = _customer(h)
    today = date.today().isoformat()

    # $1000 + GST invoice total = unit + tax = 1000 + 100 = 1100 ??? 
    # quote: unit 100000 cents = $1000, tax gst ~ 10000 -> total 110000
    unit = 100_000
    tax = 10_000
    r = client.post(
        "/v1/auto-key-jobs",
        headers=h,
        json={
            "customer_id": cid,
            "title": "Shop job",
            "assigned_user_id": tid,
            "key_quantity": 1,
            "priority": "normal",
            "status": "awaiting_quote",
            "programming_status": "pending",
            "deposit_cents": 0,
            "cost_cents": 0,
            "commission_lead_source": "shop_referred",
        },
    )
    assert r.status_code == 201, r.text
    job_id = r.json()["id"]
    q = client.post(
        f"/v1/auto-key-jobs/{job_id}/quotes",
        headers=h,
        json={"line_items": [{"description": "S", "quantity": 1, "unit_price_cents": unit}], "tax_cents": tax},
    )
    assert q.status_code == 201, q.text
    comp = client.post(f"/v1/auto-key-jobs/{job_id}/status", headers=h, json={"status": "work_completed", "note": "x"})
    assert comp.status_code == 200, comp.text

    rep = client.get(
        "/v1/reports/auto-key/commission",
        headers=h,
        params={"date_from": today, "date_to": today},
    )
    assert rep.status_code == 200, rep.text
    data = rep.json()
    assert len(data["technicians"]) == 1
    row = data["technicians"][0]
    assert row["user_id"] == tid
    total_rev = row["lines"][0]["revenue_cents"]
    # 30% of total_rev
    expected_raw = int(total_rev * 3000 / 10_000)
    assert row["raw_commission_cents"] == expected_raw
    assert row["retainer_cents"] == 36000
    assert row["bonus_payable_cents"] == max(0, expected_raw - 36000)
