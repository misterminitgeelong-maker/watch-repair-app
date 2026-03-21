import os
from pathlib import Path
from uuid import uuid4

# Use a fresh sqlite file for every test run so schema changes are always applied.
_TEST_DB = Path(__file__).with_name(f"test_{uuid4().hex}.db")
os.environ["DATABASE_URL"] = f"sqlite:///{_TEST_DB.as_posix()}"
os.environ.setdefault("JWT_SECRET", "test-secret-not-for-production")
os.environ.setdefault("APP_ENV", "test")

from fastapi.testclient import TestClient

from app.database import create_db_and_tables
from app.main import app

create_db_and_tables()
client = TestClient(app)


def _bootstrap_and_login(tenant_slug: str, email: str, password: str) -> str:
    bootstrap_payload = {
        "tenant_name": f"Tenant {tenant_slug}",
        "tenant_slug": tenant_slug,
        "owner_email": email,
        "owner_full_name": "Main Owner",
        "owner_password": password,
    }
    bootstrap_res = client.post("/v1/auth/bootstrap", json=bootstrap_payload)
    assert bootstrap_res.status_code == 200

    login_payload = {
        "tenant_slug": tenant_slug,
        "email": email,
        "password": password,
    }
    login_res = client.post("/v1/auth/login", json=login_payload)
    assert login_res.status_code == 200
    return login_res.json()["access_token"]


def _create_customer(headers: dict[str, str]) -> str:
    create_customer_res = client.post(
        "/v1/customers",
        headers=headers,
        json={"full_name": "Alice Watch Owner", "email": "alice@example.com"},
    )
    assert create_customer_res.status_code == 201
    return create_customer_res.json()["id"]


def _create_watch(headers: dict[str, str], customer_id: str) -> str:
    create_watch_res = client.post(
        "/v1/watches",
        headers=headers,
        json={"customer_id": customer_id, "brand": "Omega", "model": "Seamaster"},
    )
    assert create_watch_res.status_code == 201
    return create_watch_res.json()["id"]


def test_health():
    response = client.get("/v1/health")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"


def test_bootstrap_and_login_flow():
    suffix = uuid4().hex[:8]
    token = _bootstrap_and_login(
        tenant_slug=f"timekeepers-{suffix}",
        email=f"owner-{suffix}@timekeepers.test",
        password="supersecret123",
    )
    assert token


def test_customer_and_watch_tenant_isolation():
    suffix_a = uuid4().hex[:8]
    suffix_b = uuid4().hex[:8]

    token_a = _bootstrap_and_login(
        tenant_slug=f"alpha-{suffix_a}",
        email=f"owner-{suffix_a}@alpha.test",
        password="pass123456",
    )
    token_b = _bootstrap_and_login(
        tenant_slug=f"beta-{suffix_b}",
        email=f"owner-{suffix_b}@beta.test",
        password="pass123456",
    )

    headers_a = {"Authorization": f"Bearer {token_a}"}
    headers_b = {"Authorization": f"Bearer {token_b}"}

    customer_id = _create_customer(headers_a)

    list_a = client.get("/v1/customers", headers=headers_a)
    list_b = client.get("/v1/customers", headers=headers_b)
    assert list_a.status_code == 200
    assert list_b.status_code == 200
    assert len(list_a.json()) == 1
    assert len(list_b.json()) == 0

    forbidden_get = client.get(f"/v1/customers/{customer_id}", headers=headers_b)
    assert forbidden_get.status_code == 404

    _create_watch(headers_a, customer_id)

    watches_a = client.get("/v1/watches", headers=headers_a)
    watches_b = client.get("/v1/watches", headers=headers_b)
    assert len(watches_a.json()) == 1
    assert len(watches_b.json()) == 0

    # watch-brands: tenant A has Omega from the watch we created; tenant B has no DB brands
    brands_a = client.get("/v1/watch-brands", headers=headers_a)
    brands_b = client.get("/v1/watch-brands", headers=headers_b)
    assert brands_a.status_code == 200
    assert brands_b.status_code == 200
    assert "Omega" in brands_a.json()
    assert "Omega" in brands_b.json()  # COMMON_WATCH_BRANDS includes Omega
    # Create watch with unique brand for tenant A
    client.post(
        "/v1/watches",
        headers=headers_a,
        json={"customer_id": customer_id, "brand": "UniqueBrandForTestOnly", "model": "Test"},
    )
    brands_a2 = client.get("/v1/watch-brands", headers=headers_a)
    brands_b2 = client.get("/v1/watch-brands", headers=headers_b)
    assert "UniqueBrandForTestOnly" in brands_a2.json()
    assert "UniqueBrandForTestOnly" not in brands_b2.json()


def test_repair_jobs_and_status_history_tenant_isolation():
    suffix_a = uuid4().hex[:8]
    suffix_b = uuid4().hex[:8]

    token_a = _bootstrap_and_login(
        tenant_slug=f"jobs-alpha-{suffix_a}",
        email=f"owner-{suffix_a}@alpha.test",
        password="pass123456",
    )
    token_b = _bootstrap_and_login(
        tenant_slug=f"jobs-beta-{suffix_b}",
        email=f"owner-{suffix_b}@beta.test",
        password="pass123456",
    )

    headers_a = {"Authorization": f"Bearer {token_a}"}
    headers_b = {"Authorization": f"Bearer {token_b}"}

    customer_id = _create_customer(headers_a)
    watch_id = _create_watch(headers_a, customer_id)

    create_job_res = client.post(
        "/v1/repair-jobs",
        headers=headers_a,
        json={"watch_id": watch_id, "title": "Full service", "priority": "high"},
    )
    assert create_job_res.status_code == 201
    job_id = create_job_res.json()["id"]
    assert create_job_res.json()["status"] == "awaiting_go_ahead"

    list_a = client.get("/v1/repair-jobs", headers=headers_a)
    list_b = client.get("/v1/repair-jobs", headers=headers_b)
    assert len(list_a.json()) == 1
    assert len(list_b.json()) == 0

    denied_get = client.get(f"/v1/repair-jobs/{job_id}", headers=headers_b)
    assert denied_get.status_code == 404

    status_update = client.post(
        f"/v1/repair-jobs/{job_id}/status",
        headers=headers_a,
        json={"status": "working_on", "note": "Opened caseback and inspected movement"},
    )
    assert status_update.status_code == 200
    assert status_update.json()["status"] == "working_on"

    history = client.get(f"/v1/repair-jobs/{job_id}/status-history", headers=headers_a)
    assert history.status_code == 200
    assert len(history.json()) == 2

    denied_status_change = client.post(
        f"/v1/repair-jobs/{job_id}/status",
        headers=headers_b,
        json={"status": "completed", "note": "should fail"},
    )
    assert denied_status_change.status_code == 404


def test_quotes_tenant_isolation():
    suffix_a = uuid4().hex[:8]
    suffix_b = uuid4().hex[:8]
    token_a = _bootstrap_and_login(
        tenant_slug=f"quote-a-{suffix_a}",
        email=f"owner-{suffix_a}@a.test",
        password="pass123456",
    )
    token_b = _bootstrap_and_login(
        tenant_slug=f"quote-b-{suffix_b}",
        email=f"owner-{suffix_b}@b.test",
        password="pass123456",
    )
    headers_a = {"Authorization": f"Bearer {token_a}"}
    headers_b = {"Authorization": f"Bearer {token_b}"}
    customer_id = _create_customer(headers_a)
    watch_id = _create_watch(headers_a, customer_id)
    job_res = client.post(
        "/v1/repair-jobs",
        headers=headers_a,
        json={"watch_id": watch_id, "title": "Quote isolation", "priority": "normal"},
    )
    assert job_res.status_code == 201
    job_id = job_res.json()["id"]
    quote_res = client.post(
        "/v1/quotes",
        headers=headers_a,
        json={
            "repair_job_id": job_id,
            "tax_cents": 0,
            "line_items": [{"item_type": "labor", "description": "Service", "quantity": 1, "unit_price_cents": 10000}],
        },
    )
    assert quote_res.status_code == 201
    quote_id = quote_res.json()["id"]
    list_b = client.get("/v1/quotes", headers=headers_b)
    assert list_b.status_code == 200
    assert len(list_b.json()) == 0
    get_b = client.get(f"/v1/quotes/{quote_id}/line-items", headers=headers_b)
    assert get_b.status_code == 404


def test_quote_totals_and_public_decision_flow():
    suffix = uuid4().hex[:8]
    token = _bootstrap_and_login(
        tenant_slug=f"quotes-{suffix}",
        email=f"owner-{suffix}@quotes.test",
        password="pass123456",
    )
    headers = {"Authorization": f"Bearer {token}"}

    customer_id = _create_customer(headers)
    watch_id = _create_watch(headers, customer_id)

    job_res = client.post(
        "/v1/repair-jobs",
        headers=headers,
        json={"watch_id": watch_id, "title": "Estimate service", "priority": "normal"},
    )
    assert job_res.status_code == 201
    job_id = job_res.json()["id"]

    quote_res = client.post(
        "/v1/quotes",
        headers=headers,
        json={
            "repair_job_id": job_id,
            "tax_cents": 500,
            "line_items": [
                {"item_type": "labor", "description": "Full service", "quantity": 1, "unit_price_cents": 25000},
                {"item_type": "part", "description": "Gasket", "quantity": 2, "unit_price_cents": 1200},
            ],
        },
    )
    assert quote_res.status_code == 201
    body = quote_res.json()
    assert body["subtotal_cents"] == 27400
    assert body["total_cents"] == 27900

    send_res = client.post(f"/v1/quotes/{body['id']}/send", headers=headers)
    assert send_res.status_code == 200
    approval_token = send_res.json()["approval_token"]

    decision_res = client.post(
        f"/v1/public/quotes/{approval_token}/decision",
        json={"decision": "approved"},
    )
    assert decision_res.status_code == 200
    assert decision_res.json()["status"] == "approved"

    replay_res = client.post(
        f"/v1/public/quotes/{approval_token}/decision",
        json={"decision": "declined"},
    )
    assert replay_res.status_code == 409


def test_invoices_tenant_isolation():
    suffix_a = uuid4().hex[:8]
    suffix_b = uuid4().hex[:8]
    token_a = _bootstrap_and_login(
        tenant_slug=f"inv-a-{suffix_a}",
        email=f"owner-{suffix_a}@a.test",
        password="pass123456",
    )
    token_b = _bootstrap_and_login(
        tenant_slug=f"inv-b-{suffix_b}",
        email=f"owner-{suffix_b}@b.test",
        password="pass123456",
    )
    headers_a = {"Authorization": f"Bearer {token_a}"}
    headers_b = {"Authorization": f"Bearer {token_b}"}
    customer_id = _create_customer(headers_a)
    watch_id = _create_watch(headers_a, customer_id)
    job_res = client.post(
        "/v1/repair-jobs",
        headers=headers_a,
        json={"watch_id": watch_id, "title": "Invoice isolation", "priority": "normal"},
    )
    assert job_res.status_code == 201
    job_id = job_res.json()["id"]
    quote_res = client.post(
        "/v1/quotes",
        headers=headers_a,
        json={
            "repair_job_id": job_id,
            "tax_cents": 0,
            "line_items": [{"item_type": "labor", "description": "Service", "quantity": 1, "unit_price_cents": 10000}],
        },
    )
    assert quote_res.status_code == 201
    quote_id = quote_res.json()["id"]
    send_res = client.post(f"/v1/quotes/{quote_id}/send", headers=headers_a)
    assert send_res.status_code == 200
    approval_token = send_res.json()["approval_token"]
    decision_res = client.post(
        f"/v1/public/quotes/{approval_token}/decision",
        json={"decision": "approved"},
    )
    assert decision_res.status_code == 200
    inv_res = client.post(
        f"/v1/invoices/from-quote/{quote_id}",
        headers=headers_a,
    )
    assert inv_res.status_code == 201
    invoice_id = inv_res.json()["invoice"]["id"]
    get_b = client.get(f"/v1/invoices/{invoice_id}", headers=headers_b)
    assert get_b.status_code == 404


def test_invoice_from_approved_quote_and_payment_flow():
    suffix = uuid4().hex[:8]
    token = _bootstrap_and_login(
        tenant_slug=f"billing-{suffix}",
        email=f"owner-{suffix}@billing.test",
        password="pass123456",
    )
    headers = {"Authorization": f"Bearer {token}"}

    customer_id = _create_customer(headers)
    watch_id = _create_watch(headers, customer_id)

    job_res = client.post(
        "/v1/repair-jobs",
        headers=headers,
        json={"watch_id": watch_id, "title": "Billing flow", "priority": "normal"},
    )
    assert job_res.status_code == 201

    quote_res = client.post(
        "/v1/quotes",
        headers=headers,
        json={
            "repair_job_id": job_res.json()["id"],
            "tax_cents": 300,
            "line_items": [
                {"item_type": "labor", "description": "Service", "quantity": 1, "unit_price_cents": 10000},
            ],
        },
    )
    assert quote_res.status_code == 201
    quote_id = quote_res.json()["id"]

    send_res = client.post(f"/v1/quotes/{quote_id}/send", headers=headers)
    assert send_res.status_code == 200
    approval_token = send_res.json()["approval_token"]

    approve_res = client.post(
        f"/v1/public/quotes/{approval_token}/decision",
        json={"decision": "approved"},
    )
    assert approve_res.status_code == 200

    invoice_res = client.post(f"/v1/invoices/from-quote/{quote_id}", headers=headers)
    assert invoice_res.status_code == 201
    invoice = invoice_res.json()["invoice"]
    assert invoice["status"] == "unpaid"

    payment_res = client.post(
        f"/v1/invoices/{invoice['id']}/payments",
        headers=headers,
        json={"amount_cents": 10300, "provider_reference": "cash-1"},
    )
    assert payment_res.status_code == 201

    get_invoice = client.get(f"/v1/invoices/{invoice['id']}", headers=headers)
    assert get_invoice.status_code == 200
    assert get_invoice.json()["invoice"]["status"] == "paid"
    assert len(get_invoice.json()["payments"]) == 1


def test_work_logs_and_attachments_tenant_isolation():
    suffix_a = uuid4().hex[:8]
    suffix_b = uuid4().hex[:8]

    token_a = _bootstrap_and_login(
        tenant_slug=f"ops-alpha-{suffix_a}",
        email=f"owner-{suffix_a}@opsa.test",
        password="pass123456",
    )
    token_b = _bootstrap_and_login(
        tenant_slug=f"ops-beta-{suffix_b}",
        email=f"owner-{suffix_b}@opsb.test",
        password="pass123456",
    )

    headers_a = {"Authorization": f"Bearer {token_a}"}
    headers_b = {"Authorization": f"Bearer {token_b}"}

    customer_id = _create_customer(headers_a)
    watch_id = _create_watch(headers_a, customer_id)
    job_res = client.post(
        "/v1/repair-jobs",
        headers=headers_a,
        json={"watch_id": watch_id, "title": "Ops flow", "priority": "normal"},
    )
    assert job_res.status_code == 201
    job_id = job_res.json()["id"]

    create_log = client.post(
        "/v1/work-logs",
        headers=headers_a,
        json={
            "repair_job_id": job_id,
            "note": "Disassembled and inspected movement",
            "minutes_spent": 35,
        },
    )
    assert create_log.status_code == 201
    assert create_log.json()["minutes_spent"] == 35

    list_logs_a = client.get(f"/v1/work-logs?repair_job_id={job_id}", headers=headers_a)
    assert list_logs_a.status_code == 200
    assert len(list_logs_a.json()) == 1

    list_logs_b = client.get(f"/v1/work-logs?repair_job_id={job_id}", headers=headers_b)
    assert list_logs_b.status_code == 404

    create_attachment = client.post(
        f"/v1/attachments?repair_job_id={job_id}&label=intake-front",
        headers=headers_a,
        files={"file": ("intake-front.jpg", b"fake-jpeg-bytes", "image/jpeg")},
    )
    assert create_attachment.status_code == 201
    attachment_body = create_attachment.json()
    assert attachment_body["repair_job_id"] == job_id
    assert attachment_body["file_name"] == "intake-front.jpg"
    assert attachment_body["content_type"] == "image/jpeg"

    list_attachments_a = client.get(f"/v1/attachments?repair_job_id={job_id}", headers=headers_a)
    assert list_attachments_a.status_code == 200
    assert len(list_attachments_a.json()) == 1

    list_attachments_b = client.get(f"/v1/attachments?repair_job_id={job_id}", headers=headers_b)
    assert list_attachments_b.status_code == 200
    assert len(list_attachments_b.json()) == 0


def test_multi_site_login_and_site_switch():
    suffix = uuid4().hex[:8]
    owner_email = f"owner-{suffix}@multisite.test"
    owner_password = "pass123456"

    # Bootstrap two sites with the same owner identity.
    for site_slug in (f"site-a-{suffix}", f"site-b-{suffix}"):
        bootstrap_res = client.post(
            "/v1/auth/bootstrap",
            json={
                "tenant_name": f"Tenant {site_slug}",
                "tenant_slug": site_slug,
                "owner_email": owner_email,
                "owner_full_name": "Multi Site Owner",
                "owner_password": owner_password,
            },
        )
        assert bootstrap_res.status_code == 200

    multi_login_res = client.post(
        "/v1/auth/multi-site-login",
        json={"email": owner_email, "password": owner_password},
    )
    assert multi_login_res.status_code == 200
    login_body = multi_login_res.json()
    assert login_body["access_token"]
    assert len(login_body["available_sites"]) == 2

    token = login_body["access_token"]
    headers = {"Authorization": f"Bearer {token}"}
    session_res = client.get("/v1/auth/session", headers=headers)
    assert session_res.status_code == 200
    session_body = session_res.json()
    assert len(session_body["available_sites"]) == 2

    current_tenant = session_body["tenant_id"]
    target = next(site for site in session_body["available_sites"] if site["tenant_id"] != current_tenant)

    switch_res = client.patch(
        "/v1/auth/session/site",
        headers=headers,
        json={"tenant_id": target["tenant_id"]},
    )
    assert switch_res.status_code == 200
    switch_body = switch_res.json()
    assert switch_body["active_site_tenant_id"] == target["tenant_id"]

    switched_headers = {"Authorization": f"Bearer {switch_body['access_token']}"}
    switched_session_res = client.get("/v1/auth/session", headers=switched_headers)
    assert switched_session_res.status_code == 200
    switched_session = switched_session_res.json()
    assert switched_session["tenant_id"] == target["tenant_id"]
    assert len(switched_session["available_sites"]) == 2


def test_parent_account_summary_and_link_tenant():
    suffix = uuid4().hex[:8]
    owner_email = f"owner-{suffix}@parent.test"
    owner_password = "pass123456"

    bootstrap_a = client.post(
        "/v1/auth/bootstrap",
        json={
            "tenant_name": f"Tenant A {suffix}",
            "tenant_slug": f"parent-a-{suffix}",
            "owner_email": owner_email,
            "owner_full_name": "Parent Owner",
            "owner_password": owner_password,
            "plan_code": "enterprise",
        },
    )
    assert bootstrap_a.status_code == 200

    bootstrap_b = client.post(
        "/v1/auth/bootstrap",
        json={
            "tenant_name": f"Tenant B {suffix}",
            "tenant_slug": f"parent-b-{suffix}",
            "owner_email": f"other-{suffix}@parent.test",
            "owner_full_name": "Other Owner",
            "owner_password": owner_password,
            "plan_code": "enterprise",
        },
    )
    assert bootstrap_b.status_code == 200

    login_res = client.post(
        "/v1/auth/login",
        json={
            "tenant_slug": f"parent-a-{suffix}",
            "email": owner_email,
            "password": owner_password,
        },
    )
    assert login_res.status_code == 200
    token = login_res.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    summary_before = client.get("/v1/parent-accounts/me", headers=headers)
    assert summary_before.status_code == 200
    assert len(summary_before.json()["sites"]) == 1

    link_res = client.post(
        "/v1/parent-accounts/me/link-tenant",
        headers=headers,
        json={
            "tenant_slug": f"parent-b-{suffix}",
            "owner_email": f"other-{suffix}@parent.test",
        },
    )
    assert link_res.status_code == 200
    assert len(link_res.json()["sites"]) == 2

    # Prevent unlinking currently active site.
    remove_active_res = client.delete(
        f"/v1/parent-accounts/me/sites/{bootstrap_a.json()['tenant_id']}",
        headers=headers,
    )
    assert remove_active_res.status_code == 400

    # Unlink the secondary linked site.
    remove_linked_res = client.delete(
        f"/v1/parent-accounts/me/sites/{bootstrap_b.json()['tenant_id']}",
        headers=headers,
    )
    assert remove_linked_res.status_code == 200
    assert len(remove_linked_res.json()["sites"]) == 1

    activity_res = client.get("/v1/parent-accounts/me/activity", headers=headers)
    assert activity_res.status_code == 200
    event_types = [event["event_type"] for event in activity_res.json()]
    assert "link_tenant" in event_types
    assert "unlink_tenant" in event_types


def test_parent_account_create_tenant_and_link():
    suffix = uuid4().hex[:8]
    owner_email = f"owner-{suffix}@parent-create.test"
    owner_password = "pass123456"

    bootstrap_res = client.post(
        "/v1/auth/bootstrap",
        json={
            "tenant_name": f"Tenant A {suffix}",
            "tenant_slug": f"parent-create-a-{suffix}",
            "owner_email": owner_email,
            "owner_full_name": "Parent Create Owner",
            "owner_password": owner_password,
            "plan_code": "enterprise",
        },
    )
    assert bootstrap_res.status_code == 200

    login_res = client.post(
        "/v1/auth/login",
        json={
            "tenant_slug": f"parent-create-a-{suffix}",
            "email": owner_email,
            "password": owner_password,
        },
    )
    assert login_res.status_code == 200
    token = login_res.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    create_site_res = client.post(
        "/v1/parent-accounts/me/create-tenant",
        headers=headers,
        json={
            "tenant_name": f"Tenant B {suffix}",
            "tenant_slug": f"parent-create-b-{suffix}",
            "plan_code": "watch",
        },
    )
    assert create_site_res.status_code == 200
    body = create_site_res.json()
    assert len(body["sites"]) == 2
    created_site = next(site for site in body["sites"] if site["tenant_slug"] == f"parent-create-b-{suffix}")

    login_new_site_res = client.post(
        "/v1/auth/login",
        json={
            "tenant_slug": f"parent-create-b-{suffix}",
            "email": owner_email,
            "password": owner_password,
        },
    )
    assert login_new_site_res.status_code == 200

    switch_into_new_site = client.patch(
        "/v1/auth/session/site",
        headers=headers,
        json={"tenant_id": created_site["tenant_id"]},
    )
    assert switch_into_new_site.status_code == 200

    activity_res = client.get("/v1/parent-accounts/me/activity", headers=headers)
    assert activity_res.status_code == 200
    event_types = [event["event_type"] for event in activity_res.json()]
    assert "create_tenant" in event_types
    assert "switch_site" in event_types
