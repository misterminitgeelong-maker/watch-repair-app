"""Tenant branding (logo + brand colour) in transactional emails and PDFs."""
from app.email_templates import ShopInfo, render_transactional_email, _DEFAULT_ACCENT
from app.pdf_invoice import build_invoice_pdf, build_quote_pdf

_LINE_ITEMS = [
    {"description": "Service call", "quantity": 1, "unit_price_cents": 12000, "total_price_cents": 12000},
]


def test_email_uses_brand_color_and_logo():
    brand = "#1F6FEB"
    logo = "https://example.com/logo.png"
    html = render_transactional_email(
        title="Invoice INV-1",
        preheader="Your invoice",
        greeting="Hi Sam,",
        intro_html="Here is your invoice.",
        shop=ShopInfo(name="Acme Keys", logo_url=logo, brand_color=brand),
        cta_label="View invoice",
        cta_url="https://example.com/view",
        line_items=_LINE_ITEMS,
        total_cents=12000,
    )
    # Brand colour tints the CTA / accents.
    assert brand in html
    # Logo renders as an <img> with the URL and shop name as alt text.
    assert "<img" in html
    assert logo in html
    assert 'alt="Acme Keys"' in html


def test_email_falls_back_to_default_accent_without_brand():
    html = render_transactional_email(
        title="Invoice INV-2",
        preheader="Your invoice",
        greeting="Hi Sam,",
        intro_html="Here is your invoice.",
        shop=ShopInfo(name="Acme Keys"),
        cta_label="View invoice",
        cta_url="https://example.com/view",
        total_cents=5000,
    )
    assert _DEFAULT_ACCENT in html
    # No logo URL → no <img> in the header.
    assert "<img" not in html


def test_email_invalid_brand_color_ignored():
    html = render_transactional_email(
        title="Invoice INV-3",
        preheader="Your invoice",
        greeting="Hi Sam,",
        intro_html="Here is your invoice.",
        shop=ShopInfo(name="Acme Keys", brand_color="not-a-color"),
        cta_label="View invoice",
        cta_url="https://example.com/view",
        total_cents=5000,
    )
    assert _DEFAULT_ACCENT in html
    assert "not-a-color" not in html


def test_invoice_pdf_nonempty_without_logo():
    pdf = build_invoice_pdf(
        invoice_number="INV-100",
        job_number="J-100",
        customer_name="Sam",
        shop_name="Acme Keys",
        line_items=_LINE_ITEMS,
        subtotal_cents=12000,
        tax_cents=0,
        total_cents=12000,
        logo_url=None,
        brand_color="#1F6FEB",
    )
    assert isinstance(pdf, bytes) and len(pdf) > 100


def test_invoice_pdf_nonempty_with_unreachable_logo():
    # Unreachable/slow logo must never break PDF generation.
    pdf = build_invoice_pdf(
        invoice_number="INV-101",
        job_number="J-101",
        customer_name="Sam",
        shop_name="Acme Keys",
        line_items=_LINE_ITEMS,
        subtotal_cents=12000,
        tax_cents=0,
        total_cents=12000,
        logo_url="https://nonexistent.invalid.example/logo.png",
        brand_color="#1F6FEB",
    )
    assert isinstance(pdf, bytes) and len(pdf) > 100


def test_quote_pdf_nonempty_with_bad_logo_and_no_color():
    pdf = build_quote_pdf(
        job_number="J-200",
        customer_name="Sam",
        shop_name="Acme Keys",
        line_items=_LINE_ITEMS,
        subtotal_cents=12000,
        tax_cents=0,
        total_cents=12000,
        logo_url="ftp://bad-scheme/logo.png",
        brand_color=None,
    )
    assert isinstance(pdf, bytes) and len(pdf) > 100
