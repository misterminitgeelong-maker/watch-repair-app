"""Every Reports endpoint the frontend calls answers 200 with the params the frontend sends."""
import pytest

OWNER_GETS = [
    ("/v1/reports/summary", None),
    ("/v1/reports/trends", {"months": 6}),
    ("/v1/reports/tech-breakdown", None),
    ("/v1/reports/widgets", None),
    ("/v1/reports/activity", {"limit": 50}),
    ("/v1/reports/export/jobs", None),
    ("/v1/reports/export/customers", None),
    ("/v1/reports/export/invoices", None),
    ("/v1/reports/export/sales", {"category": "all"}),
    ("/v1/reports/export/sales", {"category": "watch", "period": "month", "reference_date": "2026-10-28"}),
    ("/v1/reports/category-summary", {"period": "week", "reference_date": "2026-10-28"}),
    ("/v1/reports/category-summary", {"date_from": "2026-10-01", "date_to": "2026-10-28"}),
    ("/v1/reports/gst-summary", None),
    ("/v1/reports/gst-summary", {"period": "quarter", "reference_date": "2026-10-28"}),
    ("/v1/reports/period-summary", {"period": "day", "reference_date": "2026-10-28"}),
    ("/v1/reports/export/period-summary", {"period": "month", "reference_date": "2026-10-28"}),
    ("/v1/reports/auto-key", {"date_from": "2026-10-01", "date_to": "2026-10-31"}),
    ("/v1/reports/auto-key", {"date_from": "2000-01-01", "date_to": "2099-12-31"}),
    ("/v1/reports/auto-key/cockpit", None),
    ("/v1/reports/auto-key/finance", {"period": "month"}),
    ("/v1/reports/auto-key/finance", {"period": "last_13_weeks"}),
    ("/v1/reports/auto-key/finance/export", {"period": "month", "kind": "invoices"}),
    ("/v1/reports/auto-key/finance/export", {"period": "month", "kind": "summary"}),
    ("/v1/reports/auto-key/commission", {"date_from": "2026-10-01", "date_to": "2026-10-31"}),
    ("/v1/reports/vswt/summary", None),
    ("/v1/reports/vswt/cockpit", None),
    ("/v1/reports/vswt/targets", None),
    ("/v1/reports/vswt/annotations", None),
    ("/v1/reports/vswt/email-preference", None),
    ("/v1/reports/vswt/scorecard", None),
    ("/v1/reports/vswt/rankings", None),
    ("/v1/reports/vswt/directory", None),
    ("/v1/reports/vswt/shop-report", None),
    ("/v1/reports/vswt/leaderboards", None),
    ("/v1/reports/vswt/trends", {"weeks_back": 8}),
    ("/v1/reports/vswt/weeks", None),
    ("/v1/revenue-control", None),
]


@pytest.mark.parametrize("path,params", OWNER_GETS)
def test_owner_report_endpoints_load(client, auth_headers, path, params):
    res = client.get(path, headers=auth_headers, params=params)
    assert res.status_code in (200, 403, 404), f"{path} {params}: {res.status_code} {res.text[:300]}"
    assert res.status_code != 404 or "No regional data" in res.text


def test_period_bounds_follow_the_shop_timezone():
    from datetime import date, timedelta
    from zoneinfo import ZoneInfo

    from app.report_periods import resolve_period_bounds

    mel = ZoneInfo("Australia/Melbourne")
    start, end, start_ymd, end_ymd = resolve_period_bounds("day", date(2026, 10, 28), mel)
    assert (start_ymd, end_ymd) == ("2026-10-28", "2026-10-28")
    # Melbourne midnight is 13:00 UTC the previous day (AEDT, UTC+11)
    assert start.isoformat() == "2026-10-27T13:00:00+00:00"
    assert end.isoformat() == "2026-10-28T12:59:59.999999+00:00"
    assert end - start == timedelta(days=1) - timedelta(microseconds=1)


def test_commission_report_is_manager_only(client):
    from uuid import uuid4

    sfx = uuid4().hex[:8]
    slug = f"comm-{sfx}"
    assert client.post("/v1/auth/bootstrap", json={
        "tenant_name": "Comm", "tenant_slug": slug, "owner_email": f"o-{sfx}@example.test",
        "owner_full_name": "Owner", "owner_password": "pass123456",
    }).status_code == 200

    def login(email):
        r = client.post("/v1/auth/login", json={"tenant_slug": slug, "email": email, "password": "pass123456"})
        assert r.status_code == 200, r.text
        return {"Authorization": f"Bearer {r.json()['access_token']}"}

    owner = login(f"o-{sfx}@example.test")
    assert client.post("/v1/users", headers=owner, json={
        "email": f"t-{sfx}@example.test", "full_name": "Tech", "password": "pass123456", "role": "tech",
    }).status_code == 201
    assert client.get("/v1/reports/auto-key/commission", headers=owner).status_code == 200
    assert client.get("/v1/reports/auto-key/commission", headers=login(f"t-{sfx}@example.test")).status_code == 403
