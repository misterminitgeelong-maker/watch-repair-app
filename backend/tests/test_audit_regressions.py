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
