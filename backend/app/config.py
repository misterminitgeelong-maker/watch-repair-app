from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    app_name: str = "Watch Repair API"
    database_url: str = "sqlite:///./watch_repair.db"
    jwt_secret: str = "change-me-in-production"
    jwt_algorithm: str = "HS256"
    jwt_expire_minutes: int = 480  # 8 hours for shop use
    allow_public_bootstrap: bool = True

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
