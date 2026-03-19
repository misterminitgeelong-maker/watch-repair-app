import httpx
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from typing import Optional
from ..config import settings
from ..dependencies import AuthContext, get_auth_context

router = APIRouter(prefix="/v1/prospects", tags=["prospects"])

PLACES_URL = "https://maps.googleapis.com/maps/api/place/textsearch/json"

CATEGORY_QUERIES = {
    "car_dealerships": "car dealership Victoria Australia",
    "used_car_dealers": "used car dealer Victoria Australia",
    "car_rental": "car rental hire company Victoria Australia",
    "mechanics": "mechanic workshop auto repair Victoria Australia",
    "panel_beaters": "panel beater smash repair Victoria Australia",
    "insurance": "car insurance company Victoria Australia",
    "fleet_management": "fleet management company Victoria Australia",
    "car_auctions": "car auction Victoria Australia",
}

class Prospect(BaseModel):
    name: str
    address: str
    phone: Optional[str] = None
    website: Optional[str] = None
    rating: Optional[float] = None
    review_count: Optional[int] = None
    category: str
    place_id: str

class ProspectSearchResponse(BaseModel):
    results: list[Prospect]
    total: int
    category: str

@router.get("/search", response_model=ProspectSearchResponse)
async def search_prospects(
    category: str = Query(..., description="Category key from the allowed list"),
    auth: AuthContext = Depends(get_auth_context),
):
    if not settings.google_places_api_key:
        raise HTTPException(status_code=500, detail="Google Places API key not configured")

    if category not in CATEGORY_QUERIES:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid category. Choose from: {', '.join(CATEGORY_QUERIES.keys())}",
        )

    query = CATEGORY_QUERIES[category]

    async with httpx.AsyncClient(timeout=10.0) as client:
        resp = await client.get(
            PLACES_URL,
            params={
                "query": query,
                "key": settings.google_places_api_key,
                "region": "au",
            },
        )

    if resp.status_code != 200:
        raise HTTPException(status_code=502, detail="Google Places API request failed")

    data = resp.json()

    if data.get("status") == "REQUEST_DENIED":
        raise HTTPException(
            status_code=502,
            detail=f"Google Places API denied: {data.get('error_message', 'Unknown error')}",
        )

    places = data.get("results", [])

    prospects = [
        Prospect(
            name=p.get("name", ""),
            address=p.get("formatted_address", ""),
            phone=p.get("formatted_phone_number"),
            website=p.get("website"),
            rating=p.get("rating"),
            review_count=p.get("user_ratings_total"),
            category=category,
            place_id=p.get("place_id", ""),
        )
        for p in places
    ]

    return ProspectSearchResponse(results=prospects, total=len(prospects), category=category)

@router.get("/categories")
async def list_categories(auth: AuthContext = Depends(get_auth_context)):
    return {
        "categories": [
            {"key": k, "label": k.replace("_", " ").title()}
            for k in CATEGORY_QUERIES.keys()
        ]
    }
