import io
import os
from pathlib import Path
from uuid import uuid4

_TEST_DB = Path(__file__).with_name(f"test_stocktakes_{uuid4().hex}.db")
os.environ["DATABASE_URL"] = f"sqlite:///{_TEST_DB.as_posix()}"
os.environ.setdefault("JWT_SECRET", "test-secret-not-for-production")
os.environ.setdefault("APP_ENV", "test")

from fastapi.testclient import TestClient

from app.database import create_db_and_tables
from app.main import app

create_db_and_tables()
client = TestClient(app)


def _bootstrap_and_login(tenant_slug: str, email: str, password: str, plan_code: str = "pro") -> str:
    bootstrap_payload = {
        "tenant_name": f"Tenant {tenant_slug}",
        "tenant_slug": tenant_slug,
        "owner_email": email,
        "owner_full_name": "Owner",
        "owner_password": password,
        "plan_code": plan_code,
    }
    bootstrap_res = client.post("/v1/auth/bootstrap", json=bootstrap_payload)
    assert bootstrap_res.status_code == 200

    login_res = client.post(
        "/v1/auth/login",
        json={
            "tenant_slug": tenant_slug,
            "email": email,
            "password": password,
        },
    )
    assert login_res.status_code == 200
    return login_res.json()["access_token"]


def _stock_csv_bytes() -> bytes:
    return (
        "Item Code,Group,Line Desc,Description (2),Description (3),Per,Pack Description,Pack Qty,Item Price,Ord Inc Tax,Stock\n"
        "A100,DA,BLANK KEY,,BRASS,EA,PKT,10,1.23,2.34,5\n"
        "A100,DA,BLANK KEY,PRECUT,,EA,PKT,10,1.23,2.34,7\n"
        "B200,NB,BATTERY CR2032,,,EA,,1,0.50,4.95,0\n"
    ).encode("utf-8")


def _import_stock(headers: dict[str, str]):
    return client.post(
        "/v1/stock/import",
        headers=headers,
        files={"file": ("stock.csv", io.BytesIO(_stock_csv_bytes()), "text/csv")},
    )


def test_stock_import_deduplicates_and_maps_groups():
    suffix = uuid4().hex[:8]
    token = _bootstrap_and_login(
        tenant_slug=f"stock-import-{suffix}",
        email=f"owner-{suffix}@stock-import.test",
        password="pass123456",
    )
    headers = {"Authorization": f"Bearer {token}"}

    import_res = _import_stock(headers)
    assert import_res.status_code == 200
    body = import_res.json()
    assert body["imported"] == 2
    assert body["created"] == 2
    assert body["updated"] == 0
    assert body["sheet_names"] == ["DATA"]

    items_res = client.get("/v1/stock/items", headers=headers)
    assert items_res.status_code == 200
    items = items_res.json()
    assert len(items) == 2

    key_item = next(item for item in items if item["item_code"] == "A100")
    assert key_item["group_code"] == "DA"
    assert key_item["group_name"] == "FLAT KEYS"
    assert key_item["system_stock_qty"] == 7
    assert key_item["cost_price_cents"] == 123
    assert key_item["retail_price_cents"] == 234
    assert key_item["full_description"] == "BLANK KEY | PRECUT"

    filtered_res = client.get("/v1/stock/items", headers=headers, params={"group_code": "DA"})
    assert filtered_res.status_code == 200
    assert [item["item_code"] for item in filtered_res.json()] == ["A100"]


def test_stocktake_workflow_filters_counts_completion_and_export():
    suffix = uuid4().hex[:8]
    token = _bootstrap_and_login(
        tenant_slug=f"stocktake-{suffix}",
        email=f"owner-{suffix}@stocktake.test",
        password="pass123456",
    )
    headers = {"Authorization": f"Bearer {token}"}

    import_res = _import_stock(headers)
    assert import_res.status_code == 200

    create_res = client.post(
        "/v1/stocktakes",
        headers=headers,
        json={"name": "March count", "search": "KEY"},
    )
    assert create_res.status_code == 201
    session = create_res.json()
    assert session["progress"] == {"counted_items": 0, "total_items": 1}
    session_id = session["id"]

    detail_res = client.get(f"/v1/stocktakes/{session_id}", headers=headers)
    assert detail_res.status_code == 200
    detail = detail_res.json()
    assert len(detail["lines"]) == 1
    line = detail["lines"][0]
    assert line["group_code"] == "DA"

    save_res = client.post(
        f"/v1/stocktakes/{session_id}/lines",
        headers=headers,
        json={
            "lines": [
                {
                    "stock_item_id": line["stock_item_id"],
                    "counted_qty": 8,
                }
            ]
        },
    )
    assert save_res.status_code == 200
    saved_line = save_res.json()[0]
    assert saved_line["variance_qty"] == 1
    assert saved_line["variance_value_cents"] == 123

    hidden_counted_res = client.get(
        f"/v1/stocktakes/{session_id}",
        headers=headers,
        params={"hide_counted": True},
    )
    assert hidden_counted_res.status_code == 200
    assert hidden_counted_res.json()["lines"] == []

    list_res = client.get("/v1/stocktakes", headers=headers)
    assert list_res.status_code == 200
    listed_session = next(item for item in list_res.json() if item["id"] == session_id)
    assert listed_session["progress"] == {"counted_items": 1, "total_items": 1}

    report_res = client.get(f"/v1/stocktakes/{session_id}/report", headers=headers)
    assert report_res.status_code == 200
    report = report_res.json()
    assert report["matched_item_count"] == 0
    assert report["over_count_item_count"] == 1
    assert report["missing_item_count"] == 0
    assert report["total_variance_qty"] == 1
    assert report["total_variance_value_cents"] == 123
    assert report["groups"][0]["group_code"] == "DA"
    assert report["groups"][0]["group_name"] == "FLAT KEYS"

    complete_res = client.post(f"/v1/stocktakes/{session_id}/complete", headers=headers)
    assert complete_res.status_code == 200
    completed = complete_res.json()
    assert completed["session"]["status"] == "completed"

    stock_item_res = client.get("/v1/stock/items", headers=headers, params={"group_code": "DA"})
    assert stock_item_res.status_code == 200
    assert stock_item_res.json()[0]["system_stock_qty"] == 8

    export_csv_res = client.get(f"/v1/stocktakes/{session_id}/export", headers=headers, params={"format": "csv"})
    assert export_csv_res.status_code == 200
    assert export_csv_res.headers["content-type"].startswith("text/csv")
    assert "DA" in export_csv_res.text
    assert "FLAT KEYS" in export_csv_res.text

    export_xlsx_res = client.get(f"/v1/stocktakes/{session_id}/export", headers=headers, params={"format": "xlsx"})
    assert export_xlsx_res.status_code == 200
    assert export_xlsx_res.headers["content-type"].startswith(
        "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )
    assert export_xlsx_res.content[:2] == b"PK"


def test_stocktake_can_be_deleted_with_lines_and_adjustments():
    suffix = uuid4().hex[:8]
    token = _bootstrap_and_login(
        tenant_slug=f"stocktake-delete-{suffix}",
        email=f"owner-{suffix}@stocktake-delete.test",
        password="pass123456",
    )
    headers = {"Authorization": f"Bearer {token}"}

    import_res = _import_stock(headers)
    assert import_res.status_code == 200

    create_res = client.post(
        "/v1/stocktakes",
        headers=headers,
        json={"name": "Delete me", "group_code": "DA"},
    )
    assert create_res.status_code == 201
    session_id = create_res.json()["id"]

    detail_res = client.get(f"/v1/stocktakes/{session_id}", headers=headers)
    assert detail_res.status_code == 200
    line = detail_res.json()["lines"][0]

    save_res = client.post(
        f"/v1/stocktakes/{session_id}/lines",
        headers=headers,
        json={"lines": [{"stock_item_id": line["stock_item_id"], "counted_qty": 9}]},
    )
    assert save_res.status_code == 200

    complete_res = client.post(f"/v1/stocktakes/{session_id}/complete", headers=headers)
    assert complete_res.status_code == 200

    delete_res = client.delete(f"/v1/stocktakes/{session_id}", headers=headers)
    assert delete_res.status_code == 204

    get_deleted_res = client.get(f"/v1/stocktakes/{session_id}", headers=headers)
    assert get_deleted_res.status_code == 404

    list_res = client.get("/v1/stocktakes", headers=headers)
    assert list_res.status_code == 200
    assert all(item["id"] != session_id for item in list_res.json())