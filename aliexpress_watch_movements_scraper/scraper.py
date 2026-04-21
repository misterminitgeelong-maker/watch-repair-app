"""
Playwright-based scraper for AliExpress search results.
Uses retries, rate limiting, and random delays.
"""

import logging
import random
import time
from pathlib import Path
from urllib.parse import quote_plus

from playwright.sync_api import (
    Error as PlaywrightError,
    TimeoutError as PlaywrightTimeout,
    sync_playwright,
)
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type

from config import (
    ALIEXPRESS_LOGIN_URL,
    ALIEXPRESS_SEARCH_URL,
    MIN_DELAY_BETWEEN_REQUESTS,
    MAX_DELAY_BETWEEN_REQUESTS,
    PAGE_LOAD_TIMEOUT_MS,
    MAX_RETRIES,
    PAGES_PER_SEARCH,
    SEARCH_TERMS,
    HTML_SAMPLES_DIR,
    BROWSER_PROFILE_DIR,
)

logger = logging.getLogger(__name__)


def _random_delay():
    """Apply rate limiting with random delay."""
    delay = random.uniform(MIN_DELAY_BETWEEN_REQUESTS, MAX_DELAY_BETWEEN_REQUESTS)
    logger.debug("Sleeping %.1fs", delay)
    time.sleep(delay)


# Narrow retry set: only retry on clearly-transient network/browser issues.
# Previously included `Exception` catch-all which would also retry programming
# bugs (AttributeError, TypeError, KeyError, etc.) — that hid the real error
# behind MAX_RETRIES * exponential backoff of dead time.
@retry(
    stop=stop_after_attempt(MAX_RETRIES),
    wait=wait_exponential(multiplier=2, min=4, max=60),
    retry=retry_if_exception_type((
        PlaywrightTimeout,
        PlaywrightError,
        ConnectionError,
        TimeoutError,
        OSError,
    )),
    reraise=True,
)
def _fetch_page_with_retry(page, url: str) -> str:
    """Fetch page HTML with retries."""
    logger.info("Fetching: %s", url[:80] + "..." if len(url) > 80 else url)
    page.goto(url, wait_until="domcontentloaded", timeout=PAGE_LOAD_TIMEOUT_MS)
    _random_delay()
    return page.content()


def scrape_search_results(search_term: str, page, max_pages: int = PAGES_PER_SEARCH) -> list[str]:
    """
    Scrape HTML for a search term across multiple pages.
    Returns list of raw HTML strings (one per page).
    """
    results = []
    query = quote_plus(search_term)
    base_url = ALIEXPRESS_SEARCH_URL.format(query=query)

    for page_num in range(1, max_pages + 1):
        if page_num == 1:
            url = base_url
        else:
            url = f"{base_url}&page={page_num}"
        try:
            html = _fetch_page_with_retry(page, url)
            results.append(html)
        except Exception as e:
            logger.warning("Failed to fetch page %d for '%s': %s", page_num, search_term, e)
            break
    return results


def run_login_session(user_data_dir: Path) -> None:
    """
    Open a headed browser with persistent profile, navigate to AliExpress,
    and wait for you to log in. Session is saved to user_data_dir for reuse.
    Close the browser or press Enter in the terminal when done.
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
        page.goto(ALIEXPRESS_LOGIN_URL, wait_until="domcontentloaded", timeout=60000)
        logger.info("Browser opened. Log in to AliExpress, then press Enter here to save session...")
        input()
        context.close()


def run_live_scrape(
    output_dir: Path,
    search_terms: list[str] | None = None,
    pages_per_search: int | None = None,
    user_data_dir: Path | str | None = None,
) -> list[tuple[str, str, str]]:
    """
    Run live scraping with Playwright.
    If user_data_dir is set, uses a persistent browser profile (logged-in session).
    Returns list of (search_term, page_num, html) tuples.
    """
    search_terms = search_terms or SEARCH_TERMS
    max_pages = pages_per_search if pages_per_search is not None else PAGES_PER_SEARCH
    Path(output_dir).mkdir(parents=True, exist_ok=True)
    all_pages: list[tuple[str, str, str]] = []

    use_persistent = user_data_dir is not None
    if use_persistent:
        Path(user_data_dir).mkdir(parents=True, exist_ok=True)

    with sync_playwright() as p:
        if use_persistent:
            context = p.chromium.launch_persistent_context(
                str(user_data_dir),
                headless=True,
                viewport={"width": 1920, "height": 1080},
                user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
                args=["--disable-blink-features=AutomationControlled"],
            )
            page = context.pages[0] if context.pages else context.new_page()
            logger.info("Using persistent profile from %s (logged-in session)", user_data_dir)
        else:
            browser = p.chromium.launch(headless=True)
            context = browser.new_context(
                viewport={"width": 1920, "height": 1080},
                user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            )
            page = context.new_page()

        for term in search_terms:
            pages_html = scrape_search_results(term, page, max_pages=max_pages)
            for i, html in enumerate(pages_html):
                all_pages.append((term, str(i + 1), html))
                # Optionally save raw HTML for debugging
                safe_name = term.replace(" ", "_")[:50]
                out_path = output_dir / f"search_{safe_name}_p{i + 1}.html"
                out_path.write_text(html, encoding="utf-8")
                logger.info("Saved %s (page %d)", out_path.name, i + 1)

        context.close()
        if not use_persistent:
            browser.close()

    return all_pages


def load_html_fallback(html_dir: Path) -> list[tuple[str, str, str]]:
    """
    Fallback: load HTML from local files.
    Expects files named like: search_watch_movement_p1.html or *.html
    Returns list of (search_term, page_num, html).
    """
    html_dir = Path(html_dir)
    if not html_dir.exists():
        logger.warning("HTML fallback dir not found: %s", html_dir)
        return []

    results = []
    for path in sorted(html_dir.glob("*.html")):
        # Try to parse search term from filename: search_<term>_p<n>.html
        name = path.stem
        if name.startswith("search_") and "_p" in name:
            parts = name.replace("search_", "").rsplit("_p", 1)
            term = parts[0].replace("_", " ")
            page_num = parts[1] if len(parts) > 1 else "1"
        else:
            term = "unknown"
            page_num = "1"
        html = path.read_text(encoding="utf-8")
        results.append((term, page_num, html))
        logger.info("Loaded fallback: %s", path.name)
    return results
