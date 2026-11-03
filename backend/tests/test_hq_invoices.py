"""Issued HQ bundled invoices: freeze, Stripe issue, webhook paid, access."""
from types import SimpleNamespace
from uuid import uuid4

from fastapi.testclient import TestClient
from sqlmodel import Session

from app.database import engine
from app.main import app
from app.models import HqInvoice, ParentAccount
from app.routes import billing as billing_routes
from app.routes import hq_billing
from tests.test_minit_plan_and_billing import _network

client = TestClient(app)
BASE = "/v1/hq-billing"


class FakeStripe:
    def __init__(self, fail_on=None):
        self.calls, self.fail_on = [], fail_on
        outer = self

        class _Obj:
            def __init__(self, name):
                self.name = name

            def __getattr__(self, fn):
                def call(*a, **kw):
                    outer.calls.append((self.name, fn, a, kw))
                    if outer.fail_on == (self.name, fn):
                        raise RuntimeError("boom")
                    if fn == "create" and self.name == "Customer":
                        return {"id": "cus_1"}
                    if fn == "create" and self.name == "Invoice":
                        return {"id": f"in_{uuid4().hex[:8]}"}
                    if fn == "send_invoice":
                        return {"hosted_invoice_url": "https://pay.example/in", "invoice_pdf": "https://pay.example/in.pdf"}
                    return {}
                return call

        for n in ("Customer", "Invoice", "InvoiceItem"):
            setattr(self, n, _Obj(n))


def _setup(monkeypatch, fake=None):
    fake = fake or FakeStripe()
    monkeypatch.setattr(hq_billing, "_stripe", lambda: fake)
    return fake


def test_settings_drive_summary_and_only_admin_writes(monkeypatch):
    pid, hq, other, admin = _network()
    assert client.put(f"{BASE}/settings", headers=hq, params={"parent_account_id": pid},
                      json={"routing_addon": True, "prospecting_addon": False}).status_code == 403
    r = client.put(f"{BASE}/settings", headers=admin, params={"parent_account_id": pid},
                   json={"routing_addon": True, "prospecting_addon": True, "billing_email": "ap@minit.test"})
    assert r.status_code == 200 and r.json()["billing_email"] == "ap@minit.test"
    d = client.get(f"{BASE}/monthly-summary", headers=hq, params={"month": "2027-03"}).json()
    # 2 billable operators x (55 + 25 + 25)
    assert d["subtotal_ex_gst_cents"] == 2 * 10500 and d["routing"] and d["prospecting"]
    # explicit flag still overrides the saved setting
    d2 = client.get(f"{BASE}/monthly-summary", headers=hq, params={"month": "2027-03", "routing": "false", "prospecting": "false"}).json()
    assert d2["subtotal_ex_gst_cents"] == 2 * 5500
    assert client.put(f"{BASE}/settings", headers=admin, params={"parent_account_id": pid},
                      json={"routing_addon": False, "prospecting_addon": False, "billing_email": "nope"}).status_code == 422


def test_create_freeze_issue_and_pay(monkeypatch):
    fake = _setup(monkeypatch)
    pid, hq, other, admin = _network()
    assert client.post(f"{BASE}/invoices", headers=hq, json={"parent_account_id": pid, "month": "2026-11"}).status_code == 403
    r = client.post(f"{BASE}/invoices", headers=admin, json={"parent_account_id": pid, "month": "2026-11"})
    assert r.status_code == 201, r.text
    inv = r.json()
    assert inv["status"] == "draft" and inv["operator_count"] == 2
    assert inv["subtotal_ex_gst_cents"] == 11000 and inv["gst_cents"] == 550 + 825
    # redraft is allowed until issued
    assert client.post(f"{BASE}/invoices", headers=admin, json={"parent_account_id": pid, "month": "2026-11"}).json()["id"] == inv["id"]

    r = client.post(f"{BASE}/invoices/{inv['id']}/issue", headers=admin)
    assert r.status_code == 200, r.text
    out = r.json()
    assert out["status"] == "issued" and out["stripe_hosted_url"] == "https://pay.example/in" and out["due_at"]
    items = [c for c in fake.calls if c[0] == "InvoiceItem"]
    assert sum(c[3]["amount"] for c in items) == inv["total_inc_gst_cents"]
    created = next(c for c in fake.calls if c[:2] == ("Invoice", "create"))
    assert created[3]["collection_method"] == "send_invoice" and created[3]["pending_invoice_items_behavior"] == "exclude"
    # frozen: cannot redraft or reissue
    assert client.post(f"{BASE}/invoices", headers=admin, json={"parent_account_id": pid, "month": "2026-11"}).status_code == 409
    assert client.post(f"{BASE}/invoices/{inv['id']}/issue", headers=admin).status_code == 409

    # HQ owner can read their invoice + pdf; an unrelated owner cannot
    assert client.get(f"{BASE}/invoices", headers=hq).json()["invoices"][0]["id"] == inv["id"]
    pdf = client.get(f"{BASE}/invoices/{inv['id']}/pdf", headers=hq)
    assert pdf.status_code == 200 and pdf.content.startswith(b"%PDF")
    assert client.get(f"{BASE}/invoices/{inv['id']}", headers=other).status_code in (403, 404)

    # Stripe tells us it was paid
    with Session(engine) as s:
        sid = s.get(HqInvoice, __import__("uuid").UUID(inv["id"])).stripe_invoice_id
        res = billing_routes._handle_invoice_paid(s, {"id": sid, "subscription": None}, None)
        assert res == {"status": "ok"}
        row = s.get(HqInvoice, __import__("uuid").UUID(inv["id"]))
        assert row.status == "paid" and row.paid_at
    assert client.post(f"{BASE}/invoices/{inv['id']}/void", headers=admin).status_code == 409


def test_stripe_failure_leaves_draft_and_voids_partial(monkeypatch):
    fake = _setup(monkeypatch, FakeStripe(fail_on=("Invoice", "finalize_invoice")))
    pid, hq, other, admin = _network()
    inv = client.post(f"{BASE}/invoices", headers=admin, json={"parent_account_id": pid, "month": "2026-12"}).json()
    r = client.post(f"{BASE}/invoices/{inv['id']}/issue", headers=admin)
    assert r.status_code == 502
    assert any(c[:2] == ("Invoice", "void_invoice") for c in fake.calls)
    assert client.get(f"{BASE}/invoices/{inv['id']}", headers=admin).json()["status"] == "draft"


def test_void_issued_invoice_and_no_operators(monkeypatch):
    fake = _setup(monkeypatch)
    pid, hq, other, admin = _network()
    inv = client.post(f"{BASE}/invoices", headers=admin, json={"parent_account_id": pid, "month": "2027-01"}).json()
    client.post(f"{BASE}/invoices/{inv['id']}/issue", headers=admin)
    r = client.post(f"{BASE}/invoices/{inv['id']}/void", headers=admin)
    assert r.status_code == 200 and r.json()["status"] == "void"
    assert any(c[:2] == ("Invoice", "void_invoice") for c in fake.calls)
    with Session(engine) as s:
        empty = ParentAccount(name="Empty", owner_email="e@test.com")
        s.add(empty)
        s.commit()
        eid = str(empty.id)
    assert client.post(f"{BASE}/invoices", headers=admin, json={"parent_account_id": eid, "month": "2027-01"}).status_code == 422
