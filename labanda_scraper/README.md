# Labanda Watch Movements

Imports the Labanda movements catalogue into the app.

**Source:** https://www.labanda.com.au/watch-movements

## Quick start (no live scrape)

The catalogue is already in `docs/labanda_movements_catalogue.md`. To import all 695 movements:

```bash
python parse_catalogue_md.py --import
```

This writes:
- `data/labanda_movements.json` — parsed movements
- `data/labanda_movements.csv` — same as CSV
- Merges into `backend/seed/watch_movements.json` (new entries only)

Edit `purchase_cost_cents` in `watch_movements.json` to add your Labanda prices.

## Match to AliExpress costs

To fill in costs from AliExpress (where the same movements are sold cheaper):

```bash
python match_to_aliexpress.py
```

This matches Labanda movements to AliExpress listings and sets `purchase_cost_cents` from the AliExpress price data. Requires the AliExpress scraper data in `aliexpress_watch_movements_scraper/data/`. Use `--force` to overwrite existing costs.

## Live scraper (when site is reachable)

If labanda.com.au is accessible from your network:

```bash
pip install -r requirements.txt
playwright install chromium
python scraper.py
```

This saves HTML to `data/raw_html/` for all 8 categories. Parse and import with prices:

```bash
python parse_labanda_html.py --import
```

Extracts movements with Labanda prices into `watch_movements.json`.

### Authenticated scraping (login required)

If Labanda requires login to view the catalogue:

```bash
# 1. Log in once (opens browser)
python scraper.py --login

# 2. Scrape with your saved session
python scraper.py
```

Session is stored in `browser_profile/` and reused automatically on subsequent runs.

## Categories in catalogue

- ETA & Other Swiss
- France Ebauches
- Seiko, Hattori, TMI & Epson
- ISA
- Citizen & Miyota
- Ronda & Harley
- Swiss Ebauches
- China
