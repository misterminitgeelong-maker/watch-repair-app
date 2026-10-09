"""Platform admin creates company HQs; each HQ's modules gate what it can open."""
from uuid import UUID, uuid4

from fastapi.testclient import TestClient
from sqlmodel import Session, select

from app.database import create_db_and_tables, engine
from app.main import app
from app.models import ParentAccount, ParentAccountEventLog, ParentAccountSite, Tenant, User
from app.security import create_access_token, hash_password

client = TestClient(app)
OVERVIEW = "/v1/parent-accounts/me/operations/overview"


def _admin():
    create_db_and_tables()
    suffix = uuid4().hex[:8]
    with Session(engine) as db:
        tenant = Tenant(name="Admin", slug=f"admin-{suffix}")
        db.add(tenant); db.flush()
        user = User(tenant_id=tenant.id, email=f"admin-{suffix}@test.com", full_name="Admin", role="platform_admin", password_hash=hash_password("Password2026!"))
        other = Tenant(name="Shop", slug=f"shop-{suffix}")
        db.add_all([user, other]); db.flush()
        shop_owner = User(tenant_id=other.id, email=f"o-{suffix}@test.com", full_name="O", role="owner", password_hash=hash_password("Password2026!"))
        db.add(shop_owner); db.commit()
        a, _ = create_access_token(user.tenant_id, user.id, user.role)
        s, _ = create_access_token(shop_owner.tenant_id, shop_owner.id, shop_owner.role)
    return {"Authorization": f"Bearer {a}"}, {"Authorization": f"Bearer {s}"}


def _payload(slug, modules, **extra):
    return {"slug": slug, "display_name": f"Co {slug}", "brand_color": "#00aa55", "modules": modules,
            "site_plans": ["basic_shoe"], "owner_name": "Owner", "owner_email": f"{slug}@test.com", "send_invite": False, **extra}


def _owner_headers(created):
    token = created["invite_url"].rsplit("/", 1)[1]
    done = client.post(f"/v1/public/hq-invite/{token}/complete", json={"password": "Password2026!"})
    assert done.status_code == 200, done.text
    return {"Authorization": f"Bearer {done.json()['access_token']}"}


def test_only_platform_admins_manage_hqs():
    admin, shop = _admin()
    assert client.get("/v1/platform-admin/hqs", headers=shop).status_code == 403
    assert client.post("/v1/platform-admin/hqs", headers=shop, json=_payload("nope-co", ["shoe"])).status_code == 403
    assert client.get("/v1/platform-admin/hqs", headers=admin).status_code == 200


def test_create_hq_builds_tenant_network_settings_and_invite():
    admin, _ = _admin()
    slug = f"bk-{uuid4().hex[:6]}"
    res = client.post("/v1/platform-admin/hqs", headers=admin, json=_payload(slug, ["shoe", "stock"]))
    assert res.status_code == 201, res.text
    data = res.json()
    assert data["tenant_slug"] == slug and data["modules"] == ["shoe", "stock"] and data["shop_count"] == 0
    assert data["invite_url"] and data["email_sent"] is False
    with Session(engine) as db:
        tenant = db.exec(select(Tenant).where(Tenant.slug == slug)).one()
        assert tenant.plan_code == "minit_hq" and tenant.is_minit is False
        site = db.exec(select(ParentAccountSite).where(ParentAccountSite.tenant_id == tenant.id)).one()
        assert site.network_role == "hq"
        assert db.exec(select(ParentAccountEventLog).where(ParentAccountEventLog.parent_account_id == site.parent_account_id, ParentAccountEventLog.event_type == "hq_created")).first()
    listed = client.get("/v1/platform-admin/hqs", headers=admin).json()
    assert any(h["tenant_slug"] == slug for h in listed["hqs"])
    assert "shoe" in listed["available_modules"] and "minit_hq" not in listed["available_site_plans"]


def test_create_hq_validation():
    admin, _ = _admin()
    slug = f"v-{uuid4().hex[:6]}"
    assert client.post("/v1/platform-admin/hqs", headers=admin, json=_payload("minit-evil", ["shoe"])).status_code == 400
    assert client.post("/v1/platform-admin/hqs", headers=admin, json=_payload("mmsupport", ["shoe"])).status_code == 400
    assert client.post("/v1/platform-admin/hqs", headers=admin, json=_payload(slug, ["teleport"])).status_code == 400
    assert client.post("/v1/platform-admin/hqs", headers=admin, json=_payload(slug, ["shoe"], brand_color="red")).status_code == 400
    assert client.post("/v1/platform-admin/hqs", headers=admin, json=_payload(slug, ["shoe"], site_plans=["minit_hq"])).status_code == 400
    assert client.post("/v1/platform-admin/hqs", headers=admin, json=_payload(slug, ["shoe"], logo_url="http://insecure/x.png")).status_code == 400
    assert client.post("/v1/platform-admin/hqs", headers=admin, json=_payload(slug, ["shoe"], owner_email="not-an-email")).status_code == 400
    assert client.post("/v1/platform-admin/hqs", headers=admin, json=_payload(slug, ["shoe"])).status_code == 201
    assert client.post("/v1/platform-admin/hqs", headers=admin, json=_payload(slug, ["shoe"])).status_code == 409


def test_modules_gate_hq_routes_and_edits_apply_immediately():
    admin, _ = _admin()
    shoe_only = client.post("/v1/platform-admin/hqs", headers=admin, json=_payload(f"s-{uuid4().hex[:6]}", ["shoe"])).json()
    mobile = client.post("/v1/platform-admin/hqs", headers=admin, json=_payload(f"m-{uuid4().hex[:6]}", ["mobile_services"])).json()
    shoe_h, mobile_h = _owner_headers(shoe_only), _owner_headers(mobile)
    blocked = client.get(OVERVIEW, headers=shoe_h)
    assert blocked.status_code == 403 and "mobile_services" in blocked.json()["detail"]
    assert client.get(OVERVIEW, headers=mobile_h).status_code == 200
    # Turn the module on: the shoe HQ can open it straight away.
    edit = client.patch(f"/v1/platform-admin/hqs/{shoe_only['parent_account_id']}", headers=admin,
                        json={"display_name": "Shoe Co", "modules": ["shoe", "mobile_services"], "site_plans": ["basic_shoe"]})
    assert edit.status_code == 200 and edit.json()["modules"] == ["mobile_services", "shoe"]
    assert client.get(OVERVIEW, headers=shoe_h).status_code == 200
    with Session(engine) as db:
        assert db.exec(select(ParentAccountEventLog).where(
            ParentAccountEventLog.parent_account_id == UUID(shoe_only["parent_account_id"]),
            ParentAccountEventLog.event_type == "hq_settings_updated")).first()
    assert client.patch(f"/v1/platform-admin/hqs/{uuid4()}", headers=admin,
                        json={"display_name": "x", "modules": [], "site_plans": []}).status_code == 404


def test_hqs_are_isolated_from_each_other():
    admin, _ = _admin()
    a = client.post("/v1/platform-admin/hqs", headers=admin, json=_payload(f"a-{uuid4().hex[:6]}", ["mobile_services"])).json()
    b = client.post("/v1/platform-admin/hqs", headers=admin, json=_payload(f"b-{uuid4().hex[:6]}", ["mobile_services"])).json()
    assert a["parent_account_id"] != b["parent_account_id"] and a["tenant_id"] != b["tenant_id"]
    a_summary = client.get("/v1/parent-accounts/me", headers=_owner_headers(a)).json()
    b_summary = client.get("/v1/parent-accounts/me", headers=_owner_headers(b)).json()
    assert a_summary["parent_account_id"] == a["parent_account_id"]
    assert b_summary["parent_account_id"] == b["parent_account_id"]


def test_minit_hq_without_a_settings_row_still_passes_the_gate():
    """Databases that predate the settings row keep working for Minit."""
    create_db_and_tables()
    suffix = uuid4().hex[:8]
    with Session(engine) as db:
        hq = Tenant(name="Old Minit HQ", slug=f"oldhq-{suffix}", plan_code="minit_hq", is_minit=True)
        db.add(hq); db.flush()
        owner = User(tenant_id=hq.id, email=f"o-{suffix}@test.com", full_name="O", role="owner", password_hash=hash_password("Password2026!"))
        parent = ParentAccount(name="Old Minit", owner_email=owner.email)
        db.add_all([owner, parent]); db.flush()
        db.add(ParentAccountSite(parent_account_id=parent.id, tenant_id=hq.id, network_role="hq"))
        db.commit()
        token, _ = create_access_token(owner.tenant_id, owner.id, owner.role)
    assert client.get(OVERVIEW, headers={"Authorization": f"Bearer {token}"}).status_code != 403


def test_hq_plan_is_locked_for_the_hq_and_shop_plans_follow_the_hq():
    admin, _ = _admin()
    created = client.post("/v1/platform-admin/hqs", headers=admin, json=_payload(f"p-{uuid4().hex[:6]}", ["shoe"])).json()
    res = client.patch(f"/v1/platform-admin/tenants/{created['tenant_id']}/plan", headers=admin, json={"plan_code": "basic_shoe"})
    assert res.status_code == 400 and "minit_hq" in res.json()["detail"]
    with Session(engine) as db:
        shop = Tenant(name="BK Shop", slug=f"shop-{uuid4().hex[:6]}", plan_code="basic_shoe")
        db.add(shop); db.flush()
        db.add(ParentAccountSite(parent_account_id=UUID(created["parent_account_id"]), tenant_id=shop.id, network_role="retail"))
        db.commit()
        shop_id = str(shop.id)
    assert client.patch(f"/v1/platform-admin/tenants/{shop_id}/plan", headers=admin, json={"plan_code": "basic_watch"}).status_code == 400
    assert client.patch(f"/v1/platform-admin/tenants/{shop_id}/plan", headers=admin, json={"plan_code": "basic_shoe"}).status_code == 200


def test_hq_config_endpoint_reports_the_callers_own_settings():
    admin, shop = _admin()
    made = client.post("/v1/platform-admin/hqs", headers=admin, json=_payload(f"c-{uuid4().hex[:6]}", ["shoe", "stock"])).json()
    headers = _owner_headers(made)
    cfg = client.get("/v1/parent-accounts/me/hq-config", headers=headers)
    assert cfg.status_code == 200
    body = cfg.json()
    assert body["modules"] == ["shoe", "stock"] and body["brand_color"] == "#00aa55" and body["logo_url"] is None
    assert body["display_name"] == made["display_name"]
    assert client.get("/v1/parent-accounts/me/hq-config", headers=shop).status_code == 403
