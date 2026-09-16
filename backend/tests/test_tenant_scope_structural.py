"""Tenant isolation is now a property of the session, not of 325 memories.

These tests exist to prove the mechanism actually bites. A guard that silently
does nothing is worse than no guard, because it stops people looking — and this
mechanism has a specific way of failing silently, which one of the tests below
pins directly.
"""
from __future__ import annotations

from uuid import UUID, uuid4

import pytest
from sqlalchemy import update
from sqlmodel import Session, select

from app.database import engine
from app.models import Customer, RepairJob, Tenant, Watch
from app.tenant_scope import (
    SCOPE_KEY,
    clear_scope,
    current_scope,
    is_scoped,
    scope_to_tenant,
    tenant_scoped_models,
)


@pytest.fixture
def two_tenants():
    """Two tenants, each with one customer. The classic isolation setup."""
    a_id, b_id = uuid4(), uuid4()
    with Session(engine) as s:
        s.add(Tenant(id=a_id, name="Shop A", slug=f"scope-a-{uuid4().hex[:8]}"))
        s.add(Tenant(id=b_id, name="Shop B", slug=f"scope-b-{uuid4().hex[:8]}"))
        s.commit()
        a_cust = Customer(tenant_id=a_id, full_name="Alice of A")
        b_cust = Customer(tenant_id=b_id, full_name="Bob of B")
        s.add(a_cust)
        s.add(b_cust)
        s.commit()
        s.refresh(a_cust)
        s.refresh(b_cust)
        ids = (a_id, b_id, a_cust.id, b_cust.id)
    yield ids


def test_select_returns_only_the_scoped_tenants_rows(two_tenants):
    a_id, _b_id, a_cust, b_cust = two_tenants
    with Session(engine) as s:
        scope_to_tenant(s, a_id)
        rows = s.exec(select(Customer).where(Customer.id.in_([a_cust, b_cust]))).all()
    assert [r.full_name for r in rows] == ["Alice of A"]


def test_session_get_cannot_reach_another_tenants_row(two_tenants):
    """The reason this design was chosen over a helper function.

    327 lookups in routes/ are `session.get(Model, id)`. If the filter did not
    intercept get(), every one of them would have needed editing — and the ones
    added next year would not be covered at all.
    """
    a_id, _b, a_cust, b_cust = two_tenants
    with Session(engine) as s:
        scope_to_tenant(s, a_id)
        assert s.get(Customer, a_cust) is not None, "own row must still be reachable"
        assert s.get(Customer, b_cust) is None, "reached another tenant's row by primary key"


def test_cross_tenant_bulk_update_is_blocked(two_tenants):
    """Not read-only protection: a write aimed at another tenant does nothing."""
    a_id, _b, _a_cust, b_cust = two_tenants
    with Session(engine) as s:
        scope_to_tenant(s, a_id)
        s.exec(update(Customer).where(Customer.id == b_cust).values(full_name="OVERWRITTEN"))
        s.commit()

    with Session(engine) as s:  # unscoped, to see the truth
        assert s.get(Customer, b_cust).full_name == "Bob of B"


def test_an_unscoped_session_still_sees_everything(two_tenants):
    """The escape hatch has to work, or the cross-tenant features break."""
    _a, _b, a_cust, b_cust = two_tenants
    with Session(engine) as s:
        assert not is_scoped(s)
        rows = s.exec(select(Customer).where(Customer.id.in_([a_cust, b_cust]))).all()
    assert len(rows) == 2


def test_scope_can_be_cleared_and_reapplied(two_tenants):
    a_id, _b, _a_cust, b_cust = two_tenants
    with Session(engine) as s:
        scope_to_tenant(s, a_id)
        assert current_scope(s) == a_id
        assert s.get(Customer, b_cust) is None
        clear_scope(s)
        s.expunge_all()
        assert not is_scoped(s)
        assert s.get(Customer, b_cust) is not None


def test_joined_query_is_scoped_on_every_participating_table(two_tenants):
    """A join must not become a side door into another tenant's rows."""
    a_id, b_id, _a_cust, b_cust = two_tenants
    with Session(engine) as s:
        watch = Watch(tenant_id=b_id, customer_id=b_cust, brand="B's watch")
        s.add(watch)
        s.commit()
        s.refresh(watch)
        job = RepairJob(
            tenant_id=b_id, watch_id=watch.id, job_number=f"J-{uuid4().hex[:6]}",
            status_token=uuid4().hex, title="B's job",
        )
        s.add(job)
        s.commit()

    with Session(engine) as s:
        scope_to_tenant(s, a_id)
        rows = s.exec(select(RepairJob).join(Watch, RepairJob.watch_id == Watch.id)).all()
    assert rows == [], "a join leaked another tenant's rows"


def test_every_table_with_a_tenant_id_is_covered(two_tenants):
    """The model list is derived, not hand-maintained.

    A hand-written list is the same 'remember to add it' problem this module
    exists to remove, so this asserts the derivation actually finds the tables.
    """
    models = tenant_scoped_models()
    names = {m.__tablename__ for m in models}
    # A representative spread across the product's domains.
    for expected in ("customer", "repairjob", "invoice", "quote", "autokeyjob", "attachment"):
        assert expected in names, f"{expected} is tenant-scoped but not covered"
    assert len(models) >= 50, f"only {len(models)} scoped models found; derivation looks broken"


def test_scope_key_is_absent_by_default():
    """Sessions are unscoped until something scopes them, so the escape hatch
    is the default and the protection is opt-in per request."""
    with Session(engine) as s:
        assert SCOPE_KEY not in s.info


# ── The actual claim ──────────────────────────────────────────────────────────
# Everything above tests the mechanism. This tests the property the mechanism
# exists for: an endpoint that forgets its manual tenant check is safe anyway.

from fastapi import APIRouter, Depends  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

from app.database import get_session, unscoped_session  # noqa: E402
from app.dependencies import AuthContext, get_auth_context  # noqa: E402
from app.main import app  # noqa: E402

_careless = APIRouter()


@_careless.get("/v1/_test/careless-lookup/{customer_id}")
def _careless_lookup(
    customer_id: UUID,
    session: Session = Depends(get_session),
    auth: AuthContext = Depends(get_auth_context),
):
    """Deliberately written the wrong way: no `if row.tenant_id != auth.tenant_id`.

    This is exactly the endpoint someone writes in a hurry. Before the scoped
    session it returned any tenant's customer to any authenticated caller.
    """
    row = session.get(Customer, customer_id)
    return {"found": row is not None, "name": row.full_name if row else None}


@_careless.get("/v1/_test/careless-unscoped/{customer_id}")
def _careless_unscoped(
    customer_id: UUID,
    session: Session = Depends(unscoped_session),
    auth: AuthContext = Depends(get_auth_context),
):
    """The same mistake on an unscoped session — still a leak, by construction.

    Pinned so the escape hatch is understood for what it is: taking
    `unscoped_session` means the endpoint owns its own tenant checks.
    """
    row = session.get(Customer, customer_id)
    return {"found": row is not None}


app.include_router(_careless)


def test_a_route_that_forgets_its_tenant_check_is_safe_anyway(
    client: TestClient, auth_headers, two_tenants
):
    _a_id, _b_id, a_cust, b_cust = two_tenants

    own = client.get(f"/v1/_test/careless-lookup/{a_cust}", headers=auth_headers)
    other = client.get(f"/v1/_test/careless-lookup/{b_cust}", headers=auth_headers)

    assert own.status_code == 200 and other.status_code == 200
    # The caller's tenant is neither A nor B (the fixture makes fresh tenants),
    # so the honest assertion is that *neither* foreign row is reachable.
    assert other.json()["found"] is False, "reached another tenant's customer"
    assert own.json()["found"] is False, "reached another tenant's customer"


def test_the_escape_hatch_really_is_unscoped(client: TestClient, auth_headers, two_tenants):
    """If this ever starts returning found=False, the unscoped session is no
    longer unscoped and the cross-tenant features are silently broken."""
    _a, _b, _a_cust, b_cust = two_tenants
    r = client.get(f"/v1/_test/careless-unscoped/{b_cust}", headers=auth_headers)
    assert r.status_code == 200
    assert r.json()["found"] is True


def test_the_set_of_cross_tenant_modules_is_pinned():
    """Crossing the tenant boundary must stay a deliberate, reviewed decision.

    The whole argument for this design over a helper function is auditability:
    instead of checking 325 query sites, a reviewer checks the handful of
    modules that opt out. That only holds if the list cannot grow quietly.

    If you are adding a module here, say in the PR why it genuinely spans
    tenants. If you are adding it to make a test pass, that is the bug.
    """
    import pathlib

    routes = pathlib.Path(__file__).resolve().parents[1] / "app" / "routes"
    actual = {
        p.stem for p in routes.glob("*.py")
        if "unscoped_session" in p.read_text()
    }
    expected = {
        "auth",                  # resolves a user before a tenant is known
        "billing",               # Stripe webhooks carry a tenant id, not a token
        "inbound_email",         # routes mail to whichever shop in the network owns it
        "parent_accounts",       # parent-account membership across its shops
        "parent_network_admin",  # HQ support sessions into sibling shops; network org chart, roles, regions
        "parent_operations",     # franchise-network reporting across shops
        "platform_admin",        # administration across all tenants
        "shop_mobile_bookings",  # dispatch between a requesting and an operator shop
        "shop_owner_invites",    # onboards a shop that is not the caller's tenant
    }
    assert actual == expected, (
        "the set of tenant-boundary-crossing route modules changed.\n"
        f"  added:   {sorted(actual - expected)}\n"
        f"  removed: {sorted(expected - actual)}"
    )
