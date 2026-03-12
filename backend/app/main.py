from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from sqlmodel import Session

from .config import settings
from .database import create_db_and_tables, engine
from .limiter import limiter
from .routes.auth import router as auth_router
from .routes.customers import router as customer_router
from .routes.repair_jobs import router as repair_job_router
from .routes.quotes import router as quote_router
from .routes.invoices import router as invoice_router
from .routes.work_logs import router as work_log_router
from .routes.attachments import router as attachment_router
from .routes.csv_import import router as csv_import_router
from .routes.reports import router as report_router
from .routes.public_jobs import router as public_jobs_router
from .routes.users import router as users_router
from .routes.platform_admin import router as platform_admin_router
from .routes.shoe_catalogue import router as shoe_catalogue_router
from .routes.shoe_repair_jobs import router as shoe_repair_jobs_router
from .routes.auto_key_jobs import router as auto_key_jobs_router
from .routes.customer_accounts import router as customer_accounts_router
from .routes.parent_accounts import router as parent_accounts_router
from .routes.billing import router as billing_router
from .startup_seed import ensure_platform_admin_account, get_seed_status, seed_from_csv_if_empty


@asynccontextmanager
async def lifespan(app: FastAPI):
    create_db_and_tables()
    with Session(engine) as session:
        ensure_platform_admin_account(session)
        seed_from_csv_if_empty(session)
    yield


app = FastAPI(title=settings.app_name, lifespan=lifespan)

app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=[o.strip() for o in settings.cors_origins.split(",") if o.strip()],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/v1/health")
def health():
    return {"status": "ok", "startup_seed": get_seed_status()}


@app.get("/v1/seed-status")
def seed_status():
    return get_seed_status()


app.include_router(auth_router)
app.include_router(customer_router)
app.include_router(repair_job_router)
app.include_router(quote_router)
app.include_router(invoice_router)
app.include_router(work_log_router)
app.include_router(attachment_router)
app.include_router(csv_import_router)
app.include_router(report_router)
app.include_router(public_jobs_router)
app.include_router(users_router)
app.include_router(platform_admin_router)
app.include_router(shoe_catalogue_router)
app.include_router(shoe_repair_jobs_router)
app.include_router(auto_key_jobs_router)
app.include_router(customer_accounts_router)
app.include_router(parent_accounts_router)
app.include_router(billing_router)

# ---------- Serve the built React frontend ----------
_static = Path(settings.static_dir) if settings.static_dir else None
if _static and _static.is_dir():
    # Serve JS/CSS/assets at /assets
    app.mount("/assets", StaticFiles(directory=str(_static / "assets")), name="frontend-assets")

    # SPA fallback — any non-API path serves index.html
    @app.api_route("/{full_path:path}", methods=["GET", "HEAD"], include_in_schema=False)
    async def spa_fallback(request: Request, full_path: str):
        # Never intercept API or docs paths
        if full_path.startswith("v1/") or full_path in ("docs", "openapi.json", "redoc"):
            from fastapi.responses import JSONResponse
            return JSONResponse({"detail": "Not Found"}, status_code=404)
        file_path = _static / full_path
        if full_path and file_path.is_file():
            return FileResponse(str(file_path))
        return FileResponse(str(_static / "index.html"))
