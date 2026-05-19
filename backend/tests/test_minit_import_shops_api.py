"""API tests for HQ bulk shop import from Excel."""

from __future__ import annotations

import io
import os
from pathlib import Path
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from openpyxl import Workbook

_TEST_DB = Path(__file__).with_name(f"test_minit_import_api_{uuid4().hex}.db")
os.environ["DATABASE_URL"] = f"sqlite:///{_TEST_DB.as_posix()}"
os.environ.setdefault("JWT_SECRET", "test-secret-not-for-production")
os.environ.setdefault("APP_ENV", "test")

from app.database import create_db_and_tables
from app.main import app
from app.minit_branding import MINIT_HQ_SLUG
from app.minit_provision import ensure_minit_pilot_account

create_db_and_tables()
client = TestClient(app)

HQ_EMAIL = "minit-hq@test.mainspring.au"
HQ_PASSWORD = "MinitPilot2026!"


def _login_hq() -> str:
    res = client.post(
        "/v1/auth/login",
        json={"tenant_slug": MINIT_HQ_SLUG, "email": HQ_EMAIL, "password": HQ_PASSWORD},
    )
    assert res.status_code == 200, res.text
    return res.json()["access_token"]


def _headers(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def _shops_xlsx_bytes() -> bytes:
    wb = Workbook()
    ws = wb.active
    ws.title = "Shops"
    ws.append(["Shop #", "Shop Name", "Area", "Region"])
    ws.append([7001, "Import Test Shop", "VIC SOUTH", "VIC"])
    ws.append([7002, "Second Import", "NSW", "NSW"])
    buf = io.BytesIO()
    wb.save(buf)
    wb.close()
    return buf.getvalue()


@pytest.fixture(scope="module", autouse=True)
def _seed_hq() -> None:
    from sqlmodel import Session

    from app.database import engine

    with Session(engine) as session:
        ensure_minit_pilot_account(
            session,
            parent_name="Mister Minit",
            hq_tenant_slug=MINIT_HQ_SLUG,
            hq_tenant_name="Mister Minit HQ",
            hq_owner_email=HQ_EMAIL,
            hq_owner_password=HQ_PASSWORD,
        )


def test_import_shops_rejects_non_xlsx() -> None:
    token = _login_hq()
    res = client.post(
        "/v1/parent-accounts/me/import-shops",
        headers=_headers(token),
        files={"file": ("shops.csv", b"a,b,c", "text/csv")},
    )
    assert res.status_code == 400
    assert "xlsx" in res.json()["detail"].lower()


def test_import_shops_from_xlsx() -> None:
    token = _login_hq()
    data = _shops_xlsx_bytes()
    res = client.post(
        "/v1/parent-accounts/me/import-shops",
        headers=_headers(token),
        files={
            "file": (
                "shops.xlsx",
                data,
                "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            )
        },
    )
    assert res.status_code == 200, res.text
    body = res.json()
    assert body["parsed_count"] == 2
    assert body["created_count"] == 2
    assert body["sheet_name"] == "Shops"
    assert body["errors"] == []

    second = client.post(
        "/v1/parent-accounts/me/import-shops",
        headers=_headers(token),
        files={
            "file": (
                "shops.xlsx",
                data,
                "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            )
        },
    )
    assert second.status_code == 200, second.text
    repeat = second.json()
    assert repeat["created_count"] == 0
    assert repeat["skipped_count"] >= 2
