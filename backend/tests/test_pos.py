"""Shop counter POS: HQ-managed price books, what tills download, and the sales ledger."""
from datetime import datetime, timezone
from uuid import UUID, uuid4

import pytest
from fastapi.testclient import TestClient
from sqlmodel import Session, select

from app.database import engine
from app.main import app
from app.models import Customer, CustomerLoyalty, ParentAccount, ParentAccountSite, PosSale, Tenant, User
from app.pos_catalogue import CatalogueError, parse_catalogue
from app.security import create_access_token, hash_password

client = TestClient(app)


def _headers(user: User) -> dict[str, str]:
    token, _ = create_access_token(user.tenant_id, user.id, user.role)
    return {"Authorization": f"Bearer {token}"}


def _user(db: Session, tenant: Tenant, role: str) -> User:
    user = User(tenant_id=tenant.id, email=f"{role}-{uuid4().hex[:6]}@test.com", full_name=role.title(), role=role, password_hash=hash_password("Password2026!"))
    db.add(user)
    db.flush()
    return user


def _network(nz_shop: bool = False) -> dict:
    """A Minit-style HQ with two shops in its network, plus an unrelated independent shop."""
    s = uuid4().hex[:6]
    with Session(engine) as db:
        hq = Tenant(name="HQ", slug=f"hq-{s}", plan_code="minit_hq", is_minit=True)
        shop = Tenant(name="Chadstone", slug=f"minit-a{s}", plan_code="booking_only", is_minit=True, shop_number="3269")
        shop2 = Tenant(name="Geelong", slug=f"minit-b{s}", plan_code="booking_only", is_minit=True,
                       minit_region="NZ" if nz_shop else "VIC")
        indie = Tenant(name="Indie", slug=f"indie-{s}", plan_code="pro")
        db.add_all([hq, shop, shop2, indie])
        db.flush()
        parent = ParentAccount(name=f"Minit {s}", owner_email=f"hq-{s}@test.com")
        db.add(parent)
        db.flush()
        db.add_all([
            ParentAccountSite(parent_account_id=parent.id, tenant_id=hq.id, network_role="hq"),
            ParentAccountSite(parent_account_id=parent.id, tenant_id=shop.id, network_role="retail"),
            ParentAccountSite(parent_account_id=parent.id, tenant_id=shop2.id, network_role="retail"),
        ])
        users = {
            "hq": _user(db, hq, "owner"),
            "shop": _user(db, shop, "owner"),
            "staff": _user(db, shop, "tech"),
            "shop2": _user(db, shop2, "owner"),
            "indie": _user(db, indie, "owner"),
        }
        customer = Customer(tenant_id=shop.id, full_name="Pat Customer", phone="0400000000")
        other_customer = Customer(tenant_id=indie.id, full_name="Not Yours")
        db.add_all([customer, other_customer])
        db.commit()
        return {
            **{k: _headers(u) for k, u in users.items()},
            "shop_id": str(shop.id), "shop2_id": str(shop2.id), "indie_id": str(indie.id),
            "customer_id": str(customer.id), "other_customer_id": str(other_customer.id),
        }


def _catalogue(price: int = 3500, **extra) -> dict:
    return {
        "groups": [{"key": "shoes", "label": "Shoe repairs", "color": "shoes"}, {"key": "keys", "label": "Keys", "color": "keys"}],
        "categories": [
            {"key": "heels", "name": "Heels", "group": "shoes", "icon": "boot"},
            {"key": "care", "name": "Shoe care", "group": "shoes"},
            {"key": "house-keys", "name": "House keys", "group": "keys", "icon": "key"},
        ],
        "items": [
            {"key": "mens-heels", "category": "heels", "name": "Mens heels", "price_cents": price, "tags": ["shoe-repair"], "job_type": "shoe"},
            {"key": "polish", "category": "care", "name": "Polish", "price_cents": 1200, "tags": ["shoe-care"], "is_service": False},
            {"key": "flat-key", "category": "house-keys", "name": "Flat key", "price_cents": 1000, "tags": ["flat-key", "key-cutting"]},
        ],
        "combos": [
            {"key": "shoe-care", "name": "Shoe care combo", "type": "tag_percent",
             "params": {"percent": 20, "target_tag": "shoe-care", "requires_tag": "shoe-repair"}},
            {"key": "multi-key", "name": "Multi key", "type": "copy_tiers",
             "params": {"tag": "flat-key", "per_copy": [0, 10, 15, 20, 25], "bulk": [[6, 30], [11, 35]]}},
        ],
        **extra,
    }


def _publish_default(net: dict, price: int = 3500, region: str = "AU") -> str:
    created = client.post("/v1/pos/admin/price-books", headers=net["hq"],
                          json={"name": f"{region} 2026-27", "region": region, "is_default": True, "catalogue": _catalogue(price)})
    assert created.status_code == 201, created.text
    book_id = created.json()["id"]
    assert client.post(f"/v1/pos/admin/price-books/{book_id}/publish", headers=net["hq"], json={"note": "launch"}).status_code == 200
    return book_id


def _sale(**overrides) -> dict:
    body = {
        "client_sale_id": uuid4().hex,
        "till_id": "T1",
        "staff_name": "Sam",
        "occurred_at": datetime.now(timezone.utc).isoformat(),
        "gst_rate_bp": 1000,
        "gross_cents": 4700,
        "combo_cents": 240,
        "discount_cents": 0,
        "total_cents": 4460,
        "gst_cents": 405,
        "rounding_cents": 0,
        "lines": [
            {"item_key": "mens-heels", "item_name": "Mens heels", "category_name": "Heels", "unit_price_cents": 3500, "qty": 1},
            {"item_key": "polish", "item_name": "Polish", "category_name": "Shoe care", "unit_price_cents": 1200, "qty": 1,
             "combo_cents": 240, "combo_label": "Shoe care combo", "is_service": False},
        ],
        "tenders": [{"tender_type": "eftpos", "amount_cents": 4460, "provider": "tyro", "reference": "abc", "card_type": "visa"}],
    }
    body.update(overrides)
    return body


# ── Catalogue validation ─────────────────────────────────────────────────────

def test_catalogue_validation_catches_broken_references_and_unknown_combos():
    parse_catalogue(_catalogue())
    with pytest.raises(CatalogueError, match="unknown category"):
        parse_catalogue(_catalogue(items=[{"key": "x", "category": "nope", "name": "X"}]))
    with pytest.raises(CatalogueError, match="unknown combo type"):
        parse_catalogue(_catalogue(combos=[{"key": "c", "name": "C", "type": "buy_one_get_ten", "params": {}}]))
    with pytest.raises(CatalogueError, match="requires_tag or requires_service_without_tag"):
        parse_catalogue(_catalogue(combos=[{"key": "c", "name": "C", "type": "tag_percent", "params": {"percent": 10, "target_tag": "a"}}]))
    with pytest.raises(CatalogueError, match="duplicate item key"):
        cat = _catalogue()
        cat["items"].append(dict(cat["items"][0]))
        parse_catalogue(cat)


# ── HQ edits, publishes, and shops download ──────────────────────────────────

def test_hq_publishes_a_book_and_its_shops_sell_from_it():
    net = _network()
    assert client.get("/v1/pos/catalogue", headers=net["shop"]).status_code == 404

    book_id = _publish_default(net)
    res = client.get("/v1/pos/catalogue", headers=net["shop"])
    assert res.status_code == 200, res.text
    data = res.json()
    assert data["version"] == 1 and data["gst_rate_bp"] == 1000 and data["cash_rounding_cents"] == 5
    assert [i["key"] for i in data["catalogue"]["items"]] == ["mens-heels", "polish", "flat-key"]
    assert data["catalogue"]["combos"][1]["params"]["per_copy"] == [0, 10, 15, 20, 25]
    assert res.headers["etag"]

    # A draft edit reaches no till until it is published.
    detail = client.get(f"/v1/pos/admin/price-books/{book_id}", headers=net["hq"]).json()
    saved = client.put(f"/v1/pos/admin/price-books/{book_id}/draft", headers=net["hq"],
                       json={"catalogue": _catalogue(price=3900), "expected_updated_at": detail["draft_updated_at"]})
    assert saved.status_code == 200, saved.text
    assert client.get("/v1/pos/catalogue", headers=net["shop"]).json()["catalogue"]["items"][0]["price_cents"] == 3500
    client.post(f"/v1/pos/admin/price-books/{book_id}/publish", headers=net["hq"], json={})
    after = client.get("/v1/pos/catalogue", headers=net["shop"]).json()
    assert after["version"] == 2 and after["catalogue"]["items"][0]["price_cents"] == 3900


def test_invalid_drafts_are_rejected_and_concurrent_edits_conflict():
    net = _network()
    book_id = _publish_default(net)
    bad = client.put(f"/v1/pos/admin/price-books/{book_id}/draft", headers=net["hq"],
                     json={"catalogue": _catalogue(combos=[{"key": "c", "name": "C", "type": "mystery", "params": {}}])})
    assert bad.status_code == 422 and "unknown combo type" in bad.json()["detail"]
    stale = client.put(f"/v1/pos/admin/price-books/{book_id}/draft", headers=net["hq"],
                       json={"catalogue": _catalogue(), "expected_updated_at": "2020-01-01T00:00:00Z"})
    assert stale.status_code == 409


def test_restoring_an_old_version_only_changes_the_draft():
    net = _network()
    book_id = _publish_default(net, price=3500)
    client.put(f"/v1/pos/admin/price-books/{book_id}/draft", headers=net["hq"], json={"catalogue": _catalogue(price=4100)})
    client.post(f"/v1/pos/admin/price-books/{book_id}/publish", headers=net["hq"], json={})
    restored = client.post(f"/v1/pos/admin/price-books/{book_id}/versions/1/restore", headers=net["hq"])
    assert restored.status_code == 200 and restored.json()["draft"]["items"][0]["price_cents"] == 3500
    assert client.get("/v1/pos/catalogue", headers=net["shop"]).json()["catalogue"]["items"][0]["price_cents"] == 4100
    v1 = client.get(f"/v1/pos/admin/price-books/{book_id}/versions/1", headers=net["hq"]).json()
    assert v1["note"] == "launch"


def test_assigned_book_beats_the_default_and_region_picks_the_default():
    net = _network(nz_shop=True)
    _publish_default(net, price=3500, region="AU")
    nz_book = _publish_default(net, price=4500, region="NZ")
    nz = client.get("/v1/pos/catalogue", headers=net["shop2"]).json()
    assert nz["region"] == "NZ" and nz["gst_rate_bp"] == 1500 and nz["cash_rounding_cents"] == 10 and nz["price_book_id"] == nz_book

    special = client.post("/v1/pos/admin/price-books", headers=net["hq"], json={"name": "CBD pricing", "catalogue": _catalogue(price=4000)}).json()
    client.post(f"/v1/pos/admin/price-books/{special['id']}/publish", headers=net["hq"], json={})
    assigned = client.put(f"/v1/pos/admin/price-books/{special['id']}/shops", headers=net["hq"], json={"tenant_ids": [net["shop_id"]]})
    assert assigned.status_code == 200
    assert client.get("/v1/pos/catalogue", headers=net["shop"]).json()["price_book_id"] == special["id"]
    shops = {s["tenant_id"]: s for s in client.get("/v1/pos/admin/shops", headers=net["hq"]).json()}
    assert set(shops) == {net["shop_id"], net["shop2_id"]} and shops[net["shop_id"]]["price_book_id"] == special["id"]

    outside = client.put(f"/v1/pos/admin/price-books/{special['id']}/shops", headers=net["hq"], json={"tenant_ids": [net["indie_id"]]})
    assert outside.status_code == 403


def test_books_are_private_to_their_owner():
    net = _network()
    book_id = _publish_default(net)
    # A shop in the network can't open HQ's book for editing; it manages only its own.
    assert client.get(f"/v1/pos/admin/price-books/{book_id}", headers=net["shop"]).status_code == 404
    assert client.get("/v1/pos/admin/price-books", headers=net["indie"]).json() == []
    assert client.get("/v1/pos/admin/price-books", headers=net["staff"]).status_code == 403

    # An independent shop runs its own book.
    own = client.post("/v1/pos/admin/price-books", headers=net["indie"], json={"name": "Mine", "is_default": True, "catalogue": _catalogue(price=2500)})
    assert own.status_code == 201
    client.post(f"/v1/pos/admin/price-books/{own.json()['id']}/publish", headers=net["indie"], json={})
    assert client.get("/v1/pos/catalogue", headers=net["indie"]).json()["catalogue"]["items"][0]["price_cents"] == 2500
    assert client.get(f"/v1/pos/admin/price-books/{own.json()['id']}", headers=net["hq"]).status_code == 404


def test_shop_overrides_change_price_and_hide_items_for_that_shop_only():
    net = _network()
    _publish_default(net)
    assert client.put("/v1/pos/overrides/polish", headers=net["staff"], json={"price_cents": 1500}).status_code == 403
    assert client.put("/v1/pos/overrides/polish", headers=net["shop"], json={"price_cents": 1500}).status_code == 200
    assert client.put("/v1/pos/overrides/flat-key", headers=net["shop"], json={"hidden": True}).status_code == 200
    assert client.put("/v1/pos/overrides/not-an-item", headers=net["shop"], json={"price_cents": 1}).status_code == 404
    items = {i["key"]: i for i in client.get("/v1/pos/catalogue", headers=net["shop"]).json()["catalogue"]["items"]}
    assert items["polish"]["price_cents"] == 1500 and "flat-key" not in items
    other = {i["key"]: i for i in client.get("/v1/pos/catalogue", headers=net["shop2"]).json()["catalogue"]["items"]}
    assert other["polish"]["price_cents"] == 1200 and "flat-key" in other
    assert client.delete("/v1/pos/overrides/flat-key", headers=net["shop"]).json() == {"polish": {"price_cents": 1500}}
    assert client.delete("/v1/pos/overrides/flat-key", headers=net["shop"]).status_code == 404


# ── Sales ────────────────────────────────────────────────────────────────────

def test_posting_a_sale_twice_records_it_once_and_earns_points_once():
    net = _network()
    body = _sale(customer_id=net["customer_id"])
    first = client.post("/v1/pos/sales", headers=net["staff"], json=body)
    assert first.status_code == 201, first.text
    assert first.json()["loyalty_points_earned"] == 44 and first.json()["duplicate"] is False
    again = client.post("/v1/pos/sales", headers=net["staff"], json=body)
    assert again.status_code == 200 and again.json()["id"] == first.json()["id"] and again.json()["duplicate"] is True
    with Session(engine) as db:
        assert len(db.exec(select(PosSale).where(PosSale.client_sale_id == body["client_sale_id"])).all()) == 1
        loyalty = db.exec(select(CustomerLoyalty).where(CustomerLoyalty.customer_id == UUID(net["customer_id"]))).one()
        assert loyalty.points_balance == 50 + 44


def test_sale_arithmetic_and_ownership_are_checked():
    net = _network()
    assert client.post("/v1/pos/sales", headers=net["staff"], json=_sale(total_cents=4000)).status_code == 422
    assert client.post("/v1/pos/sales", headers=net["staff"], json=_sale(gross_cents=9999)).status_code == 422
    short = _sale(tenders=[{"tender_type": "cash", "amount_cents": 4000}])
    assert client.post("/v1/pos/sales", headers=net["staff"], json=short).status_code == 422
    assert client.post("/v1/pos/sales", headers=net["staff"], json=_sale(gst_cents=2000)).status_code == 422
    assert client.post("/v1/pos/sales", headers=net["staff"], json=_sale(customer_id=net["other_customer_id"])).status_code == 422
    # Cash rounded to 5c: customer hands over $44.60 for $44.62.
    rounded = _sale(gross_cents=4702, combo_cents=240, total_cents=4462,
                    lines=[{"item_key": "a", "item_name": "A", "unit_price_cents": 3502, "qty": 1},
                           {"item_key": "polish", "item_name": "Polish", "unit_price_cents": 1200, "qty": 1, "combo_cents": 240}],
                    rounding_cents=-2, tenders=[{"tender_type": "cash", "amount_cents": 4460, "tendered_cents": 5000}])
    assert client.post("/v1/pos/sales", headers=net["staff"], json=rounded).status_code == 201


def test_sales_are_private_to_the_shop():
    net = _network()
    sale = client.post("/v1/pos/sales", headers=net["staff"], json=_sale()).json()
    assert client.get(f"/v1/pos/sales/{sale['id']}", headers=net["shop"]).status_code == 200
    assert client.get(f"/v1/pos/sales/{sale['id']}", headers=net["shop2"]).status_code == 404
    assert client.get("/v1/pos/sales", headers=net["shop2"]).json() == []
    refund_other = _sale(status="refund", refund_of_sale_id=sale["id"], gross_cents=-1200, combo_cents=0, total_cents=-1200, gst_cents=-109,
                         lines=[{"item_key": "polish", "item_name": "Polish", "unit_price_cents": 1200, "qty": -1}],
                         tenders=[{"tender_type": "cash", "amount_cents": -1200}])
    assert client.post("/v1/pos/sales", headers=net["shop2"], json=refund_other).status_code == 422


def test_z_report_totals_the_day_by_tender_category_and_staff():
    net = _network()
    day = "2026-10-20T03:00:00Z"  # 2pm in Melbourne
    client.post("/v1/pos/sales", headers=net["staff"], json=_sale(occurred_at=day))
    cash = _sale(occurred_at=day, staff_name="Alex", gross_cents=1000, combo_cents=0, total_cents=1000, gst_cents=91,
                 lines=[{"item_key": "flat-key", "item_name": "Flat key", "category_name": "House keys", "unit_price_cents": 1000, "qty": 1}],
                 tenders=[{"tender_type": "cash", "amount_cents": 1000, "tendered_cents": 2000}])
    sale = client.post("/v1/pos/sales", headers=net["staff"], json=cash).json()
    refund = _sale(occurred_at=day, staff_name="Alex", status="refund", refund_of_sale_id=sale["id"], gross_cents=-1000, combo_cents=0,
                   total_cents=-1000, gst_cents=-91,
                   lines=[{"item_key": "flat-key", "item_name": "Flat key", "category_name": "House keys", "unit_price_cents": 1000, "qty": -1}],
                   tenders=[{"tender_type": "cash", "amount_cents": -1000}])
    assert client.post("/v1/pos/sales", headers=net["staff"], json=refund).status_code == 201
    # The next day, and another shop's sale, stay out.
    client.post("/v1/pos/sales", headers=net["staff"], json=_sale(occurred_at="2026-10-20T14:00:00Z"))
    client.post("/v1/pos/sales", headers=net["shop2"], json=_sale(occurred_at=day))

    z = client.get("/v1/pos/z-report", headers=net["shop"], params={"business_date": "2026-10-20"}).json()
    assert z["sale_count"] == 2 and z["refund_count"] == 1
    assert z["net_cents"] == 4460 and z["refund_cents"] == -1000 and z["gst_cents"] == 405
    assert z["by_tender"] == {"cash": {"count": 2, "amount_cents": 0}, "eftpos": {"count": 1, "amount_cents": 4460}}
    assert z["by_category"]["House keys"] == {"qty": 0, "gross_cents": 0, "combo_cents": 0}
    assert z["by_category"]["Shoe care"]["combo_cents"] == 240
    assert z["by_staff"]["Alex"] == {"sales": 1, "total_cents": 0}
    assert client.get("/v1/pos/z-report", headers=net["shop"], params={"business_date": "2026-10-21"}).json()["sale_count"] == 1
