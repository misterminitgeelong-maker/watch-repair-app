"""Additional synthetic records for local native screenshot review; never production."""
import json
import os
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from uuid import UUID

import httpx

root = Path(__file__).resolve().parents[3]
folder = root / "artifacts/native-local-backend"
connection = json.loads((folder / "connection.json").read_text(encoding="utf-8"))
assert connection["base_url"] == "http://127.0.0.1:8716/"
assert connection["slug"].startswith("native-qa-") and connection["email"].endswith("@native.example.test")
database = Path(connection["database"]).resolve()
assert database.is_relative_to(folder.resolve()) and database.name.startswith("native-test-")
os.environ.update(DATABASE_URL=f"sqlite:///{database.as_posix()}", APP_ENV="test")
sys.path.insert(0, str(root / "backend"))
from sqlmodel import Session, select
from app.database import engine
from app.models import Tenant, Quote, ShopMobileBookingRequest, TenantEventLog

client = httpx.Client(base_url=connection["base_url"], timeout=30)
def call(method, path, **kwargs):
    response = client.request(method, path, **kwargs)
    response.raise_for_status()
    return response.json()
tokens = call("POST", "v1/auth/login", json={"tenant_slug": connection["slug"], "email": connection["email"], "password": "Native-local-test-only!"})
client.headers["Authorization"] = "Bearer " + tokens["access_token"]
session = call("GET", "v1/auth/session")
assert session["tenant_id"] == connection["tenant_id"]
ids = json.loads((folder / "parity-data.json").read_text(encoding="utf-8"))
watch_job = call("GET", f"v1/repair-jobs/{ids['watch_job_id']}")
ids["watch_id"] = watch_job["watch_id"]
quotes = call("GET", "v1/quotes", params={"repair_job_id": watch_job["id"], "limit": 500})
quote = next((q for q in quotes if q["repair_job_id"] == watch_job["id"]), None)
if not quote:
    quote = call("POST", "v1/quotes", json={"repair_job_id": watch_job["id"], "gst_enabled": True, "gst_inclusive": True,
        "line_items": [{"item_type": "labor", "description": "Battery replacement and inspection", "quantity": 1, "unit_price_cents": 4500},
                       {"item_type": "part", "description": "Replacement seal", "quantity": 1, "unit_price_cents": 1500}]})
with Session(engine) as db:
    tenant = db.get(Tenant, UUID(session["tenant_id"]))
    assert tenant.slug == connection["slug"]
    tenant.name = "Mainspring Demo Workshop"
    tenant.abn = "00 000 000 000"
    tenant.shop_phone = "03 0000 0000"
    tenant.business_address = "Demo Workshop, Geelong VIC"
    db.add(tenant)
    saved = db.get(Quote, UUID(quote["id"]))
    saved.status = "approved"
    db.add(saved)
    booking = db.exec(select(ShopMobileBookingRequest).where(ShopMobileBookingRequest.requesting_tenant_id == tenant.id)).first()
    if booking is None:
        booking = ShopMobileBookingRequest(parent_account_id=UUID(ids["network_id"]), requesting_tenant_id=tenant.id,
            target_operator_tenant_id=tenant.id, created_by_user_id=UUID(session["user"]["id"]), customer_name="Avery Taylor (Demo)",
            job_address="Geelong VIC", job_suburb="Geelong", job_state_code="VIC", vehicle_make="Toyota", vehicle_model="Corolla",
            job_type="Spare key", notes="Synthetic screenshot review request; no delivery providers.",
            preferred_scheduled_at=datetime.now(timezone.utc) + timedelta(days=1), offer_expires_at=datetime.now(timezone.utc) + timedelta(days=2))
        db.add(booking)
    db.commit()
    db.refresh(booking)
    ids["booking_id"] = str(booking.id)
    notice = db.exec(select(TenantEventLog).where(TenantEventLog.tenant_id == tenant.id, TenantEventLog.event_type == "hq_message")).first()
    if notice is None:
        notice = TenantEventLog(tenant_id=tenant.id, entity_type="tenant", event_type="hq_message",
            event_summary="Demo Support Office update: the new repair workflow is ready for your team to review. This is synthetic screenshot data.")
        db.add(notice); db.commit(); db.refresh(notice)
    ids["hq_notice_id"] = str(notice.id)
invoices = call("GET", "v1/invoices", params={"limit": 500})
if isinstance(invoices, dict): invoices = invoices.get("items", [])
invoice = next((i for i in invoices if i.get("quote_id") == quote["id"]), None)
if not invoice:
    created = call("POST", f"v1/invoices/from-quote/{quote['id']}")
    invoice = created.get("invoice", created)
ids["watch_quote_id"] = quote["id"]
ids["watch_invoice_id"] = invoice["id"]
mobile_jobs = call("GET", "v1/auto-key-jobs", params={"limit": 500})
ids["mobile_job_id"] = next(j["id"] for j in mobile_jobs if j["title"] == "Lockout - Car")
ids["mobile_completed_job_id"] = next(j["id"] for j in mobile_jobs if j["title"] == "Duplicate Key")
ids["mobile_quote_id"] = call("GET", f"v1/auto-key-jobs/{ids['mobile_job_id']}/quotes")[0]["id"]
accounts = call("GET", "v1/customer-accounts")
account = next((a for a in accounts if a["name"] == "Demo Fleet Services"), None)
if not account:
    account = call("POST", "v1/customer-accounts", json={"name": "Demo Fleet Services", "contact_name": "Morgan (Demo)",
        "contact_email": "fleet@native.example.test", "account_type": "Corporate Fleet", "fleet_size": 12,
        "payment_terms_days": 30, "billing_cycle": "Monthly", "notes": "Synthetic account for screenshot review"})
ids["business_account_id"] = account["id"]
aliases = {"customer": "customer_id", "watchJob": "watch_job_id", "watch": "watch_id", "watchQuote": "watch_quote_id",
    "watchInvoice": "watch_invoice_id", "shoeJob": "shoe_job_id", "mobileJob": "mobile_job_id", "mobileCompletedJob": "mobile_completed_job_id",
    "network": "network_id", "conversation": "conversation_id", "engravingEvent": "engraving_event_id", "booking": "booking_id",
    "businessAccount": "business_account_id", "mobileQuote": "mobile_quote_id", "hqNotice": "hq_notice_id"}
ids.update({alias: ids[key] for alias, key in aliases.items()})
(folder / "screen-review-data.json").write_text(json.dumps(ids, indent=2), encoding="utf-8")
print("Local screenshot fixtures ready; no provider delivery was requested.")
