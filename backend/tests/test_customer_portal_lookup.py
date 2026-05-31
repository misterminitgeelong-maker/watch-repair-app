"""Customer portal email lookup — cross-tenant shop grouping."""

from uuid import UUID, uuid4

import pytest
from fastapi.testclient import TestClient
from sqlmodel import Session, select

from app.database import engine
from app.models import AutoKeyJob, RepairJob, ShoeRepairJob, Tenant


def _bootstrap(
    client: TestClient,
    slug: str | None = None,
    owner_email: str | None = None,
    *,
    plan_code: str = "enterprise",
    tenant_name: str | None = None,
) -> dict[str, str]:
    suffix = uuid4().hex[:8]
    slug = slug or f"portal-{suffix}"
    owner_email = owner_email or f"owner-{suffix}@portal.test"
    res = client.post(
        "/v1/auth/bootstrap",
        json={
            "tenant_name": tenant_name or f"Shop {slug}",
            "tenant_slug": slug,
            "owner_email": owner_email,
            "owner_full_name": "Portal Owner",
            "owner_password": "pass123456",
            "plan_code": plan_code,
        },
    )
    assert res.status_code == 200, res.text
    login = client.post(
        "/v1/auth/login",
        json={"tenant_slug": slug, "email": owner_email, "password": "pass123456"},
    )
    assert login.status_code == 200, login.text
    token = login.json()["access_token"]
    return {"Authorization": f"Bearer {token}", "tenant_slug": slug}


def _create_watch_job(client: TestClient, headers: dict[str, str], email: str, title: str) -> RepairJob:
    customer = client.post(
        "/v1/customers",
        headers=headers,
        json={"full_name": "Portal Customer", "email": email},
    )
    assert customer.status_code == 201, customer.text
    watch = client.post(
        "/v1/watches",
        headers=headers,
        json={"customer_id": customer.json()["id"], "brand": "Rolex", "model": "Sub"},
    )
    assert watch.status_code == 201, watch.text
    job = client.post(
        "/v1/repair-jobs",
        headers=headers,
        json={"watch_id": watch.json()["id"], "title": title, "priority": "normal"},
    )
    assert job.status_code == 201, job.text
    with Session(engine) as session:
        return session.get(RepairJob, UUID(job.json()["id"]))


_SHOE_ITEM = {
    "catalogue_key": "soles__half_sole_leather",
    "catalogue_group": "soles",
    "item_name": "Half sole leather",
    "pricing_type": "fixed",
    "quantity": 1,
    "unit_price_cents": 5000,
}


def _create_shoe_job(client: TestClient, headers: dict[str, str], email: str, title: str) -> ShoeRepairJob:
    customer = client.post(
        "/v1/customers",
        headers=headers,
        json={"full_name": "Shoe Customer", "email": email},
    )
    assert customer.status_code == 201, customer.text
    shoe = client.post(
        "/v1/shoe-repair-jobs/shoes",
        headers=headers,
        json={"customer_id": customer.json()["id"], "shoe_type": "Boot", "brand": "RM"},
    )
    assert shoe.status_code == 201, shoe.text
    job = client.post(
        "/v1/shoe-repair-jobs",
        headers=headers,
        json={
            "shoe_id": shoe.json()["id"],
            "title": title,
            "priority": "normal",
            "items": [{**_SHOE_ITEM, "description": "Sole repair"}],
        },
    )
    assert job.status_code == 201, job.text
    with Session(engine) as session:
        return session.get(ShoeRepairJob, UUID(job.json()["id"]))


def _create_auto_key_job(client: TestClient, headers: dict[str, str], email: str, title: str) -> AutoKeyJob:
    customer = client.post(
        "/v1/customers",
        headers=headers,
        json={"full_name": "Auto Key Customer", "email": email},
    )
    assert customer.status_code == 201, customer.text
    job = client.post(
        "/v1/auto-key-jobs",
        headers=headers,
        json={
            "customer_id": customer.json()["id"],
            "title": title,
            "vehicle_make": "Toyota",
            "vehicle_model": "Camry",
        },
    )
    assert job.status_code == 201, job.text
    with Session(engine) as session:
        return session.get(AutoKeyJob, UUID(job.json()["id"]))


def test_customer_lookup_groups_jobs_by_shop(client: TestClient):
    email = f"multi-{uuid4().hex[:8]}@portal.test"
    headers_a = _bootstrap(client, tenant_name="Alpha Watches")
    headers_b = _bootstrap(client, tenant_name="Beta Shoes")

    _create_watch_job(client, headers_a, email, "Watch service")
    _create_shoe_job(client, headers_b, email, "Boot resole")

    res = client.post("/v1/public/customer-lookup", json={"email": email})
    assert res.status_code == 200, res.text
    body = res.json()
    assert body["email"] == email
    assert "jobs" not in body
    assert len(body["shops"]) == 2
    shop_names = {s["shop_name"] for s in body["shops"]}
    assert "Alpha Watches" in shop_names
    assert "Beta Shoes" in shop_names

    types_by_shop = {s["shop_name"]: {j["type"] for j in s["jobs"]} for s in body["shops"]}
    assert types_by_shop["Alpha Watches"] == {"watch"}
    assert types_by_shop["Beta Shoes"] == {"shoe"}


def test_customer_lookup_includes_auto_key_jobs(client: TestClient):
    email = f"auto-{uuid4().hex[:8]}@portal.test"
    headers = _bootstrap(client, tenant_name="Mobile Keys Co")
    ak_job = _create_auto_key_job(client, headers, email, "Spare key")

    res = client.post("/v1/public/customer-lookup", json={"email": email})
    assert res.status_code == 200, res.text
    jobs = res.json()["shops"][0]["jobs"]
    assert len(jobs) == 1
    assert jobs[0]["type"] == "auto_key"
    assert jobs[0]["job_number"] == ak_job.job_number
    assert jobs[0]["status_url"].startswith("/customer-portal/job/auto_key/")


def test_customer_lookup_merges_duplicate_customers_same_shop(client: TestClient):
    email = f"dup-{uuid4().hex[:8]}@portal.test"
    headers = _bootstrap(client)

    _create_watch_job(client, headers, email, "Job one")
    _create_watch_job(client, headers, email, "Job two")

    res = client.post("/v1/public/customer-lookup", json={"email": email})
    assert res.status_code == 200, res.text
    assert len(res.json()["shops"]) == 1
    assert len(res.json()["shops"][0]["jobs"]) == 2


def test_customer_lookup_excludes_history_by_default(client: TestClient):
    email = f"hist-{uuid4().hex[:8]}@portal.test"
    headers = _bootstrap(client)
    watch_job = _create_watch_job(client, headers, email, "Collected watch")
    shoe_job = _create_shoe_job(client, headers, email, "Collected shoe")

    with Session(engine) as session:
        w = session.get(RepairJob, watch_job.id)
        assert w is not None
        w.status = "collected"
        session.add(w)
        s = session.get(ShoeRepairJob, shoe_job.id)
        assert s is not None
        s.status = "collected"
        session.add(s)
        session.commit()

    active = client.post("/v1/public/customer-lookup", json={"email": email})
    assert active.status_code == 200
    assert active.json()["shops"] == []

    history = client.post(
        "/v1/public/customer-lookup",
        json={"email": email, "include_history": True},
    )
    assert history.status_code == 200
    jobs = history.json()["shops"][0]["jobs"]
    assert len(jobs) == 2
    assert {j["status"] for j in jobs} == {"collected"}


def test_portal_session_returns_grouped_jobs(client: TestClient):
    email = f"session-{uuid4().hex[:8]}@portal.test"
    headers = _bootstrap(client)
    _create_watch_job(client, headers, email, "Session watch")

    session_res = client.post("/v1/public/portal/create-session", json={"email": email})
    assert session_res.status_code == 200, session_res.text
    token = session_res.json()["session_token"]

    jobs_res = client.get(f"/v1/public/portal/session/{token}")
    assert jobs_res.status_code == 200, jobs_res.text
    body = jobs_res.json()
    assert body["email"] == email
    assert len(body["shops"]) == 1
    assert body["shops"][0]["jobs"][0]["type"] == "watch"


def test_portal_session_include_history_query_param(client: TestClient):
    email = f"session-h-{uuid4().hex[:8]}@portal.test"
    headers = _bootstrap(client)
    ak_job = _create_auto_key_job(client, headers, email, "Done key job")

    with Session(engine) as session:
        row = session.get(AutoKeyJob, ak_job.id)
        assert row is not None
        row.status = "invoice_paid"
        session.add(row)
        session.commit()

    token = client.post("/v1/public/portal/create-session", json={"email": email}).json()["session_token"]

    active = client.get(f"/v1/public/portal/session/{token}")
    assert active.json()["shops"] == []

    history = client.get(f"/v1/public/portal/session/{token}?include_history=true")
    assert len(history.json()["shops"][0]["jobs"]) == 1
    assert history.json()["shops"][0]["jobs"][0]["status"] == "invoice_paid"


def test_customer_lookup_includes_tenant_branding(client: TestClient):
    email = f"brand-{uuid4().hex[:8]}@portal.test"
    headers = _bootstrap(client, tenant_name="Branded Shop")
    _create_watch_job(client, headers, email, "Branded job")

    with Session(engine) as session:
        tenant = session.exec(
            select(Tenant).where(Tenant.slug == headers["tenant_slug"])
        ).first()
        assert tenant is not None
        tenant.logo_url = "https://cdn.example/logo.png"
        tenant.brand_color = "#1F6D4C"
        session.add(tenant)
        session.commit()

    shop = client.post("/v1/public/customer-lookup", json={"email": email}).json()["shops"][0]
    assert shop["logo_url"] == "https://cdn.example/logo.png"
    assert shop["brand_color"] == "#1F6D4C"
