# Prospect Collector

Fetches businesses via **Google Places API** and stores them in the database for fast prospect search.

## Setup

1. Set `GOOGLE_PLACES_API_KEY` in `.env`
2. Ensure suburbs are seeded (run the app once; it seeds suburbs on startup if empty)
3. Run the prospect migration or start the app (table is created if missing)

## Usage

```bash
cd backend

# Dry run (see what would be fetched)
python -m scripts.collect_prospects --dry-run

# Collect for one state, limit suburbs (for testing)
python -m scripts.collect_prospects --state VIC --limit 20

# Collect one category only
python -m scripts.collect_prospects --state NSW --category mechanics --limit 50

# Full run (all categories × all suburbs) — can take hours and use API quota
python -m scripts.collect_prospects --delay 1.5
```

## Options

| Flag       | Description                                  | Default |
|-----------|----------------------------------------------|---------|
| `--state` | Limit to one state (VIC, NSW, etc.)          | All     |
| `--category` | Limit to one category                     | All     |
| `--limit` | Max suburbs to process (0 = no limit)       | 0       |
| `--delay` | Seconds between API calls (rate limiting)    | 1.2     |
| `--dry-run` | Don't call API or write to DB              | false   |

## API Cost

Google Places Text Search costs ~$32 per 1000 requests. With ~4000 suburbs × 8 categories ≈ 32,000 requests for a full run. Use `--state` and `--limit` for smaller batches.

## Search Behavior

- **Prospects tab**: Uses stored data by default. Faster, no per-search API cost.
- **"Refresh from Google"** checkbox: Forces live Places API for fresh data.
