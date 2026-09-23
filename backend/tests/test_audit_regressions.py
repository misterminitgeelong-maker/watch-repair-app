"""Regression tests for findings from the security / correctness walkthrough.

Each test is the proof-of-concept for one finding turned into an assertion, so
the hole cannot quietly reopen. The finding id (L1, L13, HQ3, ...) is in each
test's name.
"""
from __future__ import annotations

from uuid import uuid4

from sqlmodel import Session, select

from app.database import engine
from app.dependencies import (
    LOWEST_PLAN_CODE,
    PLAN_FEATURES,
    AuthContext,
    normalize_plan_code,
    require_feature,
)
from app.models import Tenant


# ── L1: an unrecognised plan code must not grant Pro ─────────────────────────

def test_l1_unknown_plan_code_normalizes_to_lowest_plan():
    assert normalize_plan_code("platinum_ultra") == LOWEST_PLAN_CODE
    assert normalize_plan_code("") == LOWEST_PLAN_CODE
    assert normalize_plan_code(None) == LOWEST_PLAN_CODE
    assert normalize_plan_code("PRO") == "pro"
    assert normalize_plan_code("enterprise") == "pro"


def test_l1_unknown_plan_code_on_auth_context_is_denied_features():
    check = require_feature("watch")
    ctx = AuthContext(tenant_id=uuid4(), user_id=uuid4(), role="owner", plan_code="bogus")
    try:
        check(auth=ctx)
    except Exception as exc:  # HTTPException
        assert getattr(exc, "status_code", None) == 403
    else:
        raise AssertionError("unknown plan code was granted the 'watch' feature")
    assert "watch" not in PLAN_FEATURES[LOWEST_PLAN_CODE]


def test_l1_tenant_with_corrupt_plan_code_gets_lowest_plan_in_session(client, bootstrap_and_login):
    slug = f"l1-{uuid4().hex[:8]}"
    token = bootstrap_and_login(tenant_slug=slug)
    with Session(engine) as session:
        row = session.exec(select(Tenant).where(Tenant.slug == slug)).one()
        row.plan_code = "legacy_gold"
        session.add(row)
        session.commit()
    from app.dependencies import invalidate_auth_cache

    invalidate_auth_cache()
    res = client.get("/v1/auth/session", headers={"Authorization": f"Bearer {token}"})
    assert res.status_code == 200, res.text
    body = res.json()
    assert body["plan_code"] == LOWEST_PLAN_CODE
    assert "watch" not in body["enabled_features"]


# ── L12: whole-cent GST that matches Xero; no GST on non-AUD ─────────────────

def test_l12_gst_rounds_half_up_like_xero():
    from app.gst import compute_gst_amounts, line_total_cents

    # 25c ex-GST → 2.5c GST. Banker's rounding gave 2c; Xero gives 3c.
    assert compute_gst_amounts(25, True, False) == (25, 3, 28)
    # $1.65 inc-GST → 15c GST exactly; $0.55 inc → 5c.
    assert compute_gst_amounts(165, True, True) == (150, 15, 165)
    assert compute_gst_amounts(55, True, True) == (50, 5, 55)
    # Every inclusive total still splits exactly.
    for cents in range(0, 5000):
        sub, tax, total = compute_gst_amounts(cents, True, True)
        assert sub + tax == total == cents
    # Float quantity maths no longer loses a cent (0.3 × 5 = 1.4999… in float).
    assert line_total_cents(0.3, 5) == 2
    assert line_total_cents(1.5, 333) == 500


def test_l12_no_gst_for_non_aud_currency():
    from app.gst import compute_gst_amounts

    assert compute_gst_amounts(10000, True, False, currency="NZD") == (10000, 0, 10000)
    assert compute_gst_amounts(10000, True, False, currency="aud") == (10000, 1000, 11000)
    assert compute_gst_amounts(10000, True, False) == (10000, 1000, 11000)


# ── L13: no negative prices or quantities; discounts are their own line ──────

def _repair_job(client, headers, make_customer, make_watch) -> str:
    watch_id = make_watch(headers, make_customer(headers))
    res = client.post(
        "/v1/repair-jobs",
        headers=headers,
        json={"watch_id": watch_id, "title": "L13 job", "priority": "normal"},
    )
    assert res.status_code == 201, res.text
    return res.json()["id"]


def test_l13_negative_quote_line_rejected(client, auth_headers, make_customer, make_watch):
    job_id = _repair_job(client, auth_headers, make_customer, make_watch)
    for bad in (
        {"quantity": 1, "unit_price_cents": -5000},
        {"quantity": -1, "unit_price_cents": 5000},
        {"quantity": 0, "unit_price_cents": 5000},
    ):
        res = client.post(
            "/v1/quotes",
            headers=auth_headers,
            json={
                "repair_job_id": job_id,
                "line_items": [{"item_type": "labor", "description": "x", **bad}],
            },
        )
        assert res.status_code == 422, (bad, res.text)


def test_l13_discount_line_reduces_total_but_not_below_zero(client, auth_headers, make_customer, make_watch):
    job_id = _repair_job(client, auth_headers, make_customer, make_watch)
    ok = client.post(
        "/v1/quotes",
        headers=auth_headers,
        json={
            "repair_job_id": job_id,
            "gst_inclusive": True,
            "line_items": [
                {"item_type": "labor", "description": "Service", "quantity": 1, "unit_price_cents": 11000},
                {"item_type": "discount", "description": "Loyalty", "quantity": 1, "unit_price_cents": 1100},
            ],
        },
    )
    assert ok.status_code == 201, ok.text
    assert ok.json()["total_cents"] == 9900
    lines = client.get(f"/v1/quotes/{ok.json()['id']}/line-items", headers=auth_headers).json()
    discount = next(li for li in lines if li["item_type"] == "discount")
    assert discount["unit_price_cents"] == -1100
    assert discount["total_price_cents"] == -1100

    too_much = client.post(
        "/v1/quotes",
        headers=auth_headers,
        json={
            "repair_job_id": job_id,
            "line_items": [
                {"item_type": "labor", "description": "Service", "quantity": 1, "unit_price_cents": 1000},
                {"item_type": "discount", "description": "Oops", "quantity": 1, "unit_price_cents": 5000},
            ],
        },
    )
    assert too_much.status_code == 400, too_much.text


def test_l13_negative_job_cost_rejected(client, auth_headers, make_customer, make_watch):
    watch_id = make_watch(auth_headers, make_customer(auth_headers))
    res = client.post(
        "/v1/repair-jobs",
        headers=auth_headers,
        json={"watch_id": watch_id, "title": "neg", "priority": "normal", "cost_cents": -100},
    )
    assert res.status_code == 422, res.text
