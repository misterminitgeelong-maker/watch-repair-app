"""HQ shoe catalogue and stock: parts, parts list per model and size, locations, transfers, use on jobs, purchases."""
from uuid import UUID, uuid4

from fastapi.testclient import TestClient
from sqlmodel import Session

from app.database import engine
from app.main import app
from app.models import Customer, ParentAccountSite, Shoe, ShoeRepairJob, Tenant, User
from app.security import create_access_token, hash_password

from test_parent_shoe_operations import _admin, _hq

client = TestClient(app)
HQ = "/v1/parent-accounts/me/stock"
SHOP = "/v1/stock"


def _shop_with_job(parent_id, *, model="Arizona", size="41"):
    with Session(engine) as db:
        shop = Tenant(name=f"Shop {uuid4().hex[:4]}", slug=f"s-{uuid4().hex[:8]}", plan_code="basic_shoe")
        db.add(shop); db.flush()
        db.add(ParentAccountSite(parent_account_id=UUID(parent_id), tenant_id=shop.id, network_role="retail"))
        user = User(tenant_id=shop.id, email=f"u-{uuid4().hex[:6]}@t.com", full_name="Staff", role="owner", password_hash=hash_password("Password2026!"))
        db.add(user); db.flush()
        c = Customer(tenant_id=shop.id, full_name="Cust")
        db.add(c); db.flush()
        s = Shoe(tenant_id=shop.id, customer_id=c.id, brand="Birkenstock", model_name=model, size=size)
        db.add(s); db.flush()
        j = ShoeRepairJob(tenant_id=shop.id, shoe_id=s.id, job_number="SHO-00001", title="Footbed")
        db.add(j); db.commit()
        tok, _ = create_access_token(user.tenant_id, user.id, user.role)
        return str(shop.id), str(j.id), {"Authorization": f"Bearer {tok}"}


def _setup():
    admin = _admin()
    hq, h = _hq(admin, ["shoe", "stock"])
    pid = hq["parent_account_id"]
    footbed = client.post(f"{HQ}/parts", headers=h, json={"sku": "FB-ARI-41", "name": "Arizona footbed 41", "part_type": "footbed", "reorder_level": 2}).json()
    buckle = client.post(f"{HQ}/parts", headers=h, json={"sku": "BK-01", "name": "Buckle", "part_type": "buckle"}).json()
    model = client.post(f"{HQ}/models", headers=h, json={"name": "Arizona", "category": "sandal"}).json()
    assert client.put(f"{HQ}/models/{model['id']}/parts", headers=h, json=[
        {"part_id": footbed["id"], "size": "41", "quantity": 1}, {"part_id": buckle["id"], "quantity": 2},
        {"part_id": footbed["id"], "size": "36", "quantity": 1},
    ]).status_code == 200
    shop_tenant, job_id, sh = _shop_with_job(pid)
    warehouse = client.post(f"{HQ}/locations", headers=h, json={"name": "Warehouse", "kind": "warehouse"}).json()
    melb = client.post(f"{HQ}/locations", headers=h, json={"name": "Melbourne workshop", "kind": "workshop", "tenant_id": shop_tenant}).json()
    return dict(admin=admin, h=h, pid=pid, footbed=footbed, buckle=buckle, model=model, sh=sh, job_id=job_id,
                warehouse=warehouse, melb=melb, shop_tenant=shop_tenant)


def test_catalogue_transfer_and_use_on_job_flow():
    s = _setup()
    h, sh = s["h"], s["sh"]
    # Receive stock into the warehouse and send some to the workshop.
    r = client.post(f"{HQ}/adjust", headers=h, json={"location_id": s["warehouse"]["id"], "sku": "fb-ari-41", "quantity": 5})
    assert r.status_code == 200 and r.json()["quantity"] == 5
    client.post(f"{HQ}/adjust", headers=h, json={"location_id": s["warehouse"]["id"], "sku": "BK-01", "quantity": 10})
    too_many = client.post(f"{HQ}/transfers", headers=h, json={"from_location_id": s["warehouse"]["id"], "to_location_id": s["melb"]["id"], "lines": [{"sku": "BK-01", "quantity": 11}]})
    assert too_many.status_code == 409
    tr = client.post(f"{HQ}/transfers", headers=h, json={"from_location_id": s["warehouse"]["id"], "to_location_id": s["melb"]["id"],
                                                      "lines": [{"sku": "FB-ARI-41", "quantity": 3}, {"sku": "BK-01", "quantity": 4}]})
    assert tr.status_code == 201, tr.text
    tid = tr.json()["id"]
    assert tr.json()["status"] == "in_transit"
    # Stock left the warehouse but has not arrived yet.
    wh = {l["sku"]: l["quantity"] for l in client.get(f"{HQ}/levels", headers=h, params={"location_id": s["warehouse"]["id"]}).json()}
    assert wh == {"FB-ARI-41": 2, "BK-01": 6}
    assert client.get(f"{SHOP}/levels", headers=sh).json() == []
    # The workshop scans it in; it only got 3 of the 4 buckles.
    got = client.post(f"{SHOP}/transfers/{tid}/receive", headers=sh, json={"lines": [{"sku": "FB-ARI-41", "quantity": 3}, {"sku": "BK-01", "quantity": 3}]})
    assert got.status_code == 200 and got.json()["status"] == "received"
    mine = {l["sku"]: l["quantity"] for l in client.get(f"{SHOP}/levels", headers=sh).json()}
    assert mine == {"FB-ARI-41": 3, "BK-01": 3}
    assert client.post(f"{SHOP}/transfers/{tid}/receive", headers=sh, json={}).status_code == 409
    # Model picker and suggested parts for a size 41 Arizona.
    assert [m["name"] for m in client.get(f"{SHOP}/models", headers=sh).json()] == ["Arizona"]
    sug = client.get(f"{SHOP}/jobs/{s['job_id']}/suggested-parts", headers=sh).json()
    assert {(p["sku"], p["quantity"], p["in_stock"]) for p in sug} == {("FB-ARI-41", 1, 3), ("BK-01", 2, 3)}
    # Use parts on the job: stock drops, usage is recorded.
    used = client.post(f"{SHOP}/jobs/{s['job_id']}/parts", headers=sh, json={"sku": "FB-ARI-41"})
    assert used.status_code == 201 and used.json()["stock_left"] == 2
    assert client.get(f"{SHOP}/jobs/{s['job_id']}/parts", headers=sh).json()[0]["sku"] == "FB-ARI-41"
    # HQ sees low stock (reorder level 2) and what was used.
    summary = client.get(f"{HQ}/summary", headers=h).json()
    assert sorted((l["location_name"], l["sku"]) for l in summary["low_stock"]) == [("Melbourne workshop", "FB-ARI-41"), ("Warehouse", "FB-ARI-41")]
    assert summary["parts_used_30d"] == [{"sku": "FB-ARI-41", "name": "Arizona footbed 41", "quantity": 1}]


def test_size_specific_parts_and_sync():
    s = _setup()
    h, sh = s["h"], s["sh"]
    _, job36, sh36 = _shop_with_job(s["pid"], size="36")
    # Size 36 also needs a footbed row and the all-sizes buckles; size 41 gets its own footbed row only once.
    sug = client.get(f"{SHOP}/jobs/{job36}/suggested-parts", headers=sh36)
    assert sug.status_code == 200
    assert sorted(p["sku"] for p in sug.json()) == ["BK-01", "FB-ARI-41"]
    synced = client.post(f"{HQ}/sync", headers=h, json={"location_id": s["melb"]["id"], "rows": [{"sku": "BK-01", "quantity": 7}, {"sku": "NOPE", "quantity": 1}]})
    assert synced.json() == {"updated": 1, "unknown_skus": ["NOPE"]}
    assert {l["sku"]: l["quantity"] for l in client.get(f"{SHOP}/levels", headers=sh).json()} == {"BK-01": 7}


def test_purchase_import_and_lookup():
    s = _setup()
    rows = [{"purchase_ref": "R-1", "purchase_date": "2026-03-01", "store": "Melbourne", "customer_name": "Dana Smith",
             "customer_email": "dana@example.com", "customer_phone": "0400111222", "model_name": "Arizona", "size": "41"}]
    assert client.post(f"{HQ}/purchases/import", headers=s["h"], json={"rows": rows}).json() == {"created": 1, "updated": 0}
    assert client.post(f"{HQ}/purchases/import", headers=s["h"], json={"rows": rows}).json() == {"created": 0, "updated": 1}
    for q in ("smith", "R-1", "dana@example", "0400111222"):
        found = client.get(f"{SHOP}/purchases/search", headers=s["sh"], params={"q": q}).json()
        assert [f["purchase_ref"] for f in found] == ["R-1"], q
    assert client.get(f"{SHOP}/purchases/search", headers=s["sh"], params={"q": "zz"}).json() == []


def test_access_boundaries():
    s = _setup()
    other = _setup()
    # Each HQ has its own catalogue, even with the same names.
    assert {p["id"] for p in client.get(f"{HQ}/parts", headers=other["h"]).json()}.isdisjoint({p["id"] for p in client.get(f"{HQ}/parts", headers=s["h"]).json()})
    foreign = client.post(f"{SHOP}/transfers", headers=other["sh"], json={
        "from_location_id": s["melb"]["id"], "to_location_id": other["melb"]["id"], "lines": [{"sku": "BK-01", "quantity": 1}]})
    assert foreign.status_code == 404
    # A shop cannot move stock out of a location that belongs to another shop in its own network.
    _, _, sh2 = _shop_with_job(s["pid"])
    client.post(f"{HQ}/adjust", headers=s["h"], json={"location_id": s["melb"]["id"], "sku": "BK-01", "quantity": 3})
    steal = client.post(f"{SHOP}/transfers", headers=sh2, json={
        "from_location_id": s["melb"]["id"], "to_location_id": s["warehouse"]["id"], "lines": [{"sku": "BK-01", "quantity": 1}]})
    assert steal.status_code == 403
    # Without the stock module, nothing opens.
    admin = _admin()
    _, no_stock = _hq(admin, ["shoe"])
    assert client.get(f"{HQ}/parts", headers=no_stock).status_code == 403
    assert client.get(f"{HQ}/parts").status_code in (401, 403)
    assert client.get(f"{SHOP}/models", headers=s["admin"]).status_code == 403
    # Duplicate SKUs and unknown scans are refused cleanly.
    assert client.post(f"{HQ}/parts", headers=s["h"], json={"sku": "bk-01", "name": "Dup"}).status_code == 409
    assert client.post(f"{HQ}/adjust", headers=s["h"], json={"location_id": s["melb"]["id"], "sku": "UNKNOWN", "quantity": 1}).status_code == 404
