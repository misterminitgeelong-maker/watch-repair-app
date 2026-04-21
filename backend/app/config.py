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
    jwt_secret: str = "change-me-in-production"
    jwt_algorithm: str = "HS256"
    jwt_expire_minutes: int = 480  # 8 hours for shop use
    jwt_refresh_expire_days: int = 7
    # Dedicated signing secret for short-lived attachment download URLs.
    # Leave blank to reuse JWT_SECRET (backward compatible). Set in production
    # so a leaked download URL cannot share signing material with auth tokens.
    attachment_signing_secret: str = ""
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

    # CORS — comma-separated origins allowed in production. Web-only (no
    # Capacitor / native WebView origins — those builds were removed).
    cors_origins: str = (
        "https://mainspring.au,https://www.mainspring.au,"
        "https://localhost,http://localhost"
    )

    # Path to the built frontend (set by Dockerfile / deploy)
    static_dir: str = ""

    # Feature flags (env: ENABLE_* = true/false)
    enable_new_invoice_ui: bool = True
    enable_customer_portal: bool = True
    enable_email_notifications: bool = False

    # Email (when enable_email_notifications is True)
    sendgrid_api_key: str = ""
    postmark_api_key: str = ""

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
    stripe_price_basic_base: str = ""
    stripe_price_basic_addon_tab: str = ""
    stripe_price_pro: str = ""
    # Legacy one-price-per-plan IDs (kept for backward compatibility)
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

    # Rate limiting (slowapi format, e.g. "20/minute")
    rate_limit_auth_login: str = "20/minute"
    rate_limit_auth_login_test: str = "1000/minute"
    rate_limit_public_quote_get: str = "30/minute"
    rate_limit_public_quote_decision: str = "20/minute"
    rate_limit_import_csv: str = "5/minute"
    # Public customer-portal endpoints (cross-tenant lookup by email).
    # These return PII (job status + names/brands) so they must be throttled.
    rate_limit_public_customer_lookup: str = "30/minute"
    rate_limit_public_portal_create: str = "10/minute"
    rate_limit_public_portal_session: str = "60/minute"

    # Customer portal session TTL. Was 30 days; shortened because issuance only
    # requires an email + that the email has at least one active job. Move to
    # a magic-link / OTP flow before extending this back out.
    portal_session_ttl_days: int = 7

    # Public quote approval token lifetime from send time.
    quote_approval_token_ttl_hours: int = 168

    # Attachments: local storage + upload validation defaults
    attachment_allowed_content_types: str = (
        "image/jpeg,image/png,image/webp,application/pdf,text/plain"
    )
    attachment_max_upload_bytes: int = 10 * 1024 * 1024
    attachment_local_upload_dir: str = "uploads"


settings = Settings()


def _is_local_public_url(url: str) -> bool:
    parsed = urlparse((url or "").strip())
    host = (parsed.hostname or "").strip().lower()
    return host in {"localhost", "127.0.0.1", "0.0.0.0", "::1"}


def _is_sqlite_url(database_url: str) -> bool:
    return (database_url or "").strip().lower().startswith("sqlite")


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
