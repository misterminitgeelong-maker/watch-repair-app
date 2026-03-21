from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    app_name: str = "Mainspring API"
    database_url: str = "sqlite:///./watch_repair.db"
    jwt_secret: str = "change-me-in-production"
    jwt_algorithm: str = "HS256"
    jwt_expire_minutes: int = 480  # 8 hours for shop use
    jwt_refresh_expire_days: int = 7
    app_env: str = "production"
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

    # CORS — comma-separated origins allowed in production
    cors_origins: str = "https://mainspring.au,https://www.mainspring.au"

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


settings = Settings()

# Production safety: reject default JWT secret and optional bootstrap default
def _validate_production_config() -> None:
    if settings.app_env.strip().lower() != "production":
        return
    if not settings.jwt_secret or settings.jwt_secret.strip() == "change-me-in-production":
        raise ValueError(
            "JWT_SECRET must be set to a secure value in production. "
            "Run: openssl rand -hex 32"
        )
    if settings.allow_public_bootstrap:
        # Allow but warn; operator can set ALLOW_PUBLIC_BOOTSTRAP=false after first tenant
        import warnings
        warnings.warn(
            "ALLOW_PUBLIC_BOOTSTRAP is True in production. Set ALLOW_PUBLIC_BOOTSTRAP=false after bootstrapping your first tenant.",
            UserWarning,
            stacklevel=0,
        )


_validate_production_config()
