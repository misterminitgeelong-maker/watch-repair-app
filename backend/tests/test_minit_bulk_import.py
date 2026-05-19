"""Bulk Minit shop import idempotency and duplicate detection."""

from __future__ import annotations

import os
from pathlib import Path
from uuid import uuid4

_TEST_DB = Path(__file__).with_name(f"test_minit_import_{uuid4().hex}.db")
os.environ["DATABASE_URL"] = f"sqlite:///{_TEST_DB.as_posix()}"
os.environ.setdefault("JWT_SECRET", "test-secret-not-for-production")
os.environ.setdefault("APP_ENV", "test")

from sqlmodel import Session

from app.database import create_db_and_tables, engine
from app.minit_provision import ensure_minit_pilot_account, import_minit_shops
from app.minit_shops import MinitShopRow
from app.shop_number import linked_tenants_for_parent


def _seed_parent(session: Session) -> None:
    ensure_minit_pilot_account(
        session,
        parent_name="Mister Minit",
        hq_tenant_slug="mmsupport",
        hq_tenant_name="Mister Minit HQ",
        hq_owner_email="minit-hq@test.mainspring.au",
        hq_owner_password="MinitPilot2026!",
    )


def test_import_minit_shops_dry_run_skips_pilot_shops() -> None:
    create_db_and_tables()
    shops = [
        MinitShopRow(shop_number="3269", name="Chadstone", area="VIC SOUTH", region="VIC"),
        MinitShopRow(shop_number="5001", name="New Shop", area="NSW", region="NSW"),
    ]
    with Session(engine) as session:
        _seed_parent(session)
        summary = import_minit_shops(
            session,
            parent_name="Mister Minit",
            hq_owner_email="minit-hq@test.mainspring.au",
            shops=shops,
            apply=False,
        )
    assert summary["parent_found"] is True
    assert summary["would_create_count"] == 1
    assert summary["would_skip_count"] == 1
    skipped = summary["would_skip"]
    assert isinstance(skipped, list)
    assert skipped[0]["shop_number"] == "3269"
    assert skipped[0]["skip_reason"] == "duplicate_shop_number"


def test_import_minit_shops_apply_is_idempotent() -> None:
    create_db_and_tables()
    shops = [
        MinitShopRow(shop_number="3269", name="Chadstone", area="VIC SOUTH", region="VIC"),
        MinitShopRow(shop_number="5001", name="New Shop", area="NSW", region="NSW"),
        MinitShopRow(shop_number="5002", name="Another", area="QLD", region="QLD"),
    ]
    with Session(engine) as session:
        _seed_parent(session)
        first = import_minit_shops(
            session,
            parent_name="Mister Minit",
            hq_owner_email="minit-hq@test.mainspring.au",
            shops=shops,
            apply=True,
        )
        second = import_minit_shops(
            session,
            parent_name="Mister Minit",
            hq_owner_email="minit-hq@test.mainspring.au",
            shops=shops,
            apply=True,
        )
    assert first["created_count"] == 2
    assert second["created_count"] == 0
    assert second["would_skip_count"] == 3


def test_linked_tenants_for_parent_batch_load() -> None:
    create_db_and_tables()
    with Session(engine) as session:
        result = ensure_minit_pilot_account(
            session,
            parent_name="Mister Minit",
            hq_tenant_slug="mmsupport",
            hq_tenant_name="Mister Minit HQ",
            hq_owner_email="minit-hq@test.mainspring.au",
            hq_owner_password="MinitPilot2026!",
        )
        tenants = linked_tenants_for_parent(session, result.parent_account_id)
    slugs = {t.slug for t in tenants}
    assert "mmsupport" in slugs
    assert "minit-3269" in slugs
    assert "minit-mobile-3904" in slugs
