from types import SimpleNamespace

from app.gst import compute_gst_amounts
from app.regions import region_for_currency, stripe_country_for_tenant


def test_region_from_currency():
    assert region_for_currency("NZD") == "NZ"
    assert region_for_currency("aud") == "AU"
    assert region_for_currency(None) == "AU"


def test_stripe_country_follows_tenant_currency():
    assert stripe_country_for_tenant(SimpleNamespace(default_currency="NZD"), "AU") == "NZ"
    assert stripe_country_for_tenant(SimpleNamespace(default_currency="AUD"), "AU") == "AU"


def test_nz_gst_is_15_percent():
    assert compute_gst_amounts(11500, True, True, "NZD") == (10000, 1500, 11500)
    assert compute_gst_amounts(10000, True, False, "NZD") == (10000, 1500, 11500)


def test_nz_placement_presets_defaults_once():
    from app.regions import apply_nz_defaults_from_placement, is_nz_minit_placement

    assert is_nz_minit_placement("NZ", None)
    assert is_nz_minit_placement(None, "NZ NORTH")
    assert not is_nz_minit_placement("VIC", "VIC SOUTH")

    t = SimpleNamespace(minit_region="NZ", minit_area="NZ NORTH", default_currency="AUD", timezone="Australia/Melbourne")
    assert apply_nz_defaults_from_placement(t)
    assert (t.default_currency, t.timezone) == ("NZD", "Pacific/Auckland")
    assert not apply_nz_defaults_from_placement(t)

    au = SimpleNamespace(minit_region="VIC", minit_area="VIC SOUTH", default_currency="AUD", timezone="Australia/Melbourne")
    assert not apply_nz_defaults_from_placement(au)
