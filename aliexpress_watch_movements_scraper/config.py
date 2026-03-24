"""
Configuration for the AliExpress watch movements scraper.
Edit search terms, rate limits, and deduplication here.
"""

import logging

# ── Search terms ─────────────────────────────────────────────────────────────
SEARCH_TERMS = [
    "watch movement",
    "quartz watch movement",
    "miyota movement",
    "miyota 2035",
    "miyota 2115",
    "miyota 2315",
    "miyota 2305",
    "miyota os10",
    "miyota os20",
    "hattori movement",
    "seiko pc21",
    "seiko pc32",
    "vx12 movement",
    "vx32 movement",
    "vd53 movement",
    "vd54 movement",
    "vk63 movement",
    "vk64 movement",
    "ronda movement",
    "ronda 515",
    "ronda 505",
    "eta quartz movement",
    "eta 955.112",
    "eta 955.412",
    "isa movement",
    "pe50 movement",
    "sl68 movement",
]

# To add new calibre search terms: append to SEARCH_TERMS above.

# ── AliExpress URLs ──────────────────────────────────────────────────────────
ALIEXPRESS_BASE = "https://www.aliexpress.com"
ALIEXPRESS_LOGIN_URL = "https://login.aliexpress.com/?fromSite=true"
ALIEXPRESS_SEARCH_URL = "https://www.aliexpress.com/w/wholesale-{query}.html"

# ── Rate limiting (seconds) ─────────────────────────────────────────────────
MIN_DELAY_BETWEEN_REQUESTS = 2.0
MAX_DELAY_BETWEEN_REQUESTS = 6.0
PAGE_LOAD_TIMEOUT_MS = 30000
MAX_RETRIES = 3

# ── Pagination ──────────────────────────────────────────────────────────────
# Per search term, how many pages to scrape (approx 48 items per page)
# 400 listings / 32 terms ≈ 12.5, so ~2 pages per term minimum
PAGES_PER_SEARCH = 3

# ── Deduplication ───────────────────────────────────────────────────────────
# Price bucket: round price to nearest PRICE_BUCKET_USD dollars for canonical key
PRICE_BUCKET_USD = 2.0

# Canonical key = brand + calibre + seller + price_bucket
# Increase PRICE_BUCKET_USD for looser deduplication (more duplicates removed).
# Decrease for stricter (keep more near-duplicates).

# ── Output paths ───────────────────────────────────────────────────────────
DATA_DIR = "data"
RAW_CSV = "data/aliexpress_watch_movements_raw.csv"
CLEAN_JSON = "data/aliexpress_watch_movements_clean.json"
CLEAN_CSV = "data/aliexpress_watch_movements_clean.csv"
GROUPED_CSV = "data/aliexpress_watch_movements_grouped.csv"

# Fallback: local HTML directory (drop exported pages here)
HTML_SAMPLES_DIR = "html_samples"

# Persistent browser profile (cookies, localStorage) for logged-in scraping
BROWSER_PROFILE_DIR = "browser_profile"  # resolved relative to scraper dir

# ── Logging ─────────────────────────────────────────────────────────────────
LOG_LEVEL = logging.INFO
LOG_FORMAT = "%(asctime)s [%(levelname)s] %(name)s: %(message)s"
