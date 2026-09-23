import os
from pathlib import Path
from uuid import uuid4

# Use a fresh sqlite file for every test run so schema changes are always applied.
_TEST_DB = Path(__file__).with_name(f"test_{uuid4().hex}.db")
os.environ.setdefault("DATABASE_URL", f"sqlite:///{_TEST_DB.as_posix()}")
os.environ.setdefault("JWT_SECRET", "test-secret-not-for-production")
os.environ.setdefault("APP_ENV", "test")

from fastapi.testclient import TestClient

from app.config import settings
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
            "gst_enabled": False,
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
            "gst_enabled": True,
            "gst_inclusive": False,
            "line_items": [
                {"item_type": "labor", "description": "Full service", "quantity": 1, "unit_price_cents": 25000},
                {"item_type": "part", "description": "Gasket", "quantity": 2, "unit_price_cents": 1200},
            ],
        },
    )
    assert quote_res.status_code == 201
    body = quote_res.json()
    assert body["subtotal_cents"] == 27400
    assert body["tax_cents"] == 2740
    assert body["total_cents"] == 30140

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
            "gst_enabled": False,
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
            "gst_enabled": True,
            "gst_inclusive": False,
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
        json={"amount_cents": 11000, "provider_reference": "cash-1"},
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

    bootstrap_res = client.post(
        "/v1/auth/bootstrap",
        json={
            "tenant_name": f"Tenant site-a-{suffix}",
            "tenant_slug": f"site-a-{suffix}",
            "owner_email": owner_email,
            "owner_full_name": "Multi Site Owner",
            "owner_password": owner_password,
            "plan_code": "enterprise",
        },
    )
    assert bootstrap_res.status_code == 200
    first = client.post(
        "/v1/auth/login",
        json={"tenant_slug": f"site-a-{suffix}", "email": owner_email, "password": owner_password},
    )
    created = client.post(
        "/v1/parent-accounts/me/create-tenant",
        headers={"Authorization": f"Bearer {first.json()['access_token']}"},
        json={"tenant_name": f"Tenant site-b-{suffix}", "tenant_slug": f"site-b-{suffix}", "plan_code": "enterprise"},
    )
    assert created.status_code == 200, created.text

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


def _bootstrap_owner(slug: str, email: str, password: str, plan: str = "enterprise") -> dict:
    res = client.post(
        "/v1/auth/bootstrap",
        json={
            "tenant_name": f"Tenant {slug}",
            "tenant_slug": slug,
            "owner_email": email,
            "owner_full_name": "Owner",
            "owner_password": password,
            "plan_code": plan,
        },
    )
    assert res.status_code == 200, res.text
    login = client.post("/v1/auth/login", json={"tenant_slug": slug, "email": email, "password": password})
    assert login.status_code == 200, login.text
    return {"tenant_id": res.json()["tenant_id"], "headers": {"Authorization": f"Bearer {login.json()['access_token']}"}}


def test_signing_up_with_another_owners_email_grants_nothing_of_theirs():
    """Email is unverified: a second signup reusing it must not reach the first."""
    suffix = uuid4().hex[:8]
    email = f"victim-{suffix}@shared.test"
    victim = _bootstrap_owner(f"victim-{suffix}", email, "victim-pass-123")
    client.post("/v1/customers", headers=victim["headers"], json={"full_name": "Victim Customer", "phone": "0400"})
    attacker = _bootstrap_owner(f"attacker-{suffix}", email, "attacker-pass-123")

    sites = client.get("/v1/parent-accounts/me/sites", headers=attacker["headers"]).json()
    slugs = [s.get("tenant_slug") for s in sites.get("sites", sites.get("items", []))]
    assert f"victim-{suffix}" not in slugs
    entered = client.post(
        f"/v1/parent-accounts/me/sites/{victim['tenant_id']}/enter", headers=attacker["headers"], json={"reason": "x"}
    )
    assert entered.status_code == 404
    switched = client.patch("/v1/auth/session/site", headers=attacker["headers"], json={"tenant_id": victim["tenant_id"]})
    assert switched.status_code == 403

    # Multi-site login with the attacker's password opens only the attacker's shop.
    multi = client.post("/v1/auth/multi-site-login", json={"email": email, "password": "attacker-pass-123"})
    assert multi.status_code == 200
    assert {s["tenant_id"] for s in multi.json()["available_sites"]} == {attacker["tenant_id"]}


def test_linking_a_shop_needs_that_shops_consent():
    suffix = uuid4().hex[:8]
    victim = _bootstrap_owner(f"shop-{suffix}", f"shop-{suffix}@x.test", "shop-pass-123", plan="basic_watch")
    hq = _bootstrap_owner(f"hq-{suffix}", f"hq-{suffix}@x.test", "hq-pass-123")
    asked = client.post(
        "/v1/parent-accounts/me/link-tenant",
        headers=hq["headers"],
        json={"tenant_slug": f"shop-{suffix}", "owner_email": f"shop-{suffix}@x.test"},
    )
    assert asked.status_code == 200
    assert asked.json()["site_count"] == 1
    entered = client.post(
        f"/v1/parent-accounts/me/sites/{victim['tenant_id']}/enter", headers=hq["headers"], json={"reason": "x"}
    )
    assert entered.status_code == 404

    [request] = client.get("/v1/network-link-requests", headers=victim["headers"]).json()
    declined = client.post(f"/v1/network-link-requests/{request['id']}/decline", headers=victim["headers"])
    assert declined.json()["status"] == "declined"
    assert client.get("/v1/parent-accounts/me", headers=hq["headers"]).json()["site_count"] == 1
    again = client.post(f"/v1/network-link-requests/{request['id']}/accept", headers=victim["headers"])
    assert again.status_code == 409


def test_owner_cannot_self_upgrade_plan_when_stripe_is_on(monkeypatch):
    suffix = uuid4().hex[:8]
    shop = _bootstrap_owner(f"plan-{suffix}", f"plan-{suffix}@x.test", "plan-pass-123", plan="basic_watch")
    monkeypatch.setattr(settings, "stripe_secret_key", "sk_test_dummy")
    res = client.patch("/v1/auth/session/plan", headers=shop["headers"], json={"plan_code": "pro"})
    assert res.status_code == 403
    monkeypatch.setattr(settings, "stripe_secret_key", "")
    bogus = client.patch("/v1/auth/session/plan", headers=shop["headers"], json={"plan_code": "platinum"})
    assert bogus.status_code in (400, 422)


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

    summary_before = client.get("/v1/parent-accounts/me?include_sites=true", headers=headers)
    assert summary_before.status_code == 200
    assert summary_before.json()["site_count"] == 1
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
    # Nothing is linked until the other shop agrees.
    assert link_res.json()["site_count"] == 1
    assert [r["tenant_slug"] for r in link_res.json()["pending_link_requests"]] == [f"parent-b-{suffix}"]
    entered = client.post(
        f"/v1/parent-accounts/me/sites/{bootstrap_b.json()['tenant_id']}/enter",
        headers=headers,
        json={"reason": "x"},
    )
    assert entered.status_code == 404

    b_login = client.post(
        "/v1/auth/login",
        json={"tenant_slug": f"parent-b-{suffix}", "email": f"other-{suffix}@parent.test", "password": owner_password},
    )
    b_headers = {"Authorization": f"Bearer {b_login.json()['access_token']}"}
    requests_res = client.get("/v1/network-link-requests", headers=b_headers)
    assert requests_res.status_code == 200
    [request] = requests_res.json()
    accepted = client.post(f"/v1/network-link-requests/{request['id']}/accept", headers=b_headers)
    assert accepted.status_code == 200, accepted.text
    assert accepted.json()["status"] == "accepted"

    summary_after = client.get("/v1/parent-accounts/me", headers=headers)
    assert summary_after.json()["site_count"] == 2

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
    assert remove_linked_res.json()["site_count"] == 1

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
    assert body["site_count"] == 2
    sites_res = client.get("/v1/parent-accounts/me/sites?limit=50", headers=headers)
    assert sites_res.status_code == 200
    created_site = next(
        site for site in sites_res.json()["sites"]
        if site["tenant_slug"] == f"parent-create-b-{suffix}"
    )

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


def test_unusable_password_hash_cannot_be_logged_in_with():
    """The placeholder given to an imported shop owner: a real bcrypt hash that
    nobody holds the plaintext for, cheap to produce because there is nothing
    guessable to defend."""
    from app.security import hash_unusable_password, verify_password

    first = hash_unusable_password()
    second = hash_unusable_password()

    # A real bcrypt hash, so verify_password keeps working against it.
    assert first.startswith("$2b$")
    # Distinct per account — one leaked plaintext could not unlock the rest.
    assert first != second
    for guess in ("", "password", "123456", "admin", "changeme"):
        assert not verify_password(guess, first)


def test_demo_seed_refuses_a_shop_that_is_not_the_demo_tenant():
    """It wipes the tenant's jobs, customers and invoices before reseeding, so
    an ordinary shop must never reach it — in any environment, not just
    production, because a staging or local shop is somebody's work too."""
    from app.config import settings

    slug = f"realshop{uuid4().hex[:8]}"
    email = f"owner-{uuid4().hex[:8]}@example.com"
    token = _bootstrap_and_login(slug, email, "Str0ngPass!23")

    assert settings.app_env.lower() != "production"
    res = client.post("/v1/auth/demo-seed", headers={"Authorization": f"Bearer {token}"})
    assert res.status_code == 403, res.text
    assert "demo or testing tenant" in res.json()["detail"]


def test_refresh_with_an_unknown_session_is_refused():
    """A missing session row is what revoking a device looks like, so no tenant
    gets a fresh pair of tokens out of one. The demo used to, which left a
    leaked demo refresh token impossible to shut off."""
    from sqlalchemy import delete as sa_delete
    from sqlmodel import Session

    from app.database import engine
    from app.models import RefreshSession

    slug = f"revoked{uuid4().hex[:8]}"
    email = f"owner-{uuid4().hex[:8]}@example.com"
    password = "Str0ngPass!23"
    _bootstrap_and_login(slug, email, password)

    login = client.post("/v1/auth/login", json={"tenant_slug": slug, "email": email, "password": password})
    assert login.status_code == 200, login.text
    refresh_token = login.json()["refresh_token"]

    with Session(engine) as db:
        db.execute(sa_delete(RefreshSession))
        db.commit()

    res = client.post("/v1/auth/refresh", json={"refresh_token": refresh_token})
    assert res.status_code == 401, res.text
    assert "revoked" in res.json()["detail"].lower()
