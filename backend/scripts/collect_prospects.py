#!/usr/bin/env python3
"""
Prospect collector: fetches businesses via Google Places API and stores them in the DB.

Usage:
  python -m scripts.collect_prospects [--state VIC] [--category mechanics] [--limit 50] [--delay 1.5]
  cd backend && python -m scripts.collect_prospects --state VIC --limit 20

Options:
  --state    Limit to one state (e.g. VIC, NSW). Default: all.
  --category Limit to one category. Default: all.
  --limit    Max suburbs to process (default: no limit). Use for testing.
  --delay    Seconds between API calls (default: 1.2) to respect rate limits.
  --dry-run  Show what would be fetched, don't call API or write DB.
"""
from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path

# Ensure app is importable when run from backend/
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import httpx
from sqlmodel import Session, select

from app.config import settings
from app.database import engine
from app.models import ProspectBusiness, Suburb
from app.routes.prospects import (
    AU_STATES,
    CATEGORY_BASES,
    PLACES_URL,
    STATE_CODES,
    _state_name_for_query,
)


def fetch_places_page(
    client: httpx.Client,
    query: str,
    *,
    next_page_token: str | None = None,
) -> tuple[list[dict], str | None]:
    """Call Places Text Search. Returns (results, next_page_token or None)."""
    params: dict = {
        "query": query,
        "key": settings.google_places_api_key,
        "region": "au",
    }
    if next_page_token:
        params["pagetoken"] = next_page_token
    resp = client.get(PLACES_URL, params=params, timeout=15.0)
    resp.raise_for_status()
    data = resp.json()
    if data.get("status") == "REQUEST_DENIED":
        raise RuntimeError(f"Places API denied: {data.get('error_message', 'Unknown')}")
    if data.get("status") not in ("OK", "ZERO_RESULTS"):
        raise RuntimeError(f"Places API status: {data.get('status')}")
    results = data.get("results", [])
    next_token = data.get("next_page_token")
    if next_token:
        time.sleep(2)  # Required before using next_page_token
    return results, next_token if next_token else None


def collect_for_suburb(
    client: httpx.Client,
    session: Session,
    category: str,
    suburb: Suburb,
    *,
    max_pages: int = 3,
    dry_run: bool = False,
) -> int:
    """Fetch and store prospects for one category+suburb. Returns count stored."""
    base = CATEGORY_BASES.get(category)
    if not base:
        return 0
    state_name = _state_name_for_query(suburb.state_code)
    query = f"{base} {suburb.name} {state_name} Australia"

    all_results: list[dict] = []
    next_token: str | None = None
    for _ in range(max_pages):
        results, next_token = fetch_places_page(client, query, next_page_token=next_token)
        all_results.extend(results)
        if not next_token:
            break

    if dry_run:
        return len(all_results)

    stored = 0
    for p in all_results:
        pid = p.get("place_id") or ""
        if not pid:
            continue
        existing = session.exec(select(ProspectBusiness).where(ProspectBusiness.place_id == pid)).first()
        if existing:
            existing.name = p.get("name", "")
            existing.address = p.get("formatted_address", "") or ""
            existing.phone = p.get("formatted_phone_number")
            existing.website = p.get("website")
            existing.rating = p.get("rating")
            existing.review_count = p.get("user_ratings_total")
            existing.category = category
            existing.suburb_name = suburb.name
            existing.state_code = suburb.state_code
            session.add(existing)
        else:
            session.add(
                ProspectBusiness(
                    place_id=pid,
                    name=p.get("name", ""),
                    address=p.get("formatted_address", "") or "",
                    phone=p.get("formatted_phone_number"),
                    website=p.get("website"),
                    rating=p.get("rating"),
                    review_count=p.get("user_ratings_total"),
                    category=category,
                    suburb_name=suburb.name,
                    state_code=suburb.state_code,
                )
            )
        stored += 1
    return stored


def main() -> int:
    parser = argparse.ArgumentParser(description="Collect prospect businesses via Google Places API")
    parser.add_argument("--state", type=str, help="Limit to state code (e.g. VIC)")
    parser.add_argument("--category", type=str, help="Limit to one category key")
    parser.add_argument("--limit", type=int, default=0, help="Max suburbs to process (0 = no limit)")
    parser.add_argument("--delay", type=float, default=1.2, help="Seconds between API calls")
    parser.add_argument("--dry-run", action="store_true", help="Don't call API or write DB")
    args = parser.parse_args()

    if not settings.google_places_api_key:
        print("ERROR: GOOGLE_PLACES_API_KEY not set")
        return 1

    state_filter = args.state.upper() if args.state else None
    if state_filter and state_filter not in STATE_CODES:
        print(f"ERROR: Invalid state {args.state}")
        return 1

    categories = [args.category] if args.category else list(CATEGORY_BASES.keys())
    if args.category and args.category not in CATEGORY_BASES:
        print(f"ERROR: Invalid category. Choose from: {', '.join(CATEGORY_BASES.keys())}")
        return 1

    with Session(engine) as session:
        suburb_query = select(Suburb).order_by(Suburb.state_code, Suburb.name)
        if state_filter:
            suburb_query = suburb_query.where(Suburb.state_code == state_filter)
        suburbs = list(session.exec(suburb_query).all())

        if not suburbs:
            suburb_query = select(Suburb)
            if state_filter:
                suburb_query = suburb_query.where(Suburb.state_code == state_filter)
            suburbs = list(session.exec(suburb_query).all())
        if not suburbs:
            print("No suburbs in DB. Run the app to seed suburbs first.")
            return 1

        if args.limit:
            suburbs = suburbs[: args.limit]

    total_combos = len(suburbs) * len(categories)
    print(f"Collecting: {len(categories)} category(ies) × {len(suburbs)} suburbs = {total_combos} queries")
    if args.dry_run:
        print("DRY RUN - no API calls or DB writes")
        return 0

    total_stored = 0
    done = 0
    with httpx.Client(timeout=20.0) as client:
        with Session(engine) as session:
            for i, suburb in enumerate(suburbs):
                for cat in categories:
                    try:
                        n = collect_for_suburb(client, session, cat, suburb, dry_run=False)
                        total_stored += n
                    except Exception as e:
                        print(f"  ERROR {cat} / {suburb.name}: {e}")
                    done += 1
                    if done % 10 == 0:
                        session.commit()
                        print(f"  Progress: {done}/{total_combos} | stored: {total_stored}")
                    time.sleep(args.delay)
            session.commit()

    print(f"Done. Stored/updated {total_stored} prospects.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
