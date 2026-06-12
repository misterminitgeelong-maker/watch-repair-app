"""Cross-tenant isolation probes.

Tenant scoping is enforced by hand-written ``tenant_id ==`` filters in every
route, so one forgotten filter silently leaks one shop's data to another.
These tests create a fully-populated tenant A and a hostile tenant B, then:

1. hit every resource endpoint directly with B's token and A's resource ids,
2. walk *all* registered GET routes generically, substituting A's ids into
   path parameters, asserting no response ever contains A's data,
3. attempt mutations on A's resources with B's token.

If a new route leaks, the generic walker should catch it without this file
needing to know the route exists.
"""
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from app.main import app


@pytest.fixture(scope="module")
def tenants(request):
    """Tenant A with data + tenant B (hostile). Module-scoped for speed."""
    client = TestClient(app)

    def bootstrap(label: str) -> dict[str, str]:
        suffix = uuid4().hex[:8]
        slug = f"iso-{label}-{suffix}"
        email = f"owner-{suffix}@example.test"
        res = client.post(
            "/v1/auth/bootstrap",
            json={
                "tenant_name": f"Isolation {label}",
                "tenant_slug": slug,
                "owner_email": email,
                "owner_full_name": f"Owner {label}",
                "owner_password": "supersecret123",
            },
        )
        assert res.status_code == 200, res.text
        login = client.post(
            "/v1/auth/login",
            json={"tenant_slug": slug, "email": email, "password": "supersecret123"},
        )
        assert login.status_code == 200, login.text
        return {"Authorization": f"Bearer {login.json()['access_token']}"}

    a = bootstrap("a")
    b = bootstrap("b")

    # Populate tenant A with one of everything reachable via the API.
    ids: dict[str, str] = {}

    cust = client.post(
        "/v1/customers",
        headers=a,
        json={"full_name": "Secret Customer", "email": "secret@example.test", "phone": "0400000001"},
    )
    assert cust.status_code == 201, cust.text
    ids["customer_id"] = cust.json()["id"]

    watch = client.post(
        "/v1/watches",
        headers=a,
        json={"customer_id": ids["customer_id"], "brand": "SecretBrand", "model": "SecretModel"},
    )
    assert watch.status_code == 201, watch.text
    ids["watch_id"] = watch.json()["id"]

    job = client.post(
        "/v1/repair-jobs",
        headers=a,
        json={"watch_id": ids["watch_id"], "title": "Secret repair", "priority": "normal"},
    )
    assert job.status_code == 201, job.text
    ids["job_id"] = job.json()["id"]

    quote = client.post(
        "/v1/quotes",
        headers=a,
        json={
            "repair_job_id": ids["job_id"],
            "line_items": [
                {"item_type": "labor", "description": "Secret work", "quantity": 1, "unit_price_cents": 10000}
            ],
        },
    )
    assert quote.status_code == 201, quote.text
    ids["quote_id"] = quote.json()["id"]

    return {"client": client, "a": a, "b": b, "ids": ids}


# ── 1. Direct resource probes ───────────────────────────────────────────────

DIRECT_PATHS = [
    "/v1/customers/{customer_id}",
    "/v1/watches/{watch_id}",
    "/v1/repair-jobs/{job_id}",
    "/v1/repair-jobs/{job_id}/status-history",
    "/v1/repair-jobs/{job_id}/sms-log",
    "/v1/repair-jobs/{job_id}/messages",
    "/v1/quotes/{quote_id}/line-items",
]


@pytest.mark.parametrize("template", DIRECT_PATHS)
def test_direct_resource_access_denied(tenants, template):
    client, b, ids = tenants["client"], tenants["b"], tenants["ids"]
    path = template.format(**ids)
    res = client.get(path, headers=b)
    assert res.status_code in (403, 404), (
        f"{path} returned {res.status_code} for another tenant: {res.text[:300]}"
    )


# ── 2. List endpoints must not include tenant A's records ───────────────────

LIST_PATHS = [
    "/v1/customers",
    "/v1/watches",
    "/v1/repair-jobs",
    "/v1/quotes",
    "/v1/invoices",
]


@pytest.mark.parametrize("path", LIST_PATHS)
def test_list_endpoints_exclude_other_tenant(tenants, path):
    client, b, ids = tenants["client"], tenants["b"], tenants["ids"]
    res = client.get(path, headers=b)
    assert res.status_code == 200, res.text
    body = res.text
    for key, value in ids.items():
        assert value not in body, f"{path} leaked tenant A's {key} to tenant B"
    assert "Secret" not in body, f"{path} leaked tenant A's data to tenant B"


# ── 3. Generic walker over every registered GET route ───────────────────────

def _walkable_get_routes():
    """All GET routes whose path params we can fill with tenant A's ids."""
    param_map_keys = {"customer_id", "watch_id", "job_id", "quote_id", "invoice_id", "id"}
    routes = []
    for route in app.routes:
        methods = getattr(route, "methods", None) or set()
        path = getattr(route, "path", "")
        if "GET" not in methods or not path.startswith("/v1/"):
            continue
        if "/public/" in path or path.startswith("/v1/auth"):
            continue  # public token routes + auth endpoints are out of scope
        params = [p.strip("{}") for p in path.split("/") if p.startswith("{")]
        if not params:
            continue
        if all(p in param_map_keys for p in params):
            routes.append(path)
    return sorted(set(routes))


@pytest.mark.parametrize("template", _walkable_get_routes())
def test_generic_get_routes_do_not_leak(tenants, template):
    client, b, ids = tenants["client"], tenants["b"], tenants["ids"]
    # Fill any recognised param; unknown resource types get the repair job id,
    # which simply 404s on mismatched routes (still a pass — nothing leaked).
    values = {**ids, "invoice_id": ids["job_id"], "id": ids["job_id"]}
    path = template.format(**{k: values[k] for k in values})
    res = client.get(path, headers=b)
    if res.status_code == 200:
        body = res.text
        leaked = [k for k, v in ids.items() if v in body] + (["text"] if "Secret" in body else [])
        assert not leaked, f"{template} returned 200 leaking {leaked} to another tenant"


# ── 4. Mutations on another tenant's resources must be rejected ─────────────

def test_patch_other_tenant_job_rejected(tenants):
    client, a, b, ids = tenants["client"], tenants["a"], tenants["b"], tenants["ids"]
    res = client.patch(
        f"/v1/repair-jobs/{ids['job_id']}",
        headers=b,
        json={"title": "HACKED"},
    )
    assert res.status_code in (403, 404), res.text
    # Tenant A's job is untouched
    own = client.get(f"/v1/repair-jobs/{ids['job_id']}", headers=a)
    assert own.status_code == 200
    assert own.json()["title"] == "Secret repair"


def test_delete_other_tenant_job_rejected(tenants):
    client, a, b, ids = tenants["client"], tenants["a"], tenants["b"], tenants["ids"]
    res = client.delete(f"/v1/repair-jobs/{ids['job_id']}", headers=b)
    assert res.status_code in (403, 404), res.text
    own = client.get(f"/v1/repair-jobs/{ids['job_id']}", headers=a)
    assert own.status_code == 200


def test_quote_send_for_other_tenant_rejected(tenants):
    client, b, ids = tenants["client"], tenants["b"], tenants["ids"]
    res = client.post(f"/v1/quotes/{ids['quote_id']}/send", headers=b, json={})
    assert res.status_code in (400, 403, 404, 422), (
        f"quote send returned {res.status_code} for another tenant: {res.text[:300]}"
    )
