"""Synthetic parity walkthrough data for the disposable localhost native QA server.

The helper refuses non-loopback APIs and databases outside its QA artifact folder.
It creates no production data and never uses delivery-provider credentials. Run
with the repository Python environment after qa/local_backend.py (or its restart
using the same disposable database). Re-running preserves existing demo records.
"""
from __future__ import annotations

import json
import os
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from uuid import UUID
from zoneinfo import ZoneInfo

import httpx


def main() -> None:
    root = Path(__file__).resolve().parents[3]
    artifacts = (root / "artifacts/native-local-backend").resolve()
    metadata = json.loads((artifacts / "connection.json").read_text(encoding="utf-8"))
    assert metadata["base_url"] == "http://127.0.0.1:8716/", "Only the disposable localhost API is permitted"
    assert metadata["slug"].startswith("native-qa-")
    assert metadata["email"].endswith("@native.example.test")
    database = Path(metadata["database"]).resolve(strict=True)
    assert database.is_relative_to(artifacts), "The database must remain in native-local-backend"
    assert database.name.startswith("native-test-") and database.suffix == ".db"
    # These settings apply only to this seed process. The running QA server must
    # also have its delivery integrations disabled (as local_backend.py does).
    os.environ.update({
        "DATABASE_URL": f"sqlite:///{database.as_posix()}", "APP_ENV": "test",
        "ENABLE_EMAIL_NOTIFICATIONS": "false", "SENDGRID_API_KEY": "",
        "TWILIO_ACCOUNT_SID": "", "TWILIO_AUTH_TOKEN": "", "TWILIO_FROM_NUMBER": "",
        "FCM_SERVICE_ACCOUNT_JSON": "", "STRIPE_SECRET_KEY": "", "SENTRY_DSN": "",
        "RUN_SWEEPS_IN_WEB_PROCESS": "false", "STARTUP_SEED_ENABLED": "false",
    })
    sys.path.insert(0, str(root / "backend"))
    from sqlmodel import Session, create_engine, select
    from app.models import (
        Customer, EngravingEvent, EngravingOrder, HqPurchaseRecord, HqSettings,
        HqShoeModel, HqShoeModelPart, NetworkAnnouncement, NetworkConversation,
        NetworkMessage, ParentAccount, ParentAccountSite, ParentAccountUser, Region,
        RepairJob, Shoe, ShoeRepairJob, ShoeRepairJobItem, StateHubMessage,
        StockLevel, StockLocation, StockPart, StockTransfer, StockTransferLine,
        Tenant, TenantEventLog, User, Watch,
    )
    from app.security import hash_password

    client = httpx.Client(base_url=metadata["base_url"], timeout=30, trust_env=False, follow_redirects=False)

    def call(method: str, path: str, **kwargs):
        response = client.request(method, path, **kwargs)
        response.raise_for_status()
        return response.json() if response.content else None

    login = call("POST", "v1/auth/login", json={"tenant_slug": metadata["slug"], "email": metadata["email"], "password": "Native-local-test-only!"})
    client.headers["Authorization"] = "Bearer " + login["access_token"]
    api_session = call("GET", "v1/auth/session")
    assert api_session["tenant_id"] == metadata["tenant_id"]
    tenant_id = UUID(metadata["tenant_id"])
    day = datetime.now(ZoneInfo(api_session["schedule_calendar_timezone"])).date()
    now = datetime.now(timezone.utc)
    # Pro bootstrap may already provision the owner's multi-shop parent. Reuse
    # the exact parent returned to this login so the My Shops page and stock
    # network are the same account, rather than introducing a competing parent.
    parent_summary = call("GET", "v1/parent-accounts/me")
    existing_parent_id = UUID(parent_summary["parent_account_id"])
    engine = create_engine(f"sqlite:///{database.as_posix()}", connect_args={"check_same_thread": False})

    with Session(engine) as db:
        tenant = db.get(Tenant, tenant_id)
        assert tenant and tenant.slug == metadata["slug"] and tenant.plan_code == "pro"
        owner = db.exec(select(User).where(User.tenant_id == tenant_id, User.email == metadata["email"])).one()
        assert owner.role == "owner"

        def ensure(model_type, identity: dict, **values):
            statement = select(model_type)
            for key, value in identity.items():
                statement = statement.where(getattr(model_type, key) == value)
            row = db.exec(statement).first()
            if row is None:
                row = model_type(**identity, **values)
                db.add(row)
                db.flush()
            return row

        network = db.get(ParentAccount, existing_parent_id)
        assert network is not None
        region = ensure(Region, {"parent_account_id": network.id, "code": "VIC DEMO"}, name="Victoria Demo Region")
        ensure(HqSettings, {"parent_account_id": network.id}, product_key="native-parity-demo", display_name="Mainspring Demo Network",
               modules_json=json.dumps(["shoe", "watch", "stock", "mobile_services"]), site_plans_json=json.dumps(["pro", "basic_shoe"]))
        own_site = ensure(ParentAccountSite, {"parent_account_id": network.id, "tenant_id": tenant_id}, network_role="retail", region_id=region.id, messaging_state="VIC")
        own_site.region_id = region.id
        own_site.messaging_state = "VIC"
        db.add(own_site)
        # The verified local owner can open My Shops, while the active shop keeps
        # its Pro plan and retail identity (it is not changed into an HQ tenant).
        ensure(ParentAccountUser, {"parent_account_id": network.id, "user_id": owner.id}, role="hq_admin")
        partner = ensure(Tenant, {"slug": metadata["slug"] + "-partner"}, name="Chadstone (Parity Demo)", plan_code="basic_shoe", timezone="Australia/Melbourne")
        partner_email = metadata["email"].replace("owner-", "partner-")
        partner_user = ensure(User, {"tenant_id": partner.id, "email": partner_email}, full_name="Alex (Demo)", role="owner", password_hash=hash_password("Native-local-test-only!"))
        ensure(ParentAccountSite, {"parent_account_id": network.id, "tenant_id": partner.id}, network_role="retail", region_id=region.id, messaging_state="VIC")

        customer = ensure(Customer, {"tenant_id": tenant_id, "full_name": "Avery Lee (Parity Demo)"}, email="avery@native.example.test", notes="Synthetic localhost data only")
        watch = ensure(Watch, {"tenant_id": tenant_id, "customer_id": customer.id, "serial_number": "DEMO-WATCH-01"}, brand="Seiko", model="5 Sports (Demo)", movement_type="automatic", condition_notes="Intake checklist: scratched clasp; crystal intact; crown present. Demo only.")
        watch_job = ensure(RepairJob, {"tenant_id": tenant_id, "job_number": "DEMO-W-001"}, watch_id=watch.id, title="Movement service (Demo)", description="Check timekeeping and worn crown seal.", status="no_go", priority="normal", cost_cents=19500, pre_quote_cents=18000, deposit_cents=2000, internal_notes="Demo: customer considering the quote; keep this No Go job active until collection.", collection_date=day + timedelta(days=4), salesperson="Native QA Owner")
        purchase_day = day - timedelta(days=30)
        shoe = ensure(Shoe, {"tenant_id": tenant_id, "customer_id": customer.id, "purchase_ref": "DEMO-RECEIPT-001"}, shoe_type="Birkenstocks", brand="Birkenstock", model_name="Arizona", size="41", color="Tan", description_notes="Worn footbed and buckle. Demo only.", purchase_date=purchase_day, purchase_store="Geelong (Demo)")
        shoe_job = ensure(ShoeRepairJob, {"tenant_id": tenant_id, "job_number": "DEMO-S-001"}, shoe_id=shoe.id, title="Arizona footbed replacement (Demo)", status="awaiting_parts", description="Demonstrates model, purchase warranty and suggested parts.", cost_cents=8900, deposit_cents=2000, collection_date=day + timedelta(days=3), salesperson="Native QA Owner")
        ensure(ShoeRepairJobItem, {"tenant_id": tenant_id, "shoe_repair_job_id": shoe_job.id, "catalogue_key": "demo-footbed"}, catalogue_group="demo", item_name="Footbed replacement (Demo)", pricing_type="fixed", unit_price_cents=8900, quantity=1)
        ensure(HqPurchaseRecord, {"parent_account_id": network.id, "purchase_ref": "DEMO-RECEIPT-001"}, purchase_date=purchase_day, store="Geelong (Demo)", customer_name=customer.full_name, customer_email="avery@native.example.test", model_name="Arizona", size="41")
        model = ensure(HqShoeModel, {"parent_account_id": network.id, "name": "Arizona"}, category="sandal")
        sole = ensure(StockPart, {"parent_account_id": network.id, "sku": "DEMO-ARI-41"}, name="Arizona footbed size 41 (Demo)", part_type="footbed", cost_cents=1800, reorder_level=5)
        buckle = ensure(StockPart, {"parent_account_id": network.id, "sku": "DEMO-BUCKLE"}, name="Buckle (Demo)", part_type="buckle", cost_cents=300, reorder_level=2)
        ensure(HqShoeModelPart, {"parent_account_id": network.id, "model_id": model.id, "part_id": sole.id, "size": "41"}, quantity=1)
        ensure(HqShoeModelPart, {"parent_account_id": network.id, "model_id": model.id, "part_id": buckle.id, "size": None}, quantity=2)
        location = ensure(StockLocation, {"parent_account_id": network.id, "name": "Geelong Demo Shop"}, kind="store", tenant_id=tenant_id)
        warehouse = ensure(StockLocation, {"parent_account_id": network.id, "name": "Demo Warehouse"}, kind="warehouse")
        for loc, part, quantity in ((location, sole, 3), (location, buckle, 4), (warehouse, sole, 18), (warehouse, buckle, 20)):
            ensure(StockLevel, {"parent_account_id": network.id, "location_id": loc.id, "part_id": part.id}, quantity=quantity)
        transfer = ensure(StockTransfer, {"parent_account_id": network.id, "from_location_id": warehouse.id, "to_location_id": location.id, "note": "Demo incoming parts"}, created_by_user_id=owner.id)
        ensure(StockTransferLine, {"transfer_id": transfer.id, "part_id": sole.id}, quantity=2)

        hub = ensure(StateHubMessage, {"parent_account_id": network.id, "state_code": "VIC", "body": "Demo stock request: does anyone have Arizona footbeds in size 41?"}, sender_tenant_id=partner.id, sender_user_id=partner_user.id, kind="stock_request", pinned_at=now)
        ensure(StateHubMessage, {"parent_account_id": network.id, "state_code": "VIC", "body": "Demo reply: Geelong has three pairs available. Happy to arrange a transfer."}, sender_tenant_id=tenant_id, sender_user_id=owner.id, reply_to_id=hub.id, created_at=now + timedelta(seconds=1))
        low, high = sorted((tenant_id, partner.id))
        conversation = ensure(NetworkConversation, {"parent_account_id": network.id, "tenant_low_id": low, "tenant_high_id": high}, last_message_at=now)
        ensure(NetworkMessage, {"conversation_id": conversation.id, "body": "Demo direct message: the replacement buckles are ready for your next transfer."}, sender_tenant_id=partner.id, sender_user_id=partner_user.id)
        announcement = ensure(NetworkAnnouncement, {"parent_account_id": network.id, "title": "Demo: Saturday engraving setup"}, state_code="VIC", body="Synthetic training announcement. Check the medal preview, confirm names and use the ready queue for pickup.", category="training", pinned=True, requires_confirmation=True, author_user_id=partner_user.id)
        ensure(TenantEventLog, {"tenant_id": tenant_id, "event_type": "network_message", "entity_id": conversation.id}, entity_type="network_conversation", event_summary="Demo message from Chadstone", actor_email=partner_email)
        ensure(TenantEventLog, {"tenant_id": tenant_id, "event_type": "network_announcement", "entity_id": announcement.id}, entity_type="network_announcement", event_summary=announcement.title, actor_email=partner_email)
        event = ensure(EngravingEvent, {"tenant_id": tenant_id, "name": "Saturday athletics (Parity Demo)"}, event_date=day, location="Geelong Demo Oval", price_cents=1500, minutes_per_medal=3, sms_enabled=False, online_payments=False)
        for seq, name, line2, place, qty, done, status, paid in ((1, "Avery Lee (Demo)", "100 metres", "1st", 2, 0, "engraving", True), (2, "Jordan Kim (Demo)", "Long jump", "2nd", 1, 0, "waiting", False), (3, "Taylor Ng (Demo)", "Relay", "Participant", 1, 1, "ready", True)):
            ensure(EngravingOrder, {"tenant_id": tenant_id, "event_id": event.id, "order_seq": seq}, order_number=f"DEMO-{seq:03d}", athlete_name=name, line2=line2, place=place, qty=qty, medals_done=done, status=status, paid=paid, payment_method="stall" if paid else None, amount_cents=1500 * qty, source="walk_up", notes="Synthetic walkthrough order; provider delivery disabled", ready_sms_status="skipped" if status == "ready" else None)
        event.next_order_seq = max(event.next_order_seq, 4)
        db.add(event)
        db.commit()
        ids = {"network_id": str(network.id), "region_id": str(region.id), "customer_id": str(customer.id), "watch_job_id": str(watch_job.id), "shoe_job_id": str(shoe_job.id), "part_sku": sole.sku, "part_id": str(sole.id), "location_id": str(location.id), "recipient_tenant_id": str(partner.id), "conversation_id": str(conversation.id), "engraving_event_id": str(event.id), "announcement_id": str(announcement.id)}

    # Verify the running real API sees the same data and computed warranty fields.
    networks = call("GET", "v1/network-community/networks")
    assert any(n["id"] == ids["network_id"] for n in networks)
    hubs = call("GET", f"v1/network-community/{ids['network_id']}/hubs")
    assert any(h["code"] == "VIC" and h["accessible"] for h in hubs)
    assert call("GET", f"v1/network-community/{ids['network_id']}/hubs/VIC/messages")["messages"]
    assert any(c["id"] == ids["conversation_id"] for c in call("GET", "v1/network-messages/conversations"))
    assert any(a["id"] == ids["announcement_id"] for a in call("GET", f"v1/network-community/{ids['network_id']}/announcements")["announcements"])
    actual_shoe = call("GET", f"v1/shoe-repair-jobs/{ids['shoe_job_id']}")
    assert actual_shoe["shoe"]["model_name"] == "Arizona" and actual_shoe["shoe"]["warranty_status"] == "in_warranty"
    assert any(row["sku"] == ids["part_sku"] for row in call("GET", "v1/stock/levels"))
    assert any(row["part_id"] == ids["part_id"] for row in call("GET", f"v1/stock/jobs/{ids['shoe_job_id']}/suggested-parts"))
    assert any(row["purchase_ref"] == "DEMO-RECEIPT-001" for row in call("GET", "v1/stock/purchases/search", params={"q": "DEMO"}))
    assert call("GET", "v1/parent-accounts/me")["parent_account_id"] == ids["network_id"]
    engraving = call("GET", f"v1/engraving/events/{ids['engraving_event_id']}/queue")
    assert len(engraving["orders"]) >= 3 and not engraving["event"]["sms_enabled"] and not engraving["event"]["online_payments"]
    (artifacts / "parity-data.json").write_text(json.dumps({"source": "disposable localhost synthetic data only", "tenant_id": metadata["tenant_id"], "database": str(database), "day": str(day), **ids}, indent=2), encoding="utf-8")
    client.close()
    print("Seeded and verified synthetic watch, Birkenstock purchase/warranty/parts, network chats, My Shops and engraving data.")


if __name__ == "__main__":
    main()
