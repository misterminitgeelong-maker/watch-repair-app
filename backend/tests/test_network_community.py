"""API contract and boundary tests for state hubs, shop DMs and announcements."""
from datetime import datetime, timezone
from uuid import UUID, uuid4

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlmodel import Session, select

from app.database import unscoped_session, engine as database_engine
from app.dependencies import AuthContext, get_auth_context
from app.models import ParentAccount, ParentAccountSite, ParentAccountUser, Region, Tenant, User
from app.models.network_community import AnnouncementReceipt, StateHubMessage
from app.routes.network_community import router, state_code
from app.routes.network_messages import router as direct_router


@pytest.fixture
def world():
    engine = database_engine
    current = {}
    with Session(engine) as session:
        parent = ParentAccount(name="Minit", owner_email="hq@example.test")
        other_parent = ParentAccount(name="Other network", owner_email="other@example.test")
        session.add(parent)
        session.add(other_parent)
        session.flush()
        regions = {}
        for code in ("VIC SOUTH", "QLD WEST", "NZ NORTH"):
            region = Region(parent_account_id=parent.id, code=code, name=code)
            session.add(region)
            session.flush()
            regions[code] = region
        people = {}
        for name, code, role, parent_id in (
            ("vic", "VIC SOUTH", "retail", parent.id),
            ("vic2", "VIC SOUTH", "retail", parent.id),
            ("qld", "QLD WEST", "retail", parent.id),
            ("hq", None, "hq", parent.id),
            ("manager", None, "hq", parent.id),
            ("stranger", None, "retail", other_parent.id),
            ("unknown", None, "retail", parent.id),
        ):
            tenant = Tenant(name=name, slug=name + "-" + uuid4().hex, minit_region=code, is_minit=True)
            session.add(tenant)
            session.flush()
            user = User(tenant_id=tenant.id, email=name + "@example.test", full_name=name, password_hash="unused", role="owner")
            session.add(user)
            session.flush()
            site = ParentAccountSite(parent_account_id=parent_id, tenant_id=tenant.id, network_role=role,
                                     region_id=regions[code].id if code else None)
            session.add(site)
            people[name] = (tenant.id, user.id, site.id)
        manager_grant = ParentAccountUser(parent_account_id=parent.id, user_id=people["manager"][1],
                                          role="hq_viewer", region_id=regions["VIC SOUTH"].id)
        session.add(manager_grant)
        staff = User(tenant_id=people["vic"][0], email="staff@example.test", full_name="Staff", password_hash="unused", role="tech")
        session.add(staff)
        session.commit()
        people["staff"] = (people["vic"][0], staff.id, people["vic"][2])
        pid = str(parent.id)
    test_app = FastAPI()
    test_app.include_router(router)
    test_app.include_router(direct_router)

    def auth():
        return current["auth"]

    def db():
        with Session(engine) as session:
            yield session

    test_app.dependency_overrides[get_auth_context] = auth
    test_app.dependency_overrides[unscoped_session] = db
    client = TestClient(test_app)

    def as_user(name, support=False):
        tenant, user, _ = people[name]
        current["auth"] = AuthContext(tenant_id=tenant, user_id=user, support_actor_user_id=uuid4() if support else None)
        return client

    yield {"client": client, "as": as_user, "people": people, "parent": parent.id,
           "base": "/v1/network-community/" + pid, "engine": engine}


@pytest.mark.parametrize("raw,expected", [(" vic  south ", "VIC"), ("QLD-WEST", "QLD"), ("NZ NORTH", "NZ"), ("New South Wales", "NSW"), ("SW", None), ("SEA", None), ("", None)])
def test_state_normalisation(raw, expected):
    assert state_code(raw) == expected


def test_state_hubs_are_automatic_but_other_states_are_private(world):
    c = world["as"]("vic")
    hubs = c.get(world["base"] + "/hubs").json()
    assert next(h for h in hubs if h["code"] == "VIC")["accessible"]
    assert not next(h for h in hubs if h["code"] == "QLD")["accessible"]
    assert c.post(world["base"] + "/hubs/QLD/messages", json={"body": "not permitted"}).status_code == 403
    assert c.get(world["base"] + "/hubs/QLD/messages").status_code == 403
    world["as"]("stranger")
    assert c.get(world["base"] + "/hubs").status_code == 404
    world["as"]("unknown")
    assert all(not h["accessible"] for h in c.get(world["base"] + "/hubs").json())


def test_replies_pins_and_stock_resolution_are_persisted_and_authorised(world):
    c = world["as"]("vic")
    path = world["base"] + "/hubs/VIC/messages"
    post = c.post(path, json={"body": "Need a spring bar", "kind": "stock_request"})
    assert post.status_code == 201, post.text
    message = post.json()
    assert c.patch(path + "/" + message["id"], json={"pinned": True}).json()["pinned"]
    world["as"]("vic2")
    assert c.patch(path + "/" + message["id"], json={"resolved": True}).status_code == 403
    reply = c.post(path, json={"body": "We have one", "reply_to_id": message["id"]})
    assert reply.json()["reply_preview"] == "Need a spring bar"
    assert reply.json()["mine"] is True
    world["as"]("manager")
    assert c.patch(path + "/" + message["id"], json={"resolved": True}).json()["resolved_at"]
    world["as"]("qld")
    assert c.post(world["base"] + "/hubs/QLD/messages", json={"body": "cross-state reply", "reply_to_id": message["id"]}).status_code == 404


def test_read_markers_are_shared_by_shop_and_do_not_hide_new_arrivals(world):
    c = world["as"]("vic2")
    path = world["base"] + "/hubs/VIC"
    first = c.post(path + "/messages", json={"body": "first"}).json()
    world["as"]("vic")
    assert next(h for h in c.get(world["base"] + "/hubs").json() if h["code"] == "VIC")["unread"] == 1
    world["as"]("vic2")
    second = c.post(path + "/messages", json={"body": "arrived after first was rendered"}).json()
    world["as"]("vic")
    assert c.post(path + "/read", json={"message_id": first["id"]}).status_code == 204
    world["as"]("staff")
    assert next(h for h in c.get(world["base"] + "/hubs").json() if h["code"] == "VIC")["unread"] == 1
    c.post(path + "/read", json={"message_id": second["id"]})
    c.post(path + "/read", json={"message_id": first["id"]})
    assert next(h for h in c.get(world["base"] + "/hubs").json() if h["code"] == "VIC")["unread"] == 0


def test_cursor_history_preserves_messages_with_identical_timestamps(world):
    c = world["as"]("vic")
    now = datetime.now(timezone.utc)
    with Session(world["engine"]) as s:
        for i in range(7):
            s.add(StateHubMessage(parent_account_id=world["parent"], state_code="VIC",
                                 sender_tenant_id=world["people"]["vic2"][0], body=str(i), created_at=now))
        s.commit()
    path = world["base"] + "/hubs/VIC/messages"
    ids = []
    cursor = None
    while True:
        page = c.get(path, params={"limit": 2, **({"before": cursor} if cursor else {})}).json()
        ids += [m["id"] for m in page["messages"]]
        if not page["has_more"]:
            break
        cursor = page["next_before"]
    assert len(ids) == len(set(ids)) == 7


def test_only_hq_and_assigned_managers_publish_and_receipts_are_shared(world):
    c = world["as"]("vic")
    path = world["base"] + "/announcements"
    data = {"title": "Campaign kit", "body": "Please confirm", "requires_confirmation": True}
    assert c.post(path, json=data).status_code == 403
    world["as"]("manager")
    assert c.post(path, json=data).status_code == 403
    assert c.post(path, json={**data, "state_code": "QLD"}).status_code == 403
    vic = c.post(path, json={**data, "state_code": "VIC"}).json()
    assert vic["state_code"] == "VIC"
    world["as"]("hq")
    all_shops = c.post(path, json=data)
    assert all_shops.status_code == 201, all_shops.text
    aid = all_shops.json()["id"]
    world["as"]("qld")
    assert {a["id"] for a in c.get(path).json()["announcements"]} == {aid}
    assert c.post(path + "/" + vic["id"] + "/receipt", json={"confirm": True}).status_code == 404
    world["as"]("vic")
    for _ in range(2):
        assert c.post(path + "/" + aid + "/receipt", json={"confirm": True}).json()["confirmed"]
    world["as"]("staff")
    receipt = next(a for a in c.get(path).json()["announcements"] if a["id"] == aid)
    assert receipt["read"] and receipt["confirmed"]
    with Session(world["engine"]) as s:
        receipts = s.exec(select(AnnouncementReceipt).where(AnnouncementReceipt.announcement_id == UUID(aid), AnnouncementReceipt.tenant_id == world["people"]["vic"][0])).all()
        assert len(receipts) == 1


def test_support_sessions_and_unlinked_sites_cannot_use_community(world):
    c = world["as"]("vic", support=True)
    assert c.get("/v1/network-community/networks").status_code == 403
    assert c.get(world["base"] + "/announcements").status_code == 403
    assert c.get("/v1/network-messages/contacts").status_code == 403
    world["as"]("vic")
    with Session(world["engine"]) as s:
        s.delete(s.get(ParentAccountSite, world["people"]["vic"][2]))
        s.commit()
    assert c.get(world["base"] + "/hubs").status_code == 404


def test_signed_up_sites_can_direct_message_across_states_only_in_network(world):
    c = world["as"]("vic")
    contacts = c.get("/v1/network-messages/contacts", params={"parent_account_id": world["parent"]}).json()
    qld = next(contact for contact in contacts if contact["tenant_id"] == str(world["people"]["qld"][0]))
    assert qld["state_code"] == "QLD"
    assert all(contact["tenant_id"] != str(world["people"]["stranger"][0]) for contact in contacts)
    assert c.post("/v1/network-messages/with/" + str(world["people"]["qld"][0]), json={"body": "Hello interstate"}).status_code == 201
    assert c.post("/v1/network-messages/with/" + str(world["people"]["stranger"][0]), json={"body": "Not our network"}).status_code == 403
    with Session(world["engine"]) as s:
        for user in s.exec(select(User).where(User.tenant_id == world["people"]["qld"][0])).all():
            user.is_active = False
            s.add(user)
        s.commit()
    contacts = c.get("/v1/network-messages/contacts").json()
    assert not any(contact["tenant_id"] == str(world["people"]["qld"][0]) for contact in contacts)


def test_empty_and_invalid_posts_fail_without_writing(world):
    c = world["as"]("vic")
    path = world["base"] + "/hubs/VIC/messages"
    assert c.post(path, json={"body": "   "}).status_code == 400
    assert c.post(path, json={"body": "test", "kind": "announcement"}).status_code == 400
    assert c.post(path, json={"body": "x" * 2001}).status_code == 422
    assert c.get(path).json()["messages"] == []


def test_files_commit_with_message_and_download_requires_current_membership(world):
    from app.models.network_community import NetworkMessageAttachment
    c = world["as"]("vic")
    path = world["base"] + "/hubs/VIC/posts"
    import base64
    png = base64.b64decode("iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+jwZkAAAAASUVORK5CYII=")
    result = c.post(path, data={"body": "Which part is this?"}, files=[("files", ("part.png", png, "image/png"))])
    assert result.status_code == 201, result.text
    file = result.json()["attachments"][0]
    download = "/v1/network-community/attachments/" + file["id"]
    assert c.get(download).content == png
    assert c.get(download).headers["cache-control"] == "private, no-store"
    world["as"]("vic2")
    assert c.get(download).status_code == 200
    world["as"]("qld")
    assert c.get(download).status_code == 403
    world["as"]("vic", support=True)
    assert c.get(download).status_code == 403
    world["as"]("vic")
    with Session(world["engine"]) as s:
        s.delete(s.get(ParentAccountSite, world["people"]["vic"][2]))
        s.commit()
        assert s.get(NetworkMessageAttachment, UUID(file["id"]))
    assert c.get(download).status_code == 404


def test_bad_files_are_rejected_without_partial_message(world):
    c = world["as"]("vic")
    path = world["base"] + "/hubs/VIC"
    result = c.post(path + "/posts", data={"body": "Do not partially save"}, files=[("files", ("bad.html", b"<script>alert(1)</script>", "image/png"))])
    assert result.status_code == 415
    assert c.get(path + "/messages").json()["messages"] == []
    result = c.post(path + "/posts", files=[("files", ("big.pdf", b"%PDF-" + b"0" * (5 * 1024 * 1024), "application/pdf"))])
    assert result.status_code == 413
    assert c.get(path + "/messages").json()["messages"] == []


def test_direct_files_are_visible_only_to_the_two_participating_shops(world):
    c = world["as"]("vic")
    recipient = str(world["people"]["qld"][0])
    result = c.post(world["base"] + "/direct/" + recipient + "/posts",
                    files=[("files", ("guide.pdf", b"%PDF-1.4\nexample", "application/pdf"))])
    assert result.status_code == 201, result.text
    message = result.json()
    url = "/v1/network-community/attachments/" + message["attachments"][0]["id"]
    world["as"]("qld")
    assert c.get(url).status_code == 200
    thread = c.get("/v1/network-messages/conversations/" + message["conversation_id"] + "/messages").json()
    assert thread[0]["attachments"][0]["filename"] == "guide.pdf"
    world["as"]("vic2")
    assert c.get(url).status_code == 404
    world["as"]("hq")
    assert c.get(url).status_code == 404




def test_publishers_see_which_shops_read_and_confirmed(world):
    c = world["as"]("hq")
    made = c.post(world["base"] + "/announcements", json={"title": "New returns policy", "body": "Read this", "requires_confirmation": True})
    assert made.status_code == 201, made.text
    assert made.json()["can_view_receipts"] is True
    aid = made.json()["id"]
    world["as"]("vic")
    shop_view = c.get(world["base"] + "/announcements").json()["announcements"][0]
    assert shop_view["can_view_receipts"] is False
    assert c.get(f"{world['base']}/announcements/{aid}/receipts").status_code == 403
    c.post(f"{world['base']}/announcements/{aid}/receipt", json={"confirm": True})
    world["as"]("qld")
    c.post(f"{world['base']}/announcements/{aid}/receipt", json={})
    world["as"]("hq")
    data = c.get(f"{world['base']}/announcements/{aid}/receipts").json()
    assert data["summary"]["audience"] == 4  # vic, qld and the unknown-state shop, plus vic2
    assert data["summary"]["read"] == 2 and data["summary"]["confirmed"] == 1
    names = {s["name"]: s for s in data["shops"]}
    assert names["vic"]["confirmed_at"] and names["qld"]["read_at"] and not names["qld"]["confirmed_at"]
    assert not names["vic2"]["read_at"]
    assert "Shop,State" in c.get(f"{world['base']}/announcements/{aid}/receipts?export=csv").text


def test_state_manager_sees_receipts_only_for_their_own_state(world):
    c = world["as"]("manager")
    own = c.post(world["base"] + "/announcements", json={"title": "VIC only", "body": "x", "state_code": "VIC"}).json()
    data = c.get(f"{world['base']}/announcements/{own['id']}/receipts").json()
    assert {s["name"] for s in data["shops"]} == {"vic", "vic2"}
    world["as"]("hq")
    network = c.post(world["base"] + "/announcements", json={"title": "Everyone", "body": "x"}).json()
    world["as"]("manager")
    assert c.get(f"{world['base']}/announcements/{network['id']}/receipts").status_code == 403


def test_state_gaps_list_only_for_hq_admins(world):
    c = world["as"]("hq")
    gaps = c.get(world["base"] + "/state-gaps").json()["shops"]
    assert [g["name"] for g in gaps] == ["unknown"]
    world["as"]("vic")
    assert c.get(world["base"] + "/state-gaps").status_code == 403


def test_hub_message_list_uses_a_fixed_number_of_queries(world):
    from sqlalchemy import event
    c = world["as"]("vic")
    path = world["base"] + "/hubs/VIC/messages"
    first = c.post(path, json={"body": "root"}).json()
    for i in range(30):
        c.post(path, json={"body": f"reply {i}", "reply_to_id": first["id"]})
    counted = []
    def count(*_):
        counted.append(1)
    event.listen(world["engine"], "before_cursor_execute", count)
    try:
        assert len(c.get(path).json()["messages"]) == 31
    finally:
        event.remove(world["engine"], "before_cursor_execute", count)
    assert len(counted) < 40, len(counted)


def test_moderators_can_delete_hub_messages_and_edit_or_remove_announcements(world):
    c = world["as"]("vic")
    path = world["base"] + "/hubs/VIC/messages"
    root = c.post(path, json={"body": "oops"}).json()
    reply = c.post(path, json={"body": "reply", "reply_to_id": root["id"]}).json()
    world["as"]("vic2")
    assert c.delete(path + "/" + root["id"]).status_code == 403  # a different shop
    world["as"]("staff")
    assert c.delete(path + "/" + root["id"]).status_code == 204  # colleague at the posting shop
    listing = c.get(path).json()["messages"]
    assert [m["id"] for m in listing] == [reply["id"]] and listing[0]["reply_preview"] is None
    world["as"]("qld")
    assert c.delete(path + "/" + reply["id"]).status_code == 403
    world["as"]("manager")
    assert c.delete(path + "/" + reply["id"]).status_code == 204
    world["as"]("hq")
    ann = c.post(world["base"] + "/announcements", json={"title": "Typo", "body": "b", "category": "important"}).json()
    edited = c.patch(f"{world['base']}/announcements/{ann['id']}", json={"title": "Fixed", "pinned": True}).json()
    assert edited["title"] == "Fixed" and edited["pinned"] is True and edited["body"] == "b"
    world["as"]("vic")
    assert c.patch(f"{world['base']}/announcements/{ann['id']}", json={"pinned": False}).status_code == 403
    assert c.delete(f"{world['base']}/announcements/{ann['id']}").status_code == 403
    world["as"]("hq")
    assert c.delete(f"{world['base']}/announcements/{ann['id']}").status_code == 204
    assert c.get(world["base"] + "/announcements").json()["announcements"] == []


def test_important_announcements_raise_an_inbox_alert_that_clears_when_read(world):
    from app.models import TenantEventLog
    c = world["as"]("hq")
    ann = c.post(world["base"] + "/announcements", json={"title": "Recall", "body": "b", "category": "important", "state_code": "VIC"}).json()
    c.post(world["base"] + "/announcements", json={"title": "FYI", "body": "b"})  # ordinary: no alert

    def alerts(name):
        with Session(world["engine"]) as s:
            return len(s.exec(select(TenantEventLog).where(TenantEventLog.tenant_id == world["people"][name][0],
                                                           TenantEventLog.event_type == "network_announcement")).all())
    assert alerts("vic") == 1 and alerts("vic2") == 1 and alerts("qld") == 0 and alerts("hq") == 0
    world["as"]("vic")
    c.post(f"{world['base']}/announcements/{ann['id']}/receipt", json={})
    assert alerts("vic") == 0
