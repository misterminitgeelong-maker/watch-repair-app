# AliExpress Watch Movements Scraper

Collects watch movement listings from AliExpress search results and exports them to CSV and JSON. Targets ~400 raw listings across 32 search terms (quartz movements, Miyota, Seiko, Ronda, ETA, etc.).

## Installation

### 1. Create a virtual environment (recommended)

```bash
cd aliexpress_watch_movements_scraper
python -m venv venv
# Windows:
venv\Scripts\activate
# macOS/Linux:
source venv/bin/activate
```

### 2. Install dependencies

```bash
pip install -r requirements.txt
```

### 3. Install Playwright browsers (for live scraping)

```bash
playwright install chromium
```

## How to Run

### Option A: Live scraping with Playwright

```bash
python main.py --live
```

Runs headless Chrome, visits each search page, and extracts product cards. Uses retries, rate limiting, and random delays (2–6 seconds between requests) to reduce blocking risk.

### Option B: HTML fallback (parse local files)

If live scraping is unstable (captchas, blocks, etc.):

1. Manually search AliExpress for each term and save the page HTML:
   - `File → Save As` or right‑click → “Save as…” in your browser
   - Or use a “Save page” extension
2. Put HTML files in `html_samples/` with names like:
   - `search_watch_movement_p1.html`
   - `search_miyota_2035_p1.html`
   - `search_vk63_movement_p2.html`
3. Run:

```bash
python main.py --html
```

File naming:
- `search_<term>_p<n>.html` — `term` is the search phrase with spaces as underscores; `n` is the page number.
- Example: `search_quartz_watch_movement_p2.html` → search term `quartz watch movement`, page 2.
- Any `*.html` in the directory will be parsed; a generic name yields `search_term: unknown`.

## Where Outputs Are Saved

All outputs go under `data/`:

| File | Description |
|------|-------------|
| `data/aliexpress_watch_movements_raw.csv` | Every parsed listing (no deduplication) |
| `data/aliexpress_watch_movements_clean.csv` | Deduplicated, normalized listings |
| `data/aliexpress_watch_movements_clean.json` | Same as clean CSV, in JSON format |
| `data/aliexpress_watch_movements_grouped.csv` | Aggregated by brand+calibre (min/median/max price, seller counts) |

With `--live`, raw HTML is also stored in `data/raw_html/` for debugging.

## How to Add New Calibre Search Terms

1. Edit `config.py`
2. Add terms to `SEARCH_TERMS`:

```python
SEARCH_TERMS = [
    "watch movement",
    "miyota 2035",
    # Add new terms here:
    "your new calibre",
]
```

3. Run the scraper again.

## How to Tune Deduplication

Deduplication uses a canonical key: `brand + calibre + seller + price_bucket`.

The price bucket rounds prices to reduce near-duplicates. Configure in `config.py`:

```python
# Round price to nearest N dollars for the canonical key
PRICE_BUCKET_USD = 2.0
```

- **Increase** (e.g. `5.0`): stronger deduplication, more near-duplicates removed
- **Decrease** (e.g. `0.5`): weaker deduplication, more similar listings kept

## Classification Rules

- **listing_kind**: `bare_movement` | `watch_with_movement` | `parts_bundle` | `unclear`
- **mechanical_or_quartz**: `quartz` | `mechanical` | `unknown`
- **mechaquartz**: `true` for VK63, VK64, etc.
- Full watch wording (e.g. “watch”, “wristwatch”) → `watch_with_movement`
- “Movement only”, “loose movement”, “no case” → `bare_movement`

Brand aliases (e.g. TMI → Seiko/TMI, Citizen → Miyota) and calibre formatting (e.g. `955112` → `955.112`) are applied automatically.

## Project Structure

```
aliexpress_watch_movements_scraper/
├── config.py       # Search terms, rate limits, deduplication
├── main.py         # Entry point
├── scraper.py      # Playwright live scrape + HTML fallback loader
├── parser.py       # HTML → raw listing extraction
├── normalizer.py   # Clean, classify, dedupe, group
├── exporter.py     # CSV/JSON export
├── requirements.txt
├── data/           # Output directory (created on first run)
└── html_samples/   # Put saved HTML here for fallback mode
```

## Troubleshooting

- **No listings extracted**: AliExpress may have changed markup. Use the HTML fallback and inspect `html_samples/*.html` to see current structure.
- **Blocked or captchas**: Use `--html` and save pages manually.
- **Too few listings**: Increase `PAGES_PER_SEARCH` in `config.py` or add more search terms.
