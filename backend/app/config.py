from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    app_name: str = "Watch Repair API"
    database_url: str = "sqlite:///./watch_repair.db"
    jwt_secret: str = "change-me-in-production"
    jwt_algorithm: str = "HS256"
    jwt_expire_minutes: int = 480  # 8 hours for shop use
    allow_public_bootstrap: bool = True

    # One-time startup data seeding (for single-shop bootstrap)
    startup_seed_enabled: bool = True
    startup_seed_csv_path: str = "seed/repairs_import.csv"
    startup_seed_tenant_slug: str = "myshop"
    startup_seed_tenant_name: str = "My Shop"
    startup_seed_owner_email: str = "admin@admin.com"
    startup_seed_owner_password: str = "Admin"

    # Twilio SMS — leave blank to disable SMS (dry-run / log-only mode)
    twilio_account_sid: str = ""
    twilio_auth_token: str = ""
    twilio_from_number: str = ""  # E.164 format, e.g. +61400000000

    # Public base URL used to build approval links in SMS messages
    public_base_url: str = "http://localhost:5173"

    # CORS — comma-separated origins allowed in production
    cors_origins: str = "*"

    # Path to the built frontend (set by Dockerfile / deploy)
    static_dir: str = ""


settings = Settings()
