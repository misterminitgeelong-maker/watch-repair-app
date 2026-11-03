"""A Minit-network shop flagged keep_own_plan keeps Pro; others are forced to booking_only."""
from app.minit_branding import (
    allowed_plans_for_minit_tenant,
    effective_plan_code,
    target_plan_for_minit_tenant,
)
from app.models import Tenant


def _shop(**kw):
    return Tenant(name="S", slug=kw.pop("slug", "minit-6441"), plan_code=kw.pop("plan_code", "pro"), is_minit=True, **kw)


def test_minit_shop_on_pro_is_forced_to_booking_only_by_default():
    t = _shop()
    assert target_plan_for_minit_tenant(t) == "booking_only"
    assert effective_plan_code(t) == "booking_only"
    assert allowed_plans_for_minit_tenant(t) is not None


def test_keep_own_plan_keeps_pro_and_lifts_restriction():
    t = _shop(keep_own_plan=True)
    assert target_plan_for_minit_tenant(t) is None
    assert effective_plan_code(t) == "pro"
    assert allowed_plans_for_minit_tenant(t) is None


def test_hq_cannot_opt_out():
    t = _shop(slug="mmsupport", plan_code="pro", keep_own_plan=True)
    assert target_plan_for_minit_tenant(t) == "minit_hq"
    assert allowed_plans_for_minit_tenant(t) == frozenset({"minit_hq"})
