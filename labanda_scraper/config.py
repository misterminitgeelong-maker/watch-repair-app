"""
Labanda watch movements scraper configuration.
Source: https://www.labanda.com.au/watch-movements
"""

LABANDA_BASE = "https://www.labanda.com.au"
LABANDA_MOVEMENTS = "https://www.labanda.com.au/watch-movements"
LABANDA_LOGIN = "https://www.labanda.com.au/customer/account/login"
BROWSER_PROFILE_DIR = "browser_profile"

# Category subpages (from /watch-movements hub - each has movement tables with prices)
CATEGORY_PATHS = [
    "/watch-movements/eta",
    "/watch-movements/france-ebauches",
    "/watch-movements/hattori",
    "/watch-movements/isa",
    "/watch-movements/citizen-and-miyota",
    "/watch-movements/ronda",
    "/watch-movements/swiss-ebauches",
    "/watch-movements/china",
]

MIN_DELAY = 3.0
MAX_DELAY = 7.0
PAGE_LOAD_TIMEOUT_MS = 25000
MAX_RETRIES = 3

DATA_DIR = "data"
RAW_CSV = "data/labanda_movements_raw.csv"
