"""Audit-proposed cross-tenant leak tests (areas B and H).

Place at backend/tests/test_audit_cross_tenant_leaks.py (uses backend/tests/conftest.py).

Broader than tests/test_tenant_isolation.py, whose generic walker only covers GET
routes whose params are named customer_id/watch_id/job_id/quote_id/invoice_id/id
(so shoe, auto-key, attachment, user, customer-account routes are never walked) and
which never walks mutating methods.

Design:
  * Tenant A is populated with every entity reachable via the public API; then
    ALL UUIDs and the marker string are harvested from every parameterless GET
    route as A.
  * Tenant B (hostile, owner role) baseline-harvested BEFORE A's data exists.
  * Test 1: every parameterless GET /v1 route as B must not contain A's marker/UUIDs.
  * Test 2: every route with path params, every method, with A's ids substituted,
    as B, must never return 2xx (GET additionally must not contain the marker).
  * Test 3: foreign-key injection (B creates child rows pointing at A's parents).
  * Test 4: forged-token and role checks.
  * Test 5: attachments cross-tenant.
  * Test 6: intake role vs owner-only / bulk-export endpoints.
  * Test 7: Twilio signature enforcement outside test env, replay behaviour.
"""
from __future__ import annotations

import re
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from app.main import app

UUID_RE = re.compile(r"[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}", re.I)
MARKER = "ZZTENANTAMARKER"


def _bootstrap(client, label):
    sfx = uuid4().hex[:8]
    slug = f"aud-{label}-{sfx}"
    email = f"owner-{sfx}@example.test"
    r = client.post("/v1/auth/bootstrap", json={
        "tenant_name": f"Audit {label}", "tenant_slug": slug, "owner_email": email,
        "owner_full_name": f"Owner {label}", "owner_password": "supersecret123"})
    assert r.status_code == 200, r.text
    l = client.post("/v1/auth/login", json={"tenant_slug": slug, "email": email, "password": "supersecret123"})
    assert l.status_code == 200, l.text
    return {"Authorization": f"Bearer {l.json()['access_token']}"}, slug, r.json()


def _get_routes(spec):
    out = []
    for path, ops in spec["paths"].items():
        if not path.startswith("/v1/"):
            continue
        # /v1/_test/* are deliberately-leaky fixtures other test modules register on the shared app.
        if path.startswith(("/v1/auth", "/v1/public", "/v1/webhook", "/v1/webhooks", "/v1/debug", "/v1/_test")):
            continue
        for method in ops:
            if method in ("get", "post", "put", "patch", "delete"):
                out.append((method, path))
    return sorted(out)


def _harvest(client, headers, routes):
    ids, texts = set(), []
    for method, path in routes:
        if method != "get" or "{" in path:
            continue
        r = client.get(path, headers=headers)
        if r.status_code == 200:
            ids |= set(UUID_RE.findall(r.text.lower()))
            texts.append(r.text)
    return ids


@pytest.fixture(scope="module")
def world():
    client = TestClient(app)
    spec = app.openapi()
    routes = _get_routes(spec)
    a, a_slug, a_boot = _bootstrap(client, "a")
    b, b_slug, _ = _bootstrap(client, "b")
    b_baseline = _harvest(client, b, routes)

    ids = {}
    c = client.post("/v1/customers", headers=a, json={
        "full_name": f"{MARKER} Customer", "email": "marker-a@example.test", "phone": "0400000111"})
    assert c.status_code == 201, c.text
    ids["customer_id"] = c.json()["id"]
    w = client.post("/v1/watches", headers=a, json={
        "customer_id": ids["customer_id"], "brand": MARKER, "model": "M"})
    assert w.status_code == 201, w.text
    ids["watch_id"] = w.json()["id"]
    j = client.post("/v1/repair-jobs", headers=a, json={
        "watch_id": ids["watch_id"], "title": f"{MARKER} repair", "priority": "normal"})
    assert j.status_code == 201, j.text
    ids["job_id"] = j.json()["id"]
    q = client.post("/v1/quotes", headers=a, json={"repair_job_id": ids["job_id"], "line_items": [
        {"item_type": "labor", "description": MARKER, "quantity": 1, "unit_price_cents": 10000}]})
    assert q.status_code == 201, q.text
    ids["quote_id"] = q.json()["id"]
    s = client.post("/v1/shoe-repair-jobs/shoes", headers=a, json={
        "customer_id": ids["customer_id"], "shoe_type": "Boot", "brand": MARKER})
    assert s.status_code == 201, s.text
    ids["shoe_id"] = s.json()["id"]
    sj = client.post("/v1/shoe-repair-jobs", headers=a, json={
        "shoe_id": ids["shoe_id"], "title": f"{MARKER} shoe", "priority": "normal",
        "items": [{"catalogue_key": "soles__half_sole_leather", "catalogue_group": "soles",
                   "item_name": "Half sole leather", "pricing_type": "fixed", "quantity": 1,
                   "unit_price_cents": 5000}]})
    assert sj.status_code == 201, sj.text
    ids["shoe_job_id"] = sj.json()["id"]
    ak = client.post("/v1/auto-key-jobs", headers=a, json={
        "customer_id": ids["customer_id"], "title": f"{MARKER} key", "key_quantity": 1,
        "priority": "normal", "status": "awaiting_quote", "programming_status": "pending",
        "deposit_cents": 0, "cost_cents": 0, "tech_notes": MARKER})
    assert ak.status_code == 201, ak.text
    ids["auto_key_job_id"] = ak.json()["id"]
    att = client.post("/v1/attachments", headers=a, params={"repair_job_id": ids["job_id"]},
                      files={"file": ("secret.txt", MARKER.encode(), "text/plain")})
    assert att.status_code == 201, att.text
    ids["attachment_id"] = att.json()["id"]
    ids["storage_key"] = att.json()["storage_key"]
    u = client.post("/v1/users", headers=a, json={
        "email": f"intake-{uuid4().hex[:6]}@example.test", "full_name": "A Intake",
        "password": "supersecret123", "role": "intake"})
    assert u.status_code == 201, u.text
    ids["user_id"] = u.json()["id"]
    client.post(f"/v1/repair-jobs/{ids['job_id']}/messages", headers=a, json={"body": MARKER})

    a_ids = _harvest(client, a, routes) | set(v for v in ids.values() if UUID_RE.fullmatch(v))
    a_ids -= b_baseline
    return {"client": client, "a": a, "b": b, "ids": ids, "a_ids": a_ids, "routes": routes,
            "a_slug": a_slug, "b_slug": b_slug}


def test_world_has_substantial_a_data(world):
    assert len(world["a_ids"]) >= 8, "harvest found too little tenant-A data; test would be vacuous"


def test_every_parameterless_get_excludes_tenant_a(world):
    client, b = world["client"], world["b"]
    leaks, checked = [], 0
    for method, path in world["routes"]:
        if method != "get" or "{" in path:
            continue
        r = client.get(path, headers=b)
        if r.status_code != 200:
            continue
        checked += 1
        t = r.text
        bad = (["marker"] if MARKER in t else []) + [i for i in world["a_ids"] if i in t.lower()]
        if bad:
            leaks.append((path, bad[:3]))
    assert checked > 40, f"only {checked} GET routes returned 200; walker is not covering enough"
    assert not leaks, f"cross-tenant leaks: {leaks}"


def test_every_param_route_all_methods_reject_tenant_a_ids(world):
    client, b = world["client"], world["b"]
    pool = [v for v in world["ids"].values() if UUID_RE.fullmatch(v)]
    leaks, exercised, not_exercised = [], 0, 0
    # GET first, so a mutating success cannot hide the read behaviour.
    ordered = sorted(world["routes"], key=lambda r: (r[0] != "get", r[1]))
    for method, path in ordered:
        params = re.findall(r"\{([^}]+)\}", path)
        if not params:
            continue
        for val in pool:
            url = path
            for p in params:
                name = p.split(":")[0]
                url = url.replace("{" + p + "}", val if not name.endswith(("token", "key", "slug")) else "x")
            kw = {"headers": b}
            if method in ("post", "put", "patch"):
                kw["json"] = {}
            r = client.request(method.upper(), url, **kw)
            if r.status_code == 422:
                not_exercised += 1
                continue
            exercised += 1
            if 200 <= r.status_code < 300:
                leaks.append((method.upper(), url, r.status_code))
            elif r.status_code == 200 and MARKER in r.text:
                leaks.append((method.upper(), url, "marker"))
    print(f"param-route probes exercised={exercised} rejected_by_validation={not_exercised}")
    assert exercised > 500
    assert not leaks, f"B obtained 2xx on tenant A's ids: {leaks[:25]}"


def test_foreign_key_injection_rejected(world):
    """B creating rows that reference A's parent ids must fail, and must not
    produce rows carrying A's tenant or B-owned children of A's rows."""
    client, b, ids = world["client"], world["b"], world["ids"]
    attempts = [
        ("/v1/watches", {"customer_id": ids["customer_id"], "brand": "X", "model": "Y"}),
        ("/v1/repair-jobs", {"watch_id": ids["watch_id"], "title": "x", "priority": "normal"}),
        ("/v1/quotes", {"repair_job_id": ids["job_id"], "line_items": [
            {"item_type": "labor", "description": "x", "quantity": 1, "unit_price_cents": 1}]}),
        ("/v1/shoe-repair-jobs/shoes", {"customer_id": ids["customer_id"], "shoe_type": "Boot", "brand": "x"}),
        ("/v1/shoe-repair-jobs", {"shoe_id": ids["shoe_id"], "title": "x", "priority": "normal", "items": []}),
        ("/v1/auto-key-jobs", {"customer_id": ids["customer_id"], "title": "x", "key_quantity": 1,
                               "priority": "normal", "status": "awaiting_quote",
                               "programming_status": "pending", "deposit_cents": 0, "cost_cents": 0}),
    ]
    bad = []
    for path, body in attempts:
        r = client.post(path, headers=b, json=body)
        if r.status_code < 400:
            bad.append((path, r.status_code))
    assert not bad, f"foreign-key injection accepted: {bad}"
    r = client.post(f"/v1/repair-jobs/{ids['job_id']}/messages", headers=b, json={"body": "hi"})
    assert r.status_code in (403, 404), r.text


def test_forged_and_mismatched_tokens_rejected(world):
    from app.security import create_access_token
    client, ids = world["client"], world["ids"]
    me_b = client.get("/v1/auth/session", headers=world["b"]).json()
    b_tenant = me_b.get("tenant_id") or me_b["user"]["tenant_id"]
    # A's user id inside B's tenant claim
    tok, _ = create_access_token(b_tenant, ids["user_id"], "intake")
    assert client.get("/v1/customers", headers={"Authorization": f"Bearer {tok}"}).status_code == 401
    # Role claim escalated beyond the DB row
    me_a = client.get("/v1/auth/session", headers=world["a"]).json()
    a_tenant = me_a.get("tenant_id") or me_a["user"]["tenant_id"]
    tok2, _ = create_access_token(a_tenant, ids["user_id"], "owner")
    assert client.get("/v1/users", headers={"Authorization": f"Bearer {tok2}"}).status_code == 401
    # Refresh token used as access token
    from app.security import create_refresh_token
    rt, _ = create_refresh_token(a_tenant, ids["user_id"], "intake")
    assert client.get("/v1/customers", headers={"Authorization": f"Bearer {rt}"}).status_code == 401
    # alg=none
    import base64, json
    h = base64.urlsafe_b64encode(json.dumps({"alg": "none", "typ": "JWT"}).encode()).rstrip(b"=").decode()
    p = base64.urlsafe_b64encode(json.dumps({"sub": ids["user_id"], "tenant_id": a_tenant,
                                             "user_id": ids["user_id"], "role": "owner"}).encode()).rstrip(b"=").decode()
    assert client.get("/v1/users", headers={"Authorization": f"Bearer {h}.{p}."}).status_code == 401


def test_attachments_cross_tenant(world):
    client, a, b, ids = world["client"], world["a"], world["b"], world["ids"]
    key = ids["storage_key"]
    assert client.get(f"/v1/attachments/download/{key}", headers=a).status_code in (200, 302)
    assert client.get(f"/v1/attachments/download/{key}", headers=b).status_code == 404
    assert client.get(f"/v1/attachments/download-link/{key}", headers=b).status_code == 404
    lst = client.get("/v1/attachments", headers=b, params={"repair_job_id": ids["job_id"]})
    assert lst.status_code in (200, 404) and key not in lst.text
    up = client.post("/v1/attachments", headers=b, params={"repair_job_id": ids["job_id"]},
                     files={"file": ("x.txt", b"x", "text/plain")})
    assert up.status_code == 404
    # No credentials at all
    assert client.get(f"/v1/attachments/download/{key}").status_code == 401


def test_intake_role_cannot_bulk_export_or_manage(world):
    """Expected secure behaviour: lowest role must not dump every customer record.
    (AUDIT FINDING: /v1/auth/export-my-data has no role check.)"""
    client, ids = world["client"], world["ids"]
    # Create an intake user in a fresh tenant so we can log in as them.
    h, slug, _ = _bootstrap(client, "i")
    email = f"intake-{uuid4().hex[:6]}@example.test"
    assert client.post("/v1/users", headers=h, json={"email": email, "full_name": "I",
                       "password": "supersecret123", "role": "intake"}).status_code == 201
    lg = client.post("/v1/auth/login", json={"tenant_slug": slug, "email": email, "password": "supersecret123"})
    ih = {"Authorization": f"Bearer {lg.json()['access_token']}"}
    assert client.post("/v1/users", headers=ih, json={"email": "z@example.test", "full_name": "Z",
                       "password": "supersecret123", "role": "owner"}).status_code == 403
    assert client.get("/v1/auth/export-my-data", headers=ih).status_code in (401, 403), \
        "intake role can bulk-export all customer PII via /v1/auth/export-my-data"


def test_twilio_signature_enforced_outside_test_env(world, monkeypatch):
    from app.config import settings
    from app.routes import sms_webhook as sw
    client = world["client"]
    monkeypatch.setattr(settings, "app_env", "staging")
    monkeypatch.setattr(settings, "twilio_auth_token", "tok_audit")
    monkeypatch.setattr(settings, "public_base_url", "https://example.test")
    data = {"From": "+61400000111", "Body": "YES", "MessageSid": "SMaudit1"}
    assert client.post("/v1/webhook/sms/incoming", data=data).status_code == 403
    assert client.post("/v1/webhook/sms/incoming", data=data,
                       headers={"X-Twilio-Signature": "AAAA"}).status_code == 403
    import hashlib, hmac
    from base64 import b64encode
    url = "https://example.test/v1/webhook/sms/incoming"
    sig = b64encode(hmac.new(b"tok_audit", (url + "".join(k + data[k] for k in sorted(data))).encode(),
                             hashlib.sha1).digest()).decode()
    r1 = client.post("/v1/webhook/sms/incoming", data=data, headers={"X-Twilio-Signature": sig})
    r2 = client.post("/v1/webhook/sms/incoming", data=data, headers={"X-Twilio-Signature": sig})
    assert r1.status_code == 200
    # Documents the absence of replay protection: an identical, validly-signed
    # delivery is processed again (JobMessage written twice). Flip to == 200 / dedupe
    # on MessageSid when fixed.
    assert r2.status_code in (200, 409)


def test_production_requires_twilio_token(monkeypatch, world):
    from app.config import settings
    monkeypatch.setattr(settings, "app_env", "production")
    monkeypatch.setattr(settings, "twilio_auth_token", "")
    r = world["client"].post("/v1/webhook/sms/incoming", data={"From": "+61400000111", "Body": "YES"})
    assert r.status_code == 403
