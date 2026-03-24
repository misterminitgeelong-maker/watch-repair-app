# Prospect Scripts

## 1. Raw Scraper → Excel (no API)

`scrape_prospects.py` — Scrapes directory sites (Yellow Pages AU) via HTTP and exports to Excel.

```bash
cd backend

# Required: state. Output to Excel
python -m scripts.scrape_prospects --state VIC -o prospects.xlsx

# Limit suburbs for testing
python -m scripts.scrape_prospects --state NSW --limit 10 -o test.xlsx

# One category only
python -m scripts.scrape_prospects --state VIC --category mechanics -o mechanics.xlsx
```

| Flag        | Description                     |
|------------|---------------------------------|
| `--state`  | State code (required)           |
| `--category` | One category (default: all)  |
| `--limit`  | Max suburbs (0 = all)           |
| `--delay`  | Seconds between requests (default: 2) |
| `-o`       | Output Excel path               |
| `--source` | `yp` or `truelocal` (default: truelocal) |
| `--browser`| Use Playwright headless browser — bypasses 403 from many sites |
| `--dry-run`| No fetch or write               |

**If you get 403 Forbidden:** Directory sites often block plain HTTP requests. Install Playwright and use `--browser`:
```bash
pip install playwright
playwright install chromium
python -m scripts.scrape_prospects --state VIC --limit 5 --browser -o prospects.xlsx
```

**Note:** HTML selectors may need updates if directory sites change structure.

---

## 2. Google Places API Collector (optional)

`collect_prospects.py` — Fetches via Places API and stores in DB. Requires `GOOGLE_PLACES_API_KEY`.

```bash
python -m scripts.collect_prospects --state VIC --limit 20
```
