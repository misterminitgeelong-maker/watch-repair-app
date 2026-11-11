"""Local screenshot server with a labelled demo signature; no production credentials/providers."""
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path
from uuid import UUID, uuid4

root = Path(__file__).resolve().parents[3]
folder = root / "artifacts/native-local-backend"
connection = json.loads((folder / "connection.json").read_text(encoding="utf-8"))
ids = json.loads((folder / "screen-review-data.json").read_text(encoding="utf-8"))
database = Path(connection["database"]).resolve()
assert connection["base_url"] == "http://127.0.0.1:8716/"
assert connection["slug"].startswith("native-qa-") and connection["email"].endswith("@native.example.test")
assert database.is_relative_to(folder.resolve()) and database.name.startswith("native-test-")
os.environ.update(DATABASE_URL=f"sqlite:///{database.as_posix()}", APP_ENV="test", JWT_SECRET="screenshot-local-" + uuid4().hex,
    ENABLE_EMAIL_NOTIFICATIONS="false", SENDGRID_API_KEY="", TWILIO_ACCOUNT_SID="", TWILIO_AUTH_TOKEN="", TWILIO_FROM_NUMBER="",
    FCM_SERVICE_ACCOUNT_JSON="", SENTRY_DSN="", STRIPE_SECRET_KEY="", SUPABASE_URL="", SUPABASE_SERVICE_ROLE_KEY="",
    GOOGLE_PLACES_API_KEY="", RUN_SWEEPS_IN_WEB_PROCESS="false", STARTUP_SEED_ENABLED="false", MINIT_SEED_ENABLED="false",
    PUBLIC_BASE_URL="http://127.0.0.1:8716", ATTACHMENT_STORAGE_BACKEND="local")
sys.path.insert(0, str(root / "backend"))
from PIL import Image, ImageDraw, ImageFont
from sqlmodel import Session
from app.database import engine
from app.models import AutoKeyQuote, Tenant
from app.main import app
from app.routes import attachments
from fastapi.responses import FileResponse

image_path = folder / "demo-signature.png"
image = Image.new("RGB", (800, 240), "white")
draw = ImageDraw.Draw(image)
draw.text((38, 45), "DEMO SIGNATURE", font=ImageFont.truetype("C:/Windows/Fonts/segoeui.ttf", 42), fill="#222222")
draw.text((40, 130), "Synthetic screenshot sample only", font=ImageFont.truetype("C:/Windows/Fonts/segoeui.ttf", 24), fill="#777777")
image.save(image_path)
storage_key = "qa-only/demo-signature.png"
with Session(engine) as db:
    tenant = db.get(Tenant, UUID(connection["tenant_id"]))
    assert tenant.slug == connection["slug"]
    quote = db.get(AutoKeyQuote, UUID(ids["mobile_quote_id"]))
    assert str(quote.tenant_id) == connection["tenant_id"]
    quote.signature_storage_key = storage_key
    quote.signer_name = "Avery Taylor (Demo)"
    quote.signed_at = datetime.now(timezone.utc)
    quote.status = "approved"
    db.add(quote); db.commit()

@app.get("/__screenshot_fixture__/demo-signature.png", include_in_schema=False)
def demo_signature():
    return FileResponse(image_path, media_type="image/png")

# The real authenticated signature route resolves a private-object URL. This
# process-local adapter serves only the labelled fixture key and never accesses
# external storage; production app modules and their storage classes are unchanged.
attachments.attachment_storage.get_signed_url = lambda key, expires_in_seconds=60: (
    "http://127.0.0.1:8716/__screenshot_fixture__/demo-signature.png" if key == storage_key else None)

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="127.0.0.1", port=8716, lifespan="off", log_level="warning")
