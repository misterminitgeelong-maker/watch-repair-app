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


def test_wa_placement_moves_default_timezone_to_perth_once():
    from datetime import datetime, timezone

    from app.datetime_utils import format_in_timezone
    from app.regions import apply_au_state_timezone

    t = SimpleNamespace(minit_region="WA", timezone="Australia/Melbourne")
    assert apply_au_state_timezone(t)
    assert t.timezone == "Australia/Perth"
    assert not apply_au_state_timezone(t)

    # Fergus's booking: 11:30am Perth is 03:30 UTC. Melbourne clocks would have said 2:30pm.
    booked = datetime(2026, 10, 20, 3, 30, tzinfo=timezone.utc)
    assert format_in_timezone(booked, "Australia/Perth", "%I:%M%p") == "11:30AM"
    assert format_in_timezone(booked, "Australia/Melbourne", "%I:%M%p") == "02:30PM"


def test_state_timezone_leaves_chosen_zone_and_vic_alone():
    from app.regions import apply_au_state_timezone

    chosen = SimpleNamespace(minit_region="WA", timezone="Australia/Adelaide")
    assert not apply_au_state_timezone(chosen)
    assert chosen.timezone == "Australia/Adelaide"
    vic = SimpleNamespace(minit_region="VIC", timezone="Australia/Melbourne")
    assert not apply_au_state_timezone(vic)
