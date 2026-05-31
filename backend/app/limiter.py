"""Shared slowapi limiter.

Uses ``settings.rate_limit_storage_uri`` so that, behind a load balancer, all
instances can share counters via Redis/Memcached. When the setting is empty
(default), slowapi falls back to in-process memory storage, which is fine for a
single instance / pilot but does not enforce limits consistently across
multiple instances.
"""
from slowapi import Limiter
from slowapi.util import get_remote_address

from .config import settings

_storage_uri = (settings.rate_limit_storage_uri or "").strip() or None

# storage_uri=None lets slowapi use its default in-memory storage.
limiter = Limiter(key_func=get_remote_address, storage_uri=_storage_uri)
