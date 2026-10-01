from datetime import datetime, timedelta, timezone
from uuid import uuid4
from fastapi.testclient import TestClient
from sqlmodel import Session, select

from app.database import create_db_and_tables, engine
from app.main import app
from app.models import HqOwnerInvite, ParentAccount, ParentAccountSite, ParentAccountUser, Tenant, User, TenantEventLog
from app.security import hash_password, create_access_token
from app.routes import hq_owner_invites

client = TestClient(app)


def seed():
    create_db_and_tables()
    suffix = uuid4().hex[:8]
    with Session(engine) as db:
        admin_tenant = Tenant(name="Admin", slug=f"admin-{suffix}")
        hq = Tenant(name="HQ", slug=f"hq-{suffix}", plan_code="minit_hq", is_minit=True)
        retail = Tenant(name="Retail", slug=f"retail-{suffix}")
        db.add_all([admin_tenant, hq, retail]); db.flush()
        admin = User(tenant_id=admin_tenant.id, email=f"admin-{suffix}@test.com", full_name="Admin", role="platform_admin", password_hash=hash_password("Password2026!"))
        shop_owner = User(tenant_id=retail.id, email=f"shop-{suffix}@test.com", full_name="Shop", role="owner", password_hash=hash_password("Password2026!"))
        parent = ParentAccount(name="Minit HQ", owner_email=f"original-{suffix}@test.com")
        db.add_all([admin, shop_owner, parent]); db.flush()
        db.add(ParentAccountSite(parent_account_id=parent.id, tenant_id=hq.id, network_role="hq"))
        db.add(ParentAccountSite(parent_account_id=parent.id, tenant_id=retail.id, network_role="retail"))
        db.commit()
        admin_token, _ = create_access_token(admin.tenant_id, admin.id, admin.role)
        shop_token, _ = create_access_token(shop_owner.tenant_id, shop_owner.id, shop_owner.role)
        return {"parent_account_id": str(parent.id), "tenant_id": str(hq.id), "email": f"hq-owner-{suffix}@test.com", "full_name": "HQ Owner", "send_email": False}, {"Authorization": f"Bearer {admin_token}"}, {"Authorization": f"Bearer {shop_token}"}, str(retail.id)


def test_platform_invite_acceptance_and_permissions():
    payload, admin, shop, retail = seed()
    assert client.get('/v1/platform-admin/hq-owners', headers=shop).status_code == 403
    assert client.post('/v1/platform-admin/hq-owners', headers=shop, json=payload).status_code == 403
    assert client.post('/v1/platform-admin/hq-owners', headers=admin, json={**payload, 'tenant_id': retail}).status_code == 400
    created = client.post('/v1/platform-admin/hq-owners', headers=admin, json=payload)
    assert created.status_code == 200, created.text
    data = created.json(); token = data['invite_url'].rsplit('/', 1)[1]
    with Session(engine) as db:
        invite = db.exec(select(HqOwnerInvite).where(HqOwnerInvite.email == payload['email'])).one()
        assert token not in invite.token_hash and len(invite.token_hash) == 64
    public = client.get(f'/v1/public/hq-invite/{token}').json()
    assert public['email'] == payload['email'] and not public['existing_account']
    assert client.post(f'/v1/public/hq-invite/{token}/complete', json={'password': 'short'}).status_code == 400
    accepted = client.post(f'/v1/public/hq-invite/{token}/complete', json={'password': 'Password2026!'})
    assert accepted.status_code == 200, accepted.text
    assert client.post(f'/v1/public/hq-invite/{token}/complete', json={'password': 'Password2026!'}).status_code == 410
    headers = {'Authorization': f"Bearer {accepted.json()['access_token']}"}
    summary = client.get('/v1/parent-accounts/me', headers=headers)
    assert summary.status_code == 200 and summary.json()['parent_account_id'] == payload['parent_account_id']
    assert client.get('/v1/platform-admin/hq-owners', headers=headers).status_code == 403
    with Session(engine) as db:
        user = db.exec(select(User).where(User.email == payload['email'])).one()
        grant = db.exec(select(ParentAccountUser).where(ParentAccountUser.user_id == user.id)).one()
        assert grant.role == 'hq_admin' and str(grant.parent_account_id) == payload['parent_account_id']
        assert db.exec(select(TenantEventLog).where(TenantEventLog.entity_type == 'hq_owner_invite')).all()


def test_resend_revocation_expiry_and_existing_password():
    payload, admin, _, _ = seed()
    with Session(engine) as db:
        from uuid import UUID
        owner = User(tenant_id=UUID(payload['tenant_id']), email=payload['email'], full_name="Existing", role="owner", password_hash=hash_password('Existing2026!'))
        db.add(owner); db.commit()
        original_hash = owner.password_hash
    first = client.post('/v1/platform-admin/hq-owners', headers=admin, json=payload).json()
    second = client.post('/v1/platform-admin/hq-owners', headers=admin, json=payload).json()
    first_token = first['invite_url'].rsplit('/', 1)[1]; token = second['invite_url'].rsplit('/', 1)[1]
    assert client.get(f'/v1/public/hq-invite/{first_token}').status_code == 410
    assert client.get(f'/v1/public/hq-invite/{token}').json()['existing_account']
    assert client.post(f'/v1/public/hq-invite/{token}/complete', json={'password': 'Wrong2026!'}).status_code == 403
    assert client.post(f'/v1/public/hq-invite/{token}/complete', json={'password': 'Existing2026!'}).status_code == 200
    with Session(engine) as db:
        owner = db.exec(select(User).where(User.email == payload['email'])).one()
        assert owner.password_hash == original_hash and owner.full_name == 'Existing'
    third = client.post('/v1/platform-admin/hq-owners', headers=admin, json=payload).json()
    assert client.delete('/v1/platform-admin/hq-owners/' + third['id'], headers=admin).status_code == 200
    assert client.get('/v1/public/hq-invite/' + third['invite_url'].rsplit('/', 1)[1]).status_code == 410
    fourth = client.post('/v1/platform-admin/hq-owners', headers=admin, json=payload).json()
    with Session(engine) as db:
        invite = db.exec(select(HqOwnerInvite).where(HqOwnerInvite.email == payload['email'], HqOwnerInvite.status == 'pending')).one()
        invite.expires_at = datetime.now(timezone.utc) - timedelta(seconds=1); db.add(invite); db.commit()
    assert client.post('/v1/public/hq-invite/' + fourth['invite_url'].rsplit('/', 1)[1] + '/complete', json={'password': 'Existing2026!'}).status_code == 410


def test_email_delivery_and_listing(monkeypatch):
    payload, admin, _, _ = seed()
    messages = []
    monkeypatch.setattr(hq_owner_invites.email_client, 'send_email_from_payload', lambda **kwargs: (messages.append(kwargs) or True, None))
    response = client.post('/v1/platform-admin/hq-owners', headers=admin, json={**payload, 'send_email': True})
    assert response.status_code == 200 and response.json()['email_sent']
    assert messages[0]['to_email'] == payload['email'] and '/hq-invite/' in messages[0]['payload']['body_plain']
    listing = client.get('/v1/platform-admin/hq-owners', headers=admin).json()
    assert any(a['tenant_id'] == payload['tenant_id'] for a in listing['accounts'])
    assert 'token_hash' not in str(listing) and response.json()['invite_url'] not in str(listing)
