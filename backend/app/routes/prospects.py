import httpx
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from typing import Optional
from ..config import settings
from ..dependencies import AuthContext, get_auth_context

router = APIRouter(prefix="/v1/prospects", tags=["prospects"])

PLACES_URL = "https://maps.googleapis.com/maps/api/place/textsearch/json"

# Category base queries (no location) — we append state/suburb when searching
CATEGORY_BASES = {
    "car_dealerships": "car dealership",
    "used_car_dealers": "used car dealer",
    "car_rental": "car rental hire company",
    "mechanics": "mechanic workshop auto repair",
    "panel_beaters": "panel beater smash repair",
    "insurance": "car insurance company",
    "fleet_management": "fleet management company",
    "car_auctions": "car auction",
}

AU_STATES = [
    {"code": "ACT", "name": "Australian Capital Territory"},
    {"code": "NSW", "name": "New South Wales"},
    {"code": "NT", "name": "Northern Territory"},
    {"code": "QLD", "name": "Queensland"},
    {"code": "SA", "name": "South Australia"},
    {"code": "TAS", "name": "Tasmania"},
    {"code": "VIC", "name": "Victoria"},
    {"code": "WA", "name": "Western Australia"},
]

STATE_CODES = {s["code"] for s in AU_STATES}

# Major suburbs per state (curated list for prospect search)
SUBURBS_BY_STATE: dict[str, list[str]] = {
    "ACT": ["Canberra", "Belconnen", "Woden", "Tuggeranong", "Gungahlin", "Queanbeyan", "Fyshwick", "Dickson", "Kingston", "Braddon"],
    "NSW": ["Sydney", "Parramatta", "Newcastle", "Wollongong", "Central Coast", "Penrith", "Liverpool", "Blacktown", "Chatswood", "North Sydney", "Bondi", "Surry Hills", "Marrickville", "Randwick", "Hurstville", "Campbelltown", "Dubbo", "Wagga Wagga", "Albury", "Tamworth"],
    "NT": ["Darwin", "Alice Springs", "Palmerston", "Katherine", "Tennant Creek", "Jabiru", "Nhulunbuy"],
    "QLD": ["Brisbane", "Gold Coast", "Sunshine Coast", "Townsville", "Cairns", "Toowoomba", "Mackay", "Rockhampton", "Bundaberg", "Hervey Bay", "Southport", "Surfers Paradise", "Fortitude Valley", "New Farm", "West End", "Logan", "Ipswich", "Redlands"],
    "SA": ["Adelaide", "North Adelaide", "Glenelg", "Norwood", "Port Adelaide", "Mount Barker", "Victor Harbor", "Whyalla", "Murray Bridge", "Elizabeth", "Marion", "Unley", "Prospect", "Burnside"],
    "TAS": ["Hobart", "Launceston", "Devonport", "Burnie", "Ulverstone", "New Norfolk", "Queenstown", "St Helens", "Smithton", "Wynyard"],
    "VIC": ["Melbourne", "Geelong", "Ballarat", "Bendigo", "Richmond", "Collingwood", "Fitzroy", "St Kilda", "Prahran", "South Yarra", "Carlton", "Footscray", "Dandenong", "Box Hill", "Frankston", "Sunbury", "Traralgon", "Warragul", "Warrnambool", "Shepparton", "Wodonga", "Mildura", "Echuca"],
    "WA": ["Perth", "Fremantle", "Joondalup", "Mandurah", "Bunbury", "Geraldton", "Kalgoorlie", "Albany", "Northbridge", "Subiaco", "Claremont", "Rockingham", "Canning Vale", "Midland", "Armadale"],
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

def _state_name_for_query(code: str) -> str:
    return next((s["name"] for s in AU_STATES if s["code"] == code), code)


async def _fetch_places(client: httpx.AsyncClient, query: str) -> list[dict]:
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
    return data.get("results", [])


@router.get("/search", response_model=ProspectSearchResponse)
async def search_prospects(
    category: str = Query(..., description="Category key from the allowed list"),
    state: str = Query(..., description="State code (e.g. VIC, NSW)"),
    suburbs: str | None = Query(default=None, description="Comma-separated suburb names to narrow search"),
    auth: AuthContext = Depends(get_auth_context),
):
    if not settings.google_places_api_key:
        raise HTTPException(status_code=500, detail="Google Places API key not configured")

    if category not in CATEGORY_BASES:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid category. Choose from: {', '.join(CATEGORY_BASES.keys())}",
        )
    if state.upper() not in STATE_CODES:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid state. Choose from: {', '.join(STATE_CODES)}",
        )

    base = CATEGORY_BASES[category]
    state_name = _state_name_for_query(state.upper())
    suburb_list = [s.strip() for s in (suburbs or "").split(",") if s.strip()] if suburbs else []
    suburb_list = suburb_list[:5]  # max 5 suburbs to avoid rate limits

    seen_place_ids: set[str] = set()
    all_prospects: list[Prospect] = []

    async with httpx.AsyncClient(timeout=10.0) as client:
        if suburb_list:
            for suburb in suburb_list:
                search_query = f"{base} {suburb} {state_name} Australia"
                places = await _fetch_places(client, search_query)
                for p in places:
                    pid = p.get("place_id", "")
                    if pid and pid not in seen_place_ids:
                        seen_place_ids.add(pid)
                        all_prospects.append(
                            Prospect(
                                name=p.get("name", ""),
                                address=p.get("formatted_address", ""),
                                phone=p.get("formatted_phone_number"),
                                website=p.get("website"),
                                rating=p.get("rating"),
                                review_count=p.get("user_ratings_total"),
                                category=category,
                                place_id=pid,
                            )
                        )
        else:
            search_query = f"{base} {state_name} Australia"
            places = await _fetch_places(client, search_query)
            for p in places:
                pid = p.get("place_id", "")
                if pid and pid not in seen_place_ids:
                    seen_place_ids.add(pid)
                    all_prospects.append(
                        Prospect(
                            name=p.get("name", ""),
                            address=p.get("formatted_address", ""),
                            phone=p.get("formatted_phone_number"),
                            website=p.get("website"),
                            rating=p.get("rating"),
                            review_count=p.get("user_ratings_total"),
                            category=category,
                            place_id=pid,
                        )
                    )

    return ProspectSearchResponse(results=all_prospects, total=len(all_prospects), category=category)

@router.get("/categories")
async def list_categories(auth: AuthContext = Depends(get_auth_context)):
    return {
        "categories": [
            {"key": k, "label": k.replace("_", " ").title()}
            for k in CATEGORY_BASES.keys()
        ]
    }


@router.get("/regions")
async def list_regions(auth: AuthContext = Depends(get_auth_context)):
    """States and suburbs for prospect search filters."""
    return {"states": AU_STATES, "suburbs": SUBURBS_BY_STATE}
