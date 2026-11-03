"""Medal engraving events: QR ordering, operator queue, laser CSV, ready alerts."""
import csv
import io
from uuid import UUID

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


def test_public_batch_order_creates_one_order_per_medal(client, owner):
    event = _make_event(client, owner)
    token = event["public_token"]
    res = client.post(
        f"/v1/public/engraving/events/{token}/orders/batch",
        json={
            "orders": [
                {"athlete_name": "Mia Thompson", "line2": "U9 100m", "place": "1st", "qty": 1},
                {"athlete_name": "Leo Thompson", "place": "3rd", "qty": 2},
            ],
            "phone": "0412 345 678",
            "ticket_number": " 17 ",
        },
    )
    assert res.status_code == 200, res.text
    body = res.json()
    assert [o["order_number"] for o in body] == ["A-001", "A-002"]
    assert all(o["ticket_number"] == "17" for o in body)
    assert body[1]["amount_cents"] == 3000
    assert all(o["phone_masked"] for o in body)
    # Medals ordered together know about each other; a single order has no group.
    assert [m["order_number"] for m in body[0]["group_members"]] == ["A-002"]
    assert [m["order_number"] for m in body[1]["group_members"]] == ["A-001"]
    single = _public_order(client, token, athlete_name="Solo Kid").json()
    assert client.get(f"/v1/public/engraving/orders/{single['status_token']}").json()["group_members"] == []
    queue_orders = client.get(f"/v1/engraving/events/{event['id']}/queue", headers=owner).json()["orders"]
    groups = {o["order_number"]: o["group_id"] for o in queue_orders}
    assert groups["A-001"] == groups["A-002"] and groups["A-001"] is not None and groups["A-003"] is None
    queue = client.get(f"/v1/engraving/events/{event['id']}/queue", headers=owner).json()
    assert queue["event"]["stats"]["medals_total"] == 4


def test_public_batch_is_all_or_nothing_and_bounded(client, owner):
    event = _make_event(client, owner)
    token = event["public_token"]
    url = f"/v1/public/engraving/events/{token}/orders/batch"
    bad = client.post(url, json={"ticket_number": "5", "orders": [
        {"athlete_name": "Mia Thompson", "qty": 1},
        {"athlete_name": "", "qty": 1},
    ]})
    assert bad.status_code == 422
    assert client.get(f"/v1/engraving/events/{event['id']}/queue", headers=owner).json()["event"]["stats"]["medals_total"] == 0
    assert client.post(url, json={"ticket_number": "5", "orders": []}).status_code == 422
    too_many = [{"athlete_name": f"Kid {i}", "qty": 1} for i in range(11)]
    assert client.post(url, json={"ticket_number": "5", "orders": too_many}).status_code == 422
    client.patch(f"/v1/engraving/events/{event['id']}", json={"status": "paused"}, headers=owner)
    assert client.post(url, json={"ticket_number": "5", "orders": [{"athlete_name": "Mia", "qty": 1}]}).status_code == 409


def test_public_batch_requires_unique_ticket(client, owner):
    event = _make_event(client, owner)
    url = f"/v1/public/engraving/events/{event['public_token']}/orders/batch"
    one = {"orders": [{"athlete_name": "Mia", "qty": 1}]}
    assert client.post(url, json=one).status_code == 422  # ticket missing
    assert client.post(url, json={**one, "ticket_number": "  "}).status_code == 422
    first = client.post(url, json={**one, "ticket_number": "ab12"})
    assert first.status_code == 200 and first.json()[0]["ticket_number"] == "AB12"
    assert client.post(url, json={**one, "ticket_number": "AB12"}).status_code == 409
    # Once the tub has been collected the ticket can be used again.
    order = client.get(f"/v1/engraving/events/{event['id']}/queue", headers=owner).json()["orders"][0]
    client.patch(f"/v1/engraving/orders/{order['id']}", json={"status": "collected"}, headers=owner)
    assert client.post(url, json={**one, "ticket_number": "ab12"}).status_code == 200


# ── Online card payments ─────────────────────────────────────────────────────

def _enable_card_payments(monkeypatch, headers, client):
    from uuid import UUID

    from app.config import settings
    from app.models import Tenant

    monkeypatch.setattr(settings, "enable_stripe_invoice_checkout", True)
    monkeypatch.setattr(settings, "stripe_secret_key", "sk_test_123")
    tid = UUID(client.get("/v1/auth/session", headers=headers).json()["tenant_id"])
    with Session(engine) as s:
        t = s.get(Tenant, tid)
        t.stripe_connect_account_id = "acct_shop1"
        t.stripe_connect_charges_enabled = True
        s.add(t)
        s.commit()
    return tid


def _batch(client, token):
    res = client.post(
        f"/v1/public/engraving/events/{token}/orders/batch",
        json={
            "orders": [
                {"athlete_name": "Mia Thompson", "place": "1st", "qty": 1},
                {"athlete_name": "Leo Thompson", "place": "3rd", "qty": 2},
            ],
            "phone": "0412 345 678",
            "ticket_number": "21",
        },
    )
    assert res.status_code == 200, res.text
    return res.json()


def test_card_payment_hidden_until_shop_has_stripe(client, owner):
    event = _make_event(client, owner)
    assert event["online_payments_ready"] is False
    order = _public_order(client, event["public_token"]).json()
    assert order["can_pay_online"] is False
    res = client.post(f"/v1/public/engraving/orders/{order['status_token']}/checkout")
    assert res.status_code == 503


def test_checkout_covers_the_whole_group_and_charges_shop_account(client, owner, monkeypatch):
    _enable_card_payments(monkeypatch, owner, client)
    event = _make_event(client, owner)
    assert event["online_payments_ready"] is True
    orders = _batch(client, event["public_token"])
    status = client.get(f"/v1/public/engraving/orders/{orders[0]['status_token']}").json()
    assert status["can_pay_online"] is True
    assert status["amount_due_cents"] == 4500

    captured = {}

    class FakeSession:
        @staticmethod
        def create(**params):
            captured.update(params)
            return type("S", (), {"url": "https://checkout.stripe.test/c/1"})()

    import stripe

    monkeypatch.setattr(stripe.checkout, "Session", FakeSession)
    res = client.post(f"/v1/public/engraving/orders/{orders[0]['status_token']}/checkout")
    assert res.status_code == 200, res.text
    assert res.json()["checkout_url"] == "https://checkout.stripe.test/c/1"
    assert captured["stripe_account"] == "acct_shop1"
    assert captured["metadata"]["purpose"] == "engraving_orders"
    assert sum(i["price_data"]["unit_amount"] for i in captured["line_items"]) == 4500
    assert len(captured["metadata"]["engraving_order_ids"].split(",")) == 2


def test_paid_webhook_marks_group_paid_once(client, owner, monkeypatch):
    from app.routes.engraving import apply_engraving_checkout
    from app.models import EngravingOrder

    _enable_card_payments(monkeypatch, owner, client)
    event = _make_event(client, owner)
    orders = _batch(client, event["public_token"])
    queue = client.get(f"/v1/engraving/events/{event['id']}/queue", headers=owner).json()["orders"]
    ids = ",".join(o["id"] for o in queue)
    obj = {
        "id": "cs_eng_1", "payment_status": "paid", "amount_total": 4500,
        "metadata": {"purpose": "engraving_orders", "engraving_order_ids": ids},
    }
    with Session(engine) as s:
        apply_engraving_checkout(s, obj, connect_account="acct_shop1")
        apply_engraving_checkout(s, obj, connect_account="acct_shop1")  # redelivery is harmless
        rows = [s.get(EngravingOrder, UUID(i)) for i in ids.split(",")]
        assert all(o.paid and o.payment_method == "stripe" and o.stripe_checkout_id == "cs_eng_1" for o in rows)
    status = client.get(f"/v1/public/engraving/orders/{orders[0]['status_token']}").json()
    assert status["paid"] is True and status["can_pay_online"] is False
    assert client.post(f"/v1/public/engraving/orders/{orders[0]['status_token']}/checkout").status_code == 409


def test_webhook_ignores_wrong_account_and_wrong_amount(client, owner, monkeypatch):
    from app.routes.engraving import apply_engraving_checkout
    from app.models import EngravingOrder

    _enable_card_payments(monkeypatch, owner, client)
    event = _make_event(client, owner)
    _batch(client, event["public_token"])
    queue = client.get(f"/v1/engraving/events/{event['id']}/queue", headers=owner).json()["orders"]
    ids = ",".join(o["id"] for o in queue)
    base = {"id": "cs_x", "payment_status": "paid", "metadata": {"purpose": "engraving_orders", "engraving_order_ids": ids}}
    with Session(engine) as s:
        apply_engraving_checkout(s, {**base, "amount_total": 4500}, connect_account="acct_someone_else")
        apply_engraving_checkout(s, {**base, "amount_total": 100}, connect_account="acct_shop1")
        assert not any(s.get(EngravingOrder, UUID(i)).paid for i in ids.split(","))


def test_operator_marking_paid_records_stall_payment(client, owner):
    event = _make_event(client, owner)
    order = client.post(
        f"/v1/engraving/events/{event['id']}/orders",
        json={"athlete_name": "Walk Up", "paid": True},
        headers=owner,
    ).json()
    assert order["paid"] and order["payment_method"] == "stall"
