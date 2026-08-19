"""VSWT Regional Intelligence: parser, ranking helpers, and the upload/read API."""
from __future__ import annotations

import io
from uuid import UUID

import openpyxl
import pytest
from sqlmodel import Session

from app.database import engine
from app.models import Tenant, VswtWeeklyShopMetric
from app.routes.vswt_reports import _average, _parse_vswt_workbook, _peer_rows, _rank_of
from app.vswt_kpis import COLUMN_MAP


# ── Workbook builder (mirrors the real VSWT-WSS Summary sheet layout) ──────────────────────

def _build_workbook(week_number, shop_rows: list[dict]) -> bytes:
    """Build an in-memory .xlsx matching the brief's row/column layout for the Summary sheet."""
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "Summary"
    ws["A3"] = "Week Number:"
    ws["C3"] = week_number
    for i, row in enumerate(shop_rows):
        excel_row = 6 + i
        for field, col in COLUMN_MAP:
            if field in row:
                ws.cell(row=excel_row, column=col, value=row[field])
    buf = io.BytesIO()
    wb.save(buf)
    return buf.getvalue()


def _shop_row(shop_number, shop_name, sales_ty, **extra) -> dict:
    row = {
        "shop_number": shop_number,
        "shop_name": shop_name,
        "area_name": extra.pop("area_name", "VIC SOUTH"),
        "store_format": extra.pop("store_format", "FR"),
        "comp_status": extra.pop("comp_status", "Comp"),
        "sales_ty": sales_ty,
    }
    row.update(extra)
    return row


# ── Parser ───────────────────────────────────────────────────────────────────────────────

def test_parse_detects_week_number_and_shop_rows():
    raw = _build_workbook(32, [
        _shop_row(3269, "Chadstone", 50000),
        _shop_row(3904, "Doncaster", 42000),
    ])
    result = _parse_vswt_workbook(raw, "VSWT-WSS__new_version__32.xlsx")
    assert result["internal_week"] == 32
    assert result["shop_count"] == 2
    numbers = {r["shop_number"] for r in result["rows"]}
    assert numbers == {"3269", "3904"}


def test_parse_skips_rows_with_no_shop_number():
    raw = _build_workbook(32, [
        _shop_row(3269, "Chadstone", 50000),
        {"sales_ty": 99999},  # no shop_number -> not a real shop row
    ])
    result = _parse_vswt_workbook(raw, "f.xlsx")
    assert result["shop_count"] == 1


def test_parse_treats_excel_errors_and_blanks_as_null():
    raw = _build_workbook(32, [
        _shop_row(3269, "Chadstone", "#DIV/0!", jobs_ty="#REF!", customer_ty=""),
    ])
    result = _parse_vswt_workbook(raw, "f.xlsx")
    row = result["rows"][0]
    assert row["sales_ty"] is None
    assert row["jobs_ty"] is None
    assert row["customer_ty"] is None


def test_parse_normalises_shop_number_to_string_without_decimal():
    raw = _build_workbook(32, [_shop_row(3269, "Chadstone", 50000)])
    result = _parse_vswt_workbook(raw, "f.xlsx")
    # openpyxl round-trips a bare int fine, but the source column is genuinely numeric in
    # real exports (float), so shop_number must come out as a clean "3269", not "3269.0".
    assert result["rows"][0]["shop_number"] == "3269"


def test_parse_falls_back_to_first_sheet_when_no_summary_tab():
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "Data"
    ws["C3"] = 5
    ws.cell(row=6, column=2, value=3269)
    ws.cell(row=6, column=9, value=1000)
    buf = io.BytesIO()
    wb.save(buf)
    result = _parse_vswt_workbook(buf.getvalue(), "f.xlsx")
    assert result["shop_count"] == 1


# ── Ranking helpers ──────────────────────────────────────────────────────────────────────

def _metric(shop_number, sales_ty, store_format="FR", comp_status="Comp") -> VswtWeeklyShopMetric:
    return VswtWeeklyShopMetric(
        week_seq=1, shop_number=shop_number, sales_ty=sales_ty,
        store_format=store_format, comp_status=comp_status,
    )


def test_rank_of_higher_is_better_and_ties_share_no_special_casing():
    rows = [_metric("1", 100), _metric("2", 90), _metric("3", 90), _metric("4", 50)]
    assert _rank_of(rows, "sales_ty", 100) == 1
    # two shops ahead at 100 and 90(tie)... shop with 90 has exactly one shop strictly above it (100)
    assert _rank_of(rows, "sales_ty", 90) == 2
    assert _rank_of(rows, "sales_ty", 50) == 4


def test_rank_of_none_value_is_unranked():
    rows = [_metric("1", 100), _metric("2", None)]
    assert _rank_of(rows, "sales_ty", None) is None


def test_average_ignores_nulls():
    assert _average([10, None, 20, None]) == 15
    assert _average([None, None]) is None


def test_peer_rows_filters_franchise_comparable_only():
    rows = [
        _metric("1", 100, store_format="FR", comp_status="Comp"),
        _metric("2", 90, store_format="CO", comp_status="Comp"),
        _metric("3", 80, store_format="FR", comp_status="Non Comp"),
        _metric("4", 70, store_format="FR", comp_status="Comp"),
    ]
    peers = _peer_rows(rows)
    assert {r.shop_number for r in peers} == {"1", "4"}


# ── API: upload -> commit -> read ───────────────────────────────────────────────────────

def _bootstrap(client, tenant_slug, email, role="owner") -> tuple[dict, str]:
    """Bootstrap a tenant (owner) and return (headers, tenant_id)."""
    res = client.post(
        "/v1/auth/bootstrap",
        json={
            "tenant_name": f"Tenant {tenant_slug}",
            "tenant_slug": tenant_slug,
            "owner_email": email,
            "owner_full_name": "Owner",
            "owner_password": "pass123456",
        },
    )
    assert res.status_code == 200, res.text
    tenant_id = res.json()["tenant_id"]
    login = client.post(
        "/v1/auth/login",
        json={"tenant_slug": tenant_slug, "email": email, "password": "pass123456"},
    )
    assert login.status_code == 200, login.text
    return {"Authorization": f"Bearer {login.json()['access_token']}"}, tenant_id


def _set_shop_number(tenant_id: str, shop_number: str) -> None:
    with Session(engine) as session:
        tenant = session.get(Tenant, UUID(tenant_id))
        assert tenant is not None
        tenant.shop_number = shop_number
        session.add(tenant)
        session.commit()


def _make_lower_role_user(client, headers, suffix: str, role: str) -> dict:
    res = client.post(
        "/v1/users",
        headers=headers,
        json={
            "full_name": f"{role.title()} {suffix}",
            "email": f"{role}-{suffix}@test.com",
            "password": "pass123456",
            "role": role,
        },
    )
    assert res.status_code == 201, res.text
    return res.json()


@pytest.fixture
def vswt_client(client):
    return client


def test_upload_then_commit_then_read_flow(vswt_client):
    headers, tenant_id = _bootstrap(vswt_client, "vswt-shop-3269", "owner-3269@test.com")
    _set_shop_number(tenant_id, "3269")

    raw = _build_workbook(41, [
        _shop_row(3269, "Chadstone", 50000, jobs_ty=120, customer_ty=90, budget_sales_target=45000),
        _shop_row(3904, "Doncaster", 70000, jobs_ty=150, customer_ty=110),
        _shop_row(4100, "Bondi", 30000, jobs_ty=60, customer_ty=40, store_format="CO"),
    ])
    upload = vswt_client.post(
        "/v1/reports/vswt/upload",
        headers=headers,
        files=[("files", ("VSWT-WSS__new_version__41.xlsx", raw,
                           "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"))],
    )
    assert upload.status_code == 200, upload.text
    batch = upload.json()["batch"]
    assert len(batch) == 1
    assert batch[0]["week_number"] == 41
    assert batch[0]["shop_count"] == 3
    assert batch[0]["overwrite"] is False

    commit = vswt_client.post(
        "/v1/reports/vswt/commit",
        headers=headers,
        json={"batch": [{"filename": batch[0]["filename"], "week_number": 41, "rows": batch[0]["rows"]}]},
    )
    assert commit.status_code == 200, commit.text
    assert commit.json()["saved"] == [{"week_number": 41, "shop_count": 3}]

    summary = vswt_client.get("/v1/reports/vswt/summary", headers=headers)
    assert summary.status_code == 200, summary.text
    body = summary.json()
    assert body["available"] is True
    assert body["shop_number"] == "3269"
    assert body["sales"]["value"] == 50000
    # Doncaster (70000) is the only shop ahead of Chadstone on sales.
    assert body["sales"]["region_rank"] == 2

    rankings = vswt_client.get("/v1/reports/vswt/rankings", headers=headers, params={"week": 41})
    assert rankings.status_code == 200
    sales_row = next(r for r in rankings.json()["rows"] if r["key"] == "sales_ty")
    assert sales_row["region_rank"] == 2
    assert sales_row["region_avg"] == pytest.approx(50000.0)

    scorecard = vswt_client.get("/v1/reports/vswt/scorecard", headers=headers)
    assert scorecard.status_code == 200
    assert scorecard.json()["matrix"][0]["week"] == 41

    leaderboards = vswt_client.get("/v1/reports/vswt/leaderboards", headers=headers, params={"week": 41})
    assert leaderboards.status_code == 200
    sales_board = next(b for b in leaderboards.json()["boards"] if b["key"] == "sales_ty")
    assert sales_board["top"][0]["shop_number"] == "3904"

    trends = vswt_client.get("/v1/reports/vswt/trends", headers=headers)
    assert trends.status_code == 200
    assert trends.json()["sales_series"][-1]["shop"] == 50000


def test_reupload_same_week_auto_bumps_to_a_free_week(vswt_client):
    """Auto-assignment always steers clear of a collision (matches the reference app): the
    second upload of an already-stored week number lands on the next free week, it does not
    silently overwrite. Overwriting only happens if the *user* edits the week number back."""
    headers, tenant_id = _bootstrap(vswt_client, "vswt-shop-overwrite", "owner-ow@test.com")
    _set_shop_number(tenant_id, "9001")

    raw1 = _build_workbook(50, [_shop_row(9001, "Shop A", 10000)])
    up1 = vswt_client.post("/v1/reports/vswt/upload", headers=headers,
                            files=[("files", ("w50a.xlsx", raw1))])
    b1 = up1.json()["batch"][0]
    assert b1["week_number"] == 50
    vswt_client.post("/v1/reports/vswt/commit", headers=headers,
                      json={"batch": [{"filename": b1["filename"], "week_number": 50, "rows": b1["rows"]}]})

    raw2 = _build_workbook(50, [_shop_row(9001, "Shop A", 20000)])
    up2 = vswt_client.post("/v1/reports/vswt/upload", headers=headers,
                            files=[("files", ("w50b.xlsx", raw2))])
    b2 = up2.json()["batch"][0]
    assert b2["internal_week"] == 50
    assert b2["week_number"] == 51  # bumped, not overwritten
    assert b2["overwrite"] is False
    assert 50 in up2.json()["existing_weeks"]  # frontend uses this to warn on a manual edit


def test_commit_with_an_existing_week_number_overwrites_not_duplicates(vswt_client):
    """The commit step itself (delete-then-insert per week) is what actually overwrites —
    exercised here as if the user had edited the confirm step's week number back onto week 50."""
    headers, tenant_id = _bootstrap(vswt_client, "vswt-shop-manual-overwrite", "owner-mo@test.com")
    _set_shop_number(tenant_id, "9002")

    raw1 = _build_workbook(50, [_shop_row(9002, "Shop A", 10000)])
    up1 = vswt_client.post("/v1/reports/vswt/upload", headers=headers,
                            files=[("files", ("w50a.xlsx", raw1))])
    b1 = up1.json()["batch"][0]
    vswt_client.post("/v1/reports/vswt/commit", headers=headers,
                      json={"batch": [{"filename": b1["filename"], "week_number": 50, "rows": b1["rows"]}]})

    raw2 = _build_workbook(50, [_shop_row(9002, "Shop A", 20000)])
    up2 = vswt_client.post("/v1/reports/vswt/upload", headers=headers,
                            files=[("files", ("w50b.xlsx", raw2))])
    b2 = up2.json()["batch"][0]
    # User corrects the auto-bumped number back to 50 in the confirm step.
    vswt_client.post("/v1/reports/vswt/commit", headers=headers,
                      json={"batch": [{"filename": b2["filename"], "week_number": 50, "rows": b2["rows"]}]})

    summary = vswt_client.get("/v1/reports/vswt/summary", headers=headers)
    assert summary.json()["sales"]["value"] == 20000  # overwritten, not duplicated

    weeks = vswt_client.get("/v1/reports/vswt/weeks", headers=headers)
    week_50 = next(w for w in weeks.json()["weeks"] if w["week"] == 50)
    assert week_50["shop_count"] == 1


def test_commit_rejects_duplicate_week_numbers_in_one_batch(vswt_client):
    headers, _tid = _bootstrap(vswt_client, "vswt-dup-batch", "owner-dup@test.com")
    raw = _build_workbook(9, [_shop_row(1, "A", 100)])
    res = vswt_client.post(
        "/v1/reports/vswt/commit",
        headers=headers,
        json={"batch": [
            {"filename": "a.xlsx", "week_number": 9, "rows": [_shop_row(1, "A", 100)]},
            {"filename": "b.xlsx", "week_number": 9, "rows": [_shop_row(2, "B", 200)]},
        ]},
    )
    assert res.status_code == 400


def test_upload_requires_manager_or_above(vswt_client):
    headers, _tid = _bootstrap(vswt_client, "vswt-role-gate", "owner-rg@test.com")
    intake = _make_lower_role_user(vswt_client, headers, "rg", "intake")
    login = vswt_client.post(
        "/v1/auth/login",
        json={"tenant_slug": "vswt-role-gate", "email": intake["email"], "password": "pass123456"},
    )
    intake_headers = {"Authorization": f"Bearer {login.json()['access_token']}"}

    raw = _build_workbook(12, [_shop_row(1, "A", 100)])
    res = vswt_client.post("/v1/reports/vswt/upload", headers=intake_headers,
                            files=[("files", ("f.xlsx", raw))])
    assert res.status_code == 403


def test_summary_unavailable_without_shop_number(vswt_client):
    headers, _tid = _bootstrap(vswt_client, "vswt-no-shop-number", "owner-ns@test.com")
    res = vswt_client.get("/v1/reports/vswt/summary", headers=headers)
    assert res.status_code == 200
    body = res.json()
    assert body["available"] is False
    assert body["reason"] == "no_shop_number"


def test_summary_unavailable_when_shop_not_in_data(vswt_client):
    headers, tenant_id = _bootstrap(vswt_client, "vswt-shop-missing", "owner-sm@test.com")
    _set_shop_number(tenant_id, "5555")

    raw = _build_workbook(60, [_shop_row(1, "A", 100)])
    up = vswt_client.post("/v1/reports/vswt/upload", headers=headers,
                           files=[("files", ("f.xlsx", raw))])
    b = up.json()["batch"][0]
    vswt_client.post("/v1/reports/vswt/commit", headers=headers,
                      json={"batch": [{"filename": b["filename"], "week_number": 60, "rows": b["rows"]}]})

    res = vswt_client.get("/v1/reports/vswt/summary", headers=headers)
    body = res.json()
    assert body["available"] is False
    assert body["reason"] == "shop_not_found"
