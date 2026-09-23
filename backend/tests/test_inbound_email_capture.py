"""Inbound email capture webhook (SendGrid Inbound Parse) + HQ triage APIs."""

import os
from pathlib import Path
from uuid import uuid4

_TEST_DB = Path(__file__).with_name(f"test_inbound_email_{uuid4().hex}.db")
os.environ.setdefault("DATABASE_URL", f"sqlite:///{_TEST_DB.as_posix()}")
os.environ.setdefault("JWT_SECRET", "test-secret-not-for-production")
os.environ.setdefault("APP_ENV", "test")

from fastapi.testclient import TestClient

from app.database import create_db_and_tables
from app.main import app

create_db_and_tables()
client = TestClient(app)

SECRET = "super-secret-inbound-key-123"


def _bootstrap(slug: str, email: str, plan_code: str = "pro") -> dict:
    res = client.post(
        "/v1/auth/bootstrap",
        json={
            "tenant_name": f"Tenant {slug}",
            "tenant_slug": slug,
            "owner_email": email,
            "owner_full_name": "Owner",
            "owner_password": "pass123456",
            "plan_code": plan_code,
        },
    )
    assert res.status_code == 200, res.text
    return res.json()


def _login(slug: str, email: str) -> dict[str, str]:
    res = client.post(
        "/v1/auth/login",
        json={"tenant_slug": slug, "email": email, "password": "pass123456"},
    )
    assert res.status_code == 200, res.text
    return {"Authorization": f"Bearer {res.json()['access_token']}"}


def _setup_parent_with_ingest() -> dict:
    suffix = uuid4().hex[:8]
    slug = f"hq-{suffix}"
    email = f"hq-{suffix}@test.local"
    boot = _bootstrap(slug, email)
    headers = _login(slug, email)

    enable = client.post("/v1/parent-accounts/me/mobile-lead-ingest/enable", headers=headers)
    assert enable.status_code == 200, enable.text
    ingest_id = enable.json()["mobile_lead_ingest_public_id"]
    assert ingest_id

    secret = client.put(
        "/v1/parent-accounts/me/mobile-lead-ingest/secret",
        headers=headers,
        json={"webhook_secret": SECRET},
    )
    assert secret.status_code == 200, secret.text

    default = client.put(
        "/v1/parent-accounts/me/mobile-lead-ingest/default-tenant",
        headers=headers,
        json={"tenant_id": boot["tenant_id"]},
    )
    assert default.status_code == 200, default.text
    return {"headers": headers, "ingest_id": ingest_id, "tenant_id": boot["tenant_id"]}


def _post_email(ingest_id: str, key: str = SECRET, **overrides):
    data = {
        "from": "Web Enquiry <noreply@misterminit.example>",
        "to": "minit-autokey@leads.mainspring.test",
        "subject": "Auto key enquiry — Toyota Corolla",
        "text": "Suburb: Chadstone\nState: VIC\nName: Jane Citizen\nPhone: 0400 000 000",
        "headers": "Message-ID: <abc-123@misterminit.example>\nFrom: noreply@misterminit.example",
        "SPF": "pass",
        "sender_ip": "203.0.113.10",
    }
    data.update(overrides)
    data = {k: v for k, v in data.items() if v is not None}
    return client.post(f"/v1/public/inbound-email/{ingest_id}?key={key}", data=data)


def test_capture_stores_email_and_raises_inbox_alert():
    ctx = _setup_parent_with_ingest()
    res = _post_email(ctx["ingest_id"])
    assert res.status_code == 200, res.text
    body = res.json()
    assert body["status"] == "received"

    rows = client.get("/v1/parent-accounts/me/inbound-emails", headers=ctx["headers"])
    assert rows.status_code == 200, rows.text
    items = rows.json()
    assert len(items) == 1
    assert items[0]["subject"] == "Auto key enquiry — Toyota Corolla"
    assert items[0]["status"] == "new"

    detail = client.get(
        f"/v1/parent-accounts/me/inbound-emails/{items[0]['id']}", headers=ctx["headers"]
    )
    assert detail.status_code == 200, detail.text
    assert "Chadstone" in detail.json()["text_body"]
    assert detail.json()["message_id"] == "<abc-123@misterminit.example>"

    inbox = client.get("/v1/inbox", headers=ctx["headers"])
    assert inbox.status_code == 200, inbox.text
    events = [e for e in inbox.json() if e["event_type"] == "inbound_email_received"]
    assert len(events) == 1
    assert "Auto key enquiry" in events[0]["event_summary"]


def test_duplicate_message_id_not_stored_twice():
    ctx = _setup_parent_with_ingest()
    first = _post_email(ctx["ingest_id"])
    assert first.json()["status"] == "received"
    second = _post_email(ctx["ingest_id"])
    assert second.status_code == 200
    assert second.json()["status"] == "duplicate"
    assert second.json()["inbound_email_id"] == first.json()["inbound_email_id"]

    rows = client.get("/v1/parent-accounts/me/inbound-emails", headers=ctx["headers"])
    assert len(rows.json()) == 1


def test_bad_key_and_unknown_ingest_id_rejected():
    ctx = _setup_parent_with_ingest()
    bad_key = _post_email(ctx["ingest_id"], key="wrong-key-but-long-enough")
    assert bad_key.status_code == 401

    unknown = _post_email(str(uuid4()))
    assert unknown.status_code == 404


def test_raw_mime_mode_is_parsed():
    ctx = _setup_parent_with_ingest()
    raw = (
        "From: forms@misterminit.example\r\n"
        "To: minit-autokey@leads.mainspring.test\r\n"
        "Subject: Key enquiry Mazda 3\r\n"
        "Message-ID: <raw-mode-456@misterminit.example>\r\n"
        "Content-Type: text/plain; charset=utf-8\r\n"
        "\r\n"
        "Suburb: Werribee\r\nState: VIC\r\n"
    )
    res = _post_email(
        ctx["ingest_id"], text=None, html=None, headers=None, subject=None, email=raw
    )
    assert res.status_code == 200, res.text
    rows = client.get("/v1/parent-accounts/me/inbound-emails", headers=ctx["headers"]).json()
    assert rows[0]["subject"] == "Key enquiry Mazda 3"
    detail = client.get(
        f"/v1/parent-accounts/me/inbound-emails/{rows[0]['id']}", headers=ctx["headers"]
    ).json()
    assert "Werribee" in detail["text_body"]
    assert detail["message_id"] == "<raw-mode-456@misterminit.example>"


def test_status_update_and_validation():
    ctx = _setup_parent_with_ingest()
    _post_email(ctx["ingest_id"])
    rows = client.get("/v1/parent-accounts/me/inbound-emails", headers=ctx["headers"]).json()
    email_id = rows[0]["id"]

    patched = client.patch(
        f"/v1/parent-accounts/me/inbound-emails/{email_id}",
        headers=ctx["headers"],
        json={"status": "processed"},
    )
    assert patched.status_code == 200, patched.text
    assert patched.json()["status"] == "processed"

    invalid = client.patch(
        f"/v1/parent-accounts/me/inbound-emails/{email_id}",
        headers=ctx["headers"],
        json={"status": "archived"},
    )
    assert invalid.status_code == 400

    filtered = client.get(
        "/v1/parent-accounts/me/inbound-emails?status=new", headers=ctx["headers"]
    )
    assert filtered.status_code == 200
    assert all(r["status"] == "new" for r in filtered.json())


def test_other_parent_cannot_see_emails():
    ctx = _setup_parent_with_ingest()
    _post_email(ctx["ingest_id"])
    rows = client.get("/v1/parent-accounts/me/inbound-emails", headers=ctx["headers"]).json()
    email_id = rows[0]["id"]

    other = _setup_parent_with_ingest()
    stranger = client.get(
        f"/v1/parent-accounts/me/inbound-emails/{email_id}", headers=other["headers"]
    )
    assert stranger.status_code == 404
    assert client.get("/v1/parent-accounts/me/inbound-emails", headers=other["headers"]).json() == []


# ── HQ3: dedicated inbound secret, sent as basic auth instead of in the URL ──

INBOUND_SECRET = "a-different-inbound-only-secret-456"


def _post_email_basic(ingest_id: str, secret: str, *, query_key: str | None = None):
    url = f"/v1/public/inbound-email/{ingest_id}"
    if query_key:
        url += f"?key={query_key}"
    return client.post(
        url,
        auth=("inbound", secret),
        data={
            "from": "Web Enquiry <noreply@misterminit.example>",
            "subject": f"Enquiry {uuid4().hex[:6]}",
            "text": "Suburb: Chadstone",
            "headers": f"Message-ID: <{uuid4().hex}@misterminit.example>",
        },
    )


def test_hq3_dedicated_inbound_secret_via_basic_auth():
    ctx = _setup_parent_with_ingest()
    res = client.put(
        "/v1/parent-accounts/me/inbound-email/secret",
        headers=ctx["headers"],
        json={"webhook_secret": INBOUND_SECRET},
    )
    assert res.status_code == 200, res.text
    assert res.json()["inbound_email_secret_configured"] is True

    ok = _post_email_basic(ctx["ingest_id"], INBOUND_SECRET)
    assert ok.status_code == 200, ok.text

    # The website lead feed secret no longer opens the inbound endpoint…
    assert _post_email_basic(ctx["ingest_id"], SECRET).status_code == 401
    # …and neither does the old query-string key once the new secret is set.
    assert _post_email(ctx["ingest_id"]).status_code == 401
    # Header form works too.
    hdr = client.post(
        f"/v1/public/inbound-email/{ctx['ingest_id']}",
        headers={"X-Inbound-Email-Secret": INBOUND_SECRET},
        data={"subject": "hdr", "text": "x", "headers": f"Message-ID: <{uuid4().hex}@x>"},
    )
    assert hdr.status_code == 200, hdr.text


def test_hq3_missing_credentials_rejected():
    ctx = _setup_parent_with_ingest()
    res = client.post(f"/v1/public/inbound-email/{ctx['ingest_id']}", data={"subject": "x"})
    assert res.status_code == 401
