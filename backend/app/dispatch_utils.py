"""Ring-map dispatch utilities: geocoding and Haversine distance/ring calculation."""
import math
from typing import Optional, Tuple

import httpx

from .config import settings


async def geocode_address(address: str) -> Tuple[float, float]:
    """Return (lat, lng) for an address string using the Google Maps Geocoding API.

    Raises ValueError if geocoding fails or returns no results.
    """
    api_key = settings.google_maps_web_services_key
    if not api_key:
        raise ValueError("GOOGLE_MAPS_WEB_SERVICES_KEY is not configured.")

    url = "https://maps.googleapis.com/maps/api/geocode/json"
    async with httpx.AsyncClient(timeout=10.0) as client:
        resp = await client.get(url, params={"address": address, "key": api_key})
        resp.raise_for_status()
        data = resp.json()

    if data.get("status") != "OK" or not data.get("results"):
        raise ValueError(f"Geocoding failed for address '{address}': {data.get('status')}")

    loc = data["results"][0]["geometry"]["location"]
    return float(loc["lat"]), float(loc["lng"])


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
