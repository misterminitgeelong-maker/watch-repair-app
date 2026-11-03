"""Privacy and hygiene basics: log redaction, export/API-key role guards, webhook
SSRF guard, mobile quote link expiry/single-use, and repo hygiene for seed data."""
from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone
from pathlib import Path
from uuid import uuid4

import pytest
from sqlmodel import Session, select

from app.database import engine
from app.log_redaction import mask_email, mask_phone, redact_path, redact_text
from app.models import AutoKeyJob, AutoKeyQuote, Customer, Tenant, TenantEventLog
from app.services import webhook_url_guard as guard
from app.services.webhook_url_guard import WebhookUrlError, validate_webhook_url

REPO = Path(__file__).resolve().parents[2]
PW = "supersecret123"


# ── helpers ───────────────────────────────────────────────────────────────────

def _tenant(client, label="p"):
    sfx = uuid4().hex[:8]
    slug = f"priv-{label}-{sfx}"
    email = f"owner-{sfx}@example.test"
    r = client.post("/v1/auth/bootstrap", json={
        "tenant_name": f"Priv {label}", "tenant_slug": slug, "owner_email": email,
        "owner_full_name": "Owner", "owner_password": PW})
    assert r.status_code == 200, r.text
    return slug, email


def _login(client, slug, email):
    r = client.post("/v1/auth/login", json={"tenant_slug": slug, "email": email, "password": PW})
    assert r.status_code == 200, r.text
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


def _user_headers(client, slug, owner_h, role):
    email = f"{role}-{uuid4().hex[:6]}@example.test"
    r = client.post("/v1/users", headers=owner_h, json={
        "email": email, "full_name": role, "password": PW, "role": role})
    assert r.status_code == 201, r.text
    return _login(client, slug, email)


# ── 1. repo hygiene ───────────────────────────────────────────────────────────

def test_customer_csv_not_tracked_and_ignored():
    assert not (REPO / "backend/seed/repairs_import.csv").exists() or "repairs_import.csv" in (
        REPO / ".gitignore").read_text()
    assert "backend/seed/repairs_import.csv" in (REPO / ".gitignore").read_text()


@pytest.mark.parametrize("rel", [".env.example", "backend/.env.example"])
def test_env_examples_are_safe_by_default(rel):
    vals = {}
    for line in (REPO / rel).read_text().splitlines():
        if "=" in line and not line.lstrip().startswith("#"):
            k, _, v = line.partition("=")
            vals[k.strip()] = v.strip()
    for flag in ("ALLOW_PUBLIC_BOOTSTRAP", "STARTUP_SEED_ENABLED", "PLATFORM_ADMIN_ENABLED",
                 "ALLOW_ENSURE_TESTING_TENANT"):
        assert vals.get(flag, "false").lower() == "false", f"{rel}: {flag} must default off"
    for secret in ("STARTUP_SEED_OWNER_PASSWORD", "TESTING_OWNER_PASSWORD", "PLATFORM_ADMIN_PASSWORD"):
        assert vals.get(secret, "") == "", f"{rel}: {secret} must be empty"
    assert "BIGFATTESTER" not in (REPO / rel).read_text()


def test_startup_seed_skips_when_csv_missing(monkeypatch, tmp_path):
    from app import startup_seed
    from app.config import settings
    monkeypatch.setattr(settings, "startup_seed_csv_path", str(tmp_path / "absent.csv"))
    monkeypatch.setattr(settings, "startup_seed_enabled", True)
    with Session(engine) as s:
        startup_seed.seed_from_csv_if_empty(s)  # must not raise
    assert startup_seed._seed_status.get("seeded") is not True
    assert startup_seed._seed_status.get("reason") in ("csv_not_found", "database_not_empty")


# ── 2. log redaction ──────────────────────────────────────────────────────────

def test_redact_path_hides_tokens_keeps_routes():
    tok = "kP9xQ2mZ7vLw4NbT8cYd3A"
    assert redact_path(f"/v1/public/quotes/{tok}/decision") == "/v1/public/quotes/[token]/decision"
    assert redact_path(f"/v1/public/portal/session/{tok}") == "/v1/public/portal/session/[token]"
    hexs = uuid4().hex
    assert hexs not in redact_path(f"/v1/public/auto-key-quote/{hexs}")
    assert redact_path("/v1/public/auto-key-quote/") == "/v1/public/auto-key-quote/"
    assert redact_path("/v1/customers/1234") == "/v1/customers/1234"


def test_mask_phone_email_and_text():
    assert mask_phone("+61412345678") == "***678"
    assert mask_email("jane@example.com") == "j***@example.com"
    out = redact_text("Hi jane@example.com approve: https://x.example/quote/Abc123Def456Ghi789 ok")
    assert "jane@" not in out and "Abc123Def456Ghi789" not in out


def test_request_log_does_not_contain_public_token(client, caplog):
    tok = "Zz9Yy8Xx7Ww6Vv5Uu4Tt3S"
    with caplog.at_level(logging.INFO):
        client.get(f"/v1/public/auto-key-quote/{tok}")
    app_logs = "\n".join(r.getMessage() for r in caplog.records if r.name.startswith("mainspring"))
    assert "auto-key-quote/[token]" in app_logs
    assert tok not in app_logs


def test_sms_dry_run_and_email_logs_are_masked(caplog, monkeypatch):
    from app import sms, email_client
    from app.config import settings
    monkeypatch.setattr(settings, "twilio_account_sid", "")
    with caplog.at_level(logging.INFO):
        sms._send_sms("+61412345678", "link https://x.example/q/Abc123Def456Ghi789")
    assert "+61412345678" not in caplog.text and "***678" in caplog.text
    assert "Abc123Def456Ghi789" not in caplog.text


# ── 3. export-my-data ─────────────────────────────────────────────────────────

def test_export_my_data_owner_only_and_logged(client):
    slug, email = _tenant(client, "x")
    owner_h = _login(client, slug, email)
    r = client.get("/v1/auth/export-my-data", headers=owner_h)
    assert r.status_code == 200
    for role in ("intake", "tech", "manager"):
        h = _user_headers(client, slug, owner_h, role)
        assert client.get("/v1/auth/export-my-data", headers=h).status_code == 403, role
    assert client.get("/v1/auth/export-my-data").status_code in (401, 403)
    with Session(engine) as s:
        t = s.exec(select(Tenant).where(Tenant.slug == slug)).one()
        rows = s.exec(select(TenantEventLog).where(
            TenantEventLog.tenant_id == t.id, TenantEventLog.event_type == "data_export")).all()
        assert len(rows) == 1


# ── 4. API keys and webhooks ──────────────────────────────────────────────────

def test_api_key_and_webhook_creation_requires_manager(client, monkeypatch):
    monkeypatch.setenv("WEBHOOK_ALLOWED_HOSTS", "hooks.example.test")
    slug, email = _tenant(client, "k")
    owner_h = _login(client, slug, email)
    tech_h = _user_headers(client, slug, owner_h, "tech")
    mgr_h = _user_headers(client, slug, owner_h, "manager")
    hook = {"url": "https://hooks.example.test/in", "event_types": ["*"]}

    assert client.post("/v1/tenant/api-keys", headers=tech_h, json={"name": "k"}).status_code == 403
    assert client.post("/v1/tenant/webhooks", headers=tech_h, json=hook).status_code == 403
    assert client.post("/v1/tenant/api-keys", headers=mgr_h, json={"name": "k"}).status_code == 201
    r = client.post("/v1/tenant/webhooks", headers=mgr_h, json=hook)
    assert r.status_code == 201, r.text
    assert client.delete(f"/v1/tenant/webhooks/{r.json()['id']}", headers=tech_h).status_code == 403
    assert client.delete(f"/v1/tenant/webhooks/{r.json()['id']}", headers=mgr_h).status_code == 204


@pytest.mark.parametrize("url", [
    "http://example.com/hook",
    "https://localhost/hook",
    "https://127.0.0.1/hook",
    "https://169.254.169.254/latest/meta-data",
    "https://10.0.0.5/x",
    "https://192.168.1.1/x",
    "https://[::1]/x",
    "https://user:pw@example.com/x",
    "ftp://example.com/x",
])
def test_webhook_url_rejects_unsafe(url, monkeypatch):
    monkeypatch.setattr(guard, "_resolve", lambda h, p: ["93.184.216.34"])
    with pytest.raises(WebhookUrlError):
        validate_webhook_url(url)


def test_webhook_url_rejects_hostname_resolving_private(monkeypatch):
    monkeypatch.setattr(guard, "_resolve", lambda h, p: ["10.1.2.3"])
    with pytest.raises(WebhookUrlError):
        validate_webhook_url("https://evil.example.com/x")
    monkeypatch.setattr(guard, "_resolve", lambda h, p: ["93.184.216.34", "169.254.169.254"])
    with pytest.raises(WebhookUrlError):
        validate_webhook_url("https://mixed.example.com/x")


def test_webhook_url_accepts_public_and_allowlist(monkeypatch):
    monkeypatch.setattr(guard, "_resolve", lambda h, p: ["93.184.216.34"])
    assert validate_webhook_url("https://example.com/h") == "https://example.com/h"
    monkeypatch.setattr(guard, "_resolve", lambda h, p: ["127.0.0.1"])
    monkeypatch.setenv("WEBHOOK_ALLOWED_HOSTS", "internal-test.example")
    assert validate_webhook_url("https://internal-test.example/h")
    with pytest.raises(WebhookUrlError):
        validate_webhook_url("http://internal-test.example/h")  # https still required


def test_webhook_create_endpoint_rejects_private(client):
    slug, email = _tenant(client, "w")
    h = _login(client, slug, email)
    r = client.post("/v1/tenant/webhooks", headers=h, json={
        "url": "https://169.254.169.254/x", "event_types": ["*"]})
    assert r.status_code == 422


def test_dispatch_skips_unsafe_url_and_uses_timeout(monkeypatch):
    from app.models import TenantWebhookSubscription
    from app.services import tenant_webhooks
    calls = []
    monkeypatch.setattr(tenant_webhooks.httpx, "post", lambda *a, **k: calls.append((a, k)))
    monkeypatch.setattr(guard, "_resolve", lambda h, p: ["93.184.216.34"])
    with Session(engine) as s:
        t = Tenant(name="WH", slug=f"wh-{uuid4().hex[:6]}")
        s.add(t); s.flush()
        for url in ("https://example.com/ok", "https://127.0.0.1/bad"):
            s.add(TenantWebhookSubscription(tenant_id=t.id, url=url, event_types="*", secret="s"))
        s.commit()
        tenant_webhooks.dispatch_tenant_webhooks(s, tenant_id=t.id, event_type="x", payload={})
    assert len(calls) == 1
    assert calls[0][0][0] == "https://example.com/ok"
    assert calls[0][1]["timeout"] <= 10 and calls[0][1]["follow_redirects"] is False


# ── 5. mobile quote link expiry and single use ───────────────────────────────

def _make_quote(slug, status="sent", sent_at=None, created_at=None):
    with Session(engine) as s:
        t = s.exec(select(Tenant).where(Tenant.slug == slug)).one()
        c = Customer(tenant_id=t.id, full_name="Q Customer", phone="0400000099")
        s.add(c); s.flush()
        job = AutoKeyJob(tenant_id=t.id, customer_id=c.id, job_number=f"AK-{uuid4().hex[:5]}",
                         title="Spare key", status="quote_sent")
        s.add(job); s.flush()
        q = AutoKeyQuote(tenant_id=t.id, auto_key_job_id=job.id, status=status, total_cents=5000,
                         sent_at=sent_at, created_at=created_at or datetime.now(timezone.utc))
        s.add(q); s.commit()
        return q.quote_approval_token, q.id, job.id


def test_mobile_quote_link_expires_after_168h(client):
    slug, _ = _tenant(client, "q1")
    now = datetime.now(timezone.utc)
    fresh, *_ = _make_quote(slug, sent_at=now - timedelta(hours=167))
    old, *_ = _make_quote(slug, sent_at=now - timedelta(hours=169))
    assert client.get(f"/v1/public/auto-key-quote/{fresh}").status_code == 200
    assert client.get(f"/v1/public/auto-key-quote/{old}").status_code == 410
    r = client.post(f"/v1/public/auto-key-quote/{old}/decision", json={"decision": "approved"})
    assert r.status_code == 410
    with Session(engine) as s:
        assert s.exec(select(AutoKeyQuote).where(AutoKeyQuote.quote_approval_token == old)).one().status == "sent"


def test_mobile_quote_legacy_link_without_sent_at_uses_created_at(client):
    slug, _ = _tenant(client, "q2")
    now = datetime.now(timezone.utc)
    recent, *_ = _make_quote(slug, status="draft", sent_at=None, created_at=now - timedelta(hours=10))
    stale, *_ = _make_quote(slug, status="draft", sent_at=None, created_at=now - timedelta(days=30))
    assert client.get(f"/v1/public/auto-key-quote/{recent}").status_code == 200
    assert client.get(f"/v1/public/auto-key-quote/{stale}").status_code == 410


def test_mobile_quote_decision_is_single_use(client):
    slug, _ = _tenant(client, "q3")
    tok, qid, job_id = _make_quote(slug, sent_at=datetime.now(timezone.utc))
    r1 = client.post(f"/v1/public/auto-key-quote/{tok}/decision", json={"decision": "approved"})
    assert r1.status_code == 200 and r1.json()["status"] == "approved"
    r2 = client.post(f"/v1/public/auto-key-quote/{tok}/decision", json={"decision": "approved"})
    assert r2.status_code == 200 and r2.json()["status"] == "approved"
    r3 = client.post(f"/v1/public/auto-key-quote/{tok}/decision", json={"decision": "declined"})
    assert r3.json()["status"] == "approved"
    with Session(engine) as s:
        from app.models import AutoKeyInvoice
        assert len(s.exec(select(AutoKeyInvoice).where(AutoKeyInvoice.auto_key_quote_id == qid)).all()) == 1
        events = s.exec(select(TenantEventLog).where(
            TenantEventLog.entity_id == job_id, TenantEventLog.event_type.like("quote_%_portal"))).all()
        assert len(events) == 1
        assert s.exec(select(AutoKeyQuote).where(AutoKeyQuote.id == qid)).one().status == "approved"


# ── 6. runbook ────────────────────────────────────────────────────────────────

def test_breach_runbook_present_and_marked_draft():
    text = (REPO / "docs/BREACH_RESPONSE.md").read_text()
    assert "DRAFT" in text and "legal review" in text.lower()
    assert "OAIC" in text
