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


# ── L9: uploads are read in chunks and stopped at the limit ──────────────────

def test_l9_read_upload_capped_stops_at_limit():
    import asyncio
    import io

    from fastapi import HTTPException, UploadFile

    from app.upload_limits import read_upload_capped

    class _CountingIO(io.BytesIO):
        bytes_read = 0

        def read(self, n=-1):
            data = super().read(n)
            _CountingIO.bytes_read += len(data)
            return data

    big = _CountingIO(b"x" * (5 * 1024 * 1024))
    upload = UploadFile(file=big, filename="big.bin")
    try:
        asyncio.run(read_upload_capped(upload, 256 * 1024))
    except HTTPException as exc:
        assert exc.status_code == 413
    else:
        raise AssertionError("oversized upload was accepted")
    # Stopped shortly after the limit rather than reading the whole 5 MB.
    assert _CountingIO.bytes_read < 512 * 1024

    small = UploadFile(file=io.BytesIO(b"hello"), filename="s.txt")
    assert asyncio.run(read_upload_capped(small, 1024)) == b"hello"


def test_l9_request_body_limit_rejects_before_parsing(client, monkeypatch):
    from app.main import app as fastapi_app
    from app.upload_limits import RequestBodyLimitMiddleware

    # Find the live middleware instance and shrink its cap for this test.
    stack = fastapi_app.middleware_stack or fastapi_app.build_middleware_stack()
    node = stack
    limiter_mw = None
    while node is not None:
        if isinstance(node, RequestBodyLimitMiddleware):
            limiter_mw = node
            break
        node = getattr(node, "app", None)
    assert limiter_mw is not None, "RequestBodyLimitMiddleware is not installed"
    monkeypatch.setattr(limiter_mw, "max_bytes", 1024)

    res = client.post(
        "/v1/public/auto-key-intake/not-a-token/photos",
        files={"files": ("key.jpg", b"x" * 4096, "image/jpeg")},
    )
    assert res.status_code == 413, res.text

    # Chunked body with no Content-Length is counted as it streams.
    def _gen():
        for _ in range(8):
            yield b"y" * 512

    res = client.post("/v1/public/auto-key-intake/not-a-token/submit", content=_gen())
    assert res.status_code == 413, res.text


# ── Rate limits: every unauthenticated route has one ─────────────────────────

# Routes deliberately left unlimited: health probes, and provider webhooks that
# are authenticated by signature and whose volume is set by the provider.
_UNLIMITED_PUBLIC_ROUTES = {
    "/v1/health",
    "/v1/ready",
    "/v1/seed-status",
    "/v1/debug/demo-status",
    "/v1/debug/sms-status",
    "/v1/billing/webhook",
    "/v1/billing/xero/callback",
    "/v1/webhooks/xero",
    "/v1/webhook/sms/incoming",
}


def _dependency_names(dependant) -> list[str]:
    out: list[str] = []
    for dep in dependant.dependencies:
        out.append(getattr(dep.call, "__qualname__", str(dep.call)))
        out.extend(_dependency_names(dep))
    return out


def _all_api_routes(routes):
    """Every APIRoute, descending into included routers.

    FastAPI >= 0.13x nests each ``include_router`` as an ``_IncludedRouter``
    entry, so a flat walk of ``app.routes`` silently finds almost nothing.
    """
    from fastapi.routing import APIRoute

    for route in routes:
        if isinstance(route, APIRoute):
            yield route
        elif hasattr(route, "original_router"):
            yield from _all_api_routes(route.original_router.routes)
        elif hasattr(route, "routes"):
            yield from _all_api_routes(route.routes)


def test_every_unauthenticated_route_is_rate_limited():
    from app.limiter import limiter
    from app.main import app as fastapi_app

    limited = set(limiter._route_limits) | set(limiter._dynamic_route_limits)
    missing = []
    routes = list(_all_api_routes(fastapi_app.routes))
    assert len(routes) > 200, f"route walker found only {len(routes)} routes"
    for route in routes:
        if route.path in _UNLIMITED_PUBLIC_ROUTES:
            continue
        if route.path.startswith("/v1/_test/"):
            continue  # probe routes other test modules mount on the app
        names = _dependency_names(route.dependant)
        authenticated = any(
            n in ("get_auth_context", "_check") or n.startswith("require") or ".require" in n
            or ("auth" in n.lower() and "context" in n.lower())
            for n in names
        )
        if authenticated:
            continue
        key = f"{route.endpoint.__module__}.{route.endpoint.__name__}"
        if key not in limited:
            missing.append(f"{sorted(route.methods)} {route.path}")
    assert not missing, "Unauthenticated routes without a rate limit:\n" + "\n".join(missing)


# ── L10: address lookups are cached and budgeted ─────────────────────────────

def test_l10_geocode_is_cached_and_budgeted(monkeypatch):
    import asyncio

    from app import dispatch_utils

    calls: list[str] = []

    class _Resp:
        def __init__(self, payload):
            self._payload = payload

        def raise_for_status(self):
            return None

        def json(self):
            return self._payload

    class _Client:
        def __init__(self, *a, **k):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, *a):
            return False

        async def get(self, url, params=None):
            calls.append(params["address"])
            if "nowhere" in params["address"]:
                return _Resp({"status": "ZERO_RESULTS", "results": []})
            return _Resp({"status": "OK", "results": [{"geometry": {"location": {"lat": -37.8, "lng": 145.0}}}]})

    monkeypatch.setattr(dispatch_utils.settings, "google_maps_web_services_key", "k")
    monkeypatch.setattr(dispatch_utils.settings, "geocode_max_calls_per_minute", 3)
    monkeypatch.setattr(dispatch_utils.httpx, "AsyncClient", _Client)
    dispatch_utils.reset_geocode_cache()
    try:
        run = asyncio.run
        assert run(dispatch_utils.geocode_address("1 Main St, Chadstone")) == (-37.8, 145.0)
        # Same address with different spacing/case: served from cache.
        assert run(dispatch_utils.geocode_address("  1 main st,   CHADSTONE ")) == (-37.8, 145.0)
        assert len(calls) == 1

        # A definitive miss is cached too.
        for _ in range(3):
            try:
                run(dispatch_utils.geocode_address("nowhere road"))
            except ValueError:
                pass
        assert len(calls) == 2

        # Budget: 3 real calls a minute; the fourth distinct address is refused.
        run(dispatch_utils.geocode_address("2 Main St"))
        try:
            run(dispatch_utils.geocode_address("3 Main St"))
        except ValueError as exc:
            assert "busy" in str(exc)
        else:
            raise AssertionError("geocode budget was not enforced")
        assert len(calls) == 3

        try:
            run(dispatch_utils.geocode_address("x" * 1000))
        except ValueError:
            pass
        assert len(calls) == 3
    finally:
        dispatch_utils.reset_geocode_cache()


# ── Customer-facing status note ──────────────────────────────────────────────

def test_customer_note_shows_on_status_page_and_staff_note_does_not(client, auth_headers, make_customer, make_watch):
    watch_id = make_watch(auth_headers, make_customer(auth_headers))
    job = client.post(
        "/v1/repair-jobs", headers=auth_headers,
        json={"watch_id": watch_id, "title": "Service", "priority": "normal"},
    ).json()
    res = client.post(
        f"/v1/repair-jobs/{job['id']}/status", headers=auth_headers,
        json={
            "status": "awaiting_parts",
            "note": "Supplier quoted $40, we charge $120",
            "customer_note": "Waiting on parts from our Swiss supplier",
        },
    )
    assert res.status_code == 200, res.text
    assert res.json()["customer_note"] == "Waiting on parts from our Swiss supplier"

    public = client.get(f"/v1/public/jobs/{job['status_token']}").json()
    assert public["customer_note"] == "Waiting on parts from our Swiss supplier"
    assert "Supplier quoted" not in str(public)

    # Moving on without a new note clears the stale one.
    client.post(f"/v1/repair-jobs/{job['id']}/status", headers=auth_headers, json={"status": "working_on"})
    assert client.get(f"/v1/public/jobs/{job['status_token']}").json()["customer_note"] is None

    too_long = client.post(
        f"/v1/repair-jobs/{job['id']}/status", headers=auth_headers,
        json={"status": "working_on", "customer_note": "x" * 281},
    )
    assert too_long.status_code == 422


# ── Shop delete: the database removes a shop's rows itself ───────────────────

def test_tenant_foreign_keys_carry_delete_rules():
    import pytest
    from sqlalchemy import text as sql_text

    if engine.dialect.name != "postgresql":
        pytest.skip("ON DELETE rules are applied by a Postgres migration")
    with engine.connect() as conn:
        rows = conn.execute(
            sql_text(
                """
                SELECT rel.relname, att.attname, con.confdeltype
                FROM pg_constraint con
                JOIN pg_class rel ON rel.oid = con.conrelid
                JOIN pg_attribute att ON att.attrelid = con.conrelid AND att.attnum = con.conkey[1]
                WHERE con.contype = 'f' AND con.confrelid = 'tenant'::regclass
                """
            )
        ).fetchall()
    by_column = {(t, c): rule for t, c, rule in rows}
    owned = [(t, c) for (t, c), rule in by_column.items() if c == "tenant_id" and rule not in ("c", "n")]
    assert not owned, f"tenant_id foreign keys without an ON DELETE rule: {owned}"
    assert by_column[("repairjob", "tenant_id")] == "c"
    assert by_column[("parentaccount", "mobile_lead_default_tenant_id")] == "n"


def test_delete_tenant_row_cascades_on_postgres(client, bootstrap_and_login, make_customer, make_watch):
    import pytest
    from sqlalchemy import text as sql_text

    if engine.dialect.name != "postgresql":
        pytest.skip("cascade is a Postgres migration")
    slug = f"cascade-{uuid4().hex[:8]}"
    headers = {"Authorization": f"Bearer {bootstrap_and_login(tenant_slug=slug)}"}
    watch_id = make_watch(headers, make_customer(headers))
    client.post("/v1/repair-jobs", headers=headers, json={"watch_id": watch_id, "title": "x", "priority": "normal"})
    with Session(engine) as s:
        tenant = s.exec(select(Tenant).where(Tenant.slug == slug)).one()
        tid = str(tenant.id)
    with engine.begin() as conn:
        # Rows with no tenant_id of their own still need the app's explicit deletes;
        # everything keyed by tenant_id goes with the tenant row.
        conn.execute(sql_text("DELETE FROM refreshsession WHERE tenant_id = CAST(:t AS uuid)"), {"t": tid})
        conn.execute(
            sql_text('DELETE FROM parentaccountuser WHERE user_id IN (SELECT id FROM "user" WHERE tenant_id = CAST(:t AS uuid))'),
            {"t": tid},
        )
        conn.execute(sql_text("DELETE FROM tenant WHERE id = CAST(:t AS uuid)"), {"t": tid})
        left = conn.execute(sql_text("SELECT count(*) FROM repairjob WHERE tenant_id = CAST(:t AS uuid)"), {"t": tid}).scalar()
    assert left == 0
