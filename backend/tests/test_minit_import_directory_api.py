"""API tests for HQ bulk directory import (Organisation Graph HTML export)."""

from __future__ import annotations

import os
from pathlib import Path
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

_TEST_DB = Path(__file__).with_name(f"test_minit_import_directory_api_{uuid4().hex}.db")
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


_FIXTURE_HTML = r"""
<html><body><script>
var xQ={entities:[
  {id:`shop:9001`,kind:`shop`,label:`9001 Testville`,fields:[
    {label:`Shop Number`,value:`9001`,kind:`identifier`},
    {label:`Shop Name`,value:`Testville`,kind:`name`},
    {label:`Ownership`,value:`Franchised`,kind:`text`},
    {label:`Status`,value:`Open`,kind:`text`},
    {label:`Area`,value:`Test Area`,kind:`text`},
    {label:`Region`,value:`VIC`,kind:`text`},
    {label:`Address`,value:`1 Test St, Testville, VIC, 3000`,kind:`address`}
  ]},
  {id:`franchisee:jane-tester`,kind:`franchisee`,label:`Jane Tester`,fields:[
    {label:`Franchisee`,value:`Jane Tester`,kind:`name`},
    {label:`Email`,value:`jane.tester@example.com`,kind:`email`},
    {label:`Mobile`,value:`+61400111222`,kind:`phone`}
  ]}
],relationships:[
  {from:`franchisee:jane-tester`,to:`shop:9001`,kind:`operates`}
]};
</script></body></html>
"""


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


def test_import_directory_rejects_non_html() -> None:
    token = _login_hq()
    res = client.post(
        "/v1/parent-accounts/me/import-directory",
        headers=_headers(token),
        files={"file": ("directory.xlsx", b"not html", "application/octet-stream")},
    )
    assert res.status_code == 400
    assert "html" in res.json()["detail"].lower()


def test_import_directory_rejects_unparseable_html() -> None:
    token = _login_hq()
    res = client.post(
        "/v1/parent-accounts/me/import-directory",
        headers=_headers(token),
        files={"file": ("directory.html", b"<html>no graph here</html>", "text/html")},
    )
    assert res.status_code == 400
    assert "directory export" in res.json()["detail"].lower()


def test_import_directory_preview_makes_no_changes() -> None:
    token = _login_hq()
    res = client.post(
        "/v1/parent-accounts/me/import-directory",
        headers=_headers(token),
        files={"file": ("directory.html", _FIXTURE_HTML.encode("utf-8"), "text/html")},
    )
    assert res.status_code == 200, res.text
    body = res.json()
    assert body["dry_run"] is True
    assert body["shops"]["would_create"] == 1
    assert body["franchisees"]["single_site"] == 1
    assert "created_tenant_count" not in body

    # Preview never creates the tenant.
    check = client.get(
        "/v1/parent-accounts/me/sites",
        headers=_headers(token),
        params={"search": "Testville"},
    )
    assert check.status_code == 200
    assert check.json()["total"] == 0


def test_import_directory_apply_creates_shop_and_owner() -> None:
    token = _login_hq()
    res = client.post(
        "/v1/parent-accounts/me/import-directory",
        headers=_headers(token),
        params={"apply": "true"},
        files={"file": ("directory.html", _FIXTURE_HTML.encode("utf-8"), "text/html")},
    )
    assert res.status_code == 200, res.text
    body = res.json()
    assert body["dry_run"] is False
    assert body["created_tenant_count"] == 1
    assert body["created_owner_count"] == 1

    sites = client.get(
        "/v1/parent-accounts/me/sites",
        headers=_headers(token),
        params={"search": "Testville"},
    ).json()
    assert sites["total"] == 1
    assert sites["sites"][0]["owner_email"] == "jane.tester@example.com"

    # Re-applying the same export is a no-op — safe to click twice.
    again = client.post(
        "/v1/parent-accounts/me/import-directory",
        headers=_headers(token),
        params={"apply": "true"},
        files={"file": ("directory.html", _FIXTURE_HTML.encode("utf-8"), "text/html")},
    )
    assert again.status_code == 200, again.text
    assert again.json()["created_tenant_count"] == 0


def test_import_directory_requires_minit_hq() -> None:
    suffix = uuid4().hex[:8]
    boot = client.post(
        "/v1/auth/bootstrap",
        json={
            "tenant_name": f"Tenant {suffix}",
            "tenant_slug": f"tenant-{suffix}",
            "owner_email": f"owner-{suffix}@test.local",
            "owner_full_name": "Owner",
            "owner_password": "pass123456",
            "plan_code": "pro",
        },
    )
    assert boot.status_code == 200, boot.text
    login = client.post(
        "/v1/auth/login",
        json={"tenant_slug": f"tenant-{suffix}", "email": f"owner-{suffix}@test.local", "password": "pass123456"},
    )
    token = login.json()["access_token"]

    res = client.post(
        "/v1/parent-accounts/me/import-directory",
        headers=_headers(token),
        files={"file": ("directory.html", _FIXTURE_HTML.encode("utf-8"), "text/html")},
    )
    assert res.status_code == 403
