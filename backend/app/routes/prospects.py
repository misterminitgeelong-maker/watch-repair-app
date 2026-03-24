import httpx
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlmodel import Session, func, select
from typing import Optional

from ..config import settings
from ..database import get_session
from ..dependencies import AuthContext, get_auth_context
from ..models import ProspectBusiness, Suburb

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

# Fallback suburbs when DB is empty (e.g. before seed runs)
SUBURBS_BY_STATE_FALLBACK: dict[str, list[str]] = {
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


def _prospect_from_db_row(row: ProspectBusiness) -> Prospect:
    return Prospect(
        name=row.name,
        address=row.address,
        phone=row.phone,
        website=row.website,
        rating=row.rating,
        review_count=row.review_count,
        category=row.category,
        place_id=row.place_id,
    )


@router.get("/search", response_model=ProspectSearchResponse)
async def search_prospects(
    category: str = Query(..., description="Category key from the allowed list"),
    state: str = Query(..., description="State code (e.g. VIC, NSW)"),
    suburbs: str | None = Query(default=None, description="Comma-separated suburb names to narrow search"),
    live: bool = Query(default=False, description="Force live Places API instead of stored data"),
    auth: AuthContext = Depends(get_auth_context),
    session: Session = Depends(get_session),
):
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

    state_upper = state.upper()
    suburb_list = [s.strip() for s in (suburbs or "").split(",") if s.strip()] if suburbs else []
    suburb_list = suburb_list[:20]  # allow more when using stored data

    # Prefer stored ProspectBusiness data if available (and not forcing live)
    if not live:
        try:
            q = (
                select(ProspectBusiness)
                .where(ProspectBusiness.category == category)
                .where(ProspectBusiness.state_code == state_upper)
            )
            if suburb_list:
                q = q.where(ProspectBusiness.suburb_name.in_(suburb_list))
            stored = list(session.exec(q).all())
            if stored:
                prospects = [_prospect_from_db_row(r) for r in stored]
                return ProspectSearchResponse(results=prospects, total=len(prospects), category=category)
        except Exception:
            pass

    # Fallback to live Google Places API
    if not settings.google_places_api_key:
        raise HTTPException(status_code=500, detail="Google Places API key not configured")

    base = CATEGORY_BASES[category]
    state_name = _state_name_for_query(state_upper)
    suburb_list_api = suburb_list[:5]  # max 5 for API rate limits

    seen_place_ids: set[str] = set()
    all_prospects: list[Prospect] = []

    async with httpx.AsyncClient(timeout=10.0) as client:
        if suburb_list_api:
            for suburb in suburb_list_api:
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

@router.get("/collector-status")
async def collector_status(
    auth: AuthContext = Depends(get_auth_context),
    session: Session = Depends(get_session),
):
    """Count of stored prospects by category. Run scripts/collect_prospects to populate."""
    try:
        total = session.exec(select(func.count()).select_from(ProspectBusiness)).one()
        by_cat = session.exec(
            select(ProspectBusiness.category, func.count())
            .select_from(ProspectBusiness)
            .group_by(ProspectBusiness.category)
        ).all()
        return {
            "total": int(total),
            "by_category": [{"category": c, "count": int(n)} for c, n in by_cat],
        }
    except Exception:
        return {"total": 0, "by_category": []}


@router.get("/categories")
async def list_categories(auth: AuthContext = Depends(get_auth_context)):
    return {
        "categories": [
            {"key": k, "label": k.replace("_", " ").title()}
            for k in CATEGORY_BASES.keys()
        ]
    }


@router.get("/regions")
async def list_regions(
    auth: AuthContext = Depends(get_auth_context),
    session: Session = Depends(get_session),
):
    """States and suburbs for prospect search filters. Suburbs from DB (public data), fallback to curated list if empty."""
    try:
        suburbs_rows = session.exec(select(Suburb).order_by(Suburb.state_code, Suburb.name)).all()
        suburbs_by_state: dict[str, list[str]] = {code: [] for code in STATE_CODES}
        for sub in suburbs_rows:
            if sub.state_code in suburbs_by_state:
                suburbs_by_state[sub.state_code].append(sub.name)
        if not any(suburbs_by_state.values()):
            suburbs_by_state = SUBURBS_BY_STATE_FALLBACK
    except Exception:
        suburbs_by_state = SUBURBS_BY_STATE_FALLBACK
    return {"states": AU_STATES, "suburbs": suburbs_by_state}
