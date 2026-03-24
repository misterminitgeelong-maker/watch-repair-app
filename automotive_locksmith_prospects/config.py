"""
Configuration for the automotive locksmith prospect pipeline.
Adjust keywords, column mappings, and thresholds here.
"""

from dataclasses import dataclass, field
from typing import Mapping

# Chunked processing
CHUNKSIZE: int = 50_000

# Fuzzy matching threshold (0-100). Higher = stricter. Use for duplicate detection.
FUZZY_DUPLICATE_THRESHOLD: int = 85

# Minimum string length for fuzzy matching
FUZZY_MIN_LENGTH: int = 5

# Output sheet names
SHEET_SUBURBS: str = "suburbs"
SHEET_RAW_ABN_FILTERED: str = "raw_abn_filtered"
SHEET_PROSPECTS_CLEAN: str = "prospects_clean"
SHEET_DUPLICATES_REVIEW: str = "duplicates_review"
SHEET_SUMMARY_STATE: str = "summary_by_state"
SHEET_SUMMARY_SUBURB: str = "summary_by_suburb"
SHEET_SUMMARY_CATEGORY: str = "summary_by_category"

# Likely ABR column name candidates (try in order; first match wins)
ABR_COLUMN_CANDIDATES: Mapping[str, list[str]] = {
    "business_name": [
        "BusinessName", "Business name", "business_name", "Entity Name",
        "EntityName", "Organisation Name", "OrganisationName",
        "name", "Name", "ABN_Display_Name",
    ],
    "abn": [
        "ABN", "abn", "Australian Business Number",
        "Identifier Type", "identifier_value",
    ],
    "state": [
        "State", "state", "State code", "StateCode",
        "State/Territory", "State or Territory",
    ],
    "postcode": [
        "Postcode", "postcode", "Post code", "PostCode",
        "Postal code", "PostalCode",
    ],
    "suburb": [
        "Town name", "TownName", "Town", "town",
        "Suburb", "suburb", "Locality", "locality",
        "Local Government Area", "LGA",
    ],
}

# Likely suburb master column candidates
SUBURB_COLUMN_CANDIDATES: Mapping[str, list[str]] = {
    "suburb": [
        "suburb", "Suburb", "locality", "Locality",
        "name", "Name", "town", "Town",
    ],
    "state": [
        "state", "State", "state_code", "statecode",
        "state_abbr", "state_abbreviation",
    ],
    "postcode": [
        "postcode", "Postcode", "post_code", "postal_code",
        "postalcode",
    ],
}

# State normalization: map variations to standard 2-letter codes
STATE_NORMALIZE: Mapping[str, str] = {
    "nsw": "NSW", "new south wales": "NSW",
    "vic": "VIC", "victoria": "VIC",
    "qld": "QLD", "queensland": "QLD",
    "sa": "SA", "south australia": "SA",
    "wa": "WA", "western australia": "WA",
    "tas": "TAS", "tasmania": "TAS",
    "nt": "NT", "northern territory": "NT",
    "act": "ACT", "australian capital territory": "ACT",
}

# Category keywords: each category maps to list of keywords (lowercase).
# A record matches a category if ANY keyword appears in the combined text.
CATEGORY_KEYWORDS: Mapping[str, list[str]] = {
    "mechanic_auto_repair": [
        "mechanic", "mechanical", "auto repair", "car repair",
        "automotive repair", "service centre", "service center",
        "brake", "auto service", "car service",
        "workshop", "garage", "smog", "roadworthy",
    ],
    "car_dealer": [
        "car dealer", "car dealership", "new car", "new vehicle",
        "automotive dealer", "motor dealer", "vehicle dealer",
        "honda", "toyota", "ford", "mazda", "holden", "nissan",
        "dealership", "car sales", "vehicle sales",
    ],
    "used_car_dealer": [
        "used car", "second hand car", "pre owned", "pre-owned",
        "used vehicle", "used cars", "used car dealer",
    ],
    "smash_repair_panel_beater": [
        "smash repair", "panel beater", "panel beating",
        "panel repair", "collision repair", "body repair",
        "dent", "auto body", "crash repair",
    ],
    "auto_electrician": [
        "auto electrician", "automotive electrician",
        "car electric", "vehicle electric", "auto electrical",
    ],
    "towing": [
        "tow", "towing", "tow truck", "tow truck",
        "roadside", "breakdown", "recovery",
    ],
    "tyre_shop": [
        "tyre", "tire", "tyres", "tires",
        "wheel", "wheel alignment", "wheel alignment",
    ],
    "fleet_transport": [
        "fleet", "transport", "logistics", "trucking",
        "haulage", "freight", "courier", "delivery",
        "distribution", "heavy vehicle",
    ],
    "car_rental": [
        "car rental", "vehicle hire", "hire car",
        "rent a car", "rental car", "car hire",
    ],
    "truck_workshop_dealer": [
        "truck", "commercial vehicle", "heavy vehicle",
        "semi", "prime mover", "rig",
    ],
    "motorcycle": [
        "motorcycle", "motorbike", "bike shop",
        "harley", "yamaha", "kawasaki", "honda bikes",
    ],
    "wreckers_salvage": [
        "wrecker", "wreckers", "salvage", "auto wreck",
        "car wreck", "second hand parts", "used parts",
    ],
    "vehicle_auction": [
        "auction", "auctions", "car auction",
        "vehicle auction", "auto auction",
    ],
    "automotive_general": [
        "automotive", "auto", "motor", "vehicle",
        "car ", " cars", "automotive parts",
        "auto parts", "car parts", "spare parts",
    ],
}

# Categories that score higher (more valuable leads)
HIGH_VALUE_CATEGORIES: set[str] = {
    "mechanic_auto_repair", "car_dealer", "used_car_dealer",
    "smash_repair_panel_beater", "towing", "auto_electrician",
    "fleet_transport",
}

# Display labels for categories
CATEGORY_LABELS: Mapping[str, str] = {
    "mechanic_auto_repair": "Mechanic / Auto Repair",
    "car_dealer": "Car Dealer",
    "used_car_dealer": "Used Car Dealer",
    "smash_repair_panel_beater": "Smash Repair / Panel Beater",
    "auto_electrician": "Auto Electrician",
    "towing": "Towing",
    "tyre_shop": "Tyre Shop",
    "fleet_transport": "Fleet / Transport",
    "car_rental": "Car Rental",
    "truck_workshop_dealer": "Truck Workshop / Dealer",
    "motorcycle": "Motorcycle",
    "wreckers_salvage": "Wreckers / Salvage",
    "vehicle_auction": "Vehicle Auction",
    "automotive_general": "Automotive General",
}
