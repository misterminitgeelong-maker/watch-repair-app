"""Public native-client settings; contains only values safe to embed in an app."""
from urllib.parse import urlsplit, urlunsplit

from fastapi import APIRouter

from ..config import settings, sentry_dsn_looks_valid

router = APIRouter(prefix="/v1/client-config", tags=["client-config"])


def public_sentry_dsn(value: str) -> str | None:
    value = value.strip()
    try:
        if not value or not sentry_dsn_looks_valid(value):
            return None
        parsed = urlsplit(value)
        port = parsed.port
    except ValueError:
        # A malformed hostname or port must not break app startup/config retrieval.
        return None
    # DSNs have a public project key; the optional legacy secret must never leave the server.
    if parsed.scheme != "https" or not parsed.username or not parsed.hostname:
        return None
    hostname = f"[{parsed.hostname}]" if ":" in parsed.hostname else parsed.hostname
    netloc = f"{parsed.username}@{hostname}"
    if port:
        netloc += f":{port}"
    return urlunsplit((parsed.scheme, netloc, parsed.path, "", ""))


@router.get("/android")
def android_client_config():
    return {
        "minimum_version_code": settings.android_minimum_version_code,
        "update_message": settings.android_update_message,
        "store_url": "https://play.google.com/store/apps/details?id=au.mainspring.app",
        "sentry_dsn": public_sentry_dsn(settings.sentry_dsn),
    }
