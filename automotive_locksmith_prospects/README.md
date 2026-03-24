# Automotive Locksmith Prospects

A Python pipeline that builds a national Australian prospect database for an automotive locksmith business. Processes a suburb master CSV and ABR (Australian Business Register) bulk extract CSV, then outputs a clean Excel workbook of likely B2B prospects.

**Zero budget.** No paid APIs, no Google Maps, no Yellow Pages. Runs locally on Windows from VS Code or Cursor.

## Installation

```bash
cd automotive_locksmith_prospects
pip install -r requirements.txt
```

Dependencies: `pandas`, `openpyxl`, `rapidfuzz`.

## Quick Start

```bash
python main.py --suburbs data/input/suburbs_master.csv --abr data/input/abr_bulk_extract.csv --output data/output/prospects.xlsx
```

## Input Files

### 1. Suburb Master CSV

Lists Australian suburbs with state and postcode. Used to match and enrich ABR records.

**Example schema (column names matter):**

| suburb | state | postcode |
|--------|-------|----------|
| Melbourne | VIC | 3000 |
| Richmond | VIC | 3121 |
| Sydney | NSw | 2000 |

**Alternative column names** (configured in `config.py`):
- `suburb` or `locality` or `town` or `name`
- `state` or `state_code` or `state_abbr`
- `postcode` or `post_code` or `postal_code`

### 2. ABR Bulk Extract CSV

Download from the [Australian Business Register (ABR)](https://abr.business.gov.au/) bulk data. Contains business names, ABNs, addresses, and entity types.

**Example schema:**

| Business name | ABN | State | Postcode | Town name |
|---------------|-----|-------|----------|-----------|
| Joe's Mechanical Repairs Pty Ltd | 12345678901 | VIC | 3121 | Richmond |
| Smith & Sons Panel Beating | 98765432102 | NSw | 2150 | Parramatta |

**Alternative column names** (configured in `config.py`):
- Business name: `BusinessName`, `Entity Name`, `Organisation Name`, etc.
- ABN: `ABN`, `Australian Business Number`, etc.
- State: `State`, `State code`, etc.
- Postcode: `Postcode`, `Post code`, `Postal code`, etc.
- Suburb: `Town name`, `TownName`, `Suburb`, `Locality`, etc.

If your ABR export has different column names, add them to `ABR_COLUMN_CANDIDATES` in `config.py`.

## Output Workbook

The Excel file contains these sheets:

| Sheet | Description |
|-------|-------------|
| `suburbs` | Suburb master as loaded |
| `raw_abn_filtered` | All ABR records classified as automotive (before deduplication) |
| `prospects_clean` | Deduplicated prospects with lead scores |
| `duplicates_review` | Records flagged as potential duplicates (ABN dupes, name+postcode dupes, fuzzy matches) |
| `summary_by_state` | Prospect count per state |
| `summary_by_suburb` | Prospect count per suburb (top 500) |
| `summary_by_category` | Prospect count per category |

**prospects_clean columns** (minimum):
- `business_name`, `abn`, `category`, `suburb`, `postcode`, `state`, `lead_score`

## Target Categories

The classifier detects these automotive-related business types:

- Mechanic / Auto Repair
- Car Dealer
- Used Car Dealer
- Smash Repair / Panel Beater
- Auto Electrician
- Towing
- Tyre Shop
- Fleet / Transport
- Car Rental
- Truck Workshop / Dealer
- Motorcycle
- Wreckers / Salvage
- Vehicle Auction
- Automotive General

Extend categories and keywords in `config.py` → `CATEGORY_KEYWORDS`.

## Lead Scoring (0–100)

Scores consider:
- **Category** – High-value categories (mechanics, dealers, smash repair, towing, etc.) score higher
- **ABN present** – +15
- **Suburb, postcode, state** – Location completeness
- **Business name quality** – Length, structure

## Deduplication

1. **ABN** – Same ABN → keep first
2. **Name + postcode** – Same normalized name and postcode → keep first
3. **Fuzzy** – Similar names (rapidfuzz) → added to `duplicates_review` only, not removed

## Command-Line Options

```
python main.py --suburbs PATH --abr PATH [--output PATH] [--chunksize N]
```

| Option | Description | Default |
|--------|-------------|---------|
| `--suburbs` | Path to suburb master CSV | (required) |
| `--abr` | Path to ABR bulk extract CSV | (required) |
| `--output` | Output Excel path | data/output/prospects.xlsx |
| `--chunksize` | Rows per chunk for ABR (memory control) | 50000 |

## Limitations

- **ABR-only data** – No phone, email, or website from this pipeline. Contact details require enrichment from other sources.
- **Keyword-based classification** – Matches on business name and available text. False positives/negatives possible.
- **Suburb matching** – Exact and normalized matching only. Fuzzy suburb matching is optional and conservative.
- **Large ABR files** – Processed in chunks. Very large files (millions of rows) may take time.

## Extending the Pipeline

- **Categories** – Edit `CATEGORY_KEYWORDS` in `config.py`
- **Column mappings** – Edit `ABR_COLUMN_CANDIDATES` and `SUBURB_COLUMN_CANDIDATES` in `config.py`
- **Lead scoring** – Adjust `HIGH_VALUE_CATEGORIES` and logic in `src/scorer.py`
- **New enrichment** – Add modules under `src/` and call from `main.py` (no paid APIs in scope)

## Project Structure

```
automotive_locksmith_prospects/
├── main.py              # Entry point
├── config.py            # Keywords, column mappings, thresholds
├── requirements.txt
├── README.md
├── src/
│   ├── loader.py        # Load suburbs, stream ABR chunks
│   ├── cleaner.py       # Normalize ABN, postcode, state, suburb
│   ├── classifier.py    # Keyword-based category classification
│   ├── matcher.py       # Match to suburb master
│   ├── deduper.py       # ABN, name+postcode, fuzzy deduplication
│   ├── scorer.py        # Lead scoring 0-100
│   ├── exporter.py      # Excel export with formatting
│   └── utils.py         # Text normalization, column mapping
├── data/
│   ├── input/
│   └── output/
└── logs/
```
