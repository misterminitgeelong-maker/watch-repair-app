import io
import os
from pathlib import Path
from uuid import uuid4

from fastapi.testclient import TestClient

_TEST_DB = Path(__file__).with_name(f"test_list_querying_{uuid4().hex}.db")
os.environ["DATABASE_URL"] = f"sqlite:///{_TEST_DB.as_posix()}"
os.environ.setdefault("JWT_SECRET", "test-secret-not-for-production")
os.environ.setdefault("APP_ENV", "test")

from app.database import create_db_and_tables
from app.main import app

create_db_and_tables()
client = TestClient(app)


def _bootstrap_and_login(tenant_slug: str, email: str, password: str) -> str:
    bootstrap = client.post(
        "/v1/auth/bootstrap",
        json={
            "tenant_name": f"Tenant {tenant_slug}",
            "tenant_slug": tenant_slug,
            "owner_email": email,
            "owner_full_name": "Owner",
            "owner_password": password,
        },
    )
    assert bootstrap.status_code == 200
    login = client.post(
        "/v1/auth/login",
        json={"tenant_slug": tenant_slug, "email": email, "password": password},
    )
    assert login.status_code == 200
    return login.json()["access_token"]


def _seed_job_quote_attachment(headers: dict[str, str], customer_name: str, brand: str, status: str) -> dict:
    customer = client.post(
        "/v1/customers",
        headers=headers,
        json={"full_name": customer_name, "email": f"{customer_name.lower().replace(' ', '')}@example.com"},
    )
    assert customer.status_code == 201
    watch = client.post(
        "/v1/watches",
        headers=headers,
        json={"customer_id": customer.json()["id"], "brand": brand, "model": "M"},
    )
    assert watch.status_code == 201
    job = client.post(
        "/v1/repair-jobs",
        headers=headers,
        json={"watch_id": watch.json()["id"], "title": f"{brand} job", "priority": "normal"},
    )
    assert job.status_code == 201
    if status != "awaiting_go_ahead":
        moved = client.post(
            f"/v1/repair-jobs/{job.json()['id']}/status",
            headers=headers,
            json={"status": status},
        )
        assert moved.status_code == 200
    quote = client.post(
        "/v1/quotes",
        headers=headers,
        json={
            "repair_job_id": job.json()["id"],
            "tax_cents": 0,
            "line_items": [{"item_type": "labor", "description": "svc", "quantity": 1, "unit_price_cents": 100}],
        },
    )
    assert quote.status_code == 201
    attachment = client.post(
        "/v1/attachments",
        headers=headers,
        params={"repair_job_id": job.json()["id"]},
        files={"file": (f"{brand}.txt", io.BytesIO(b"data"), "text/plain")},
    )
    assert attachment.status_code == 201
    return {
        "customer": customer.json(),
        "watch": watch.json(),
        "job": job.json() if status == "awaiting_go_ahead" else moved.json(),
        "quote": quote.json(),
        "attachment": attachment.json(),
    }


def test_customers_pagination_and_sort():
    token = _bootstrap_and_login("list-a", "lista@example.com", "Admin123!")
    headers = {"Authorization": f"Bearer {token}"}

    for name in ["Charlie", "Alice", "Bob"]:
        res = client.post("/v1/customers", headers=headers, json={"full_name": name})
        assert res.status_code == 201

    res = client.get("/v1/customers", headers=headers, params={"sort_by": "full_name", "sort_dir": "asc", "limit": 2, "offset": 0})
    assert res.status_code == 200
    assert [c["full_name"] for c in res.json()] == ["Alice", "Bob"]

    res2 = client.get("/v1/customers", headers=headers, params={"sort_by": "full_name", "sort_dir": "asc", "limit": 2, "offset": 2})
    assert res2.status_code == 200
    assert [c["full_name"] for c in res2.json()] == ["Charlie"]


def test_repair_jobs_quotes_watches_attachments_filter_sort_and_pagination():
    token = _bootstrap_and_login("list-b", "listb@example.com", "Admin123!")
    headers = {"Authorization": f"Bearer {token}"}
    a = _seed_job_quote_attachment(headers, "Cust A", "Rolex", "working_on")
    b = _seed_job_quote_attachment(headers, "Cust B", "Omega", "awaiting_go_ahead")

    jobs = client.get(
        "/v1/repair-jobs",
        headers=headers,
        params={"status": "working_on", "sort_by": "job_number", "sort_dir": "asc", "limit": 10, "offset": 0},
    )
    assert jobs.status_code == 200
    assert len(jobs.json()) == 1
    assert jobs.json()[0]["id"] == a["job"]["id"]

    quotes = client.get(
        "/v1/quotes",
        headers=headers,
        params={"repair_job_id": b["job"]["id"], "sort_by": "created_at", "sort_dir": "desc", "limit": 10, "offset": 0},
    )
    assert quotes.status_code == 200
    assert len(quotes.json()) == 1
    assert quotes.json()[0]["repair_job_id"] == b["job"]["id"]

    watches = client.get(
        "/v1/watches",
        headers=headers,
        params={"brand": "Rolex", "sort_by": "brand", "sort_dir": "asc", "limit": 10, "offset": 0},
    )
    assert watches.status_code == 200
    assert len(watches.json()) == 1
    assert watches.json()[0]["brand"] == "Rolex"

    attachments = client.get(
        "/v1/attachments",
        headers=headers,
        params={"repair_job_id": a["job"]["id"], "sort_by": "file_name", "sort_dir": "asc", "limit": 10, "offset": 0},
    )
    assert attachments.status_code == 200
    assert len(attachments.json()) == 1
    assert attachments.json()[0]["repair_job_id"] == a["job"]["id"]


def test_tenant_isolation_for_list_endpoints():
    token_a = _bootstrap_and_login("list-c1", "listc1@example.com", "Admin123!")
    headers_a = {"Authorization": f"Bearer {token_a}"}
    data_a = _seed_job_quote_attachment(headers_a, "Tenant A Customer", "Seiko", "awaiting_go_ahead")

    token_b = _bootstrap_and_login("list-c2", "listc2@example.com", "Admin123!")
    headers_b = {"Authorization": f"Bearer {token_b}"}
    _seed_job_quote_attachment(headers_b, "Tenant B Customer", "Tissot", "awaiting_go_ahead")

    customers_b = client.get("/v1/customers", headers=headers_b)
    assert customers_b.status_code == 200
    assert all(c["id"] != data_a["customer"]["id"] for c in customers_b.json())

    watches_b = client.get("/v1/watches", headers=headers_b)
    assert watches_b.status_code == 200
    assert all(w["id"] != data_a["watch"]["id"] for w in watches_b.json())

    jobs_b = client.get("/v1/repair-jobs", headers=headers_b)
    assert jobs_b.status_code == 200
    assert all(j["id"] != data_a["job"]["id"] for j in jobs_b.json())

    quotes_b = client.get("/v1/quotes", headers=headers_b)
    assert quotes_b.status_code == 200
    assert all(q["id"] != data_a["quote"]["id"] for q in quotes_b.json())

    attachments_b = client.get("/v1/attachments", headers=headers_b)
    assert attachments_b.status_code == 200
    assert all(a["id"] != data_a["attachment"]["id"] for a in attachments_b.json())
