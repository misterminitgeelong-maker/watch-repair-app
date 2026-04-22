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

# Regional groupings for suburb picker — suburb names must match DB/fallback exactly
REGION_GROUPS: dict[str, dict[str, list[str]]] = {
    "VIC": {
        "Metro Central": ["Melbourne", "Carlton", "Collingwood", "Fitzroy", "Richmond", "South Yarra", "Prahran", "St Kilda", "Southbank", "Docklands", "Port Melbourne"],
        "Metro North": ["Coburg", "Brunswick", "Preston", "Reservoir", "Thornbury", "Northcote", "Bundoora", "Greensborough", "Heidelberg", "Macleod", "Rosanna", "Eltham", "Diamond Creek", "Epping", "Lalor", "Mill Park", "South Morang", "Sunbury", "Craigieburn", "Roxburgh Park", "Broadmeadows", "Campbellfield"],
        "Metro East": ["Box Hill", "Ringwood", "Doncaster", "Croydon", "Lilydale", "Healesville", "Mooroolbark", "Bayswater", "Knox", "Boronia", "Ferntree Gully", "Wantirna", "Mitcham", "Nunawading", "Vermont", "Forest Hill", "Blackburn", "Maroondah"],
        "Metro South East": ["Dandenong", "Frankston", "Springvale", "Noble Park", "Keysborough", "Pakenham", "Berwick", "Cranbourne", "Narre Warren", "Hampton Park", "Hallam", "Endeavour Hills", "Rowville", "Mulgrave", "Wheelers Hill", "Clayton", "Oakleigh", "Chadstone", "Moorabbin", "Cheltenham", "Mentone", "Mordialloc"],
        "Metro West": ["Footscray", "Sunshine", "Werribee", "Hoppers Crossing", "Melton", "Deer Park", "St Albans", "Keilor", "Essendon", "Moonee Ponds", "Ascot Vale", "Altona", "Williamstown", "Newport", "Laverton", "Point Cook", "Truganina", "Tarneit"],
        "Regional North": ["Shepparton", "Benalla", "Wangaratta", "Wodonga", "Albury", "Echuca", "Cobram", "Kyabram", "Mildura", "Swan Hill", "Horsham", "Warracknabeal", "Donald"],
        "Regional East": ["Traralgon", "Morwell", "Sale", "Bairnsdale", "Orbost", "Warragul", "Drouin", "Korumburra", "Leongatha", "Foster"],
        "Regional South": ["Geelong", "Torquay", "Lorne", "Apollo Bay", "Colac", "Camperdown", "Warrnambool", "Portland", "Hamilton", "Ararat"],
        "Regional West": ["Ballarat", "Bacchus Marsh", "Daylesford", "Maryborough", "Castlemaine", "Bendigo", "Heathcote", "Kyneton", "Gisborne"],
    },
    "NSW": {
        "Metro Central": ["Sydney", "Surry Hills", "Newtown", "Redfern", "Pyrmont", "Ultimo", "Glebe", "Darlinghurst", "Kings Cross", "Potts Point", "Woolloomooloo"],
        "Metro North": ["North Sydney", "Chatswood", "Hornsby", "Penrith", "Windsor", "Richmond", "Rouse Hill", "Castle Hill", "Parramatta", "Blacktown", "Seven Hills", "Bella Vista", "Norwest"],
        "Metro East": ["Bondi", "Randwick", "Maroubra", "Coogee", "Kingsford", "Mascot", "Botany", "Hurstville", "Rockdale", "Kogarah", "Sans Souci"],
        "Metro South": ["Liverpool", "Campbelltown", "Macarthur", "Ingleburn", "Minto", "Narellan", "Camden", "Picton", "Wollongong", "Shellharbour", "Kiama", "Bowral"],
        "Metro West": ["Parramatta", "Westmead", "Auburn", "Granville", "Merrylands", "Fairfield", "Cabramatta", "Wetherill Park", "Bankstown", "Lakemba", "Canterbury"],
        "Regional North": ["Newcastle", "Maitland", "Cessnock", "Singleton", "Tamworth", "Armidale", "Coffs Harbour", "Grafton", "Lismore", "Byron Bay", "Ballina", "Tweed Heads"],
        "Regional Central": ["Central Coast", "Gosford", "Wyong", "Tuggerah", "Port Macquarie", "Taree", "Forster", "Dubbo", "Orange", "Bathurst", "Mudgee"],
        "Regional South": ["Nowra", "Batemans Bay", "Narooma", "Eden", "Wagga Wagga", "Albury", "Griffith", "Leeton", "Young", "Goulburn", "Queanbeyan"],
    },
    "QLD": {
        "Metro Central": ["Brisbane", "Fortitude Valley", "New Farm", "West End", "South Brisbane", "Woolloongabba", "Spring Hill", "Kangaroo Point"],
        "Metro North": ["Chermside", "Aspley", "Northgate", "Nundah", "Virginia", "Kedron", "Stafford", "Everton Park", "Mitchelton", "Brookside", "Strathpine", "Redcliffe", "Kallangur"],
        "Metro East": ["Carindale", "Carina", "Wynnum", "Manly", "Bayside", "Cleveland", "Victoria Point", "Redland Bay", "Capalaba"],
        "Metro South": ["Sunnybank", "Runcorn", "Rochedale", "Logan", "Beenleigh", "Loganholme", "Springwood", "Daisy Hill", "Browns Plains", "Jimboomba"],
        "Metro West": ["Ipswich", "Springfield", "Richlands", "Forest Lake", "Darra", "Acacia Ridge", "Inala", "Oxley", "Moorooka", "Woolloongabba"],
        "Gold Coast": ["Surfers Paradise", "Southport", "Broadbeach", "Burleigh Heads", "Robina", "Varsity Lakes", "Nerang", "Mudgeeraba", "Helensvale", "Coomera", "Tweed Heads South"],
        "Sunshine Coast": ["Maroochydore", "Noosa", "Caloundra", "Nambour", "Buderim", "Mooloolaba", "Kawana Waters", "Sippy Downs"],
        "Regional North": ["Townsville", "Cairns", "Mackay", "Rockhampton", "Bundaberg", "Hervey Bay", "Gladstone", "Toowoomba", "Mount Isa", "Charters Towers"],
    },
    "WA": {
        "Metro Central": ["Perth", "Northbridge", "Subiaco", "Leederville", "Mount Lawley", "Highgate", "East Perth", "West Perth"],
        "Metro North": ["Joondalup", "Claremont", "Cottesloe", "Scarborough", "Stirling", "Innaloo", "Osborne Park", "Warwick", "Duncraig", "Hillarys", "Currambine", "Butler", "Yanchep"],
        "Metro East": ["Midland", "Swan", "Ellenbrook", "Bayswater", "Bassendean", "Guildford", "Kalamunda", "Maida Vale", "Forrestfield"],
        "Metro South": ["Fremantle", "Rockingham", "Mandurah", "Canning Vale", "Gosnells", "Armadale", "Kwinana", "Cockburn", "Spearwood", "Bibra Lake"],
        "Regional North": ["Geraldton", "Carnarvon", "Karratha", "Port Hedland", "Broome", "Kununurra", "Derby"],
        "Regional South": ["Albany", "Bunbury", "Busselton", "Manjimup", "Esperance", "Collie", "Harvey"],
        "Regional East": ["Kalgoorlie", "Boulder", "Coolgardie", "Merredin", "Northam", "York"],
    },
    "SA": {
        "Metro Central": ["Adelaide", "North Adelaide", "Norwood", "Hyde Park", "Unley", "Parkside", "Glenelg"],
        "Metro North": ["Prospect", "Enfield", "Salisbury", "Elizabeth", "Tea Tree Gully", "Modbury", "Golden Grove", "Mawson Lakes", "Gawler"],
        "Metro East": ["Burnside", "Kensington", "Magill", "Campbelltown", "Newton", "Athelstone", "Rostrevor"],
        "Metro South": ["Marion", "Morphett Vale", "Noarlunga", "Christies Beach", "Hallett Cove", "Reynella", "Onkaparinga"],
        "Metro West": ["Port Adelaide", "Semaphore", "Largs Bay", "Henley Beach", "Woodville", "Cheltenham", "Beverley"],
        "Regional North": ["Whyalla", "Port Augusta", "Port Pirie", "Kadina", "Yorke Peninsula"],
        "Regional South": ["Mount Barker", "Victor Harbor", "Goolwa", "Murray Bridge", "Strathalbyn", "Kangaroo Island"],
        "Regional East": ["Mount Gambier", "Naracoorte", "Keith", "Bordertown"],
    },
    "ACT": {
        "Inner North": ["Braddon", "Dickson", "Downer", "Lyneham", "O'Connor", "Ainslie", "Campbell", "Reid"],
        "Inner South": ["Kingston", "Manuka", "Barton", "Forrest", "Griffith", "Red Hill", "Deakin"],
        "Belconnen": ["Belconnen", "Bruce", "Charnwood", "Florey", "Fraser", "Giralang", "Hawker", "Higgins", "Holt", "Kaleen", "Latham", "Macquarie", "McKellar", "Melba", "Page", "Scullin", "Spence", "Weetangera"],
        "Woden / Weston": ["Woden", "Philip", "Curtin", "Hughes", "Garran", "Chifley", "Holder", "Rivett", "Stirling", "Waramanga", "Weston"],
        "Tuggeranong": ["Tuggeranong", "Erindale", "Greenway", "Kambah", "Macarthur", "Calwell", "Isabella Plains", "Fadden", "Gowrie", "Monash"],
        "Gungahlin": ["Gungahlin", "Franklin", "Harrison", "Mitchell", "Ngunnawal", "Palmerston", "Amaroo", "Casey", "Forde", "Moncrieff"],
        "Queanbeyan": ["Queanbeyan", "Jerrabomberra", "Googong"],
    },
    "TAS": {
        "Hobart Metro": ["Hobart", "Sandy Bay", "Battery Point", "North Hobart", "West Hobart", "South Hobart", "Glenorchy", "Moonah", "New Town", "Lenah Valley", "Lindisfarne", "Bellerive", "Rosny"],
        "Launceston Metro": ["Launceston", "Newstead", "Invermay", "Mowbray", "Newnham", "Kings Meadows", "Youngtown", "Riverside"],
        "North West": ["Devonport", "Ulverstone", "Burnie", "Somerset", "Wynyard", "Smithton", "Penguin"],
        "Regional": ["New Norfolk", "Queenstown", "Strahan", "St Helens", "Scottsdale", "Swansea", "Huonville"],
    },
    "NT": {
        "Darwin Metro": ["Darwin", "Palmerston", "Casuarina", "Nightcliff", "Rapid Creek", "Fannie Bay", "Stuart Park", "Larrakeyah", "Ludmilla"],
        "Alice Springs": ["Alice Springs", "Gillen", "Larapinta", "Araluen", "Eastside"],
        "Regional": ["Katherine", "Tennant Creek", "Jabiru", "Nhulunbuy", "Borroloola"],
    },
}


def _build_region_groups(state_code: str, available_suburbs: list[str]) -> dict[str, list[str]]:
    """Return region->suburbs mapping filtered to suburbs that exist in available_suburbs."""
    if state_code not in REGION_GROUPS:
        return {}
    available_set = {s.lower() for s in available_suburbs}
    result: dict[str, list[str]] = {}
    assigned: set[str] = set()
    for region, suburbs in REGION_GROUPS[state_code].items():
        matched = [s for s in suburbs if s.lower() in available_set]
        if matched:
            result[region] = matched
            assigned.update(s.lower() for s in matched)
    other = [s for s in available_suburbs if s.lower() not in assigned]
    if other:
        result["Other"] = other
    return result


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
    region_groups = {
        code: _build_region_groups(code, suburbs)
        for code, suburbs in suburbs_by_state.items()
    }
    return {"states": AU_STATES, "suburbs": suburbs_by_state, "region_groups": region_groups}
