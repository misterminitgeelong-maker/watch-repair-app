import os
from pathlib import Path
from uuid import uuid4

_TEST_DB = Path(__file__).with_name(f"test_ms_pricing_{uuid4().hex}.db")
os.environ["DATABASE_URL"] = f"sqlite:///{_TEST_DB.as_posix()}"

from fastapi.testclient import TestClient
from sqlmodel import Session

from app.database import create_db_and_tables, engine
from app.main import app
from app.models import GarageServicingPricing, OemKeyPricing, ServicePricing

create_db_and_tables()
client = TestClient(app)


def _bootstrap_and_login(tenant_slug: str, email: str, password: str) -> str:
    bootstrap_payload = {
        "tenant_name": f"Tenant {tenant_slug}",
        "tenant_slug": tenant_slug,
        "owner_email": email,
        "owner_full_name": "Owner",
        "owner_password": password,
        "plan_code": "enterprise",
    }
    assert client.post("/v1/auth/bootstrap", json=bootstrap_payload).status_code == 200
    login_res = client.post(
        "/v1/auth/login",
        json={"tenant_slug": tenant_slug, "email": email, "password": password},
    )
    assert login_res.status_code == 200
    return login_res.json()["access_token"]


def _seed_pricing():
    with Session(engine) as session:
        oem = OemKeyPricing(
            make="Toyota",
            model_variant="Hilux",
            job_type="Add Key",
            key_type="Smart",
            service_location="Mobile",
            tool_required="VVDI",
            retail_price=250.0,
            callout_inclusive=True,
            notes="Includes programming",
            active=True,
        )
        oem_poa = OemKeyPricing(
            make="Toyota",
            model_variant="LandCruiser",
            job_type="AKL",
            key_type="Smart",
            service_location="Mobile",
            tool_required="Dealer",
            retail_price=None,
            callout_inclusive=False,
            notes="Dealer only",
            active=True,
        )
        svc = ServicePricing(
            category="Locksmith",
            service_name="Lock change",
            unit="each",
            retail_price=120.0,
            callout_inclusive=False,
            active=True,
        )
        garage = GarageServicingPricing(
            service_name="Spring replacement",
            description="Replace torsion spring",
            part_cost_notes="Spring kit ~$80",
            labour_time="2h",
            retail_price=350.0,
            callout_inclusive=True,
            active=True,
        )
        session.add_all([oem, oem_poa, svc, garage])
        session.commit()
        return oem.id, oem_poa.id, svc.id, garage.id


def test_mobile_services_pricing_endpoints():
    suffix = uuid4().hex[:8]
    token = _bootstrap_and_login(
        tenant_slug=f"ms-pricing-{suffix}",
        email=f"owner-{suffix}@pricing.test",
        password="pass123456",
    )
    headers = {"Authorization": f"Bearer {token}"}
    oem_id, oem_poa_id, svc_id, garage_id = _seed_pricing()

    makes = client.get("/v1/mobile-services-pricing/oem-makes", headers=headers)
    assert makes.status_code == 200
    assert makes.json() == ["Toyota"]

    keys = client.get(
        "/v1/mobile-services-pricing/oem-keys",
        params={"make": "toyota"},
        headers=headers,
    )
    assert keys.status_code == 200
    key_rows = keys.json()
    assert len(key_rows) == 2
    assert key_rows[0]["job_type"] == "Add Key"
    assert key_rows[0]["is_poa"] is False
    assert key_rows[0]["retail_price"] == 250.0
    assert key_rows[1]["job_type"] == "AKL"
    assert key_rows[1]["is_poa"] is True

    services = client.get("/v1/mobile-services-pricing/services", headers=headers)
    assert services.status_code == 200
    assert services.json()[0]["id"] == str(svc_id)

    garage = client.get("/v1/mobile-services-pricing/garage", headers=headers)
    assert garage.status_code == 200
    assert garage.json()[0]["id"] == str(garage_id)
    assert garage.json()[0]["retail_price"] == 350.0


def test_auto_key_job_stores_pricing_fields():
    suffix = uuid4().hex[:8]
    token = _bootstrap_and_login(
        tenant_slug=f"ms-job-{suffix}",
        email=f"owner-{suffix}@job.test",
        password="pass123456",
    )
    headers = {"Authorization": f"Bearer {token}"}
    oem_id, _, _, _ = _seed_pricing()

    cust = client.post(
        "/v1/customers",
        headers=headers,
        json={"full_name": "Pricing Customer", "phone": "0400111222"},
    )
    assert cust.status_code == 201
    customer_id = cust.json()["id"]

    job_res = client.post(
        "/v1/auto-key-jobs",
        headers=headers,
        json={
            "customer_id": customer_id,
            "title": "Toyota Hilux key",
            "key_quantity": 1,
            "priority": "normal",
            "status": "awaiting_quote",
            "programming_status": "not_required",
            "deposit_cents": 0,
            "cost_cents": 0,
            "pricing_ref_id": str(oem_id),
            "pricing_type": "oem_key",
            "quoted_price": 250.0,
            "callout_inclusive": True,
        },
    )
    assert job_res.status_code == 201
    body = job_res.json()
    assert body["pricing_ref_id"] == str(oem_id)
    assert body["pricing_type"] == "oem_key"
    assert body["quoted_price"] == 250.0
    assert body["callout_inclusive"] is True
    assert body["cost_cents"] == 25000


def test_pricing_meta_endpoint():
    suffix = uuid4().hex[:8]
    token = _bootstrap_and_login(
        tenant_slug=f"ms-meta-{suffix}",
        email=f"owner-{suffix}@meta.test",
        password="pass123456",
    )
    headers = {"Authorization": f"Bearer {token}"}
    _seed_pricing()

    meta = client.get("/v1/mobile-services-pricing/meta", headers=headers)
    assert meta.status_code == 200
    body = meta.json()
    assert body["oem_row_count"] >= 2
    assert body["oem_make_count"] >= 1
    assert body["service_row_count"] >= 1
    assert body["garage_row_count"] >= 1
