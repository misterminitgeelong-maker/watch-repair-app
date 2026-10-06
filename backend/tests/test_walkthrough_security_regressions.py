"""Regression coverage for HQ permissions and delegated/revoked sessions."""
import io
from uuid import UUID, uuid4
from sqlmodel import Session, select
from app.database import engine
from app.dependencies import invalidate_auth_cache
from app.models import ParentAccount, ParentAccountUser, ParentAccountSite, User
from app.parent_network import parent_role_for_user
from app.security import decode_access_token
from test_attachments_hardening import _create_repair_job
from test_parent_network_model import _network, client, _h, _login

def viewer_network():
    net = _network(uuid4().hex[:8])
    with Session(engine) as s:
        u = s.exec(select(User).where(User.email == net["hq_email"]).where(User.tenant_id == UUID(net["hq_tenant_id"]))).one()
        p = s.exec(select(ParentAccount).where(ParentAccount.owner_email == net["hq_email"])).first()
        site = s.exec(select(ParentAccountSite).where(ParentAccountSite.parent_account_id == p.id).where(ParentAccountSite.tenant_id == u.tenant_id)).one()
        site.network_role = "hq"
        s.add(site)
        grant = s.exec(select(ParentAccountUser).where(ParentAccountUser.user_id == u.id).where(ParentAccountUser.parent_account_id == p.id)).first()
        if grant is None:
            grant = ParentAccountUser(user_id=u.id, parent_account_id=p.id, role="hq_viewer")
        grant.role = "hq_viewer"
        s.add(grant); s.commit()
    invalidate_auth_cache()
    return net

def test_viewer_cannot_switch_to_shop_owner():
    net = viewer_network()
    r = client.patch("/v1/auth/session/site", headers=net["hq"], json={"tenant_id":net["shop_id"]})
    assert r.status_code == 403, r.text

def test_viewer_cannot_create_implicit_admin():
    net = viewer_network()
    suffix=uuid4().hex[:8]; email=f"newadmin-{suffix}@example.test"
    r=client.post("/v1/users", headers=net["hq"], json={"email":email,"full_name":"Synthetic owner","password":"TestPassword123!","role":"owner"})
    assert r.status_code == 403, r.text

def test_viewer_cannot_read_pending_claim_token():
    net=_network(uuid4().hex[:8])
    r=client.post(f"/v1/parent-accounts/me/sites/{net['shop_id']}/invite",headers=net["hq"])
    assert r.status_code == 200,r.text
    # Fixture downgrade after creating a legitimate pending owner invite.
    with Session(engine) as s:
        u=s.exec(select(User).where(User.email==net["hq_email"]).where(User.tenant_id==UUID(net["hq_tenant_id"]))).one()
        p=s.exec(select(ParentAccount).where(ParentAccount.owner_email==net["hq_email"])).first()
        grant=s.exec(select(ParentAccountUser).where(ParentAccountUser.user_id==u.id).where(ParentAccountUser.parent_account_id==p.id)).first()
        if grant is None: grant=ParentAccountUser(user_id=u.id,parent_account_id=p.id,role="hq_viewer")
        grant.role="hq_viewer";s.add(grant);s.commit()
    invalidate_auth_cache()
    r=client.get(f"/v1/parent-accounts/me/sites/{net['shop_id']}/invite",headers=net["hq"])
    assert r.status_code == 403, r.text

def test_support_cannot_mint_refresh_session():
    net=_network(uuid4().hex[:8])
    r=client.post(f"/v1/parent-accounts/me/sites/{net['shop_id']}/enter",headers=net["hq"],json={"reason":"Local synthetic fixture"})
    assert r.status_code==200 and r.json()["expires_in_seconds"]==1800,r.text
    support=_h(r.json()["access_token"])
    r=client.patch("/v1/auth/session/site",headers=support,json={"tenant_id":net["shop_id"]})
    assert r.status_code==403,r.text
    assert client.get("/v1/customers", headers=support).status_code == 200
    assert client.post("/v1/auth/refresh", json={"refresh_token":support["Authorization"].split()[1]}).status_code == 401

def test_revoked_session_cannot_download_attachment():
    net=_network(uuid4().hex[:8])
    h=net["hq"]
    c=client.post("/v1/customers",headers=h,json={"full_name":"Synthetic customer"})
    assert c.status_code==201,c.text
    job_id = _create_repair_job(h)
    a=client.post("/v1/attachments",headers=h,params={"repair_job_id":job_id},files={"file":("note.txt",io.BytesIO(b"synthetic attachment"),"text/plain")})
    assert a.status_code==201,a.text
    key=a.json()["storage_key"]
    active=client.get(f"/v1/attachments/download/{key}",headers=h)
    assert active.status_code==200 and active.content==b"synthetic attachment",active.text
    link=client.get(f"/v1/attachments/download-link/{key}",headers=h)
    assert link.status_code==200,link.text
    assert client.get(link.json()["download_url"]).status_code==200
    r=client.post("/v1/auth/logout",headers=h)
    assert r.status_code==200,r.text
    normal=client.get("/v1/customers",headers=h)
    assert normal.status_code==401,normal.text
    r=client.get(f"/v1/attachments/download/{key}",headers=h)
    assert r.status_code==401,r.text

def test_admin_switch_and_shop_staff_management_remain_allowed():
    net = _network(uuid4().hex[:8])
    r = client.patch("/v1/auth/session/site", headers=net["hq"], json={"tenant_id":net["shop_id"]})
    assert r.status_code == 200, r.text
    assert r.json()["refresh_token"]
    assert decode_access_token(r.json()["access_token"]).role == "owner"
    r = client.post("/v1/users", headers=_h(r.json()["access_token"]), json={"email":f"tech-{uuid4().hex}@example.test","full_name":"Technician","password":"TestPassword123!","role":"tech"})
    assert r.status_code == 201, r.text

def test_downgraded_hq_owner_cannot_reset_or_delete_an_admin():
    net = viewer_network()
    with Session(engine) as s:
        actor=s.exec(select(User).where(User.email==net["hq_email"]).where(User.tenant_id==UUID(net["hq_tenant_id"]))).one()
        target=User(tenant_id=actor.tenant_id,email=f"admin-{uuid4().hex}@example.test",full_name="Admin",role="owner",password_hash=actor.password_hash,is_active=True)
        s.add(target);s.commit();s.refresh(target);target_id=str(target.id)
    for payload in ({"password":"ChangedPassword123!"},{"role":"owner"},{"is_active":True}):
        r=client.patch(f"/v1/users/{target_id}",headers=net["hq"],json=payload)
        assert r.status_code==403,r.text
    assert client.delete(f"/v1/users/{target_id}",headers=net["hq"]).status_code==403

def test_regional_viewer_cannot_switch_outside_region():
    from app.models import Region
    net=viewer_network()
    with Session(engine) as s:
        parent=s.exec(select(ParentAccount).where(ParentAccount.owner_email==net["hq_email"])).first()
        region=Region(parent_account_id=parent.id,code="TEST",name=f"Region-{uuid4().hex[:6]}")
        s.add(region);s.flush()
        actor=s.exec(select(User).where(User.email==net["hq_email"]).where(User.tenant_id==UUID(net["hq_tenant_id"]))).one()
        grant=s.exec(select(ParentAccountUser).where(ParentAccountUser.parent_account_id==parent.id).where(ParentAccountUser.user_id==actor.id)).one()
        grant.region_id=region.id;s.add(grant);s.commit()
    invalidate_auth_cache()
    r=client.patch("/v1/auth/session/site",headers=net["hq"],json={"tenant_id":net["shop_id"]})
    assert r.status_code==403,r.text

def test_unmarked_short_token_cannot_be_exchanged():
    from app.security import create_access_token
    net=_network(uuid4().hex[:8])
    r=client.post(f"/v1/parent-accounts/me/sites/{net['shop_id']}/enter",headers=net["hq"],json={"reason":"Synthetic fixture"})
    claims=decode_access_token(r.json()["access_token"])
    assert claims.support_actor_user_id is not None
    token,_=create_access_token(claims.tenant_id,claims.user_id,claims.role,expires_minutes=30)
    r=client.patch("/v1/auth/session/site",headers=_h(token),json={"tenant_id":net["shop_id"]})
    assert r.status_code==403,r.text
    r=client.post("/v1/users",headers=_h(token),json={"email":f"owner-{uuid4().hex}@example.test","full_name":"Owner","password":"TestPassword123!","role":"owner"})
    assert r.status_code==403,r.text
    r=client.post(f"/v1/parent-accounts/me/sites/{net['op_id']}/enter",headers=_h(token),json={"reason":"Attempted nested support"})
    assert r.status_code==403,r.text
    assert client.patch(f"/v1/users/{claims.user_id}",headers=_h(token),json={"password":"ChangedPassword123!"}).status_code==403


def test_hq_admin_can_manage_hq_users():
    net=viewer_network()
    with Session(engine) as s:
        actor=s.exec(select(User).where(User.email==net["hq_email"]).where(User.tenant_id==UUID(net["hq_tenant_id"]))).one()
        grant=s.exec(select(ParentAccountUser).where(ParentAccountUser.user_id==actor.id)).one()
        grant.role="hq_admin";s.add(grant);s.commit()
    invalidate_auth_cache()
    r=client.post("/v1/users",headers=net["hq"],json={"email":f"owner-{uuid4().hex}@example.test","full_name":"Owner","password":"TestPassword123!","role":"owner"})
    assert r.status_code==201,r.text
    assert client.patch(f"/v1/users/{r.json()['id']}",headers=net["hq"],json={"full_name":"Updated"}).status_code==200


def test_platform_support_cannot_exchange_or_manage_credentials():
    net=_network(uuid4().hex[:8])
    with Session(engine) as s:
        actor=s.exec(select(User).where(User.email==net["hq_email"]).where(User.tenant_id==UUID(net["hq_tenant_id"]))).one()
        actor.role="platform_admin";s.add(actor);s.commit()
    invalidate_auth_cache()
    admin=_h(_login(net["hq_slug"],net["hq_email"]))
    r=client.post(f"/v1/platform-admin/enter-shop/{net['shop_id']}",headers=admin)
    assert r.status_code==200,r.text
    token=r.json()["access_token"]
    assert decode_access_token(token).support_actor_user_id is not None
    support=_h(token)
    assert client.get("/v1/customers",headers=support).status_code==200
    assert client.patch("/v1/auth/session/site",headers=support,json={"tenant_id":net["shop_id"]}).status_code==403
    assert client.post("/v1/users",headers=support,json={"email":f"owner-{uuid4().hex}@example.test","full_name":"Owner","password":"TestPassword123!","role":"owner"}).status_code==403
