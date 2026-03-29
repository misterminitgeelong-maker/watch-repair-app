"""Server-side Google Directions API — driving-time stop order for Mobile Services map."""
from __future__ import annotations

import logging
from typing import Literal
from urllib.parse import urlencode

import httpx
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from ..config import settings
from ..dependencies import get_auth_context, require_feature

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/v1", tags=["maps-routing"])

MAX_STOPS = 25
DIRECTIONS_URL = "https://maps.googleapis.com/maps/api/directions/json"


class LatLng(BaseModel):
    lat: float = Field(..., ge=-90, le=90)
    lng: float = Field(..., ge=-180, le=180)


class OptimizeDrivingRouteBody(BaseModel):
    """Stops in appointment-time order. First and last stay fixed; middle stops are reordered for shorter driving."""

    stops: list[LatLng] = Field(..., min_length=1, max_length=MAX_STOPS)


class OptimizeDrivingRouteResponse(BaseModel):
    visit_order: list[int]
    source: Literal["trivial", "directions"]


def _directions_api_key() -> str:
    return (settings.google_maps_web_services_key or settings.google_places_api_key or "").strip()


def visit_order_from_waypoints(*, n: int, waypoint_order: list[int] | None) -> list[int]:
    """Build full visit indices from Google's waypoint_order (indices into middle stops only)."""
    if n <= 2:
        return list(range(n))
    middle_n = n - 2
    if waypoint_order is None or len(waypoint_order) != middle_n:
        return list(range(n))
    seen = set(waypoint_order)
    if seen != set(range(middle_n)):
        return list(range(n))
    return [0] + [1 + i for i in waypoint_order] + [n - 1]


@router.post("/maps/optimize-driving-route", response_model=OptimizeDrivingRouteResponse)
async def optimize_driving_route(
    body: OptimizeDrivingRouteBody,
    _auth=Depends(get_auth_context),
    _feat=Depends(require_feature("auto_key")),
):
    """
    Reorder middle stops using Google Directions `optimize:true` waypoints.
    First stop (earliest appointment) and last stop (latest) stay fixed — typical same-day run.
    """
    key = _directions_api_key()
    if not key:
        raise HTTPException(
            status_code=503,
            detail="Driving route optimization is not configured. Set GOOGLE_MAPS_WEB_SERVICES_KEY "
            "(or use GOOGLE_PLACES_API_KEY with Directions API enabled).",
        )

    n = len(body.stops)
    if n <= 2:
        return OptimizeDrivingRouteResponse(visit_order=list(range(n)), source="trivial")

    origin = f"{body.stops[0].lat},{body.stops[0].lng}"
    destination = f"{body.stops[-1].lat},{body.stops[-1].lng}"
    middle = body.stops[1:-1]
    wp_parts = ["optimize:true"] + [f"{p.lat},{p.lng}" for p in middle]
    waypoints = "|".join(wp_parts)

    params = {
        "origin": origin,
        "destination": destination,
        "waypoints": waypoints,
        "region": "au",
        "key": key,
    }
    url = f"{DIRECTIONS_URL}?{urlencode(params)}"

    async with httpx.AsyncClient(timeout=30.0) as client:
        resp = await client.get(url)

    if resp.status_code != 200:
        logger.warning("Directions HTTP %s", resp.status_code)
        raise HTTPException(status_code=502, detail="Directions API request failed")

    data = resp.json()
    status = data.get("status")
    if status != "OK":
        err = data.get("error_message") or status or "unknown"
        logger.warning("Directions status=%s msg=%s", status, err)
        raise HTTPException(
            status_code=502,
            detail=f"Directions API error: {err}",
        )

    routes = data.get("routes") or []
    if not routes:
        raise HTTPException(status_code=502, detail="Directions API returned no routes")

    wp_order = routes[0].get("waypoint_order")
    if wp_order is not None and not isinstance(wp_order, list):
        wp_order = None
    if wp_order is not None:
        wp_order = [int(x) for x in wp_order]

    visit_order = visit_order_from_waypoints(n=n, waypoint_order=wp_order)
    return OptimizeDrivingRouteResponse(visit_order=visit_order, source="directions")
