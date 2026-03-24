#!/usr/bin/env python3
"""
Labanda live scraper using Playwright.
Use when labanda.com.au is reachable to refresh movement data.
Save HTML to data/raw_html/ for offline parsing.
Supports --login to save session for authenticated scraping.
"""

import random
import time
from pathlib import Path

from playwright.sync_api import sync_playwright
from tenacity import retry, stop_after_attempt, wait_exponential

from config import (
    LABANDA_BASE,
    LABANDA_MOVEMENTS,
    LABANDA_LOGIN,
    CATEGORY_PATHS,
    PAGE_LOAD_TIMEOUT_MS,
    MIN_DELAY,
    MAX_DELAY,
    DATA_DIR,
    BROWSER_PROFILE_DIR,
)


def _delay():
    time.sleep(random.uniform(MIN_DELAY, MAX_DELAY))


@retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=2, max=15))
def fetch_page(url: str, page) -> str:
    page.goto(url, timeout=PAGE_LOAD_TIMEOUT_MS)
    _delay()
    return page.content()


def run_login_session(user_data_dir: Path) -> None:
    """
    Open a headed browser with persistent profile, navigate to Labanda login,
    and wait for you to log in. Session is saved for reuse when scraping.
    Press Enter in the terminal when done.
    """
    user_data_dir = Path(user_data_dir)
    user_data_dir.mkdir(parents=True, exist_ok=True)

    with sync_playwright() as p:
        context = p.chromium.launch_persistent_context(
            str(user_data_dir),
            headless=False,
            viewport={"width": 1920, "height": 1080},
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        )
        page = context.pages[0] if context.pages else context.new_page()
        page.goto(LABANDA_LOGIN, wait_until="domcontentloaded", timeout=60000)
        print("Browser opened. Log in to Labanda, then press Enter here to save session...")
        input()
        context.close()


def scrape_to_html(output_dir: Path, user_data_dir: Path | str | None = None) -> list[Path]:
    """Fetch Labanda movement pages (hub + all category subpages with pagination) and save HTML."""
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    saved = []
    use_persistent = user_data_dir is not None

    # Hub page + all category URLs
    urls_to_fetch = [(LABANDA_MOVEMENTS, "labanda_movements")]
    for path in CATEGORY_PATHS:
        slug = path.replace("/watch-movements/", "").replace("-", "_")
        urls_to_fetch.append((LABANDA_BASE + path, f"labanda_{slug}"))

    with sync_playwright() as p:
        if use_persistent:
            Path(user_data_dir).mkdir(parents=True, exist_ok=True)
            ctx = p.chromium.launch_persistent_context(
                str(user_data_dir),
                headless=True,
                viewport={"width": 1920, "height": 1080},
                user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
                args=["--disable-blink-features=AutomationControlled"],
            )
            print("Using logged-in session from", user_data_dir)
        else:
            browser = p.chromium.launch(headless=True)
            ctx = browser.new_context(
                user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
            )

        page = ctx.new_page()
        try:
            for base_url, base_name in urls_to_fetch:
                page_num = 0
                while True:
                    url = f"{base_url}?page={page_num}" if page_num > 0 else base_url
                    try:
                        html = fetch_page(url, page)
                        fname = f"{base_name}_p{page_num}.html" if page_num > 0 else f"{base_name}.html"
                        path = output_dir / fname
                        path.write_text(html, encoding="utf-8")
                        saved.append(path)
                        print(f"Saved {path.name}")
                    except Exception as e:
                        print(f"Error fetching {url}: {e}")
                        break
                    # Pagination: only for category pages (not hub). Drupal uses ?page=N
                    if base_name == "labanda_movements":
                        break
                    if page_num >= 19:  # max 20 pages per category
                        break
                    next_page = page_num + 1
                    if "views-row" in html and (f'page={next_page}' in html or 'pager-next' in html):
                        page_num = next_page
                    else:
                        break
        finally:
            ctx.close()
            if not use_persistent:
                browser.close()

    return saved


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="Scrape Labanda watch movements.")
    parser.add_argument("--login", action="store_true", help="Open browser to log in to Labanda. Session saved for scraping.")
    parser.add_argument("--user-data-dir", default=None, help="Browser profile dir for session")
    args = parser.parse_args()

    base = Path(__file__).parent
    default_profile = base / BROWSER_PROFILE_DIR

    if args.login:
        profile = Path(args.user_data_dir) if args.user_data_dir else default_profile
        run_login_session(profile)
        print(f"Session saved to {profile}. Run: python scraper.py")
    else:
        # Use profile if it exists (user ran --login) or --user-data-dir given
        profile = None
        if args.user_data_dir:
            profile = Path(args.user_data_dir)
        elif default_profile.exists():
            profile = default_profile
        out = Path(DATA_DIR) / "raw_html"
        paths = scrape_to_html(out, user_data_dir=profile)
        print(f"Saved {len(paths)} page(s) to {out}")
