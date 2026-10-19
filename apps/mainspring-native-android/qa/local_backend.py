"""Disposable localhost backend for the opt-in native API smoke check.

Run with this repository's Python environment. No production database or delivery
provider is used. Production startup/migration behavior is intentionally outside
this check; the real routes, middleware, auth and SQL persistence are exercised.
"""
import json
import os
import sys
from pathlib import Path
from uuid import UUID, uuid4

root = Path(__file__).resolve().parents[3]
artifacts = (root / "artifacts" / "native-local-backend").resolve()
assert artifacts.is_relative_to(root.resolve())
artifacts.mkdir(parents=True, exist_ok=True)
suffix = uuid4().hex[:12]
database = artifacts / f"native-test-{suffix}.db"
os.environ.update({
    "DATABASE_URL": f"sqlite:///{database.as_posix()}",
    "APP_ENV": "test", "JWT_SECRET": f"native-local-test-{uuid4().hex}",
    "ALLOW_PUBLIC_BOOTSTRAP": "true", "ENABLE_EMAIL_NOTIFICATIONS": "false",
    "SENDGRID_API_KEY": "", "TWILIO_ACCOUNT_SID": "", "TWILIO_AUTH_TOKEN": "",
    "TWILIO_FROM_NUMBER": "", "FCM_SERVICE_ACCOUNT_JSON": "", "SENTRY_DSN": "",
    "RUN_SWEEPS_IN_WEB_PROCESS": "false", "STARTUP_SEED_ENABLED": "false",
    "MINIT_SEED_ENABLED": "false", "PUBLIC_BASE_URL": "http://127.0.0.1:8716",
})
sys.path.insert(0, str(root / "backend"))
from fastapi.testclient import TestClient
from sqlmodel import Session
from app.database import create_db_and_tables, engine
from app.main import app
from app.models import StockItem

create_db_and_tables()
slug = f"native-qa-{suffix}"
email = f"owner-{suffix}@native.example.test"
with_email_password = "Native-local-test-only!"
client = TestClient(app)
response = client.post("/v1/auth/bootstrap", json={
    "tenant_name": "Disposable native QA", "tenant_slug": slug,
    "owner_email": email, "owner_full_name": "Native QA Owner",
    "owner_password": with_email_password, "plan_code": "pro",
})
response.raise_for_status()
tenant_id = UUID(response.json()["tenant_id"])
with Session(engine) as session:
    session.add(StockItem(tenant_id=tenant_id, item_code="NATIVE-QA-BAT", group_code="QA",
        item_description="Test battery", full_description="Test battery", pack_qty=1,
        system_stock_qty=5, cost_price_cents=100, retail_price_cents=200))
    session.commit()
client.close()
(artifacts / "connection.json").write_text(json.dumps({
    "base_url": "http://127.0.0.1:8716/", "slug": slug, "email": email,
    "database": str(database), "tenant_id": str(tenant_id),
}), encoding="utf-8")
print(f"Disposable native backend ready: {slug}", flush=True)
import uvicorn
uvicorn.run(app, host="127.0.0.1", port=8716, lifespan="off", log_level="warning")
