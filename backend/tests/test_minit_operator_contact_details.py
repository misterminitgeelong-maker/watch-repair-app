"""Mobile operators carry the contact details their seed already holds.

Retail shops are provisioned from the Organisation Graph directory export, which
knows each shop's franchisee and writes ``shop_phone`` / ``shop_email`` plus a real
owner ``User``. Mobile operators come from ``minit_mobile_operators_2026.json``
instead, which holds a ``dispatch_phone`` and ``dispatch_email`` per operator — and
until this, only the dispatch phone reached the tenant. HQ therefore showed every
operator as having no contact on file while the equivalent retail shop showed one.
"""

from __future__ import annotations

import os
from pathlib import Path
from uuid import uuid4

_TEST_DB = Path(__file__).with_name(f"test_minit_operator_contact_{uuid4().hex}.db")
os.environ.setdefault("DATABASE_URL", f"sqlite:///{_TEST_DB.as_posix()}")
os.environ.setdefault("JWT_SECRET", "test-secret-not-for-production")
os.environ.setdefault("APP_ENV", "test")

from sqlmodel import Session, select

from app.database import create_db_and_tables, engine
from app.minit_mobile_operators import MobileOperatorSeed, ResolvedMobileOperator
from app.minit_provision import (
    ensure_minit_pilot_account,
    import_minit_mobile_operators,
    sync_tenant_from_mobile_operator,
)
from app.minit_shops import MinitShopRow
from app.models import Tenant

HQ_EMAIL = "minit-hq@test.mainspring.au"


def _seed_parent(session: Session) -> None:
    ensure_minit_pilot_account(
        session,
        parent_name="Mister Minit",
        hq_tenant_slug="mmsupport",
        hq_tenant_name="Mister Minit HQ",
        hq_owner_email=HQ_EMAIL,
        hq_owner_password="MinitPilot2026!",
    )


def _operator(
    shop_number: str,
    label: str,
    phone: str,
    email: str | None,
) -> ResolvedMobileOperator:
    seed = MobileOperatorSeed(
        shop_number=shop_number,
        operator_label=label,
        dispatch_phone=phone,
        dispatch_email=email,
    )
    tss = MinitShopRow(shop_number=shop_number, name=label, area="WA", region="SW")
    return ResolvedMobileOperator(
        seed=seed,
        tss=tss,
        tenant_name=f"Mobile Services {label}",
        tenant_slug=f"minit-mobile-{shop_number}",
        dispatch_phone=phone,
    )


def _tenant(session: Session, slug: str) -> Tenant:
    tenant = session.exec(select(Tenant).where(Tenant.slug == slug)).first()
    assert tenant is not None, f"tenant {slug} was not created"
    return tenant


def test_a_new_operator_gets_the_seed_contact_details():
    create_db_and_tables()
    with Session(engine) as session:
        _seed_parent(session)
        import_minit_mobile_operators(
            session,
            parent_name="Mister Minit",
            hq_owner_email=HQ_EMAIL,
            operators=[_operator("6441", "Baldivis", "0481000411", "baldivis@mmms.au")],
            apply=True,
        )

        tenant = _tenant(session, "minit-mobile-6441")
        assert tenant.mobile_dispatch_phone == "0481000411"
        assert tenant.shop_phone == "0481000411"
        assert tenant.shop_email == "baldivis@mmms.au"


def test_an_existing_operator_is_backfilled_on_reimport():
    """The 25 already provisioned in production are the ones that need this."""
    create_db_and_tables()
    with Session(engine) as session:
        _seed_parent(session)
        operator = _operator("4320", "Bribie Island", "0401001308", "bribie@mmms.au")

        import_minit_mobile_operators(
            session,
            parent_name="Mister Minit",
            hq_owner_email=HQ_EMAIL,
            operators=[operator],
            apply=True,
        )
        # Simulate a tenant provisioned before contact details were carried through.
        tenant = _tenant(session, "minit-mobile-4320")
        tenant.shop_phone = None
        tenant.shop_email = None
        session.add(tenant)
        session.commit()

        import_minit_mobile_operators(
            session,
            parent_name="Mister Minit",
            hq_owner_email=HQ_EMAIL,
            operators=[operator],
            apply=True,
        )
        session.expire_all()

        tenant = _tenant(session, "minit-mobile-4320")
        assert tenant.shop_phone == "0401001308"
        assert tenant.shop_email == "bribie@mmms.au"


def test_a_contact_already_on_the_tenant_is_never_overwritten():
    """Someone may have corrected these by hand; the seed must not clobber them."""
    tenant = Tenant(
        name="Mobile Services Noosa",
        slug="minit-mobile-4499",
        shop_number="4499",
        shop_phone="0400111222",
        shop_email="corrected@example.com",
    )
    operator = _operator("4499", "Noosa", "0455000000", "seed@mmms.au")

    sync_tenant_from_mobile_operator(tenant, operator)

    assert tenant.shop_phone == "0400111222"
    assert tenant.shop_email == "corrected@example.com"
    # The dispatch number is routing config, not a display contact — seed wins there.
    assert tenant.mobile_dispatch_phone == "0455000000"


def test_an_operator_with_no_seed_email_still_gets_its_phone():
    """The four pending operators have a phone but no email on file yet."""
    tenant = Tenant(name="Mobile Services Chadstone", slug="minit-mobile-3904", shop_number="3904")
    operator = _operator("3904", "Chadstone", "0411222333", None)

    sync_tenant_from_mobile_operator(tenant, operator)

    assert tenant.shop_phone == "0411222333"
    assert tenant.shop_email is None


def test_sync_reports_no_change_once_contacts_are_filled():
    """Guards the idempotency the importer's skip/update counts depend on."""
    operator = _operator("2243", "Burwood", "0477738814", "burwood@mmms.au")
    tenant = Tenant(
        name="Mobile Services Burwood",
        slug="minit-mobile-2243",
        shop_number="2243",
        minit_area="WA",
        minit_region="SW",
        business_address="Burwood · WA · SW",
        mobile_dispatch_phone="0477738814",
    )

    assert sync_tenant_from_mobile_operator(tenant, operator) is True
    assert sync_tenant_from_mobile_operator(tenant, operator) is False
