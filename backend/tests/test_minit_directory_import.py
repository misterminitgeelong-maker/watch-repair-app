"""Parsing and planning for the Mister Minit Organisation Graph directory import."""

import os
from pathlib import Path
from uuid import uuid4

_TEST_DB = Path(__file__).with_name(f"test_minit_directory_import_{uuid4().hex}.db")
os.environ["DATABASE_URL"] = f"sqlite:///{_TEST_DB.as_posix()}"
os.environ.setdefault("JWT_SECRET", "test-secret-not-for-production")
os.environ.setdefault("APP_ENV", "test")

from sqlmodel import Session, col, select

from app.database import create_db_and_tables, engine
from app.minit_directory_import import plan_directory_import
from app.minit_directory_parser import (
    DirectoryData,
    DirectoryFranchisee,
    DirectoryShop,
    build_directory,
    extract_org_graph,
)
from app.models import ParentAccount, ParentAccountMembership, Tenant, User
from app.security import hash_password, verify_password

create_db_and_tables()

HQ_EMAIL = "hq-owner@directory-test.local"
PARENT_NAME = "Mister Minit"


def _fresh_hq():
    """A brand new HQ tenant + owner + ParentAccount, isolated per test."""
    suffix = uuid4().hex[:8]
    hq_email = f"hq-{suffix}@directory-test.local"
    with Session(engine) as session:
        hq_tenant = Tenant(name="Mister Minit HQ", slug=f"mmsupport-{suffix}", plan_code="minit_hq")
        session.add(hq_tenant)
        session.flush()
        hq_owner = User(
            tenant_id=hq_tenant.id,
            email=hq_email,
            full_name="Mister Minit HQ",
            role="owner",
            password_hash=hash_password("hqpass12345"),
            is_active=True,
        )
        session.add(hq_owner)
        session.flush()
        parent = ParentAccount(name=PARENT_NAME, owner_email=hq_email)
        session.add(parent)
        session.flush()
        session.add(ParentAccountMembership(parent_account_id=parent.id, tenant_id=hq_tenant.id, user_id=hq_owner.id))
        session.commit()
    return hq_email


# ── Parser ───────────────────────────────────────────────────────────────────

_FIXTURE_HTML = r"""
<html><body><script>
var xQ={entities:[
  {id:`shop:1001`,kind:`shop`,label:`1001 Testville`,fields:[
    {label:`Shop Number`,value:`1001`,kind:`identifier`},
    {label:`Shop Name`,value:`Testville`,kind:`name`},
    {label:`Ownership`,value:`Franchised`,kind:`text`},
    {label:`Status`,value:`Open`,kind:`text`},
    {label:`Area`,value:`Test Area`,kind:`text`},
    {label:`Region`,value:`VIC`,kind:`text`},
    {label:`Phone`,value:`+61300000000`,kind:`phone`},
    {label:`Address`,value:`1 Test St, Testville, VIC, 3000`,kind:`address`}
  ]},
  {id:`shop:1002`,kind:`shop`,label:`1002 Closedtown`,fields:[
    {label:`Shop Number`,value:`1002`,kind:`identifier`},
    {label:`Shop Name`,value:`Closedtown`,kind:`name`},
    {label:`Ownership`,value:`Company-owned`,kind:`text`},
    {label:`Status`,value:`Closed`,kind:`text`}
  ]},
  {id:`franchisee:jane-tester`,kind:`franchisee`,label:`Jane Tester`,fields:[
    {label:`Franchisee`,value:`Jane Tester`,kind:`name`},
    {label:`Business Name`,value:`Tester Pty Ltd`,kind:`text`},
    {label:`Email`,value:`jane\`s.email@example.com`,kind:`email`},
    {label:`Mobile`,value:`+61400111222`,kind:`phone`}
  ]}
],relationships:[
  {from:`franchisee:jane-tester`,to:`shop:1001`,kind:`operates`}
],places:JSON.parse(`{"shop:1001":{"locality":"Testville"}}`)};
</script></body></html>
"""


def test_extract_and_build_directory_from_fixture():
    graph = extract_org_graph(_FIXTURE_HTML)
    assert len(graph["entities"]) == 3
    assert len(graph["relationships"]) == 1

    directory = build_directory(graph)
    assert len(directory.shops) == 2
    assert len(directory.franchisees) == 1

    shop = next(s for s in directory.shops if s.shop_number == "1001")
    assert shop.name == "Testville"
    assert shop.status == "Open"
    assert shop.franchisee_id == "franchisee:jane-tester"

    franchisee = directory.franchisees[0]
    # A backtick-escaped backtick inside a value round-trips correctly.
    assert franchisee.email == "jane`s.email@example.com"
    assert franchisee.shop_ids == ["shop:1001"]
    assert not franchisee.is_multi_site


def test_extract_org_graph_missing_marker_raises():
    from app.minit_directory_parser import DirectoryParseError

    try:
        extract_org_graph("<html>no data here</html>")
        assert False, "expected DirectoryParseError"
    except DirectoryParseError:
        pass


# ── Planner ──────────────────────────────────────────────────────────────────


def _shop(number, *, status="Open", ownership="Franchised", franchisee_id=None, name=None):
    return DirectoryShop(
        id=f"shop:{number}",
        shop_number=number,
        name=name or f"Shop {number}",
        ownership=ownership,
        status=status,
        area="Test Area",
        region="VIC",
        address=f"{number} Test St",
        franchisee_id=franchisee_id,
    )


def _franchisee(slug, full_name, email, shop_ids):
    f = DirectoryFranchisee(id=f"franchisee:{slug}", full_name=full_name, business_name=full_name, email=email)
    f.shop_ids = list(shop_ids)
    return f


def test_plan_dry_run_reports_counts_without_writing():
    hq_email = _fresh_hq()
    shop = _shop("2001")
    franchisee = _franchisee("solo-owner", "Solo Owner", "solo@example.com", ["shop:2001"])
    shop.franchisee_id = franchisee.id
    directory = DirectoryData(shops=[shop], franchisees=[franchisee])

    with Session(engine) as session:
        result = plan_directory_import(
            session, directory, hq_owner_email=hq_email, apply=False
        )
        assert result["dry_run"] is True
        assert result["shops"]["would_create"] == 1
        assert result["franchisees"]["single_site"] == 1
        # Nothing written.
        assert session.exec(select(Tenant).where(Tenant.shop_number == "2001")).first() is None


def test_apply_creates_single_site_owner_with_real_identity():
    hq_email = _fresh_hq()
    shop = _shop("2101")
    franchisee = _franchisee("real-owner", "Real Owner", "real.owner@example.com", ["shop:2101"])
    shop.franchisee_id = franchisee.id
    directory = DirectoryData(shops=[shop], franchisees=[franchisee])

    with Session(engine) as session:
        result = plan_directory_import(
            session, directory, hq_owner_email=hq_email, apply=True
        )
        assert result["created_tenant_count"] == 1
        assert result["created_owner_count"] == 1
        assert result["created_franchisee_parent_account_count"] == 0  # single-site: no separate parent

        tenant = session.exec(select(Tenant).where(Tenant.shop_number == "2101")).first()
        assert tenant is not None
        owner = session.exec(select(User).where(User.tenant_id == tenant.id)).first()
        assert owner.email == "real.owner@example.com"
        assert owner.full_name == "Real Owner"
        # Placeholder password is unusable — nobody can log in with it.
        assert not verify_password("password", owner.password_hash)

        membership = session.exec(
            select(ParentAccountMembership).where(ParentAccountMembership.tenant_id == tenant.id)
        ).all()
        assert len(membership) == 1  # HQ only — no separate parent account for a single-site owner


def test_apply_creates_multi_site_franchisee_own_parent_account():
    hq_email = _fresh_hq()
    franchisee = _franchisee("multi-owner", "Multi Owner", "multi.owner@example.com", ["shop:2201", "shop:2202"])
    shop_a = _shop("2201", franchisee_id=franchisee.id)
    shop_b = _shop("2202", franchisee_id=franchisee.id, name="Shop Two")
    directory = DirectoryData(shops=[shop_a, shop_b], franchisees=[franchisee])

    with Session(engine) as session:
        result = plan_directory_import(
            session, directory, hq_owner_email=hq_email, apply=True
        )
        assert result["created_tenant_count"] == 2
        assert result["created_franchisee_parent_account_count"] == 1

        own_parent = session.exec(select(ParentAccount).where(ParentAccount.owner_email == "multi.owner@example.com")).first()
        assert own_parent is not None

        tenants = session.exec(select(Tenant).where(col(Tenant.shop_number).in_(["2201", "2202"]))).all()
        assert len(tenants) == 2
        for tenant in tenants:
            memberships = session.exec(
                select(ParentAccountMembership).where(ParentAccountMembership.tenant_id == tenant.id)
            ).all()
            parent_ids = {m.parent_account_id for m in memberships}
            assert own_parent.id in parent_ids
            assert len(parent_ids) == 2  # HQ + their own


def test_apply_falls_back_to_hq_login_for_company_owned_and_missing_email():
    hq_email = _fresh_hq()
    company_shop = _shop("2301", ownership="Company-owned", franchisee_id=None)
    no_email_franchisee = _franchisee("no-email", "No Email Owner", "", ["shop:2302"])
    ghost_shop = _shop("2302", franchisee_id=no_email_franchisee.id)
    directory = DirectoryData(shops=[company_shop, ghost_shop], franchisees=[no_email_franchisee])

    with Session(engine) as session:
        result = plan_directory_import(
            session, directory, hq_owner_email=hq_email, apply=True
        )
        assert result["fallback_to_hq_login"]["company_owned_no_franchisee"] == 1
        assert result["fallback_to_hq_login"]["franchisee_missing_email"] == 1

        for number in ("2301", "2302"):
            tenant = session.exec(select(Tenant).where(Tenant.shop_number == number)).first()
            owner = session.exec(select(User).where(User.tenant_id == tenant.id)).first()
            assert owner.email == hq_email


def test_closed_shops_are_skipped():
    hq_email = _fresh_hq()
    shop = _shop("2401", status="Closed")
    directory = DirectoryData(shops=[shop], franchisees=[])

    with Session(engine) as session:
        result = plan_directory_import(
            session, directory, hq_owner_email=hq_email, apply=True
        )
        assert result["shops"]["closed_skipped"] == 1
        assert result["shops"]["would_create"] == 0
        assert session.exec(select(Tenant).where(Tenant.shop_number == "2401")).first() is None


def test_apply_never_touches_an_existing_owners_credentials():
    hq_email = _fresh_hq()
    shop = _shop("2501")
    franchisee = _franchisee("already-claimed", "Already Claimed", "claimed@example.com", ["shop:2501"])
    shop.franchisee_id = franchisee.id
    directory = DirectoryData(shops=[shop], franchisees=[franchisee])

    # Simulate a shop that's already in the system with real, already-claimed
    # credentials (e.g. via the shop-owner invite flow) under a *different* email
    # than the directory's franchisee record.
    with Session(engine) as session:
        parent = session.exec(select(ParentAccount).where(ParentAccount.owner_email == hq_email)).first()
        tenant = Tenant(name="Shop 2501", slug="minit-2501", plan_code="booking_only", shop_number="2501")
        session.add(tenant)
        session.flush()
        real_owner = User(
            tenant_id=tenant.id,
            email="the.real.franchisee@example.com",
            full_name="The Real Franchisee",
            role="owner",
            password_hash=hash_password("realSecretPass1"),
            is_active=True,
        )
        session.add(real_owner)
        session.flush()
        session.add(ParentAccountMembership(parent_account_id=parent.id, tenant_id=tenant.id, user_id=real_owner.id))
        session.commit()
        real_owner_hash = real_owner.password_hash

    with Session(engine) as session:
        result = plan_directory_import(
            session, directory, hq_owner_email=hq_email, apply=True
        )
        assert result["shops"]["already_exists"] == 1
        assert result["created_tenant_count"] == 0
        assert result["created_owner_count"] == 0

        owners = session.exec(
            select(User).where(User.tenant_id == session.exec(select(Tenant).where(Tenant.shop_number == "2501")).first().id)
        ).all()
        # Still exactly the one, unmodified real owner — the directory's
        # franchisee record was NOT used to create a second user or overwrite this one.
        assert len(owners) == 1
        assert owners[0].email == "the.real.franchisee@example.com"
        assert owners[0].password_hash == real_owner_hash


def test_apply_is_idempotent():
    hq_email = _fresh_hq()
    franchisee = _franchisee("idempotent-owner", "Idempotent Owner", "idempotent@example.com", ["shop:2601", "shop:2602"])
    shop_a = _shop("2601", franchisee_id=franchisee.id)
    shop_b = _shop("2602", franchisee_id=franchisee.id)
    directory = DirectoryData(shops=[shop_a, shop_b], franchisees=[franchisee])

    with Session(engine) as session:
        first = plan_directory_import(session, directory, hq_owner_email=hq_email, apply=True)
    with Session(engine) as session:
        second = plan_directory_import(session, directory, hq_owner_email=hq_email, apply=True)

    assert first["created_tenant_count"] == 2
    assert second["created_tenant_count"] == 0
    assert second["created_owner_count"] == 0
    assert second["created_franchisee_parent_account_count"] == 0
    assert second["shops"]["already_exists"] == 2

    with Session(engine) as session:
        own_parent = session.exec(
            select(ParentAccount).where(ParentAccount.owner_email == "idempotent@example.com")
        ).all()
        assert len(own_parent) == 1  # not duplicated on re-run
