"""Per-page SEO for the public marketing routes.

The React app is a single index.html, so every URL would otherwise share one
title, description and set of share tags, and crawlers that do not run
JavaScript (link previews, some search bots) would never see the real ones.
The SPA fallback runs the built index.html through ``render_index`` so each
public page carries its own head tags, and marks everything else (the app,
customer links with tokens, invite pages) as noindex.
"""

from __future__ import annotations

import html
import json
import re

SITE = "https://mainspring.au"
SHARE_IMAGE = f"{SITE}/icon-512.png"

# path -> (title, description). Titles stay under ~60 characters, descriptions under ~160.
PUBLIC_PAGES: dict[str, tuple[str, str]] = {
    "": (
        "Mainspring — job tickets, quotes and invoices for repair trades",
        "Job tickets, quotes, invoices and customer texts for watch, shoe and mobile key repair "
        "businesses. Australian-owned, built in Geelong. 14-day trial.",
    ),
    "pricing": (
        "Mainspring pricing — from A$50 a month",
        "Mainspring for watch, shoe and mobile key repair businesses. Shop plan A$50 a month, Pro "
        "A$90 for multiple sites. 14-day trial; card required to start.",
    ),
    "mobile-services": (
        "Mobile locksmith and auto key software | Mainspring",
        "Quote, invoice and get paid on site. Job book, price list, arrival texts, key photos and "
        "lead inbox for mobile locksmiths and car key operators in Australia.",
    ),
}

# Public but not worth ranking: keep indexable so links resolve, but no custom tags.
INDEXABLE_PATHS = {"privacy"}

_TITLE_RE = re.compile(r"<title>.*?</title>", re.S)
_DESC_RE = re.compile(r'<meta name="description"[^>]*>')
_OG_RE = {
    "og:title": re.compile(r'<meta property="og:title"[^>]*>'),
    "og:description": re.compile(r'<meta property="og:description"[^>]*>'),
    "og:url": re.compile(r'<meta property="og:url"[^>]*>'),
}

_JSON_LD = {
    "@context": "https://schema.org",
    "@graph": [
        {
            "@type": "Organization",
            "@id": f"{SITE}/#org",
            "name": "Mainspring",
            "url": SITE,
            "logo": f"{SITE}/icon-512.png",
            "email": "admin@mainspring.au",
            "areaServed": "AU",
        },
        {
            "@type": "SoftwareApplication",
            "name": "Mainspring",
            "applicationCategory": "BusinessApplication",
            "operatingSystem": "Web, Android",
            "url": SITE,
            "publisher": {"@id": f"{SITE}/#org"},
            "offers": {
                "@type": "Offer",
                "price": "50.00",
                "priceCurrency": "AUD",
                "description": "Shop plan, per month, after a 14-day trial",
            },
        },
    ],
}


def normalise_path(full_path: str) -> str:
    return full_path.strip("/").lower()


def robots_header(full_path: str) -> str | None:
    """X-Robots-Tag value for a request path, or None when it may be indexed."""
    path = normalise_path(full_path)
    if path in PUBLIC_PAGES or path in INDEXABLE_PATHS:
        return None
    return "noindex, nofollow"


def render_index(index_html: str, full_path: str) -> str:
    """Return index.html with the head tags for ``full_path`` (unchanged if not a public page)."""
    path = normalise_path(full_path)
    page = PUBLIC_PAGES.get(path)
    if page is None:
        return index_html
    title, description = page
    url = f"{SITE}/{path}" if path else f"{SITE}/"
    t, d, u = html.escape(title, quote=True), html.escape(description, quote=True), html.escape(url, quote=True)

    out = _TITLE_RE.sub(lambda _m: f"<title>{t}</title>", index_html, count=1)
    out = _DESC_RE.sub(lambda _m: f'<meta name="description" content="{d}" />', out, count=1)
    out = _OG_RE["og:title"].sub(lambda _m: f'<meta property="og:title" content="{t}" />', out, count=1)
    out = _OG_RE["og:description"].sub(lambda _m: f'<meta property="og:description" content="{d}" />', out, count=1)
    out = _OG_RE["og:url"].sub(lambda _m: f'<meta property="og:url" content="{u}" />', out, count=1)

    extra = [f'<link rel="canonical" href="{u}" />']
    if not path:
        # JSON in a script tag: escape "</" so it cannot close the tag early.
        extra.append(
            '<script type="application/ld+json">'
            + json.dumps(_JSON_LD, separators=(",", ":")).replace("</", "<\\/")
            + "</script>"
        )
    return out.replace("</head>", "    " + "\n    ".join(extra) + "\n  </head>", 1)
