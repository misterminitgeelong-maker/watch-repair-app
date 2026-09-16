"""The regional manager's cockpit and the pieces around it.

1. A region's week is the sum of its shops, ranked against the other regions,
   with movers and a shop table underneath.
2. A regional manager sees their region and nothing else on the network.
3. A region-week note shows on every shop in it and, when excluded, drops out
   of every shop's baselines.
4. Anomalies are judged against each shop's own distribution, not a fixed %.
5. The narrative says what the numbers say.
6. Targets can be filled for a whole region from one rule.
7. Opening a shop from HQ records why, in HQ's feed and the shop's inbox.
8. The Monday email goes to the regional manager once a week.
"""

import os
from datetime import timedelta
from pathlib import Path
from uuid import UUID, uuid4

_TEST_DB = Path(__file__).with_name(f"test_regional_cockpit_{uuid4().hex}.db")
os.environ.setdefault("DATABASE_URL", f"sqlite:///{_TEST_DB.as_posix()}")
os.environ.setdefault("JWT_SECRET", "test-secret-not-for-production")
os.environ.setdefault("APP_ENV", "test")

from fastapi.testclient import TestClient
from sqlmodel import Session, select

from app.database import create_db_and_tables, engine
from app.main import app
from app.models import (
    ParentAccount,
    ParentAccountEventLog,
    Region,
    Tenant,
    TenantEventLog,
    VswtReportTarget,
    VswtWeeklyShopMetric,
)
from app.vswt_insights import baseline_for

create_db_and_tables()
client = TestClient(app)
PASSWORD = "pass123456"


def _bootstrap(slug: str, email: str, plan_code: str) -> dict:
    res = client.post(
        "/v1/auth/bootstrap",
        json={
            "tenant_name": f"Tenant {slug}",
            "tenant_slug": slug,
            "owner_email": email,
            "owner_full_name": "Owner",
            "owner_password": PASSWORD,
            "plan_code": plan_code,
        },
    )
    assert res.status_code == 200, res.text
    return res.json()


def _login(slug: str, email: str, password: str = PASSWORD) -> str:
    res = client.post("/v1/auth/login", json={"tenant_slug": slug, "email": email, "password": password})
    assert res.status_code == 200, res.text
    return res.json()["access_token"]


def _h(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def _seed_metric(week: int, shop_number: str, name: str, sales: float, customers: float = 100, jobs: float = 120, **extra):
    with Session(engine) as db:
        db.add(
            VswtWeeklyShopMetric(
                week_seq=week,
                shop_number=shop_number,
                shop_name=name,
                area_name="TEST AREA",
                store_format="FR",
                comp_status="Comp",
                sales_ty=sales,
                customer_ty=customers,
                jobs_ty=jobs,
                sales_ly=extra.pop("sales_ly", sales * 0.9),
                customer_ly=customers * 0.9,
                jobs_ly=jobs * 0.9,
                **extra,
            )
        )
        db.commit()


def _network(suffix: str) -> dict:
    """HQ + two regions (VIC: 2 shops, QLD: 1 shop) + one unassigned shop, with
    distinct week numbers per network so tests do not see each other's data."""
    hq_slug = f"hq-{suffix}"
    hq_email = f"hq-{suffix}@region.test"
    hq = _bootstrap(hq_slug, hq_email, "pro")
    hq_h = _h(_login(hq_slug, hq_email))
    base = int(suffix[:5], 16) % 800000 + 100000  # unique shop-number block per network

    def provision(n: int, name: str) -> str:
        num = str(base + n)
        res = client.post(
            "/v1/parent-accounts/me/provision-shop",
            headers=hq_h,
            json={"shop_number": num, "tenant_name": name},
        )
        assert res.status_code == 200, res.text
        return num

    shops = {
        "vic1": provision(1, "Frankston"),
        "vic2": provision(2, "Southland"),
        "qld1": provision(3, "Chermside"),
        "none": provision(4, "Nowhere"),
    }
    vic = client.post("/v1/parent-accounts/me/regions", headers=hq_h, json={"name": "VIC", "manager_name": "Dana", "manager_email": f"dana-{suffix}@region.test"})
    qld = client.post("/v1/parent-accounts/me/regions", headers=hq_h, json={"name": "QLD"})
    assert vic.status_code == 200 and qld.status_code == 200, (vic.text, qld.text)
    sites = {s["shop_number"]: s for s in client.get("/v1/parent-accounts/me/sites?limit=100", headers=hq_h).json()["sites"]}
    for key, region_id in (("vic1", vic.json()["id"]), ("vic2", vic.json()["id"]), ("qld1", qld.json()["id"])):
        r = client.patch(f"/v1/parent-accounts/me/sites/{sites[shops[key]]['tenant_id']}", headers=hq_h, json={"region_id": region_id})
        assert r.status_code == 200, r.text
    return {
        "hq": hq_h,
        "hq_slug": hq_slug,
        "hq_email": hq_email,
        "hq_tenant_id": hq["tenant_id"],
        "shops": shops,
        "sites": sites,
        "vic": vic.json()["id"],
        "qld": qld.json()["id"],
        "week0": 500000 + (int(suffix[:4], 16) % 4000) * 100,  # 100-week block per network
    }


def _seed_history(net: dict, weeks: int, *, vic1=10000.0, vic2=8000.0, qld1=6000.0, none=5000.0, last_week_override: dict | None = None):
    w0 = net["week0"]
    for i in range(weeks):
        week = w0 + i
        values = {"vic1": vic1, "vic2": vic2, "qld1": qld1, "none": none}
        if last_week_override and i == weeks - 1:
            values.update(last_week_override)
        for key, sales in values.items():
            _seed_metric(week, net["shops"][key], key.upper(), sales)
    return [w0 + i for i in range(weeks)]


# ── 1. region rollup, ranking, movers ────────────────────────────────────────


def test_region_cockpit_rolls_up_its_shops_and_ranks_against_other_regions():
    suffix = uuid4().hex[:8]
    net = _network(suffix)
    weeks = _seed_history(net, 3, last_week_override={"vic1": 12000.0, "vic2": 6000.0})

    res = client.get(f"/v1/parent-accounts/me/regions/{net['vic']}/cockpit", headers=net["hq"], params={"week": weeks[-1]})
    assert res.status_code == 200, res.text
    body = res.json()
    assert body["available"] is True
    assert body["region"]["name"] == "VIC"
    assert body["shop_count"] == 2 and body["shops_reported"] == 2
    sales = next(r for r in body["rows"] if r["key"] == "sales_ty")
    assert sales["current"] == 18000  # 12000 + 6000
    assert sales["previous"] == 18000  # 10000 + 8000
    assert sales["delta_pct"] == 0
    avg_sale = next(r for r in body["rows"] if r["key"] == "avg_sale")
    assert avg_sale["current"] == 18000 / 200  # region's real average sale, not the mean of averages
    # VIC (18000) outranks QLD (6000); the unassigned shop is in no region.
    assert sales["rank"] == 1 and body["region_count"] == 2
    lb = {row["region_name"]: row for row in body["leaderboard"]}
    assert lb["VIC"]["is_me"] and lb["QLD"]["rank"] == 2

    up, down = body["movers"]["up"], body["movers"]["down"]
    assert up[0]["shop_name"] == "VIC1" and round(up[0]["delta_pct"], 2) == 0.2
    assert down[0]["shop_name"] == "VIC2" and round(down[0]["delta_pct"], 2) == -0.25
    table = {r["shop_name"]: r for r in body["shops"]}
    assert table["VIC1"]["rank_in_region"] == 1 and table["VIC2"]["rank_in_region"] == 2
    assert table["VIC1"]["rank_in_network"] == 1  # 12000 beats every other shop in the upload
    assert "VIC's 2 shops took $18,000" in body["narrative"]
    assert "VIC2 moved most against the trend" in body["narrative"]


# ── 2. region-scoped access ──────────────────────────────────────────────────


def test_regional_manager_sees_their_region_and_nothing_else():
    suffix = uuid4().hex[:8]
    net = _network(suffix)
    _seed_history(net, 2)
    mgr_email = f"dana-{suffix}@region.test"
    made = client.post(
        "/v1/users",
        headers=net["hq"],
        json={"email": mgr_email, "full_name": "Dana", "password": PASSWORD, "role": "manager"},
    )
    assert made.status_code == 201, made.text
    granted = client.put(
        "/v1/parent-accounts/me/users",
        headers=net["hq"],
        json={"email": mgr_email, "role": "hq_viewer", "region_id": net["vic"]},
    )
    assert granted.status_code == 200, granted.text
    listing = {u["email"]: u for u in granted.json()}
    assert listing[mgr_email]["region_name"] == "VIC"

    dana = _h(_login(net["hq_slug"], mgr_email))
    me = client.get("/v1/parent-accounts/me", headers=dana).json()
    assert me["my_role"] == "hq_viewer" and me["my_region_id"] == net["vic"]
    assert me["site_count"] == 2

    assert client.get(f"/v1/parent-accounts/me/regions/{net['vic']}/cockpit", headers=dana).status_code == 200
    assert client.get(f"/v1/parent-accounts/me/regions/{net['qld']}/cockpit", headers=dana).status_code == 403
    regions = client.get("/v1/parent-accounts/me/regions", headers=dana).json()
    assert [r["name"] for r in regions] == ["VIC"]
    sites = client.get("/v1/parent-accounts/me/sites", headers=dana, params={"region": "QLD"}).json()
    assert {s["region"] for s in sites["sites"]} == {"VIC"}  # asked for QLD, confined to VIC
    # Network-wide reads are refused outright.
    assert client.get("/v1/parent-accounts/me/operations/overview", headers=dana).status_code == 403
    assert client.get("/v1/parent-accounts/me/users", headers=dana).status_code == 403
    # ...and so are writes.
    assert client.post(f"/v1/parent-accounts/me/regions/{net['vic']}/targets/fill", headers=dana, json={"strategy": "previous_week"}).status_code == 403
    # But they may annotate their own region.
    noted = client.put(
        f"/v1/parent-accounts/me/regions/{net['vic']}/annotations",
        headers=dana,
        json={"week": net["week0"] + 1, "event_type": "holiday", "note": "Cup day"},
    )
    assert noted.status_code == 200, noted.text
    assert client.put(
        f"/v1/parent-accounts/me/regions/{net['qld']}/annotations",
        headers=dana,
        json={"week": net["week0"] + 1, "event_type": "holiday", "note": "Cup day"},
    ).status_code == 403


# ── 3. region notes propagate and exclude ────────────────────────────────────


def test_region_week_note_shows_on_every_shop_and_can_exclude_the_week():
    suffix = uuid4().hex[:8]
    net = _network(suffix)
    # 5 steady weeks, then a flood week at half sales, then a normal week.
    weeks = _seed_history(net, 7, last_week_override={})
    flood = weeks[5]
    with Session(engine) as db:
        for sn in (net["shops"]["vic1"], net["shops"]["vic2"]):
            row = db.exec(select(VswtWeeklyShopMetric).where(VswtWeeklyShopMetric.week_seq == flood).where(VswtWeeklyShopMetric.shop_number == sn)).one()
            row.sales_ty = row.sales_ty / 2
            db.add(row)
        db.commit()

    shop_h = _h(_login(f"minit-{net['shops']['vic1']}", net["hq_email"]))
    before = client.get("/v1/reports/vswt/cockpit", headers=shop_h, params={"week": weeks[-1]}).json()
    assert before["available"], before
    assert before["region"]["name"] == "VIC"
    sales_before = next(r for r in before["rows"] if r["key"] == "sales_ty")
    assert sales_before["rolling_4"] == (10000 * 3 + 5000) / 4

    noted = client.put(
        f"/v1/parent-accounts/me/regions/{net['vic']}/annotations",
        headers=net["hq"],
        json={"week": flood, "event_type": "closure", "note": "Centre flooded Tuesday", "exclude_from_baselines": True},
    )
    assert noted.status_code == 200, noted.text

    after = client.get("/v1/reports/vswt/cockpit", headers=shop_h, params={"week": weeks[-1]}).json()
    assert [n["note"] for n in after["region_annotations"]] == ["Centre flooded Tuesday"]
    assert after["excluded_weeks"] == [flood]
    sales_after = next(r for r in after["rows"] if r["key"] == "sales_ty")
    assert sales_after["rolling_4"] == 10000  # the flood week no longer drags the baseline
    assert f"Week {flood} is excluded from the baselines." in after["narrative"]

    # Same on the region cockpit.
    region = client.get(f"/v1/parent-accounts/me/regions/{net['vic']}/cockpit", headers=net["hq"], params={"week": weeks[-1]}).json()
    assert region["excluded_weeks"] == [flood]
    assert next(r for r in region["rows"] if r["key"] == "sales_ty")["rolling_4"] == 18000


# ── 4. anomalies against the shop's own distribution ─────────────────────────


def test_anomaly_is_relative_to_each_shops_own_volatility():
    steady = [40000.0] * 10 + [37600.0]  # -6%
    volatile = [8000, 9500, 7000, 9800, 6800, 9200, 7300, 9600, 7100, 9400, 8100.0]  # -12% vs the last but normal
    steady_base = baseline_for(steady[-1], steady[:-1])
    volatile_base = baseline_for(volatile[-1], volatile[:-1])
    assert steady_base.anomaly == "low" and steady_base.zscore is not None and steady_base.zscore < -2
    assert volatile_base.anomaly is None
    # Too little history: no verdict either way.
    assert baseline_for(100.0, [100.0, 100.0]).zscore is None


def test_shop_cockpit_flags_an_unusual_week_and_narrates_it():
    suffix = uuid4().hex[:8]
    net = _network(suffix)
    sales = [10000, 10200, 9900, 10100, 10000, 9950, 10050, 10000, 7000.0]
    w0 = net["week0"]
    for i, value in enumerate(sales):
        _seed_metric(w0 + i, net["shops"]["vic1"], "VIC1", value, customers=100, jobs=120, key_sales_ty=value * 0.3, watch_sales_ty=value * 0.4)
        _seed_metric(w0 + i, net["shops"]["vic2"], "VIC2", 8000, customers=80)
    shop_h = _h(_login(f"minit-{net['shops']['vic1']}", net["hq_email"]))
    body = client.get("/v1/reports/vswt/cockpit", headers=shop_h, params={"week": w0 + 8}).json()
    row = next(r for r in body["rows"] if r["key"] == "sales_ty")
    assert row["anomaly"] == "low" and row["zscore"] < -2 and row["baseline_weeks"] == 8
    assert body["alerts"][0]["severity"] == "critical"
    assert "unusually low for this shop" in body["alerts"][0]["title"]
    assert any(a["key"] == "sales_ty" for a in body["anomalies"])
    assert body["narrative"].startswith("VIC1 took $7,000 in week")
    assert "30.0% below the previous week" in body["narrative"]
    assert "largest drag at -$1,200" in body["narrative"]
    assert "standard deviations" in body["narrative"]


# ── 6. targets from somewhere ────────────────────────────────────────────────


def test_fill_region_targets_from_last_year_and_median():
    suffix = uuid4().hex[:8]
    net = _network(suffix)
    weeks = _seed_history(net, 2, vic1=10000.0, vic2=6000.0)
    res = client.post(
        f"/v1/parent-accounts/me/regions/{net['vic']}/targets/fill",
        headers=net["hq"],
        json={"strategy": "last_year_plus_pct", "pct": 10, "metric_keys": ["sales_ty"], "week": weeks[-1]},
    )
    assert res.status_code == 200, res.text
    assert res.json()["shops_updated"] == 2 and res.json()["targets_written"] == 2
    with Session(engine) as db:
        vic1_tenant = UUID(net["sites"][net["shops"]["vic1"]]["tenant_id"])
        t = db.exec(select(VswtReportTarget).where(VswtReportTarget.tenant_id == vic1_tenant)).one()
        assert t.metric_key == "sales_ty" and t.target_value == round(10000 * 0.9 * 1.10, 2)

    res = client.post(
        f"/v1/parent-accounts/me/regions/{net['vic']}/targets/fill",
        headers=net["hq"],
        json={"strategy": "region_median", "metric_keys": ["sales_ty", "customer_ty"], "week": weeks[-1]},
    )
    assert res.status_code == 200, res.text
    with Session(engine) as db:
        vic2_tenant = UUID(net["sites"][net["shops"]["vic2"]]["tenant_id"])
        rows = {r.metric_key: r.target_value for r in db.exec(select(VswtReportTarget).where(VswtReportTarget.tenant_id == vic2_tenant)).all()}
        assert rows == {"sales_ty": 8000, "customer_ty": 100}  # median of (10000, 6000) and (100, 100)

    cockpit = client.get(f"/v1/parent-accounts/me/regions/{net['vic']}/cockpit", headers=net["hq"], params={"week": weeks[-1]}).json()
    att = cockpit["target_attainment"]
    assert att["shops_with_target"] == 2 and att["shops_met"] == 1  # VIC1 10000 >= 8000; VIC2 6000 < 8000
    assert "1 of 2 shops with a sales target met it" in cockpit["narrative"]
    # The shop's own cockpit sees the same target.
    shop_h = _h(_login(f"minit-{net['shops']['vic2']}", net["hq_email"]))
    body = client.get("/v1/reports/vswt/cockpit", headers=shop_h, params={"week": weeks[-1]}).json()
    assert body["targets"]["sales_ty"] == 8000


# ── 7. enter-shop with a reason ──────────────────────────────────────────────


def test_enter_shop_reason_reaches_both_logs_and_the_shops_inbox():
    suffix = uuid4().hex[:8]
    net = _network(suffix)
    tid = net["sites"][net["shops"]["vic1"]]["tenant_id"]
    entered = client.post(
        f"/v1/parent-accounts/me/sites/{tid}/enter",
        headers=net["hq"],
        json={"reason": "Checking the booking screen config"},
    )
    assert entered.status_code == 200, entered.text
    with Session(engine) as db:
        shop_event = db.exec(
            select(TenantEventLog).where(TenantEventLog.tenant_id == UUID(tid)).where(TenantEventLog.event_type == "hq_enter_shop")
        ).one()
        assert "Checking the booking screen config" in shop_event.event_summary
        hq_event = db.exec(select(ParentAccountEventLog).where(ParentAccountEventLog.event_type == "enter_shop").where(ParentAccountEventLog.tenant_id == UUID(tid))).one()
        assert "Checking the booking screen config" in hq_event.event_summary
    # The shop sees the visit in its own inbox.
    inbox = client.get("/v1/inbox", headers=_h(entered.json()["access_token"])).json()
    assert any(e["event_type"] == "hq_enter_shop" and "booking screen" in e["event_summary"] for e in inbox)


# ── 8. the Monday email ──────────────────────────────────────────────────────


def test_region_report_send_now_and_weekly_sweep_stamp_the_region():
    suffix = uuid4().hex[:8]
    net = _network(suffix)
    _seed_history(net, 2)
    res = client.post(f"/v1/parent-accounts/me/regions/{net['vic']}/report/send-now", headers=net["hq"])
    assert res.status_code == 200, res.text
    assert res.json()["to"] == f"dana-{suffix}@region.test"
    with Session(engine) as db:
        region = db.get(Region, UUID(net["vic"]))
        assert region.last_weekly_report_sent_at is not None
        first_stamp = region.last_weekly_report_sent_at

    # Opting in without a manager email is refused; QLD has none.
    assert client.patch(f"/v1/parent-accounts/me/regions/{net['qld']}", headers=net["hq"], json={"weekly_report_opt_in": True}).status_code == 400
    assert client.patch(f"/v1/parent-accounts/me/regions/{net['vic']}", headers=net["hq"], json={"weekly_report_opt_in": True}).status_code == 200

    from app.services.regional_manager_report import send_due_region_reports

    with Session(engine) as db:
        parent = db.exec(select(ParentAccount).where(ParentAccount.owner_email == net["hq_email"])).one()
        # Already sent this ISO week: skipped.
        assert send_due_region_reports(db, parent_id=parent.id) == {"sent": 0, "skipped": 1}
        region = db.get(Region, UUID(net["vic"]))
        region.last_weekly_report_sent_at = first_stamp - timedelta(days=8)
        db.add(region)
        db.commit()
        summary = send_due_region_reports(db, parent_id=parent.id)
        assert summary["sent"] + summary["skipped"] == 1
        db.refresh(region)
        assert region.last_weekly_report_sent_at > first_stamp - timedelta(days=8)
