#!/usr/bin/env python3
"""
AliExpress Watch Movements Scraper
Collects watch movement listings and exports to CSV/JSON.
Run with --live for Playwright scraping, or --html to parse local HTML.
"""

import argparse
import logging
import sys
from pathlib import Path

from config import (
    LOG_LEVEL,
    LOG_FORMAT,
    DATA_DIR,
    HTML_SAMPLES_DIR,
    SEARCH_TERMS,
    BROWSER_PROFILE_DIR,
)
from scraper import run_live_scrape, run_login_session, load_html_fallback
from parser import parse_all_pages
from normalizer import clean_and_normalize, deduplicate, build_grouped_report
from exporter import export_all

logger = logging.getLogger(__name__)


def setup_logging(verbose: bool = False) -> None:
    level = logging.DEBUG if verbose else LOG_LEVEL
    logging.basicConfig(level=level, format=LOG_FORMAT, stream=sys.stdout)


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Scrape AliExpress for watch movement listings and export to CSV/JSON."
    )
    parser.add_argument(
        "--live",
        action="store_true",
        help="Run live scraping with Playwright (default: use HTML fallback if no --live)",
    )
    parser.add_argument(
        "--login",
        action="store_true",
        help="Open browser for you to log in to AliExpress. Session saved for --live.",
    )
    parser.add_argument(
        "--user-data-dir",
        default=None,
        metavar="PATH",
        help="Browser profile dir for persistent session (default: %s)" % BROWSER_PROFILE_DIR,
    )
    parser.add_argument(
        "--html",
        action="store_true",
        help="Parse HTML from html_samples/ directory (fallback mode)",
    )
    parser.add_argument(
        "--html-dir",
        default=HTML_SAMPLES_DIR,
        help="Directory for HTML fallback files (default: html_samples)",
    )
    parser.add_argument(
        "--labanda",
        action="store_true",
        help="Use search terms from all 695 Labanda movements (602 unique calibres)",
    )
    parser.add_argument(
        "--labanda-pages",
        type=int,
        default=1,
        metavar="N",
        help="Pages per search when using --labanda (default: 1 to limit requests)",
    )
    parser.add_argument(
        "-v", "--verbose",
        action="store_true",
        help="Verbose logging",
    )
    args = parser.parse_args()

    setup_logging(args.verbose)

    if args.login:
        profile_dir = Path(args.user_data_dir) if args.user_data_dir else (Path(__file__).parent / BROWSER_PROFILE_DIR)
        run_login_session(profile_dir)
        logger.info("Session saved to %s. Run with --live (and --user-data-dir %s) to scrape.", profile_dir, profile_dir)
        return 0

    search_terms = SEARCH_TERMS
    pages_per_search = 3
    if args.labanda:
        from generate_labanda_terms import get_labanda_search_terms
        search_terms = get_labanda_search_terms()
        pages_per_search = args.labanda_pages
        logger.info("Using %d Labanda-derived search terms (%d pages each)", len(search_terms), pages_per_search)

    raw_listings = []

    if args.live:
        profile_dir = Path(args.user_data_dir) if args.user_data_dir else (Path(__file__).parent / BROWSER_PROFILE_DIR)
        logger.info("Running LIVE scrape with Playwright...")
        pages = run_live_scrape(
            Path(DATA_DIR) / "raw_html",
            search_terms=search_terms,
            pages_per_search=pages_per_search,
            user_data_dir=profile_dir,
        )
        raw_listings = parse_all_pages(pages)
    elif args.html or (Path(args.html_dir).exists() and list(Path(args.html_dir).glob("*.html"))):
        logger.info("Using HTML fallback from %s", args.html_dir)
        pages = load_html_fallback(Path(args.html_dir))
        if not pages:
            logger.error("No HTML files found in %s. Add .html files or run with --live.", args.html_dir)
            return 1
        raw_listings = parse_all_pages(pages)
    else:
        logger.error(
            "No data source. Either:\n"
            "  1. Run with --live to scrape with Playwright\n"
            "  2. Add HTML files to html_samples/ and run with --html\n"
            "  3. Run with --html after exporting pages from your browser"
        )
        return 1

    if not raw_listings:
        logger.warning("No listings extracted. Check parser selectors or HTML structure.")
        return 1

    logger.info("Raw listings: %d", len(raw_listings))

    cleaned = clean_and_normalize(raw_listings)
    cleaned = deduplicate(cleaned)
    grouped = build_grouped_report(cleaned)

    export_all(raw_listings, cleaned, grouped)

    logger.info("Done. Outputs in %s/", DATA_DIR)
    logger.info("  - %s (raw)", Path(DATA_DIR) / "aliexpress_watch_movements_raw.csv")
    logger.info("  - %s (clean)", Path(DATA_DIR) / "aliexpress_watch_movements_clean.csv")
    logger.info("  - %s (clean)", Path(DATA_DIR) / "aliexpress_watch_movements_clean.json")
    logger.info("  - %s (grouped)", Path(DATA_DIR) / "aliexpress_watch_movements_grouped.csv")
    return 0


if __name__ == "__main__":
    sys.exit(main())
