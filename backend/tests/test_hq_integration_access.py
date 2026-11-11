"""HQ membership is authoritative; keys/hooks remain owned by the active tenant."""
from uuid import uuid4

from sqlmodel import Session, select

from app.database import engine
from app.models import ParentAccount, ParentAccountSite, ParentAccountUser, Tenant, TenantApiKey, TenantWebhookSubscription, User
from app.security import hash_password


def make_account(client, *, hq: bool):
    label = uuid4().hex[:10]
    slug = f"integration-{label}"
    email = f"owner-{label}@example.test"
    response = client.post("/v1/auth/bootstrap", json={"tenant_name": slug, "tenant_slug": slug,
        "owner_email": email, "owner_full_name": "Owner", "owner_password": "supersecret123"})
    assert response.status_code == 200, response.text
    with Session(engine) as session:
        tenant = session.exec(select(Tenant).where(Tenant.slug == slug)).one()
        user = session.exec(select(User).where(User.tenant_id == tenant.id)).one()
        parent = ParentAccount(name=slug, owner_email=email)
        session.add(parent); session.flush()
        session.add(ParentAccountSite(parent_account_id=parent.id, tenant_id=tenant.id, network_role="hq" if hq else "retail"))
        # Explicit HQ rights while entered into retail still must not grant integration management.
        session.add(ParentAccountUser(parent_account_id=parent.id, user_id=user.id, role="hq_admin"))
        session.commit(); tenant_id = tenant.id
    login = client.post("/v1/auth/login", json={"tenant_slug": slug, "email": email, "password": "supersecret123"})
    assert login.status_code == 200
    return tenant_id, {"Authorization": f"Bearer {login.json()['access_token']}"}


def test_hq_can_only_list_and_delete_its_own_keys_and_webhooks(client, monkeypatch):
    monkeypatch.setenv("WEBHOOK_ALLOWED_HOSTS", "hooks.example.test")
    _, a = make_account(client, hq=True); _, b = make_account(client, hq=True)
    key = client.post("/v1/tenant/api-keys", headers=a, json={"name": "A's key"})
    hook = client.post("/v1/tenant/webhooks", headers=a, json={"url": "https://hooks.example.test/hook", "event_types": ["*"]})
    assert key.status_code == 201 and hook.status_code == 201
    assert len(client.get("/v1/tenant/api-keys", headers=a).json()) == 1
    assert client.get("/v1/tenant/api-keys", headers=b).json() == []
    assert client.get("/v1/tenant/webhooks", headers=b).json() == []
    assert client.delete(f"/v1/tenant/api-keys/{key.json()['id']}", headers=b).status_code == 404
    assert client.delete(f"/v1/tenant/webhooks/{hook.json()['id']}", headers=b).status_code == 404
    assert client.delete(f"/v1/tenant/api-keys/{key.json()['id']}", headers=a).status_code == 204
    assert client.delete(f"/v1/tenant/webhooks/{hook.json()['id']}", headers=a).status_code == 204


def test_retail_hq_grant_does_not_grant_management_or_revoke_existing_keys(client):
    tenant_id, headers = make_account(client, hq=False)
    with Session(engine) as session:
        key = TenantApiKey(tenant_id=tenant_id, name="Existing key", key_prefix="msk_existing", key_hash=hash_password("existing-test-key"))
        hook = TenantWebhookSubscription(tenant_id=tenant_id, url="https://hooks.example.test/old", event_types="*", secret="existing-test-secret")
        session.add(key); session.add(hook); session.commit(); key_id, hook_id = key.id, hook.id
    assert client.get("/v1/auth/session", headers=headers).json()["can_manage_integrations"] is False
    for path in ("/v1/tenant/api-keys", "/v1/tenant/webhooks"):
        assert client.get(path, headers=headers).status_code == 403
    assert client.delete(f"/v1/tenant/api-keys/{key_id}", headers=headers).status_code == 403
    assert client.delete(f"/v1/tenant/webhooks/{hook_id}", headers=headers).status_code == 403
    with Session(engine) as session:
        assert session.get(TenantApiKey, key_id).is_active
        assert session.get(TenantWebhookSubscription, hook_id).is_active
