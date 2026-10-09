"""Per-HQ settings, and a lock on the Minit behaviour they are seeded from.

The first half pins how Minit behaves today (plans, branding, HQ nav). The
multi-HQ work replaces those hard-coded rules with per-HQ settings; if any of
these fail during that work, Minit's behaviour changed and it must be fixed
before shipping, not the test.
"""

from uuid import uuid4

import pytest
from sqlmodel import Session

from app.database import engine
from app.hq_settings import (
    HQ_MODULES,
    MINIT_DEFAULTS,
    HqConfig,
    ensure_minit_hq_settings,
    get_hq_config,
    upsert_hq_settings,
)
from app.minit_branding import (
    MINIT_ACCENT_COLOR,
    MINIT_DOCUMENT_COLOR,
    MINIT_SITE_PLANS,
    allowed_plans_for_minit_tenant,
    customer_brand_color,
    customer_logo_url,
    document_branding,
    effective_plan_code,
    is_minit_hq_ui,
    public_shop_branding,
    target_plan_for_minit_tenant,
    tenant_product,
)
from app.minit_provision import ensure_minit_pilot_account
from app.models import ParentAccount, Tenant


def _hq() -> Tenant:
    return Tenant(name="Minit HQ", slug="mmsupport", plan_code="enterprise", is_minit=True)


def _shop(plan: str) -> Tenant:
    return Tenant(name="Shop", slug="minit-3269", plan_code=plan, is_minit=True)


# ── Minit behaviour lock ─────────────────────────────────────────────────────


def test_minit_hq_is_forced_onto_hq_plan_and_hq_nav():
    assert target_plan_for_minit_tenant(_hq()) == "minit_hq"
    assert effective_plan_code(_hq()) == "minit_hq"
    assert is_minit_hq_ui(_hq()) is True
    assert allowed_plans_for_minit_tenant(_hq()) == frozenset({"minit_hq"})


@pytest.mark.parametrize("plan", ["pro", "basic_all_tabs", "basic_watch", "basic_shoe", "enterprise"])
def test_minit_sites_never_keep_mainspring_pos_plans(plan):
    assert target_plan_for_minit_tenant(_shop(plan)) == "booking_only"
    assert effective_plan_code(_shop(plan)) == "booking_only"


@pytest.mark.parametrize("plan", ["booking_only", "basic_auto_key"])
def test_minit_sites_keep_their_own_plans(plan):
    assert target_plan_for_minit_tenant(_shop(plan)) is None
    assert is_minit_hq_ui(_shop(plan)) is False
    assert allowed_plans_for_minit_tenant(_shop(plan)) == MINIT_SITE_PLANS


def test_non_minit_tenants_are_untouched_by_minit_rules():
    other = Tenant(name="Other", slug="other-hq", plan_code="pro")
    assert tenant_product(other) == "mainspring"
    assert target_plan_for_minit_tenant(other) is None
    assert allowed_plans_for_minit_tenant(other) is None
    assert is_minit_hq_ui(other) is False


def test_minit_customer_facing_branding():
    shop = _shop("booking_only")
    assert customer_logo_url(shop).endswith("/minit-logo-cropped.jpg")
    assert customer_brand_color(shop) == MINIT_ACCENT_COLOR
    shop.brand_color = "#123456"
    assert customer_brand_color(shop) == "#123456"
    assert document_branding(shop)["brand_color"] == MINIT_DOCUMENT_COLOR
    assert public_shop_branding(shop)["is_minit"] is True
    other = Tenant(name="Other", slug="other", logo_url="https://x/logo.png", brand_color="#abcdef")
    assert customer_logo_url(other) == "https://x/logo.png"
    assert public_shop_branding(other)["is_minit"] is False


# ── Seeded defaults match that behaviour ─────────────────────────────────────


def test_minit_defaults_mirror_current_rules():
    assert MINIT_DEFAULTS.site_plans == MINIT_SITE_PLANS
    assert MINIT_DEFAULTS.brand_color == MINIT_ACCENT_COLOR
    assert MINIT_DEFAULTS.has_module("mobile_services")
    assert MINIT_DEFAULTS.has_module("lead_routing")
    # Minit does not run shoe, watch or stock tracking through HQ today.
    for module in ("shoe", "watch", "stock"):
        assert not MINIT_DEFAULTS.has_module(module)
    assert MINIT_DEFAULTS.modules <= set(HQ_MODULES)


def test_migration_seed_matches_defaults():
    import importlib.util
    from pathlib import Path

    path = Path(__file__).parents[1] / "alembic" / "versions" / "20261009a_hq_settings.py"
    spec = importlib.util.spec_from_file_location("hq_settings_migration", path)
    migration = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(migration)
    assert frozenset(migration._MINIT_MODULES) == MINIT_DEFAULTS.modules
    assert frozenset(migration._MINIT_SITE_PLANS) == MINIT_DEFAULTS.site_plans


# ── Settings storage ─────────────────────────────────────────────────────────


def _parent(session: Session, name: str) -> ParentAccount:
    parent = ParentAccount(name=name, owner_email=f"{uuid4().hex[:8]}@example.test")
    session.add(parent)
    session.flush()
    return parent


def test_two_hqs_hold_independent_settings():
    with Session(engine) as session:
        minit, other = _parent(session, "Minit"), _parent(session, "Other Co")
        ensure_minit_hq_settings(session, minit.id)
        upsert_hq_settings(session, other.id, HqConfig(
            product_key="otherco", display_name="Other Co", logo_url="https://x/o.png", brand_color="#00aa00",
            modules=frozenset({"shoe", "stock"}), site_plans=frozenset({"basic_shoe"}),
        ))
        session.commit()
        assert get_hq_config(session, minit.id) == MINIT_DEFAULTS
        got = get_hq_config(session, other.id)
        assert got.modules == {"shoe", "stock"} and got.site_plans == {"basic_shoe"}
        assert got.product_key == "otherco"


def test_ensure_minit_row_never_overwrites_admin_edits():
    with Session(engine) as session:
        parent = _parent(session, "Minit edited")
        ensure_minit_hq_settings(session, parent.id)
        edited = HqConfig(**{**MINIT_DEFAULTS.__dict__, "modules": MINIT_DEFAULTS.modules | {"stock"}})
        upsert_hq_settings(session, parent.id, edited)
        ensure_minit_hq_settings(session, parent.id)
        assert get_hq_config(session, parent.id).has_module("stock")


def test_unknown_module_rejected_and_missing_hq_is_none():
    with Session(engine) as session:
        parent = _parent(session, "Bad modules")
        with pytest.raises(ValueError):
            upsert_hq_settings(session, parent.id, HqConfig(
                product_key="x", display_name="X", logo_url=None, brand_color=None,
                modules=frozenset({"teleport"}), site_plans=frozenset(),
            ))
        assert get_hq_config(session, parent.id) is None


def test_minit_provisioning_seeds_settings_row():
    with Session(engine) as session:
        result = ensure_minit_pilot_account(
            session,
            parent_name="Mister Minit AU",
            hq_tenant_slug="mmsupport",
            hq_tenant_name="Mister Minit HQ",
            hq_owner_email="hq@example.test",
            hq_owner_password="a-real-test-password-1",
        )
        assert get_hq_config(session, result.parent_account_id) == MINIT_DEFAULTS
        # Running provisioning again keeps exactly one row.
        ensure_minit_pilot_account(
            session,
            parent_name="Mister Minit AU",
            hq_tenant_slug="mmsupport",
            hq_tenant_name="Mister Minit HQ",
            hq_owner_email="hq@example.test",
            hq_owner_password="a-real-test-password-1",
        )
        assert get_hq_config(session, result.parent_account_id) == MINIT_DEFAULTS
