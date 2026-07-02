"""Mobile operator bulk import idempotency and retail/operator shop_number coexistence."""

from __future__ import annotations

import os
from pathlib import Path
from uuid import uuid4

_TEST_DB = Path(__file__).with_name(f"test_minit_operator_import_{uuid4().hex}.db")
os.environ["DATABASE_URL"] = f"sqlite:///{_TEST_DB.as_posix()}"
os.environ.setdefault("JWT_SECRET", "test-secret-not-for-production")
os.environ.setdefault("APP_ENV", "test")

from sqlmodel import Session

from app.database import create_db_and_tables, engine
from app.minit_mobile_operators import (
    MobileOperatorSeed,
    ResolvedMobileOperator,
    index_tss_shops_by_number,
    resolve_mobile_operators,
)
from app.minit_provision import ensure_minit_pilot_account, import_minit_mobile_operators, import_minit_shops
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


def _resolved_operator(
  shop_number: str,
  label: str,
  phone: str,
  *,
  area: str | None = "NSW",
  region: str | None = "NSW",
  tss_name: str | None = None,
) -> ResolvedMobileOperator:
    seed = MobileOperatorSeed(
        shop_number=shop_number,
        operator_label=label,
        dispatch_phone=phone,
    )
    tss = MinitShopRow(
        shop_number=shop_number,
        name=tss_name or label,
        area=area,
        region=region,
    )
    return ResolvedMobileOperator(
        seed=seed,
        tss=tss,
        tenant_name=f"Mobile Services {label}",
        tenant_slug=f"minit-mobile-{shop_number}",
        dispatch_phone=phone,
    )


def test_import_mobile_operators_dry_run_skips_pilot_operator() -> None:
    create_db_and_tables()
    operators = [
        _resolved_operator("3904", "Mobile Operator", "0400000000"),
        _resolved_operator("2243", "Burwood", "0477738814"),
    ]
    with Session(engine) as session:
        _seed_parent(session)
        summary = import_minit_mobile_operators(
            session,
            parent_name="Mister Minit",
            hq_owner_email="minit-hq@test.mainspring.au",
            operators=operators,
            apply=False,
        )
    assert summary["parent_found"] is True
    assert summary["would_create_count"] == 1
    would_create = summary["would_create"]
    assert isinstance(would_create, list)
    assert would_create[0]["shop_number"] == "2243"
    # Pilot operator 3904 exists but display name differs from seed → update, not create.
    assert summary["would_update_count"] == 1


def test_import_mobile_operators_apply_is_idempotent() -> None:
    create_db_and_tables()
    operators = [
        _resolved_operator("2243", "Burwood", "0477738814"),
        _resolved_operator("2258", "Kotara", "0405951490"),
    ]
    with Session(engine) as session:
        _seed_parent(session)
        first = import_minit_mobile_operators(
            session,
            parent_name="Mister Minit",
            hq_owner_email="minit-hq@test.mainspring.au",
            operators=operators,
            apply=True,
        )
        second = import_minit_mobile_operators(
            session,
            parent_name="Mister Minit",
            hq_owner_email="minit-hq@test.mainspring.au",
            operators=operators,
            apply=True,
        )
    assert first["created_count"] == 2
    assert second["created_count"] == 0
    assert second["skipped_count"] == 2


def test_operator_and_retail_can_share_shop_number() -> None:
    """Operator minit-mobile-2243 and retail minit-2243 may coexist under one parent."""
    create_db_and_tables()
    operators = [_resolved_operator("2243", "Burwood", "0477738814")]
    retail = [
        MinitShopRow(shop_number="2243", name="Burwood", area="NSW", region="NSW"),
        MinitShopRow(shop_number="5999", name="Other Shop", area="NSW", region="NSW"),
    ]
    with Session(engine) as session:
        _seed_parent(session)
        op_summary = import_minit_mobile_operators(
            session,
            parent_name="Mister Minit",
            hq_owner_email="minit-hq@test.mainspring.au",
            operators=operators,
            apply=True,
        )
        retail_summary = import_minit_shops(
            session,
            parent_name="Mister Minit",
            hq_owner_email="minit-hq@test.mainspring.au",
            shops=retail,
            apply=True,
        )
        parent_id = op_summary["parent_account_id"]
        assert parent_id == retail_summary["parent_account_id"]
        from uuid import UUID

        tenants = linked_tenants_for_parent(session, UUID(str(parent_id)))
        by_slug = {t.slug: t for t in tenants}
        assert "minit-mobile-2243" in by_slug
        assert "minit-2243" in by_slug
        assert by_slug["minit-mobile-2243"].shop_number == "2243"
        assert by_slug["minit-2243"].shop_number == "2243"
        assert by_slug["minit-mobile-2243"].mobile_dispatch_phone == "0477738814"


def test_resolve_mobile_operators_requires_tss_row() -> None:
    seeds = [
        MobileOperatorSeed(
            shop_number="9999",
            operator_label="Missing",
            dispatch_phone="0400000000",
        )
    ]
    tss_by_number = index_tss_shops_by_number(
        [MinitShopRow(shop_number="2243", name="Burwood", area="NSW", region="NSW")]
    )
    resolved, errors = resolve_mobile_operators(seeds, tss_by_number)
    assert resolved == []
    assert len(errors) == 1
    assert errors[0]["shop_number"] == "9999"
