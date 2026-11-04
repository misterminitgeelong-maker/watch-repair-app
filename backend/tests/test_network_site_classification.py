from types import SimpleNamespace
from uuid import uuid4

import pytest
from sqlmodel import Session

from app.database import engine
from app.models import ParentAccount, ParentAccountSite, Tenant
from app.network_site_classification import MINIT_PARENT_ID, display_network_role, excluded_site_reason


@pytest.mark.parametrize("number", ["0101", "01111", "3904"])
def test_exclusions_are_scoped_to_reviewed_parent(number):
    tenant = SimpleNamespace(slug="record", shop_number=number)
    assert excluded_site_reason(MINIT_PARENT_ID, tenant)
    assert excluded_site_reason(uuid4(), tenant) is None


def test_vans_are_not_retail_targets_without_changing_reporting_or_roles():
    from app.routes.parent_operations import _classify_linked_tenants, _retail_and_operator_tenants
    from app.parent_network import mobile_reporting_tenants_for_parent
    with Session(engine) as db:
        parent = ParentAccount(id=MINIT_PARENT_ID, name="Minit review", owner_email="classification@example.test")
        db.add(parent); db.flush()
        sites = []
        for slug, number in [("real-shop", "9000"), ("van", "6902"), ("excluded", "0101")]:
            tenant = Tenant(name=slug, slug=f"{slug}-{uuid4().hex}", shop_number=number, plan_code="booking_only")
            db.add(tenant); db.flush()
            site = ParentAccountSite(parent_account_id=parent.id, tenant_id=tenant.id, network_role="retail", mobile_reporting_enabled=True)
            db.add(site); sites.append((site, tenant))
        db.commit()
        shops, operators = _retail_and_operator_tenants(db, parent.id)
        assert {t.id for t in shops} == {sites[0][1].id}
        assert {t.id for t in operators} == {sites[1][1].id}
        retail, ops, _, _ = _classify_linked_tenants(db, parent.id)
        assert set(retail) == {sites[0][1].id} and set(ops) == {sites[1][1].id}
        # This change does not remove intentional reporting visibility.
        assert {t.id for t in mobile_reporting_tenants_for_parent(db, parent.id)} == {t.id for _, t in sites}
        for site, tenant in sites:
            db.refresh(site)
            assert site.network_role == "retail"
        assert display_network_role(uuid4(), sites[1][0], sites[1][1]) == "retail"
