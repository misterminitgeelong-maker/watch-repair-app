"""Shared slowapi limiter.

Uses ``settings.rate_limit_storage_uri`` so that, behind a load balancer, all
instances can share counters via Redis/Memcached. When the setting is empty
(default), slowapi falls back to in-process memory storage, which is fine for a
single instance / pilot but does not enforce limits consistently across
multiple instances.
"""
import ipaddress
import logging

from fastapi import Request
from slowapi import Limiter
from slowapi.util import get_remote_address

from .config import settings

_log = logging.getLogger("mainspring.limiter")

_storage_uri = (settings.rate_limit_storage_uri or "").strip() or None


def client_ip_key(request: Request) -> str:
    """Rate-limit by the real client, not the Cloudflare PoP.

    Production ``mainspring.au`` is orange-clouded (Cloudflare A/AAAA + ``CF-RAY``
    on responses). Railway's ``*.up.railway.app`` edge is also Cloudflare, so
    hitting the default hostname does not skip CF or let a client-supplied
    ``CF-Connecting-IP`` survive — Cloudflare overwrites that header at the
    edge. Local / TestClient / non-CF hops fall back to uvicorn's forwarded
    address.
    """
    raw = (request.headers.get("cf-connecting-ip") or "").strip()
    if raw:
        candidate = raw.split(",", 1)[0].strip().split("%", 1)[0]
        try:
            return str(ipaddress.ip_address(candidate))
        except ValueError:
            _log.warning("Ignoring malformed CF-Connecting-IP")
    return get_remote_address(request)


# storage_uri=None lets slowapi use its default in-memory storage.
limiter = Limiter(key_func=client_ip_key, storage_uri=_storage_uri)


def _is_test() -> bool:
    return settings.app_env == "test"


def public_read_limit() -> str:
    """Per-IP limit for unauthenticated GETs (status pages, catalogues, invites)."""
    return settings.rate_limit_public_test if _is_test() else settings.rate_limit_public_read


def public_write_limit() -> str:
    """Per-IP limit for unauthenticated writes (bookings, intake, decisions)."""
    return settings.rate_limit_public_test if _is_test() else settings.rate_limit_public_write


def auth_limit() -> str:
    """Per-IP limit for unauthenticated auth endpoints (bootstrap, refresh)."""
    return settings.rate_limit_auth_login_test if _is_test() else settings.rate_limit_auth_login


def reference_read_limit() -> str:
    """Per-IP limit for public reference data (catalogues, job templates)."""
    return settings.rate_limit_public_test if _is_test() else settings.rate_limit_reference_read


def attachment_download_limit() -> str:
    return settings.rate_limit_public_test if _is_test() else settings.rate_limit_attachment_download
