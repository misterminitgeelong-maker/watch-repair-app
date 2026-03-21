"""Vehicle registration lookup — proxies to Blue Flag NEVDIS API."""
import httpx
from fastapi import APIRouter, Depends, HTTPException, Query

from ..config import settings
from ..dependencies import get_auth_context, require_feature

router = APIRouter(prefix="/v1", tags=["vehicle-lookup"])

AU_STATES = ("ACT", "NSW", "NT", "QLD", "SA", "TAS", "VIC", "WA")


@router.get("/vehicle-lookup")
async def vehicle_lookup(
    plate: str = Query(..., min_length=1, description="Registration plate"),
    state: str = Query(..., description="Registration state (ACT, NSW, NT, QLD, SA, TAS, VIC, WA)"),
    _auth=Depends(get_auth_context),
    _feat=Depends(require_feature("auto_key")),
):
    """Look up vehicle details by registration plate and state. Proxies to Blue Flag NEVDIS."""
    if not settings.rego_lookup_api_key:
        raise HTTPException(
            status_code=503,
            detail="Vehicle lookup is not configured. Set REGO_LOOKUP_API_KEY in .env",
        )
    state_upper = state.strip().upper()
    if state_upper not in AU_STATES:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid state. Use one of: {', '.join(AU_STATES)}",
        )
    plate_clean = plate.strip()
    if not plate_clean:
        raise HTTPException(status_code=400, detail="Plate is required")

    url = f"{settings.rego_lookup_base_url.rstrip('/')}/nevdis/vehicle_details"
    async with httpx.AsyncClient(timeout=15.0) as client:
        resp = await client.get(
            url,
            params={"plate": plate_clean, "state": state_upper},
            headers={"Authorization": settings.rego_lookup_api_key},
        )

    if resp.status_code != 200:
        raise HTTPException(
            status_code=502,
            detail=f"Vehicle lookup service error: {resp.status_code}",
        )

    data = resp.json()
    result_list = data.get("result") or []
    if not result_list:
        return {
            "found": False,
            "make": None,
            "model": None,
            "year": None,
            "vin": None,
            "registration_plate": plate_clean,
            "state": state_upper,
        }

    r = result_list[0]
    reg = r.get("registration") or {}
    return {
        "found": True,
        "make": r.get("make"),
        "model": r.get("model"),
        "year": None,  # Blue Flag NEVDIS response doesn't include year in doc
        "vin": r.get("vin"),
        "registration_plate": reg.get("plate") or plate_clean,
        "state": reg.get("state") or state_upper,
    }
