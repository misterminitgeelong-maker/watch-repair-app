from app import seo

INDEX = """<!doctype html><html><head>
<meta name="description" content="old" />
<meta property="og:title" content="Mainspring" />
<meta property="og:description" content="old" />
<meta property="og:url" content="https://mainspring.au/" />
<title>Mainspring</title>
</head><body><div id="root"></div></body></html>"""


def test_public_page_gets_its_own_head_tags():
    out = seo.render_index(INDEX, "mobile-services")
    assert "<title>Mobile locksmith and auto key software" in out
    assert '<link rel="canonical" href="https://mainspring.au/mobile-services" />' in out
    assert 'property="og:url" content="https://mainspring.au/mobile-services"' in out
    assert "old" not in out
    assert "application/ld+json" not in out


def test_home_page_has_structured_data_and_trailing_slash_is_ignored():
    out = seo.render_index(INDEX, "/")
    assert out.count("application/ld+json") == 1
    assert '"priceCurrency":"AUD"' in out
    assert seo.render_index(INDEX, "pricing/") == seo.render_index(INDEX, "Pricing")


def test_unknown_paths_are_untouched_and_noindex():
    assert seo.render_index(INDEX, "dashboard") == INDEX
    assert seo.robots_header("approve/abc123") == "noindex, nofollow"
    assert seo.robots_header("dashboard") == "noindex, nofollow"


def test_public_pages_are_indexable():
    for path in ("", "pricing", "mobile-services", "privacy"):
        assert seo.robots_header(path) is None


def test_titles_and_descriptions_fit_search_results():
    for title, description in seo.PUBLIC_PAGES.values():
        assert len(title) <= 65
        assert len(description) <= 165
