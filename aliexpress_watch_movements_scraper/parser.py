"""
Parse AliExpress search result HTML into structured listing data.
Supports both DOM extraction and embedded JSON (window.__PRELOADED_STATE__).
"""

import json
import logging
import re
from typing import Any

from bs4 import BeautifulSoup

from config import ALIEXPRESS_BASE

logger = logging.getLogger(__name__)

# Raw listing schema (fields we extract)
RAW_FIELDS = [
    "source_site", "search_term", "listing_title", "listing_url",
    "seller_name", "seller_url", "price_text", "price_min", "price_max", "currency",
    "shipping_text", "orders_text", "rating_text", "store_rating_text",
    "image_url", "raw_brand", "raw_calibre", "raw_type", "description_snippet",
]


def _safe_text(el, default=""):
    if el is None:
        return default
    t = el.get_text(strip=True) if hasattr(el, "get_text") else str(el)
    return (t or default).strip()


def _full_url(url: str) -> str:
    if not url:
        return ""
    return url if url.startswith("http") else (ALIEXPRESS_BASE + url)


def _safe_attr(el, attr, default=""):
    if el is None:
        return default
    return el.get(attr, default) or default


def _extract_price_range(text: str) -> tuple[float | None, float | None]:
    """Parse price text like '$3.50 - $5.20' or 'US $12.00' into (min, max)."""
    if not text:
        return None, None
    numbers = re.findall(r"[\d]+\.?[\d]*", text.replace(",", "."))
    nums = [float(n) for n in numbers if n]
    if not nums:
        return None, None
    return min(nums), max(nums)


def _extract_json_array_brackets(text: str, start_pos: int) -> tuple[list[dict] | None, int]:
    """Extract a JSON array starting at start_pos using bracket counting. Returns (parsed_list, end_pos) or (None, -1)."""
    depth = 0
    in_string = False
    escape = False
    quote_char = None
    i = start_pos
    while i < len(text):
        c = text[i]
        if escape:
            escape = False
            i += 1
            continue
        if in_string:
            if c == quote_char:
                in_string = False
            elif c == "\\":
                escape = True
            i += 1
            continue
        if c in '"\'':
            in_string = True
            quote_char = c
            i += 1
            continue
        if c == "[":
            depth += 1
        elif c == "]":
            depth -= 1
            if depth == 0:
                try:
                    arr = json.loads(text[start_pos : i + 1])
                    return (arr, i + 1) if isinstance(arr, list) else (None, -1)
                except json.JSONDecodeError:
                    return None, -1
        elif c == "{":
            depth += 1
        elif c == "}":
            depth -= 1
        i += 1
    return None, -1


def _extract_dida_itemlist(html: str) -> list[dict]:
    """Extract products from window._dida_config_._init_data_ itemList.content (AliExpress 2023+ format)."""
    # Pattern: "itemList":{"content":[
    m = re.search(r'"itemList"\s*:\s*\{\s*"content"\s*:\s*\[', html)
    if not m:
        return []
    start = m.end() - 1  # Position of [
    arr, _ = _extract_json_array_brackets(html, start)
    if not arr or not isinstance(arr, list):
        return []
    # Filter to product-like items (have title and price)
    products = []
    for item in arr:
        if isinstance(item, dict) and item.get("itemType") in ("productV3", "product", None):
            if item.get("title") or item.get("productId"):
                products.append(item)
    return products


def _extract_embedded_items(html: str) -> list[dict]:
    """Extract product items from embedded JSON in page (AliExpress preloaded state)."""
    # 1. Try AliExpress 2023+ dida format (itemList.content) - most common in scraped pages
    items = _extract_dida_itemlist(html)
    if items:
        return items

    # 2. Legacy/other formats
    for script in re.finditer(r"<script[^>]*>(.*?)</script>", html, re.DOTALL | re.IGNORECASE):
        content = script.group(1)
        for pattern, extract_key in [
            (r'"products"\s*:\s*\[(.*?)\]\s*[,}]', "products"),
            (r'"itemList"\s*:\s*\{[^}]*"products"\s*:\s*\[(.*?)\]\s*', "products"),
            (r'\[(\s*\{[^{}]*"title"[^{}]*\}[^]]*)\]', "array"),
        ]:
            try:
                m = re.search(pattern, content, re.DOTALL)
                if m:
                    raw = "[" + m.group(1) + "]" if extract_key == "products" else m.group(0)
                    raw = re.sub(r',\s*}', '}', raw)
                    raw = re.sub(r',\s*]', ']', raw)
                    arr = json.loads(raw)
                    if isinstance(arr, list) and len(arr) > 0:
                        items.extend(arr)
                        if items:
                            return items
            except (json.JSONDecodeError, IndexError):
                continue
    return items


def _item_from_embedded(product: dict, search_term: str) -> dict:
    """Convert embedded product dict to raw listing format. Handles both legacy and dida (2023+) schema."""
    title = product.get("title", "") or ""
    if isinstance(title, dict):
        title = title.get("displayTitle") or title.get("text") or ""
    title = str(title)[:500]

    # Price: dida uses prices.salePrice.minPrice / originalPrice, legacy uses price.min
    price_min = price_max = None
    prices = product.get("prices", product.get("price", {})) or {}
    if isinstance(prices, dict):
        sale = prices.get("salePrice", prices.get("originalPrice", {})) or {}
        orig = prices.get("originalPrice", {}) or {}
        price_min = (
            sale.get("minPrice") or sale.get("minAmount", {}).get("value") if isinstance(sale, dict) else None
        ) or (
            prices.get("min") or prices.get("minAmount", {}).get("value") or prices.get("value")
        )
        price_max = (
            sale.get("maxPrice") or orig.get("minPrice") if isinstance(sale, dict) and isinstance(orig, dict) else None
        ) or prices.get("max") or price_min
    price_text = str(price_min) if price_min is not None else ""
    if price_max and price_max != price_min:
        price_text = f"{price_min} - {price_max}"

    # URL: dida has productId/redirectedId, legacy has productDetailUrl
    listing_url = product.get("productDetailUrl", "")
    if not listing_url:
        pid = product.get("productId") or product.get("redirectedId")
        if pid:
            listing_url = f"/item/{pid}.html"
    listing_url = _full_url(listing_url)

    # Trade/orders: dida has trade.tradeDesc
    trade = product.get("trade", product.get("orders", ""))
    orders_text = trade.get("tradeDesc", trade) if isinstance(trade, dict) else str(trade)

    # Rating: dida has evaluation.starRating
    rating = product.get("evaluation", product.get("rating", {})) or {}
    rating_text = str(rating.get("starRating", rating.get("average", "")) if isinstance(rating, dict) else rating)

    # Currency: dida has prices.salePrice.currencyCode
    currency = "USD"
    if isinstance(prices, dict):
        for p in (prices.get("salePrice"), prices.get("originalPrice")):
            if isinstance(p, dict) and p.get("currencyCode"):
                currency = p.get("currencyCode", "USD")
                break

    # Image
    image = product.get("image", {}) or {}
    img_url = product.get("imageUrl") or (image.get("imgUrl") if isinstance(image, dict) else "")

    return {
        "source_site": "aliexpress.com",
        "search_term": search_term,
        "listing_title": title,
        "listing_url": listing_url,
        "seller_name": product.get("storeInfo", {}).get("storeName") or product.get("shopName") or "",
        "seller_url": "",
        "price_text": price_text,
        "price_min": float(price_min) if price_min is not None else None,
        "price_max": float(price_max) if price_max is not None else None,
        "currency": currency,
        "shipping_text": product.get("shipping") or "",
        "orders_text": orders_text,
        "rating_text": rating_text,
        "store_rating_text": "",
        "image_url": img_url,
        "raw_brand": "",
        "raw_calibre": "",
        "raw_type": "",
        "description_snippet": title[:200],
    }


def _extract_from_dom(soup: BeautifulSoup, search_term: str) -> list[dict]:
    """Extract listings from DOM product cards."""
    listings = []
    # Various selectors used by AliExpress over time
    card_selectors = [
        "div[class*='product-card']",
        "div[class*='list--gallery'] > div",
        "div[class*='search-card-item']",
        "a[class*='product']",
        "div[data-product-id]",
        "li[class*='list--item']",
        "div.card-item",
        "div[class*='ProductCard']",
    ]
    cards = []
    for sel in card_selectors:
        cards = soup.select(sel)
        if len(cards) >= 3:  # Expect multiple products
            break
    if not cards:
        cards = soup.find_all("a", href=re.compile(r"/item/\d+\.html"))
    for card in cards[:60]:  # Limit per page
        try:
            link = card.find("a", href=re.compile(r"/item/|/product/")) or card
            href = _safe_attr(link, "href", "")
            if href and not href.startswith("http"):
                href = ALIEXPRESS_BASE + href
            title_el = card.select_one("[class*='title'], [class*='Title'], h3, .product-title, a") or card
            title = _safe_text(title_el)[:500]
            if not title and link != card:
                title = _safe_text(link)[:500]
            price_el = card.select_one("[class*='price'], [class*='Price'], .price-current")
            price_text = _safe_text(price_el)
            pmin, pmax = _extract_price_range(price_text)
            img = card.select_one("img")
            img_url = _safe_attr(img, "src", "") or _safe_attr(img, "data-src", "")
            seller_el = card.select_one("[class*='store'], [class*='seller'], [class*='shop']")
            seller = _safe_text(seller_el)
            orders_el = card.select_one("[class*='order'], [class*='sold']")
            orders = _safe_text(orders_el)
            if title or href:
                listings.append({
                    "source_site": "aliexpress.com",
                    "search_term": search_term,
                    "listing_title": title,
                    "listing_url": href,
                    "seller_name": seller,
                    "seller_url": "",
                    "price_text": price_text,
                    "price_min": pmin,
                    "price_max": pmax,
                    "currency": "USD",
                    "shipping_text": "",
                    "orders_text": orders,
                    "rating_text": "",
                    "store_rating_text": "",
                    "image_url": img_url,
                    "raw_brand": "",
                    "raw_calibre": "",
                    "raw_type": "",
                    "description_snippet": title[:200] if title else "",
                })
        except Exception as e:
            logger.debug("Skip card: %s", e)
    return listings


def parse_search_page(html: str, search_term: str) -> list[dict]:
    """
    Parse a single search result page HTML.
    Returns list of raw listing dicts.
    """
    soup = BeautifulSoup(html, "lxml")
    listings = _extract_embedded_items(html)
    if listings:
        return [_item_from_embedded(p, search_term) for p in listings]
    return _extract_from_dom(soup, search_term)


def parse_all_pages(pages: list[tuple[str, str, str]]) -> list[dict]:
    """Parse all page HTMLs into a flat list of raw listings."""
    all_listings = []
    seen_urls = set()
    for search_term, page_num, html in pages:
        items = parse_search_page(html, search_term)
        for item in items:
            url = item.get("listing_url", "")
            if url and url in seen_urls:
                continue
            if url:
                seen_urls.add(url)
            all_listings.append(item)
        logger.info("Parsed '%s' p%s: %d items (total %d)", search_term, page_num, len(items), len(all_listings))
    return all_listings
