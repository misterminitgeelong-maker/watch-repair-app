"""Ring-map dispatch utilities: geocoding and Haversine distance/ring calculation."""
import math
import threading
import time
from collections import OrderedDict, deque
from typing import Optional, Tuple

import httpx

from .config import settings


# ── Geocoding cost controls (L10) ────────────────────────────────────────────
# Every Geocoding API call is billed. Public booking/intake forms geocode on
# submit, so without these a script could run up the Google bill:
#   * results are cached per normalised address (hits for 30 days, misses for
#     an hour so a bad address can't be retried into the API in a loop);
#   * a per-process budget caps how many real calls go out per minute;
#   * absurdly long "addresses" are refused without a call.
# Per-IP request limits on the public routes themselves live on the routes.
_GEOCODE_HIT_TTL = 30 * 24 * 3600
_GEOCODE_MISS_TTL = 3600
_GEOCODE_CACHE_MAX = 5000
_GEOCODE_MAX_ADDRESS_LEN = 300

_geocode_cache: "OrderedDict[str, tuple[float, Optional[Tuple[float, float]], str]]" = OrderedDict()
_geocode_calls: deque[float] = deque()
_geocode_lock = threading.Lock()


def _normalise_address(address: str) -> str:
    return " ".join((address or "").split()).lower()


def _cache_get(key: str) -> Optional[tuple[Optional[Tuple[float, float]], str]]:
    with _geocode_lock:
        entry = _geocode_cache.get(key)
        if entry is None:
            return None
        expires_at, result, status = entry
        if expires_at < time.monotonic():
            _geocode_cache.pop(key, None)
            return None
        _geocode_cache.move_to_end(key)
        return result, status


def _cache_put(key: str, result: Optional[Tuple[float, float]], status: str) -> None:
    ttl = _GEOCODE_HIT_TTL if result is not None else _GEOCODE_MISS_TTL
    with _geocode_lock:
        _geocode_cache[key] = (time.monotonic() + ttl, result, status)
        _geocode_cache.move_to_end(key)
        while len(_geocode_cache) > _GEOCODE_CACHE_MAX:
            _geocode_cache.popitem(last=False)


def _take_geocode_budget() -> bool:
    """Reserve one real API call against the per-minute budget."""
    limit = int(getattr(settings, "geocode_max_calls_per_minute", 60) or 0)
    if limit <= 0:
        return True
    now = time.monotonic()
    with _geocode_lock:
        while _geocode_calls and _geocode_calls[0] < now - 60:
            _geocode_calls.popleft()
        if len(_geocode_calls) >= limit:
            return False
        _geocode_calls.append(now)
        return True


def reset_geocode_cache() -> None:
    """Test hook: forget cached results and spent budget."""
    with _geocode_lock:
        _geocode_cache.clear()
        _geocode_calls.clear()


async def geocode_address(address: str) -> Tuple[float, float]:
    """Return (lat, lng) for an address string using the Google Maps Geocoding API.

    Raises ValueError if geocoding fails or returns no results.
    """
    api_key = settings.google_maps_web_services_key
    if not api_key:
        raise ValueError("GOOGLE_MAPS_WEB_SERVICES_KEY is not configured.")

    key = _normalise_address(address)
    if not key:
        raise ValueError("Address is required.")
    if len(key) > _GEOCODE_MAX_ADDRESS_LEN:
        raise ValueError("Address is too long.")

    cached = _cache_get(key)
    if cached is not None:
        result, status = cached
        if result is None:
            raise ValueError(f"Geocoding failed for address '{address}': {status}")
        return result

    if not _take_geocode_budget():
        raise ValueError("Address lookup is busy right now. Please try again in a minute.")

    url = "https://maps.googleapis.com/maps/api/geocode/json"
    async with httpx.AsyncClient(timeout=10.0) as client:
        resp = await client.get(url, params={"address": address, "key": api_key})
        resp.raise_for_status()
        data = resp.json()

    status = str(data.get("status") or "")
    if status != "OK" or not data.get("results"):
        # Only cache definitive "no such address" answers; quota/transient errors retry.
        if status == "ZERO_RESULTS":
            _cache_put(key, None, status)
        raise ValueError(f"Geocoding failed for address '{address}': {status}")

    loc = data["results"][0]["geometry"]["location"]
    result = (float(loc["lat"]), float(loc["lng"]))
    _cache_put(key, result, status)
    return result


def haversine_km(lat1: float, lng1: float, lat2: float, lng2: float) -> float:
    """Great-circle distance in kilometres between two lat/lng points."""
    R = 6371.0
    dlat = math.radians(lat2 - lat1)
    dlng = math.radians(lng2 - lng1)
    a = math.sin(dlat / 2) ** 2 + math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) * math.sin(dlng / 2) ** 2
    return R * 2 * math.asin(math.sqrt(a))


def ring_for_distance(distance_km: float, ring_radius_km: int = 10) -> int:
    """Return which priority ring (1-indexed) a distance falls into.

    Ring 1 = 0–ring_radius_km, Ring 2 = ring_radius_km–2*ring_radius_km, etc.
    """
    return max(1, math.ceil(distance_km / ring_radius_km))


def operator_ring_for_job(
    operator_lat: Optional[float],
    operator_lng: Optional[float],
    job_lat: float,
    job_lng: float,
    ring_radius_km: int = 10,
) -> Optional[int]:
    """Return the ring number this job falls into for a given operator, or None if no base set."""
    if operator_lat is None or operator_lng is None:
        return None
    dist = haversine_km(operator_lat, operator_lng, job_lat, job_lng)
    return ring_for_distance(dist, ring_radius_km)
