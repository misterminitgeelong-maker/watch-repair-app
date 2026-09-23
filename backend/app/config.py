import logging
from typing import Literal
from urllib.parse import urlparse

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    # Check .env in cwd and backend/.env (for "uvicorn backend.app.main:app" from root)
    model_config = SettingsConfigDict(
        env_file=(".env", "backend/.env"),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    app_name: str = "Mainspring API"
    database_url: str = "sqlite:///./watch_repair.db"
    # SQLAlchemy connection pool (server databases only; ignored for SQLite).
    # Sync endpoints run on the FastAPI threadpool alongside background threads,
    # so size this against the worker thread count, not the process count.
    db_pool_size: int = 10
    db_max_overflow: int = 10
    # Seconds before a pooled connection is recycled. Keep below the server's
    # idle timeout so a stale socket is never handed to a request.
    db_pool_recycle_seconds: int = 1800
    jwt_secret: str = "change-me-in-production"
    jwt_algorithm: str = "HS256"
    jwt_expire_minutes: int = 480  # 8 hours for shop use
    jwt_refresh_expire_days: int = 7
    app_env: Literal["development", "test", "staging", "production"] = "development"
    # Break-glass flag only for explicitly intended production SQLite runs.
    allow_sqlite_in_production: bool = False
    allow_public_bootstrap: bool = True
    allow_dev_auto_login: bool = False

    # Password policy (optional stricter rules)
    password_min_length: int = 8
    password_require_number: bool = False
    password_require_special: bool = False

    # One-time startup data seeding (for single-shop bootstrap)
    startup_seed_enabled: bool = False
    startup_seed_csv_path: str = "seed/repairs_import.csv"
    startup_seed_tenant_slug: str = "myshop"
    startup_seed_tenant_name: str = "My Shop"
    startup_seed_owner_email: str = "admin@admin.com"
    startup_seed_owner_password: str = "Admin"
    # Dev-only convenience flag: explicitly allow runtime create_all bootstrap.
    auto_create_schema_on_startup: bool = False

    # Optional testing tenant (no demo prompts; for internal QA/breaking things)
    testing_tenant_slug: str = ""
    testing_tenant_name: str = "Testing"
    testing_owner_email: str = ""
    testing_owner_password: str = ""
    allow_ensure_testing_tenant: bool = False  # When True, enables POST /auth/ensure-testing-tenant

    # Mister Minit pilot parent account + HQ (dev/staging; see docs/MINIT_ONBOARDING.md)
    minit_seed_enabled: bool = False
    minit_parent_account_name: str = "Mister Minit"
    minit_hq_tenant_slug: str = "mmsupport"
    minit_hq_tenant_name: str = "Mister Minit HQ"
    minit_hq_owner_email: str = "minit-hq@test.mainspring.au"
    # No default: this was "MinitPilot2026!", a password anyone with the source
    # knew. Seeding the Minit pilot now refuses to run until one is set.
    minit_hq_owner_password: str = ""
    allow_ensure_minit_pilot: bool = False  # Enables POST /auth/ensure-minit-pilot (one-off prod seed)

    # Optional global platform admin account (cross-tenant visibility)
    platform_admin_enabled: bool = False
    platform_admin_email: str = ""
    platform_admin_password: str = ""
    platform_admin_full_name: str = "Platform Admin"
    platform_admin_tenant_slug: str = "platform"
    platform_admin_tenant_name: str = "Platform"

    # Twilio SMS — leave blank to disable SMS (dry-run / log-only mode)
    twilio_account_sid: str = ""
    twilio_auth_token: str = ""
    twilio_from_number: str = ""  # E.164 format, e.g. +61400000000

    # Public base URL used to build approval links in SMS messages
    public_base_url: str = "https://mainspring.au"
    # IANA timezone: week/dispatch date filters and customer SMS use this for “local” calendar days.
    schedule_calendar_timezone: str = "Australia/Sydney"

    # CORS — comma-separated origins allowed in production (web app + local dev)
    # Includes Expo web dev ports (8081 Metro, 19006 legacy) for the mobile companion app.
    cors_origins: str = (
        "https://mainspring.au,https://www.mainspring.au,"
        "http://localhost:5173,http://localhost:3000,https://localhost,http://localhost,"
        "http://localhost:8081,http://localhost:19006"
    )

    # Path to the built frontend (set by Dockerfile / deploy)
    static_dir: str = ""

    # Feature flags (env: ENABLE_* = true/false)
    enable_new_invoice_ui: bool = True
    enable_customer_portal: bool = True
    enable_email_notifications: bool = False

    # Email via Twilio SendGrid (Console → Email → API Keys). Not the same as TWILIO_ACCOUNT_SID.
    sendgrid_api_key: str = ""
    email_from_address: str = ""  # Verified sender in SendGrid, e.g. quotes@yourshop.com
    email_from_name: str = ""  # Display name; defaults to shop name when sending

    # Sentry (leave blank to disable)
    sentry_dsn: str = ""

    # Google Places API (for Prospects search; leave blank to disable)
    google_places_api_key: str = ""
    # Google Maps Directions API (server-side; Mobile Services driving-order on map). Enable "Directions API" for this key.
    # If empty, falls back to GOOGLE_PLACES_API_KEY when that key also has Directions enabled.
    google_maps_web_services_key: str = ""

    # Vehicle registration lookup (Blue Flag NEVDIS; leave blank to disable)
    rego_lookup_api_key: str = ""
    rego_lookup_base_url: str = "https://sandbox.blueflag.com.au"  # or https://api.blueflag.com.au for prod

    # Stripe — leave blank to disable Stripe billing integration
    stripe_secret_key: str = ""
    stripe_webhook_secret: str = ""
    # Signing secret of the Connect webhook endpoint ("Events on connected accounts"). Customer
    # invoice payments are charged on each shop's own connected account, so their
    # checkout.session.completed events are delivered there, not to the platform endpoint.
    stripe_connect_webhook_secret: str = ""
    # Locked 2026-09 ladder (new signups). Create NEW Stripe Prices; do not reuse old IDs.
    stripe_price_shop: str = ""  # A$50/mo one location, all tabs
    stripe_price_extra_location: str = ""  # A$25/mo additional site on a Pro subscription
    # New Pro A$90/mo. After rotating, put the old A$50 Pro ID in stripe_price_pro_legacy.
    stripe_price_pro: str = ""
    stripe_price_pro_legacy: str = ""
    # Legacy tab-ladder IDs — webhook mapping for grandfathered shops only. Do not use for new Checkout.
    stripe_price_basic_base: str = ""
    stripe_price_basic_addon_tab: str = ""
    stripe_price_watch: str = ""
    stripe_price_shoe: str = ""
    stripe_price_auto_key: str = ""
    stripe_price_enterprise: str = ""
    # When True and stripe_secret_key is set, customers can pay Mobile Services invoices via Stripe Checkout
    # using Stripe Connect (funds go to the tenant's connected Express account).
    enable_stripe_invoice_checkout: bool = True
    # ISO country for new Express connected accounts (e.g. AU, US).
    stripe_connect_default_country: str = "AU"
    # Number of trial days added to new Stripe subscriptions (0 = no trial).
    stripe_trial_period_days: int = 14

    # Xero — Mobile Services invoice sync (register app at developer.xero.com)
    xero_client_id: str = ""
    xero_client_secret: str = ""
    xero_redirect_uri: str = ""  # e.g. https://api.example.com/v1/billing/xero/callback
    xero_webhook_key: str = ""  # signing key from Xero developer portal (webhooks)

    # Rate limiting (slowapi format, e.g. "20/minute")
    rate_limit_auth_login: str = "20/minute"
    rate_limit_auth_login_test: str = "1000/minute"
    rate_limit_public_quote_get: str = "30/minute"
    rate_limit_public_quote_decision: str = "20/minute"
    rate_limit_import_csv: str = "5/minute"
    # Unauthenticated /v1/public/* endpoints (token-addressed job/quote/portal pages).
    # Reads are generous; anything that mutates, emails, or creates a Stripe session is tight.
    rate_limit_public_read: str = "60/minute"
    rate_limit_public_write: str = "10/minute"
    # Reference data (catalogues, job templates) and attachment downloads are
    # fetched in bursts by the app itself — a shop with several staff behind one
    # IP must not trip them — so they get a looser cap than customer pages.
    rate_limit_reference_read: str = "300/minute"
    rate_limit_attachment_download: str = "600/minute"
    rate_limit_public_test: str = "1000/minute"
    # Shared limiter storage backend for multi-instance deployments, e.g.
    # "redis://localhost:6379/0" or "memcached://localhost:11211".
    # Empty string = in-process memory storage, which is correct for a single
    # instance / pilot but NOT safe behind a load balancer (each instance keeps
    # its own counters). Set this to a shared backend before horizontal scaling.
    rate_limit_storage_uri: str = ""
    # Cap on real Google Geocoding API calls per minute per process (cache hits
    # don't count). 0 disables the cap.
    geocode_max_calls_per_minute: int = 60

    # Public quote approval token lifetime from send time.
    quote_approval_token_ttl_hours: int = 168

    # Quote reminder SMS: nudge customers who haven't decided on a quote.
    # The reminder also refreshes the approval link so it works for another
    # full QUOTE_APPROVAL_TOKEN_TTL_HOURS window. One reminder per quote.
    quote_reminder_enabled: bool = True
    quote_reminder_days: int = 7
    # How often the in-app scheduler checks for due reminders.
    quote_reminder_check_interval_minutes: int = 60

    # Outbound notification retry: inline (timeouts/5xx) then an out-of-band sweep.
    notification_inline_retry_attempts: int = 3
    notification_redelivery_max_attempts: int = 5
    notification_retry_backoff_seconds: float = 0.4
    notification_retry_backoff_cap_seconds: float = 4.0
    notification_redelivery_enabled: bool = True
    notification_redelivery_check_interval_minutes: int = 15

    # Shop-to-shop live booking requests: assigned operator offer → timeout → shared Dispatch Pool.
    shop_mobile_booking_pool_enabled: bool = True
    shop_mobile_booking_check_interval_minutes: int = 2

    # Dispatch Pool digest alerts: one SMS+email per nearby operator once a job has sat
    # unclaimed this long — never a push per job, and never repeated for the same job.
    pool_alert_enabled: bool = True
    pool_alert_after_minutes: int = 10
    pool_alert_check_interval_minutes: int = 5

    # Scheduled weekly/monthly sales-by-category report emails (opt-in per user).
    sales_report_email_enabled: bool = True
    sales_report_check_interval_minutes: int = 60
    # Weekly VSWT regional cockpit email — switchable independently of sales reports.
    regional_report_email_enabled: bool = True
    regional_report_check_interval_minutes: int = 60

    # Weekly Minit HQ "mobile services network" scorecard email (opt-in per parent account).
    mobile_weekly_report_email_enabled: bool = True
    mobile_weekly_report_check_interval_minutes: int = 60
    # Close-of-trade daily (21:00) + Saturday 23:05 weekly mobile KPI snapshots.
    mobile_kpi_close_enabled: bool = True
    mobile_kpi_close_check_interval_minutes: int = 5
    attachment_allowed_content_types: str = (
        "image/jpeg,image/png,image/webp,application/pdf,text/plain"
    )
    attachment_max_upload_bytes: int = 10 * 1024 * 1024
    # Hard cap on any request body (checked before multipart parsing). Must stay
    # above the largest legitimate upload: VSWT reports accept several workbooks
    # per request, the public key-photo form two photos.
    max_request_body_bytes: int = 40 * 1024 * 1024
    attachment_local_upload_dir: str = "uploads"

    # Attachment storage backend selection:
    #   "auto"     -> use Supabase object storage when configured, else local FS
    #   "local"    -> always use local filesystem
    #   "supabase" -> always use Supabase object storage (fails fast if unconfigured)
    # Object storage is the recommended default for multi-instance / production
    # deployments; local FS is only durable for a single instance with a mounted
    # volume. See docs/ATTACHMENT_STORAGE.md for the migration runbook.
    # Retention for the two tables batch 3 added. Both hold customer data and
    # neither is useful past its purpose: an idempotency key once the client has
    # stopped replaying, an email payload once it can no longer be redelivered.
    idempotency_key_retention_days: int = 7
    email_payload_retention_days: int = 30
    retention_sweep_enabled: bool = True
    retention_sweep_check_interval_minutes: int = 360

    # The recurring sweeps can run inside the web process (the default, and how
    # this has always run) or as a separate `python -m app.worker` service.
    # Set this false on the web service once the worker service is deployed;
    # the advisory locks make the overlap in between safe rather than a window
    # where every sweep fires twice.
    # Nothing configured logging before, so every INFO record was dropped and
    # warnings arrived without a timestamp. See app/logging_config.py.
    log_level: str = "INFO"

    run_sweeps_in_web_process: bool = True
    # How long a stopping worker waits for an in-flight sweep before exiting.
    # Longer than a typical pass, shorter than a platform's SIGKILL timeout.
    worker_shutdown_grace_seconds: int = 20

    attachment_storage_backend: str = "auto"

    # Supabase Storage (set these to switch from local FS to Supabase)
    supabase_url: str = ""
    supabase_service_role_key: str = ""
    supabase_storage_bucket: str = "attachments"


settings = Settings()


def _is_local_public_url(url: str) -> bool:
    parsed = urlparse((url or "").strip())
    host = (parsed.hostname or "").strip().lower()
    return host in {"localhost", "127.0.0.1", "0.0.0.0", "::1"}


def _is_sqlite_url(database_url: str) -> bool:
    return (database_url or "").strip().lower().startswith("sqlite")


def sentry_dsn_looks_valid(dsn: str) -> bool:
    """True when DSN is empty (Sentry off) or a plausible https://key@host/project URL."""
    value = (dsn or "").strip()
    if not value:
        return True
    parsed = urlparse(value)
    if parsed.scheme not in {"http", "https"}:
        return False
    if "@" not in (parsed.netloc or ""):
        return False
    if not parsed.hostname:
        return False
    path = (parsed.path or "").strip("/")
    return bool(path)


def validate_runtime_config() -> None:
    """
    Enforce strict safety checks in production only.
    Keep development/test/staging flexible for local onboarding.
    """
    if settings.app_env != "production":
        return

    if not settings.jwt_secret or settings.jwt_secret.strip() == "change-me-in-production":
        raise ValueError(
            "Invalid production config: JWT_SECRET is unset or using the default placeholder. "
            "Set a strong secret (for example, 32+ random bytes)."
        )

    cors_values = [o.strip() for o in settings.cors_origins.split(",") if o.strip()]
    if any(origin == "*" for origin in cors_values):
        raise ValueError(
            "Invalid production config: CORS_ORIGINS cannot include '*'. "
            "Set explicit allowed origin URLs."
        )

    if _is_local_public_url(settings.public_base_url):
        raise ValueError(
            "Invalid production config: PUBLIC_BASE_URL points to localhost/loopback. "
            "Set your real public HTTPS URL."
        )

    if _is_sqlite_url(settings.database_url) and not settings.allow_sqlite_in_production:
        raise ValueError(
            "Invalid production config: DATABASE_URL uses SQLite. "
            "Use a server database for production, or set ALLOW_SQLITE_IN_PRODUCTION=true only when explicitly intended."
        )

    if settings.allow_public_bootstrap:
        # Allow but warn; operator can set ALLOW_PUBLIC_BOOTSTRAP=false after first tenant.
        import warnings
        warnings.warn(
            "ALLOW_PUBLIC_BOOTSTRAP is True in production. Set ALLOW_PUBLIC_BOOTSTRAP=false after bootstrapping your first tenant.",
            UserWarning,
            stacklevel=0,
        )

    dsn = (settings.sentry_dsn or "").strip()
    if dsn and not sentry_dsn_looks_valid(dsn):
        logging.getLogger("mainspring.startup").warning(
            "SENTRY_DSN is set but is not a valid Sentry DSN (https://<key>@<host>/<project>). "
            "Sentry will stay disabled rather than blocking boot."
        )
