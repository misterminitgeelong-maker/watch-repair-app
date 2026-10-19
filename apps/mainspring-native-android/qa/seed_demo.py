"""Synthetic UI walkthrough data. Accepts only the disposable localhost helper."""
import datetime
import json
from pathlib import Path
from zoneinfo import ZoneInfo
import httpx

root = Path(__file__).resolve().parents[3]
metadata = json.loads((root / "artifacts/native-local-backend/connection.json").read_text(encoding="utf-8"))
assert metadata["base_url"] == "http://127.0.0.1:8716/"
assert metadata["slug"].startswith("native-qa-") and metadata["email"].endswith("@native.example.test")
client = httpx.Client(base_url=metadata["base_url"], timeout=30)
response = client.post("v1/auth/login", json={"tenant_slug": metadata["slug"], "email": metadata["email"], "password": "Native-local-test-only!"})
response.raise_for_status()
client.headers["Authorization"] = "Bearer " + response.json()["access_token"]
session = client.get("v1/auth/session").json()
assert session["tenant_id"] == metadata["tenant_id"]
zone = ZoneInfo(session["schedule_calendar_timezone"])
day = datetime.datetime.now(zone).date()
output = root / "artifacts/native-design-2026-10-08/demo-records.json"
if output.exists():
    previous = json.loads(output.read_text(encoding="utf-8"))
    if previous.get("tenant_id") == metadata["tenant_id"] and previous.get("day") == str(day):
        print("Synthetic walkthrough data is already present for this local shop/day.")
        raise SystemExit(0)
users = client.get("v1/users").json()
technician = next((user["id"] for user in users if user["role"] == "tech"), None)
response = client.post("v1/customers", json={"full_name": "Hannah Lee (Demo)", "notes": "Synthetic native walkthrough data"})
response.raise_for_status()
customer = response.json()["id"]
jobs = []
for title, make, model, year, time, status, priority, address in [
    ("Lockout - Car", "Toyota", "Hilux", 2019, "09:30", "booking_confirmed", "urgent", "14 Burke Rd, Malvern East VIC"),
    ("All Keys Lost", "Mazda", "CX-5", 2021, "11:00", "quote_sent", "high", "22 Springvale Rd, Glen Waverley VIC"),
    ("Remote / Fob Sync", "Hyundai", "i30", 2018, "13:30", "booking_confirmed", "normal", "Carnegie VIC"),
    ("Ignition Repair", "Holden", "Commodore", 2012, "15:00", "awaiting_quote", "normal", "Oakleigh VIC"),
    ("Broken Key Extraction", "Ford", "Ranger", 2016, None, "booking_on_hold", "normal", "Geelong VIC"),
    ("Duplicate Key", "Kia", "Rio", 2017, None, "work_completed", "normal", "Demo counter"),
]:
    scheduled = datetime.datetime.fromisoformat(str(day) + "T" + time).replace(tzinfo=zone).isoformat() if time else None
    response = client.post("v1/auto-key-jobs", json={
        "customer_id": customer, "title": title, "job_type": title, "status": status, "priority": priority,
        "scheduled_at": scheduled, "job_address": address, "vehicle_make": make, "vehicle_model": model,
        "vehicle_year": year, "assigned_user_id": technician, "key_quantity": 1,
        "tech_notes": "Demo only. Inspect the vehicle and confirm the job before starting work.",
    })
    response.raise_for_status()
    job = response.json()
    if scheduled:
        returned = datetime.datetime.fromisoformat(job["scheduled_at"].replace("Z", "+00:00"))
        assert returned.astimezone(zone).strftime("%H:%M") == time
    jobs.append(job)
for job, price, description in [(jobs[0], 18900, "Vehicle lockout service"), (jobs[-1], 8900, "Duplicate key - demo")]:
    response = client.post(f"v1/auto-key-jobs/{job['id']}/quotes", json={"line_items": [{"description": description, "quantity": 1, "unit_price_cents": price}], "gst_enabled": True, "gst_inclusive": True})
    response.raise_for_status()
    if job is jobs[-1]:
        invoice = client.post(f"v1/auto-key-jobs/{job['id']}/invoices/from-quote/{response.json()['id']}")
        invoice.raise_for_status()
output.write_text(json.dumps({"source": "disposable localhost API only", "tenant_id": metadata["tenant_id"], "day": str(day), "jobs": [{key: job[key] for key in ("id", "job_number", "title")} for job in jobs]}, indent=2), encoding="utf-8")
print("Seeded six synthetic jobs and an unpaid invoice; booking times round-tripped correctly.")
