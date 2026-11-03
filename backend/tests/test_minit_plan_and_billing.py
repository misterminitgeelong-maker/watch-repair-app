"""Minit uncapped operator plan, active-seat counting, and bundled HQ billing."""
from datetime import date
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from sqlmodel import Session

from app import minit_billing as mb
from app.database import create_db_and_tables, engine
from app.dependencies import PLAN_FEATURES, PLAN_LIMITS, VALID_PLAN_CODES, normalize_plan_code
from app.main import app
from app.minit_branding import MINIT_SITE_PLANS
from app.models import ParentAccount, ParentAccountSite, Tenant, User
from app.security import create_access_token, hash_password

client = TestClient(app)
PW = "Password2026!"


# ── plan definition ──────────────────────────────────────────────────────────
def test_minit_operator_plan_is_uncapped_and_matches_basic_auto_key_features():
    assert "minit_operator" in VALID_PLAN_CODES
    assert normalize_plan_code("MINIT_OPERATOR") == "minit_operator"
    assert all(v == 0 for v in PLAN_LIMITS["minit_operator"].values())
    assert PLAN_FEATURES["minit_operator"] == PLAN_FEATURES["basic_auto_key"]
    assert "minit_operator" in MINIT_SITE_PLANS


# ── seat counting ────────────────────────────────────────────────────────────
def _tenant_with_owner(plan: str, extra_users: int = 0, inactive: int = 0):
    create_db_and_tables()
    sfx = uuid4().hex[:8]
    with Session(engine) as db:
        t = Tenant(name=f"T {sfx}", slug=f"t-{sfx}", plan_code=plan)
        db.add(t)
        db.flush()
        owner = User(tenant_id=t.id, email=f"o-{sfx}@test.com", full_name="O", role="owner", password_hash=hash_password(PW))
        db.add(owner)
        for i in range(extra_users + inactive):
            db.add(User(tenant_id=t.id, email=f"u{i}-{sfx}@test.com", full_name="U", role="tech",
                        password_hash=hash_password(PW), is_active=i < extra_users))
        db.commit()
        token, _ = create_access_token(t.id, owner.id, owner.role, sid=uuid4().hex)
    return {"Authorization": f"Bearer {token}"}, sfx


def _add_user(headers, sfx, n):
    return client.post("/v1/users", headers=headers, json={
        "email": f"new{n}-{sfx}@test.com", "full_name": "New", "password": PW, "role": "tech"})


def test_inactive_users_do_not_use_seats():
    # owner + 3 active + 5 inactive: 4 active seats of 5 -> one more fits, the next does not.
    headers, sfx = _tenant_with_owner("basic_auto_key", extra_users=3, inactive=5)
    assert _add_user(headers, sfx, 1).status_code == 201
    assert _add_user(headers, sfx, 2).status_code == 402


def test_minit_operator_plan_has_no_seat_cap():
    headers, sfx = _tenant_with_owner("minit_operator", extra_users=5)  # already 6 users
    assert _add_user(headers, sfx, 1).status_code == 201


# ── pricing rules ────────────────────────────────────────────────────────────
def test_addon_price_steps_after_28_feb_2027():
    assert mb.addon_price_cents(date(2026, 11, 1)) == 1500
    assert mb.addon_price_cents(date(2027, 2, 1)) == 1500
    assert mb.addon_price_cents(date(2027, 2, 28)) == 1500  # inclusive
    assert mb.addon_price_cents(date(2027, 3, 1)) == 2500
    assert mb.parse_month("2027-02") == date(2027, 2, 1)
    with pytest.raises(ValueError):
        mb.parse_month("2027-13")


def _site(i, role="operator", **kw):
    return mb.SiteForBilling(tenant_id=f"t{i}", name=f"Op {i}", network_role=role, shop_number=str(3900 + i), **kw)


def test_exclusions_and_totals():
    sites = [
        _site(1), _site(2), _site(3, billing_exempt=True), _site(4, is_active=False),
        _site(5, role="hq"), _site(6, role="retail"), _site(1),  # duplicate link billed once
    ]
    inv = mb.compute_invoice(sites, date(2027, 2, 1), routing=True, prospecting=True)
    assert inv.operator_count == 2
    assert [l.tenant_id for l in inv.lines] == ["t1", "t2"]
    assert inv.lines[0].subtotal_cents == 5500 + 1500 + 1500
    assert inv.subtotal_cents == 2 * 8500
    assert inv.gst_total_cents == 1700 and inv.total_cents == 18700
    reasons = {t: r for t, _, r in inv.excluded}
    assert reasons == {"t3": "billing_exempt", "t4": "inactive", "t5": "hq", "t6": "not_operator"}


def test_march_2027_addons_and_core_only():
    after = mb.compute_invoice([_site(1)], date(2027, 3, 1), routing=True, prospecting=True)
    assert after.subtotal_cents == 5500 + 2500 + 2500
    core = mb.compute_invoice([_site(1)], date(2027, 3, 1))
    assert core.subtotal_cents == 5500 and core.lines[0].routing_cents == 0


def test_nz_operator_gets_15_percent_gst():
    inv = mb.compute_invoice([_site(1), _site(2, is_nz=True)], date(2026, 12, 1))
    assert inv.gst_by_rate_bp == {1000: 550, 1500: 825}
    d = mb.summary_to_dict(inv)
    assert d["total_inc_gst_cents"] == 11000 + 1375
    assert {g["rate_percent"] for g in d["gst"]} == {10.0, 15.0}


def test_csv_has_line_per_operator_and_total():
    inv = mb.compute_invoice([_site(1), _site(2)], date(2026, 12, 1), routing=True)
    rows = mb.summary_to_csv(inv).strip().splitlines()
    assert len(rows) == 4 and rows[1].split(",")[3:6] == ["55.00", "15.00", "0.00"]
    assert rows[-1].split(",")[2] == "TOTAL"


# ── endpoint ─────────────────────────────────────────────────────────────────
def _network():
    create_db_and_tables()
    sfx = uuid4().hex[:8]
    with Session(engine) as db:
        def mk(slug, **kw):
            t = Tenant(name=slug, slug=f"{slug}-{sfx}", **kw)
            db.add(t)
            db.flush()
            return t

        hq = mk("hq", plan_code="minit_hq")
        parent = ParentAccount(name=f"P {sfx}", owner_email=f"hq-{sfx}@test.com")
        db.add(parent)
        db.flush()

        def link(t, role):
            db.add(ParentAccountSite(parent_account_id=parent.id, tenant_id=t.id, network_role=role))

        link(hq, "hq")
        link(mk("a", plan_code="minit_operator", is_minit=True), "operator")
        link(mk("b", plan_code="minit_operator", is_minit=True, minit_region="NZ"), "operator")
        link(mk("c", plan_code="minit_operator", is_minit=True, billing_exempt=True), "operator")
        link(mk("d", plan_code="booking_only", is_minit=True), "retail")
        hq_owner = User(tenant_id=hq.id, email=f"hq-{sfx}@test.com", full_name="H", role="owner", password_hash=hash_password(PW))
        other = mk("other", plan_code="pro")
        other_owner = User(tenant_id=other.id, email=f"x-{sfx}@test.com", full_name="X", role="owner", password_hash=hash_password(PW))
        admin_t = mk("adm")
        admin = User(tenant_id=admin_t.id, email=f"adm-{sfx}@test.com", full_name="A", role="platform_admin", password_hash=hash_password(PW))
        db.add_all([hq_owner, other_owner, admin])
        db.commit()

        def h(u):
            return {"Authorization": "Bearer " + create_access_token(u.tenant_id, u.id, u.role)[0]}

        return str(parent.id), h(hq_owner), h(other_owner), h(admin)


def test_endpoint_access_and_amounts():
    pid, hq, other, admin = _network()
    url = "/v1/hq-billing/monthly-summary"
    q = {"month": "2027-03", "routing": "true", "prospecting": "true"}
    # platform admin must name the network; unrelated shop owner is refused
    assert client.get(url, headers=admin, params=q).status_code == 422
    assert client.get(url, headers=other, params=q).status_code == 403
    r = client.get(url, headers=admin, params={**q, "parent_account_id": pid})
    assert r.status_code == 200, r.text
    d = r.json()
    assert d["operator_count"] == 2 and d["addon_unit_cents"] == 2500
    assert d["subtotal_ex_gst_cents"] == 2 * 10500
    assert d["gst_total_cents"] == 1050 + 1575
    # HQ owner reads own network without naming it, and gets the same numbers
    own = client.get(url, headers=hq, params=q)
    assert own.status_code == 200 and own.json()["total_inc_gst_cents"] == d["total_inc_gst_cents"]
    assert client.get(url, headers=hq, params={**q, "parent_account_id": str(uuid4())}).status_code == 403
    assert client.get(url, headers=hq, params={"month": "bad"}).status_code == 422
    csv_res = client.get(url + ".csv", headers=hq, params=q)
    assert csv_res.status_code == 200 and csv_res.headers["content-type"].startswith("text/csv")
    assert csv_res.text.strip().splitlines()[-1].split(",")[2] == "TOTAL"
