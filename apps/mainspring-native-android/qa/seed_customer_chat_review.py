"""Idempotent synthetic customer conversations in the verified disposable QA DB."""
import json
import os
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from uuid import UUID, uuid5, NAMESPACE_URL

root = Path(__file__).resolve().parents[3]
folder = root / "artifacts/native-local-backend"
connection = json.loads((folder / "connection.json").read_text(encoding="utf-8"))
ids = json.loads((folder / "screen-review-data.json").read_text(encoding="utf-8"))
database = Path(connection["database"]).resolve()
assert connection["base_url"] == "http://127.0.0.1:8716/"
assert connection["slug"].startswith("native-qa-")
assert database.is_relative_to(folder.resolve()) and database.name.startswith("native-test-")
os.environ.update(DATABASE_URL=f"sqlite:///{database.as_posix()}", APP_ENV="test")
sys.path.insert(0, str(root / "backend"))
from sqlmodel import Session
from app.database import engine
from app.models import Tenant, JobMessage

with Session(engine) as db:
    tenant_id = UUID(connection["tenant_id"])
    assert db.get(Tenant, tenant_id).slug == connection["slug"]
    now = datetime.now(timezone.utc)
    for field, alias, service in [("repair_job_id", "watch_job_id", "watch"),
                                  ("auto_key_job_id", "mobile_job_id", "key"),
                                  ("shoe_repair_job_id", "shoe_job_id", "shoes")]:
        conversation = [
            ("outbound", f"Hi Avery, we have received your {service}. We will keep you updated here."),
            ("inbound", "Thanks! Could you please let me know when it is ready?"),
            ("outbound", "Of course. Your quote is ready to review. Let us know if you have any questions."),
            ("inbound", "That looks good, thank you. Please go ahead."),
        ]
        for index, (direction, body) in enumerate(conversation):
            message_id = uuid5(NAMESPACE_URL, f"native-review/{ids[alias]}/{index}")
            message = db.get(JobMessage, message_id) or JobMessage(id=message_id, tenant_id=tenant_id,
                direction=direction, body=body, **{field: UUID(ids[alias])})
            message.created_at = now - timedelta(minutes=32 - index * 7)
            db.add(message)
    db.commit()
print("Seeded 12 synthetic local customer messages; no provider delivery.")
