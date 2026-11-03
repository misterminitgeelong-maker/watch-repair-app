"""Server-side Google Places address suggestions for the native apps.

The web app talks to Google Places straight from the browser with a referrer-restricted key. A phone app has
no safe place to keep a key, so it asks this API instead: `autocomplete` while the user types, then `details`
once they pick a suggestion, which also resolves the suburb and state the intake forms need.
"""
from __future__ import annotations

import logging
import re
from typing import Optional

import httpx
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel

from ..config import settings
from ..dependencies import get_auth_context

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/v1/places", tags=["places"])

AUTOCOMPLETE_URL = "https://maps.googleapis.com/maps/api/place/autocomplete/json"
DETAILS_URL = "https://maps.googleapis.com/maps/api/place/details/json"
MIN_QUERY_LENGTH = 3
MAX_QUERY_LENGTH = 120
MAX_SUGGESTIONS = 6
_PLACE_ID = re.compile(r"^[A-Za-z0-9_\-]{10,300}$")
_SESSION = re.compile(r"^[A-Za-z0-9_\-]{8,64}$")

_STATE_ALIASES = {
    "act": "ACT", "australian capital territory": "ACT",
    "nsw": "NSW", "new south wales": "NSW",
    "nt": "NT", "northern territory": "NT",
    "qld": "QLD", "queensland": "QLD",
    "sa": "SA", "south australia": "SA",
    "tas": "TAS", "tasmania": "TAS",
    "vic": "VIC", "victoria": "VIC",
    "wa": "WA", "western australia": "WA",
}
_SUBURB_TYPES = ("locality", "postal_town", "sublocality_level_1", "sublocality", "neighborhood")


class AddressSuggestion(BaseModel):
    place_id: str
    description: str
    primary_text: Optional[str] = None
    secondary_text: Optional[str] = None


class AddressSuggestionList(BaseModel):
    suggestions: list[AddressSuggestion]


class ResolvedAddress(BaseModel):
    formatted_address: str
    suburb: Optional[str] = None
    state_code: Optional[str] = None
    postcode: Optional[str] = None
    lat: Optional[float] = None
    lng: Optional[float] = None


def _api_key() -> str:
    return (settings.google_places_api_key or settings.google_maps_web_services_key or "").strip()


def _require_key() -> str:
    key = _api_key()
    if not key:
        raise HTTPException(
            status_code=503,
            detail="Address suggestions are not configured. Set GOOGLE_PLACES_API_KEY (Places API enabled).",
        )
    return key


def _component(components: list[dict], type_: str, *, short: bool = False) -> Optional[str]:
    for row in components:
        if type_ in (row.get("types") or []):
            value = (row.get("short_name") if short else row.get("long_name")) or row.get("long_name") or row.get("short_name")
            value = (value or "").strip()
            return value or None
    return None


def normalize_state(raw: Optional[str]) -> Optional[str]:
    return _STATE_ALIASES.get((raw or "").strip().lower())


def parse_components(components: list[dict]) -> tuple[Optional[str], Optional[str], Optional[str]]:
    """(suburb, state code, postcode) from Google address components, mirroring the web `auAddress.ts`."""
    suburb = next((name for t in _SUBURB_TYPES if (name := _component(components, t))), None)
    state = normalize_state(_component(components, "administrative_area_level_1", short=True)) or normalize_state(
        _component(components, "administrative_area_level_1")
    )
    return suburb, state, _component(components, "postal_code")


async def _google_get(url: str, params: dict) -> dict:
    try:
        async with httpx.AsyncClient(timeout=8.0) as client:
            resp = await client.get(url, params=params)
    except httpx.HTTPError:
        logger.warning("Places request failed", exc_info=True)
        raise HTTPException(status_code=502, detail="Address lookup is unavailable right now.")
    if resp.status_code != 200:
        logger.warning("Places HTTP %s", resp.status_code)
        raise HTTPException(status_code=502, detail="Address lookup is unavailable right now.")
    return resp.json()


@router.get("/autocomplete", response_model=AddressSuggestionList)
async def autocomplete_address(
    q: str = Query(..., max_length=MAX_QUERY_LENGTH),
    session: Optional[str] = Query(default=None, description="Opaque token that groups one typing session for Google billing"),
    _auth=Depends(get_auth_context),
):
    """Up to six Australian or New Zealand street-address suggestions for what the user has typed so far."""
    text = " ".join(q.split())
    if len(text) < MIN_QUERY_LENGTH:
        return AddressSuggestionList(suggestions=[])
    params = {"input": text, "types": "address", "components": "country:au|country:nz", "key": _require_key()}
    if session and _SESSION.match(session):
        params["sessiontoken"] = session
    data = await _google_get(AUTOCOMPLETE_URL, params)
    status = data.get("status")
    if status == "ZERO_RESULTS":
        return AddressSuggestionList(suggestions=[])
    if status != "OK":
        logger.warning("Places autocomplete status=%s msg=%s", status, data.get("error_message"))
        raise HTTPException(status_code=502, detail="Address lookup is unavailable right now.")
    out: list[AddressSuggestion] = []
    for row in (data.get("predictions") or [])[:MAX_SUGGESTIONS]:
        place_id, description = row.get("place_id"), (row.get("description") or "").strip()
        if not place_id or not description:
            continue
        fmt = row.get("structured_formatting") or {}
        out.append(AddressSuggestion(
            place_id=place_id, description=description,
            primary_text=fmt.get("main_text"), secondary_text=fmt.get("secondary_text"),
        ))
    return AddressSuggestionList(suggestions=out)


@router.get("/details", response_model=ResolvedAddress)
async def resolve_address(
    place_id: str = Query(..., max_length=300),
    session: Optional[str] = Query(default=None),
    _auth=Depends(get_auth_context),
):
    """The full formatted address, suburb, state, postcode and position for a picked suggestion."""
    if not _PLACE_ID.match(place_id):
        raise HTTPException(status_code=422, detail="Invalid place id.")
    params = {"place_id": place_id, "fields": "formatted_address,address_component,geometry/location", "key": _require_key()}
    if session and _SESSION.match(session):
        params["sessiontoken"] = session
    data = await _google_get(DETAILS_URL, params)
    status = data.get("status")
    if status in ("NOT_FOUND", "ZERO_RESULTS", "INVALID_REQUEST"):
        raise HTTPException(status_code=404, detail="That address could not be found.")
    if status != "OK":
        logger.warning("Places details status=%s msg=%s", status, data.get("error_message"))
        raise HTTPException(status_code=502, detail="Address lookup is unavailable right now.")
    result = data.get("result") or {}
    formatted = (result.get("formatted_address") or "").strip()
    if not formatted:
        raise HTTPException(status_code=404, detail="That address could not be found.")
    suburb, state, postcode = parse_components(result.get("address_components") or [])
    loc = (result.get("geometry") or {}).get("location") or {}
    return ResolvedAddress(
        formatted_address=formatted, suburb=suburb, state_code=state, postcode=postcode,
        lat=loc.get("lat"), lng=loc.get("lng"),
    )
