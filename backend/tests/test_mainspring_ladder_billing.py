"""Locked Mainspring ladder: Shop A$50, Pro A$90, extra site +A$25."""
from __future__ import annotations

import pytest
from fastapi import HTTPException

from app.config import settings
from app.routes.billing import (
    SHOP_PLAN_CODE,
    _checkout_target_plan_code,
    _line_items_for_plan,
    _plan_code_from_price_id,
    extra_location_quantity,
)


@pytest.fixture
def ladder_prices(monkeypatch):
    monkeypatch.setattr(settings, "stripe_price_shop", "price_shop_new")
    monkeypatch.setattr(settings, "stripe_price_pro", "price_pro_90")
    monkeypatch.setattr(settings, "stripe_price_pro_legacy", "price_pro_50_old")
    monkeypatch.setattr(settings, "stripe_price_extra_location", "price_extra_25")
    monkeypatch.setattr(settings, "stripe_price_basic_base", "price_basic_base_old")
    monkeypatch.setattr(settings, "stripe_price_basic_addon_tab", "price_addon_old")
    monkeypatch.setattr(settings, "stripe_price_watch", "price_watch_old")
    monkeypatch.setattr(settings, "stripe_price_enterprise", "price_ent_old")


def test_extra_location_quantity_first_site_is_included():
    assert extra_location_quantity(0) == 0
    assert extra_location_quantity(1) == 0
    assert extra_location_quantity(2) == 1
    assert extra_location_quantity(4) == 3


def test_new_checkout_collapses_tab_skus_to_shop(ladder_prices):
    assert _checkout_target_plan_code("basic_watch") == SHOP_PLAN_CODE
    assert _checkout_target_plan_code("basic_all_tabs") == SHOP_PLAN_CODE
    assert _checkout_target_plan_code("pro") == "pro"
    with pytest.raises(HTTPException) as exc:
        _checkout_target_plan_code("minit_hq")
    assert exc.value.status_code == 400


def test_shop_checkout_uses_new_shop_price(ladder_prices):
    items = _line_items_for_plan("basic_watch")
    assert items == [{"price": "price_shop_new", "quantity": 1}]
    assert _line_items_for_plan("basic_all_tabs") == items


def test_pro_checkout_includes_extra_location_quantity(ladder_prices):
    assert _line_items_for_plan("pro") == [{"price": "price_pro_90", "quantity": 1}]
    assert _line_items_for_plan("pro", extra_location_qty=2) == [
        {"price": "price_pro_90", "quantity": 1},
        {"price": "price_extra_25", "quantity": 2},
    ]


def test_webhook_maps_new_and_legacy_prices(ladder_prices):
    assert _plan_code_from_price_id("price_shop_new") == SHOP_PLAN_CODE
    assert _plan_code_from_price_id("price_pro_90") == "pro"
    assert _plan_code_from_price_id("price_pro_50_old") == "pro"
    assert _plan_code_from_price_id("price_watch_old") == "basic_watch"
    assert _plan_code_from_price_id("price_extra_25") is None


def test_shop_falls_back_to_legacy_tab_prices_when_shop_price_missing(monkeypatch):
    monkeypatch.setattr(settings, "stripe_price_shop", "")
    monkeypatch.setattr(settings, "stripe_price_basic_base", "price_basic_base_old")
    monkeypatch.setattr(settings, "stripe_price_basic_addon_tab", "price_addon_old")
    items = _line_items_for_plan("basic_all_tabs")
    assert items == [
        {"price": "price_basic_base_old", "quantity": 1},
        {"price": "price_addon_old", "quantity": 2},
    ]
