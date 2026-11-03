"""Medal engraving events: QR ordering, operator queue, laser CSV, ready alerts."""
import csv
import io

import pytest
from sqlmodel import Session, select

from app.database import engine
from app.models import SmsLog


@pytest.fixture
def owner(auth_headers):
    return auth_headers


def _make_event(client, headers, **overrides):
    payload = {"name": "Little Athletics — Saturday", "price_cents": 1500, "minutes_per_medal": 3}
    payload.update(overrides)
    res = client.post("/v1/engraving/events", json=payload, headers=headers)
    assert res.status_code == 200, res.text
    return res.json()


def _public_order(client, token, **overrides):
    payload = {"athlete_name": "Mia Thompson", "line2": "U9 Girls 100m", "place": "1st", "qty": 1, "phone": "0412 345 678"}
    payload.update(overrides)
    return client.post(f"/v1/public/engraving/events/{token}/orders", json=payload)


def test_public_order_flow_numbers_and_queue_position(client, owner):
    event = _make_event(client, owner)
    token = event["public_token"]
    assert event["public_url"].endswith(f"/engrave/{token}")

    info = client.get(f"/v1/public/engraving/events/{token}")
    assert info.status_code == 200
    assert info.json()["accepting_orders"] is True
    assert info.json()["wait_minutes"] == 0

    first = _public_order(client, token, qty=2)
    assert first.status_code == 200, first.text
    second = _public_order(client, token, athlete_name="Oliver Nguyen", place="2nd")
    assert second.status_code == 200, second.text

    a, b = first.json(), second.json()
    assert a["order_number"] == "A-001"
    assert b["order_number"] == "A-002"
    assert a["amount_cents"] == 3000
    assert b["queue_position"] == 2
    # 2 medals ahead + own 1, 3 minutes each.
    assert b["wait_minutes"] == 9
    assert b["phone_masked"].startswith("0412")

    status = client.get(f"/v1/public/engraving/orders/{b['status_token']}")
    assert status.status_code == 200
    assert status.json()["status"] == "waiting"

    info = client.get(f"/v1/public/engraving/events/{token}").json()
    assert info["medals_ahead"] == 3


def test_validation_rejects_bad_input(client, owner):
    token = _make_event(client, owner)["public_token"]
    assert _public_order(client, token, athlete_name="  ").status_code == 422
    assert _public_order(client, token, athlete_name="X" * 25).status_code == 422
    assert _public_order(client, token, place="4th").status_code == 422
    assert _public_order(client, token, qty=0).status_code == 422
    assert _public_order(client, token, phone="12").status_code == 422
    assert _public_order(client, token, phone="").status_code == 200


def test_paused_event_refuses_public_orders(client, owner):
    event = _make_event(client, owner)
    res = client.patch(f"/v1/engraving/events/{event['id']}", json={"status": "paused"}, headers=owner)
    assert res.status_code == 200
    assert _public_order(client, event["public_token"]).status_code == 409
    assert client.get(f"/v1/public/engraving/events/{event['public_token']}").json()["accepting_orders"] is False


def test_medal_done_marks_ready_and_texts_once(client, owner):
    event = _make_event(client, owner)
    order = _public_order(client, event["public_token"], qty=2).json()
    queue = client.get(f"/v1/engraving/events/{event['id']}/queue", headers=owner).json()
    order_id = queue["orders"][0]["id"]

    started = client.post(f"/v1/engraving/orders/{order_id}/start", headers=owner)
    assert started.json()["status"] == "engraving"

    one = client.post(f"/v1/engraving/orders/{order_id}/medal-done", headers=owner).json()
    assert one["medals_done"] == 1 and one["status"] == "engraving"
    two = client.post(f"/v1/engraving/orders/{order_id}/medal-done", headers=owner).json()
    assert two["status"] == "ready"
    assert two["ready_sms_status"] == "dry_run"  # no Twilio creds in tests

    again = client.post(f"/v1/engraving/orders/{order_id}/medal-done", headers=owner)
    assert again.status_code == 409

    with Session(engine) as s:
        logs = s.exec(select(SmsLog).where(SmsLog.event == "engraving_ready")).all()
        mine = [l for l in logs if order["status_token"] in l.body]
    assert len(mine) == 1
    assert mine[0].to_phone == "+61412345678"
    assert f"/engrave/o/{order['status_token']}" in mine[0].body

    public = client.get(f"/v1/public/engraving/orders/{order['status_token']}").json()
    assert public["status"] == "ready"
    assert public["queue_position"] is None

    collected = client.patch(f"/v1/engraving/orders/{order_id}", json={"status": "collected"}, headers=owner).json()
    assert collected["status"] == "collected" and collected["collected_at"]


def test_no_text_when_sms_disabled_or_no_phone(client, owner):
    event = _make_event(client, owner, sms_enabled=False)
    _public_order(client, event["public_token"])
    order_id = client.get(f"/v1/engraving/events/{event['id']}/queue", headers=owner).json()["orders"][0]["id"]
    done = client.post(f"/v1/engraving/orders/{order_id}/medal-done", headers=owner).json()
    assert done["status"] == "ready"
    assert done["ready_sms_status"] == "skipped"


def test_only_one_order_engraving_at_a_time(client, owner):
    event = _make_event(client, owner)
    _public_order(client, event["public_token"])
    _public_order(client, event["public_token"], athlete_name="Ava Patel")
    orders = client.get(f"/v1/engraving/events/{event['id']}/queue", headers=owner).json()["orders"]
    first, second = orders[0]["id"], orders[1]["id"]
    client.post(f"/v1/engraving/orders/{first}/start", headers=owner)
    client.post(f"/v1/engraving/orders/{second}/start", headers=owner)
    statuses = {o["id"]: o["status"] for o in client.get(f"/v1/engraving/events/{event['id']}/queue", headers=owner).json()["orders"]}
    assert statuses[first] == "waiting"
    assert statuses[second] == "engraving"


def test_csv_export_one_row_per_remaining_medal(client, owner):
    event = _make_event(client, owner)
    token = event["public_token"]
    _public_order(client, token, qty=3)
    _public_order(client, token, athlete_name="Oliver Nguyen", line2=None, place="Participant")
    _public_order(client, token, athlete_name="Isla Wilson", place="None")
    orders = client.get(f"/v1/engraving/events/{event['id']}/queue", headers=owner).json()["orders"]
    by_name = {o["athlete_name"]: o for o in orders}
    # One of Mia's three medals is already done; Isla is cancelled.
    client.post(f"/v1/engraving/orders/{by_name['Mia Thompson']['id']}/medal-done", headers=owner)
    client.patch(f"/v1/engraving/orders/{by_name['Isla Wilson']['id']}", json={"status": "cancelled"}, headers=owner)

    res = client.get(f"/v1/engraving/events/{event['id']}/export.csv", headers=owner)
    assert res.status_code == 200
    assert res.headers["content-type"].startswith("text/csv")
    rows = list(csv.reader(io.StringIO(res.text)))
    assert rows[0] == ["Name", "Line2", "Place", "Order", "Medal"]
    assert rows[1:] == [
        ["Mia Thompson", "U9 Girls 100m", "1st Place", "A-001", "2 of 3"],
        ["Mia Thompson", "U9 Girls 100m", "1st Place", "A-001", "3 of 3"],
        ["Oliver Nguyen", "", "Participant", "A-002", "1 of 1"],
    ]

    paid_only = client.get(f"/v1/engraving/events/{event['id']}/export.csv?paid_only=true", headers=owner)
    assert list(csv.reader(io.StringIO(paid_only.text)))[1:] == []


def test_walk_up_order_and_stats(client, owner):
    event = _make_event(client, owner)
    res = client.post(
        f"/v1/engraving/events/{event['id']}/orders",
        json={"athlete_name": "Jack Lee", "qty": 2, "paid": True},
        headers=owner,
    )
    assert res.status_code == 200, res.text
    assert res.json()["source"] == "walk_up" and res.json()["paid"] is True
    _public_order(client, event["public_token"])
    stats = client.get(f"/v1/engraving/events/{event['id']}/queue", headers=owner).json()["event"]["stats"]
    assert stats["waiting"] == 2
    assert stats["medals_total"] == 3
    assert stats["paid_cents"] == 3000
    assert stats["unpaid_cents"] == 1500


def test_tenant_isolation(client, owner, bootstrap_and_login):
    event = _make_event(client, owner)
    other = {"Authorization": f"Bearer {bootstrap_and_login()}"}
    assert client.get(f"/v1/engraving/events/{event['id']}/queue", headers=other).status_code == 404
    assert client.get("/v1/engraving/events", headers=other).json() == []
    _public_order(client, event["public_token"])
    order_id = client.get(f"/v1/engraving/events/{event['id']}/queue", headers=owner).json()["orders"][0]["id"]
    assert client.post(f"/v1/engraving/orders/{order_id}/medal-done", headers=other).status_code == 404


def test_export_formats_and_limit(client, owner):
    import zipfile

    event = _make_event(client, owner)
    token = event["public_token"]
    _public_order(client, token, athlete_name="Mia Thompson", line2="U9 Girls 100m", place="1st", qty=2)
    _public_order(client, token, athlete_name="Oliver Nguyen", line2=None, place="Participant")
    base = f"/v1/engraving/events/{event['id']}/export"

    lb = client.get(f"{base}?software=lightburn", headers=owner)
    assert lb.status_code == 200
    rows = list(csv.reader(io.StringIO(lb.text)))
    assert rows[0] == ["Mia Thompson", "U9 Girls 100m", "1st Place", "A-001", "1 of 2"]  # no header row
    assert len(rows) == 3

    xt = client.get(f"{base}?software=xtool", headers=owner)
    xt_rows = list(csv.reader(io.StringIO(xt.text)))
    assert xt_rows[0] == ["Name", "Line2", "Place", "Order", "Medal"]
    assert xt_rows[3][1] == " "  # blank second line becomes a space so xTool doesn't skip the row

    limited = client.get(f"{base}?software=lightburn&limit=2", headers=owner)
    assert len(list(csv.reader(io.StringIO(limited.text)))) == 2

    ez = client.get(f"{base}?software=ezcad2", headers=owner)
    assert ez.headers["content-type"] == "application/zip"
    zf = zipfile.ZipFile(io.BytesIO(ez.content))
    assert zf.read("names.txt").decode().split("\r\n")[:3] == ["Mia Thompson", "Mia Thompson", "Oliver Nguyen"]
    assert zf.read("line2.txt").decode().split("\r\n")[2] == " "
    assert zf.read("places.txt").decode().split("\r\n")[0] == "1st Place"

    assert client.get(f"{base}?software=bogus", headers=owner).status_code == 422
    other = client.get(f"/v1/engraving/events/{event['id']}/export", headers={"Authorization": "Bearer nope"})
    assert other.status_code in (401, 403)
