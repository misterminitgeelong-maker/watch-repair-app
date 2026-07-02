"""HQ scale: slim session payloads and paginated parent-account sites."""

from __future__ import annotations

import os
from pathlib import Path
from uuid import uuid4

from fastapi.testclient import TestClient
from sqlmodel import Session, select

_TEST_DB = Path(__file__).with_name(f"test_hq_scale_{uuid4().hex}.db")
os.environ["DATABASE_URL"] = f"sqlite:///{_TEST_DB.as_posix()}"
os.environ.setdefault("JWT_SECRET", "test-secret-not-for-production")
os.environ.setdefault("APP_ENV", "test")

from app.database import create_db_and_tables, engine
from app.main import app
from app.minit_provision import ensure_minit_pilot_account, import_minit_shops
from app.minit_shops import MinitShopRow
from app.models import ParentAccount
from app.routes.auth import _build_available_sites_for_email
from app.shop_number import linked_tenant_ids_for_parent

create_db_and_tables()
client = TestClient(app)


def _seed_many_shops(session: Session, count: int) -> None:
    ensure_minit_pilot_account(
        session,
        parent_name="Mister Minit",
        hq_tenant_slug="mmsupport",
        hq_tenant_name="Mister Minit HQ",
        hq_owner_email="hq-scale@test.mainspring.au",
        hq_owner_password="MinitPilot2026!",
    )
    shops = [
        MinitShopRow(shop_number=str(6000 + i), name=f"Shop {i}", area="VIC SOUTH", region="VIC")
        for i in range(count)
    ]
    import_minit_shops(
        session,
        parent_name="Mister Minit",
        hq_owner_email="hq-scale@test.mainspring.au",
        shops=shops,
        apply=True,
    )


def test_hq_session_returns_single_available_site_for_large_network() -> None:
    create_db_and_tables()
    with Session(engine) as session:
        _seed_many_shops(session, 25)

    login = client.post(
        "/v1/auth/login",
        json={
            "tenant_slug": "mmsupport",
            "email": "hq-scale@test.mainspring.au",
            "password": "MinitPilot2026!",
        },
    )
    assert login.status_code == 200
    token = login.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    session_res = client.get("/v1/auth/session", headers=headers)
    assert session_res.status_code == 200
    body = session_res.json()
    assert body["is_minit_hq_ui"] is True
    assert len(body["available_sites"]) == 1
    assert body["available_sites"][0]["tenant_slug"] == "mmsupport"

    summary = client.get("/v1/parent-accounts/me", headers=headers)
    assert summary.status_code == 200
    summary_body = summary.json()
    assert summary_body["site_count"] >= 26
    assert summary_body["sites"] == []

    sites_page = client.get("/v1/parent-accounts/me/sites?plan_kind=retail&limit=10", headers=headers)
    assert sites_page.status_code == 200
    page = sites_page.json()
    assert page["total"] >= 25
    assert len(page["sites"]) == 10

    ingest = client.get("/v1/parent-accounts/me/lead-ingest", headers=headers)
    assert ingest.status_code == 200
    assert "mobile_lead_ingest_public_id" in ingest.json()


def test_build_available_sites_batches_lookups() -> None:
    create_db_and_tables()
    with Session(engine) as session:
        _seed_many_shops(session, 15)
        parent = session.exec(select(ParentAccount)).first()
        assert parent is not None
        sites = _build_available_sites_for_email(session, parent.owner_email)
        assert len(sites) >= 16
        assert len(linked_tenant_ids_for_parent(session, parent.id)) >= 16
