import logging
import threading
import time
import uuid
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from sqlalchemy import text
from sqlalchemy.exc import OperationalError
from sqlmodel import Session

from .config import settings, validate_runtime_config
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
from .routes.inbox import router as inbox_router
from .routes.public_jobs import router as public_jobs_router
from .routes.users import router as users_router
from .routes.platform_admin import router as platform_admin_router
from .routes.shoe_catalogue import router as shoe_catalogue_router
from .routes.watch_catalogue import router as watch_catalogue_router
from .routes.shoe_repair_jobs import router as shoe_repair_jobs_router
from .routes.auto_key_jobs import router as auto_key_jobs_router
from .routes.customer_accounts import router as customer_accounts_router
from .routes.parent_accounts import router as parent_accounts_router
from .routes.billing import router as billing_router
from .routes.stocktakes import router as stocktake_router
from .routes.prospects import router as prospects_router
from .routes.mobile_lead_ingest import router as mobile_lead_ingest_router
from .routes.vehicle_lookup import router as vehicle_lookup_router
from .routes.vehicle_key_specs import router as vehicle_key_specs_router
from .routes.maps_routing import router as maps_routing_router
from .routes.custom_services import router as custom_services_router
from .routes.toolkit import router as toolkit_router
from .startup_seed import ensure_demo_auto_key_addresses, ensure_demo_b2b_accounts, ensure_demo_parent_account, ensure_demo_supplemental_data, ensure_demo_tenant, ensure_platform_admin_account, ensure_suburbs_seeded, ensure_testing_tenant, get_seed_status, seed_from_csv_if_empty


if getattr(settings, "sentry_dsn", "").strip():
    import sentry_sdk
    sentry_sdk.init(
        dsn=settings.sentry_dsn.strip(),
        traces_sample_rate=0.1,
        profiles_sample_rate=0.0,
        environment=getattr(settings, "app_env", "production"),
    )


def _run_optional_startup_tasks() -> None:
    """Run demo/bootstrap maintenance without blocking container health checks."""
    startup_logger = logging.getLogger("mainspring.startup")
    try:
        with Session(engine) as session:
            demo_tenant = ensure_demo_tenant(session)
            ensure_demo_b2b_accounts(session, demo_tenant)
            ensure_demo_auto_key_addresses(session, demo_tenant.id)
            ensure_demo_parent_account(session, demo_tenant)
            # Demo mobile calendar/status refresh runs on demo-seed (auth), not every API restart, so local reschedules persist.
            session.commit()
            ensure_testing_tenant(session)
            ensure_platform_admin_account(session)
            ensure_suburbs_seeded(session)
            seed_from_csv_if_empty(session)
            ensure_demo_supplemental_data(session)
            session.commit()
        startup_logger.info("Optional startup tasks completed.")
    except Exception:
        startup_logger.exception("Optional startup tasks failed.")


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Fail fast on unsafe production config before any startup side effects.
    validate_runtime_config()
    if settings.auto_create_schema_on_startup:
        create_db_and_tables()
    try:
        # Clear startup failure if schema is missing and AUTO_CREATE_SCHEMA_ON_STARTUP is off.
        with engine.connect() as conn:
            conn.execute(text("SELECT 1 FROM alembic_version LIMIT 1"))
    except OperationalError as exc:
        raise RuntimeError(
            "Database schema is missing or out of date. Run 'alembic upgrade head' "
            "in backend/ before starting the app. "
            "For dev-only auto bootstrap, set AUTO_CREATE_SCHEMA_ON_STARTUP=true."
        ) from exc

    logging.getLogger("mainspring.startup").info(
        "Database schema check passed; scheduling optional startup tasks."
    )
    threading.Thread(
        target=_run_optional_startup_tasks,
        name="mainspring-startup-seed",
        daemon=True,
    ).start()
    yield


app = FastAPI(
    title=settings.app_name,
    description="Multi-tenant API for watch, shoe, and auto-key repair shops. Handles customers, jobs, quotes, approvals, invoices, and billing.",
    version="1.0.0",
    lifespan=lifespan,
)

app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

# Request ID and logging (method, path, status, duration, request_id)
logger = logging.getLogger("mainspring.requests")
REQUEST_ID_HEADER = "X-Request-ID"
SLOW_REQUEST_WARN_MS = 750.0


@app.middleware("http")
async def request_id_and_log(request: Request, call_next):
    request_id = request.headers.get(REQUEST_ID_HEADER) or str(uuid.uuid4())
    start = time.perf_counter()
    response = await call_next(request)
    duration_ms = (time.perf_counter() - start) * 1000
    response.headers[REQUEST_ID_HEADER] = request_id
    response.headers["X-Response-Time-Ms"] = f"{duration_ms:.2f}"
    logger.info(
        "%s %s %s %.2fms request_id=%s",
        request.method,
        request.url.path,
        response.status_code,
        duration_ms,
        request_id,
    )
    if duration_ms >= SLOW_REQUEST_WARN_MS:
        logger.warning(
            "SLOW_REQUEST %s %s %s %.2fms request_id=%s",
            request.method,
            request.url.path,
            response.status_code,
            duration_ms,
            request_id,
        )
    return response

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=[o.strip() for o in settings.cors_origins.split(",") if o.strip()],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/v1/debug/demo-status")
def debug_demo_status():
    """Diagnostic: demo tenant state and B2B account count. No auth required."""
    from sqlmodel import select, func
    from .config import settings
    from .models import CustomerAccount, Tenant

    slug = (settings.startup_seed_tenant_slug or "myshop").strip().lower()
    with Session(engine) as session:
        tenant = session.exec(select(Tenant).where(Tenant.slug == slug)).first()
        if not tenant:
            return {"demo_tenant": None, "message": f"Demo tenant '{slug}' not found"}
        count = session.exec(
            select(func.count()).select_from(CustomerAccount).where(CustomerAccount.tenant_id == tenant.id)
        ).one()
        return {
            "demo_tenant": {
                "slug": tenant.slug,
                "id": str(tenant.id),
                "plan_code": tenant.plan_code,
            },
            "customer_account_count": int(count),
        }


@app.get("/v1/health")
def health():
    from sqlmodel import select
    from .config import settings
    from .models import Tenant
    testing_configured = bool(
        (settings.testing_tenant_slug or "").strip()
        and (settings.testing_owner_email or "").strip()
        and settings.testing_owner_password
    )
    testing_tenant_exists = False
    if testing_configured:
        slug = (settings.testing_tenant_slug or "").strip().lower()
        with Session(engine) as session:
            testing_tenant_exists = session.exec(
                select(Tenant).where(Tenant.slug == slug)
            ).first() is not None
    demo_status = None
    try:
        demo_status = debug_demo_status()
    except Exception:
        pass

    return {
        "status": "ok",
        "startup_seed": get_seed_status(),
        "testing_tenant_configured": testing_configured,
        "testing_tenant_exists": testing_tenant_exists,
        "demo": demo_status,
    }


@app.get("/v1/ready")
def ready():
    """Readiness: checks DB connectivity. Returns 503 if DB is unreachable."""
    from sqlalchemy import text
    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
    except Exception:
        from fastapi.responses import JSONResponse
        return JSONResponse(
            content={"status": "unhealthy", "detail": "Database unreachable"},
            status_code=503,
        )
    return {"status": "healthy"}


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
app.include_router(inbox_router)
app.include_router(public_jobs_router)
app.include_router(mobile_lead_ingest_router)
app.include_router(users_router)
app.include_router(platform_admin_router)
app.include_router(shoe_catalogue_router)
app.include_router(watch_catalogue_router)
app.include_router(shoe_repair_jobs_router)
app.include_router(auto_key_jobs_router)
app.include_router(customer_accounts_router)
app.include_router(parent_accounts_router)
app.include_router(billing_router)
app.include_router(stocktake_router)
app.include_router(prospects_router)
app.include_router(vehicle_lookup_router)
app.include_router(vehicle_key_specs_router)
app.include_router(maps_routing_router)
app.include_router(custom_services_router)
app.include_router(toolkit_router)

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
