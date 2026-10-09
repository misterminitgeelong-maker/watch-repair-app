"""HQ shoe-repair view: network-wide numbers and search, scoped to the HQ's own shops."""
from datetime import datetime, timedelta, timezone
from uuid import UUID, uuid4

from fastapi.testclient import TestClient
from sqlmodel import Session

from app.database import create_db_and_tables, engine
from app.main import app
from app.models import (
    Customer, ParentAccountSite, Shoe, ShoeJobStatusHistory, ShoeRepairJob, ShoeRepairJobItem, Tenant, User,
)
from app.security import create_access_token, hash_password

client = TestClient(app)
SUMMARY = "/v1/parent-accounts/me/operations/shoe-jobs/summary"
SEARCH = "/v1/parent-accounts/me/operations/shoe-jobs/search"


def _admin():
    create_db_and_tables()
    sfx = uuid4().hex[:8]
    with Session(engine) as db:
        t = Tenant(name="Admin", slug=f"admin-{sfx}")
        db.add(t); db.flush()
        u = User(tenant_id=t.id, email=f"a-{sfx}@t.com", full_name="A", role="platform_admin", password_hash=hash_password("Password2026!"))
        db.add(u); db.commit()
        tok, _ = create_access_token(u.tenant_id, u.id, u.role)
    return {"Authorization": f"Bearer {tok}"}


def _hq(admin, modules):
    slug = f"hq-{uuid4().hex[:6]}"
    made = client.post("/v1/platform-admin/hqs", headers=admin, json={
        "slug": slug, "display_name": f"Co {slug}", "modules": modules, "site_plans": ["basic_shoe"],
        "owner_name": "Owner", "owner_email": f"{slug}@t.com", "send_invite": False}).json()
    token = made["invite_url"].rsplit("/", 1)[1]
    done = client.post(f"/v1/public/hq-invite/{token}/complete", json={"password": "Password2026!"}).json()
    return made, {"Authorization": f"Bearer {done['access_token']}"}


def _shop(parent_id, name, jobs):
    """jobs: list of (number, status, customer, phone, price_cents, days_old)."""
    with Session(engine) as db:
        shop = Tenant(name=name, slug=f"s-{uuid4().hex[:8]}", plan_code="basic_shoe")
        db.add(shop); db.flush()
        db.add(ParentAccountSite(parent_account_id=UUID(parent_id), tenant_id=shop.id, network_role="retail"))
        for number, status, cust, phone, price, days in jobs:
            c = Customer(tenant_id=shop.id, full_name=cust, phone=phone)
            db.add(c); db.flush()
            s = Shoe(tenant_id=shop.id, customer_id=c.id, brand="Birkenstock", shoe_type="sandals")
            db.add(s); db.flush()
            created = datetime.now(timezone.utc) - timedelta(days=days)
            j = ShoeRepairJob(tenant_id=shop.id, shoe_id=s.id, job_number=number, title="Resole", status=status, created_at=created)
            db.add(j); db.flush()
            db.add(ShoeRepairJobItem(tenant_id=shop.id, shoe_repair_job_id=j.id, catalogue_key="k", catalogue_group="g",
                                     item_name="Sole", pricing_type="fixed", unit_price_cents=price, quantity=1))
            if status == "collected":
                db.add(ShoeJobStatusHistory(tenant_id=shop.id, shoe_repair_job_id=j.id, old_status="awaiting_collection",
                                            new_status="collected", created_at=created + timedelta(days=4)))
        db.commit()
        return str(shop.id)


def test_summary_and_search_cover_every_shop_in_the_network():
    admin = _admin()
    hq, headers = _hq(admin, ["shoe"])
    a = _shop(hq["parent_account_id"], "Chadstone", [
        ("SHO-00001", "working_on", "Anna Walker", "0400111222", 8000, 10),
        ("SHO-00002", "collected", "Ben Lee", None, 9000, 6),
    ])
    _shop(hq["parent_account_id"], "Bondi", [("SHO-00001", "awaiting_collection", "Cara Lim", None, 4000, 2)])
    summary = client.get(SUMMARY, headers=headers)
    assert summary.status_code == 200, summary.text
    data = summary.json()
    assert data["totals"]["shops"] == 2 and data["totals"]["opened"] == 3
    assert data["totals"]["active"] == 2 and data["totals"]["ready_to_collect"] == 1 and data["totals"]["collected"] == 1
    assert data["totals"]["billed_cents"] == 21000 and data["totals"]["avg_turnaround_days"] == 4.0
    chad = next(r for r in data["by_shop"] if r["tenant_id"] == a)
    assert chad["oldest_active_days"] == 10 and chad["avg_turnaround_days"] == 4.0
    # The same ticket number in two shops is two different repairs.
    both = client.get(SEARCH, headers=headers, params={"q": "SHO-00001"}).json()["jobs"]
    assert {j["tenant_name"] for j in both} == {"Chadstone", "Bondi"}
    assert [j["customer_name"] for j in client.get(SEARCH, headers=headers, params={"q": "walker"}).json()["jobs"]] == ["Anna Walker"]
    assert len(client.get(SEARCH, headers=headers, params={"q": "0400 111 222"}).json()["jobs"]) == 1
    assert len(client.get(SEARCH, headers=headers, params={"status": "collected"}).json()["jobs"]) == 1
    assert len(client.get(SEARCH, headers=headers, params={"tenant_id": a}).json()["jobs"]) == 2


def test_another_hqs_shops_are_invisible_and_unaddressable():
    admin = _admin()
    hq1, h1 = _hq(admin, ["shoe"])
    hq2, h2 = _hq(admin, ["shoe"])
    _shop(hq1["parent_account_id"], "Mine", [("SHO-00009", "working_on", "Mine Customer", None, 1000, 1)])
    theirs = _shop(hq2["parent_account_id"], "Theirs", [("SHO-00009", "working_on", "Their Customer", None, 5000, 1)])
    jobs = client.get(SEARCH, headers=h1, params={"q": "SHO-00009"}).json()["jobs"]
    assert [j["tenant_name"] for j in jobs] == ["Mine"]
    assert client.get(SEARCH, headers=h1, params={"tenant_id": theirs}).status_code == 404
    assert client.get(SUMMARY, headers=h1).json()["totals"]["billed_cents"] == 1000


def test_needs_shoe_module_and_hq_login():
    admin = _admin()
    _, no_shoe = _hq(admin, ["mobile_services"])
    assert client.get(SUMMARY, headers=no_shoe).status_code == 403
    assert client.get(SEARCH, headers=no_shoe).status_code == 403
    assert client.get(SUMMARY, headers=admin).status_code == 403
    assert client.get(SUMMARY).status_code in (401, 403)


def test_empty_network_and_bad_dates():
    admin = _admin()
    _, headers = _hq(admin, ["shoe"])
    assert client.get(SUMMARY, headers=headers).json()["totals"]["opened"] == 0
    assert client.get(SEARCH, headers=headers).json() == {"jobs": [], "has_more": False}
    assert client.get(SUMMARY, headers=headers, params={"from_date": "nonsense"}).status_code == 400
