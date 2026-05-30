"""
PDF invoice generator using reportlab (pure Python, no system dependencies).

Produces a byte string suitable for attaching to a SendGrid email.
"""
from __future__ import annotations

import io
import logging
import re
from datetime import date
from typing import Sequence

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import mm
from reportlab.platypus import (
    Image,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)

logger = logging.getLogger(__name__)

_DARK = colors.HexColor("#1a1a2e")
_ACCENT = colors.HexColor("#4f46e5")
_LIGHT_GREY = colors.HexColor("#f3f4f6")
_MID_GREY = colors.HexColor("#9ca3af")

# Lenient hex colour: #RGB, #RRGGBB or #RRGGBBAA (alpha ignored by reportlab).
_HEX_COLOR_RE = re.compile(r"^#(?:[0-9a-fA-F]{3}|[0-9a-fA-F]{6}|[0-9a-fA-F]{8})$")
# Cap logo height in the header to keep the layout tidy.
_LOGO_MAX_H = 16 * mm
_LOGO_MAX_W = 60 * mm


def _currency_symbol(currency: str) -> str:
    return "$" if (currency or "AUD").upper() in ("AUD", "USD", "NZD", "CAD") else f"{currency} "


def _resolve_accent(brand_color: str | None) -> colors.Color:
    cleaned = (brand_color or "").strip()
    if cleaned and _HEX_COLOR_RE.match(cleaned):
        try:
            return colors.HexColor(cleaned[:7])
        except Exception:
            return _ACCENT
    return _ACCENT


def _fetch_logo(logo_url: str | None) -> Image | None:
    """Fetch an http(s) logo into a reportlab Image; never raise on failure."""
    url = (logo_url or "").strip()
    if not (url.startswith("http://") or url.startswith("https://")):
        return None
    try:
        import httpx

        with httpx.Client(timeout=4.0, follow_redirects=True) as client:
            resp = client.get(url)
        if resp.status_code != 200 or not resp.content:
            return None
        img = Image(io.BytesIO(resp.content))
        iw, ih = img.imageWidth, img.imageHeight
        if not iw or not ih:
            return None
        scale = min(_LOGO_MAX_H / ih, _LOGO_MAX_W / iw, 1.0)
        img.drawHeight = ih * scale
        img.drawWidth = iw * scale
        img.hAlign = "LEFT"
        return img
    except Exception:
        logger.warning("Logo fetch/render failed for %s; using text header", url, exc_info=True)
        return None


def build_invoice_pdf(
    *,
    invoice_number: str,
    job_number: str,
    invoice_date: date | None = None,
    customer_name: str,
    shop_name: str,
    shop_abn: str | None = None,
    shop_address: str | None = None,
    shop_phone: str | None = None,
    shop_email: str | None = None,
    payment_instructions: str | None = None,
    logo_url: str | None = None,
    brand_color: str | None = None,
    line_items: Sequence[dict],
    subtotal_cents: int = 0,
    tax_cents: int = 0,
    total_cents: int,
    currency: str = "AUD",
) -> bytes:
    """Return PDF bytes for an invoice."""
    return _build_document_pdf(
        doc_type="INVOICE",
        number_label="Invoice #",
        document_number=invoice_number,
        job_number=job_number,
        doc_date=invoice_date or date.today(),
        customer_name=customer_name,
        shop_name=shop_name,
        shop_abn=shop_abn,
        shop_address=shop_address,
        shop_phone=shop_phone,
        shop_email=shop_email,
        logo_url=logo_url,
        brand_color=brand_color,
        footer_label="PAYMENT DETAILS",
        footer_text=payment_instructions,
        line_items=line_items,
        subtotal_cents=subtotal_cents,
        tax_cents=tax_cents,
        total_cents=total_cents,
        currency=currency,
    )


def build_quote_pdf(
    *,
    job_number: str,
    customer_name: str,
    shop_name: str,
    quote_date: date | None = None,
    quote_number: str | None = None,
    shop_abn: str | None = None,
    shop_address: str | None = None,
    shop_phone: str | None = None,
    shop_email: str | None = None,
    logo_url: str | None = None,
    brand_color: str | None = None,
    line_items: Sequence[dict],
    subtotal_cents: int = 0,
    tax_cents: int = 0,
    total_cents: int,
    currency: str = "AUD",
    note: str | None = None,
) -> bytes:
    """Return PDF bytes for a quote."""
    return _build_document_pdf(
        doc_type="QUOTE",
        number_label="Quote #",
        document_number=quote_number or job_number,
        job_number=job_number,
        doc_date=quote_date or date.today(),
        customer_name=customer_name,
        shop_name=shop_name,
        shop_abn=shop_abn,
        shop_address=shop_address,
        shop_phone=shop_phone,
        shop_email=shop_email,
        logo_url=logo_url,
        brand_color=brand_color,
        footer_label="NOTES",
        footer_text=note or "This quote is an estimate based on the information provided. Final price may vary if additional work is required.",
        line_items=line_items,
        subtotal_cents=subtotal_cents,
        tax_cents=tax_cents,
        total_cents=total_cents,
        currency=currency,
    )


def _build_document_pdf(
    *,
    doc_type: str,
    number_label: str,
    document_number: str,
    job_number: str,
    doc_date: date,
    customer_name: str,
    shop_name: str,
    shop_abn: str | None,
    shop_address: str | None,
    shop_phone: str | None,
    shop_email: str | None,
    footer_label: str | None,
    footer_text: str | None,
    line_items: Sequence[dict],
    subtotal_cents: int,
    tax_cents: int,
    total_cents: int,
    currency: str,
    logo_url: str | None = None,
    brand_color: str | None = None,
) -> bytes:
    """Shared invoice/quote PDF renderer."""
    buf = io.BytesIO()
    sym = _currency_symbol(currency)
    accent = _resolve_accent(brand_color)

    doc = SimpleDocTemplate(
        buf,
        pagesize=A4,
        leftMargin=20 * mm,
        rightMargin=20 * mm,
        topMargin=20 * mm,
        bottomMargin=20 * mm,
        title=f"{doc_type.title()} {document_number}",
    )

    styles = getSampleStyleSheet()
    normal = styles["Normal"]
    normal.fontName = "Helvetica"
    normal.fontSize = 9
    normal.leading = 13

    heading = ParagraphStyle(
        "heading",
        parent=normal,
        fontSize=20,
        fontName="Helvetica-Bold",
        textColor=_DARK,
        spaceAfter=2 * mm,
    )
    sub = ParagraphStyle(
        "sub",
        parent=normal,
        fontSize=9,
        textColor=_MID_GREY,
        spaceAfter=1 * mm,
    )
    label = ParagraphStyle(
        "label",
        parent=normal,
        fontSize=8,
        fontName="Helvetica-Bold",
        textColor=_MID_GREY,
        spaceAfter=1 * mm,
    )
    bold9 = ParagraphStyle(
        "bold9",
        parent=normal,
        fontSize=9,
        fontName="Helvetica-Bold",
        textColor=_DARK,
    )

    page_width = A4[0] - 40 * mm  # usable width
    col_right = 70 * mm
    col_left = page_width - col_right

    story = []

    # ── Header row: logo or shop name (left) / INVOICE label (right) ──
    logo_flowable = _fetch_logo(logo_url)
    left_header = logo_flowable if logo_flowable is not None else Paragraph(shop_name, heading)
    header_data = [
        [
            left_header,
            Paragraph(doc_type, heading),
        ]
    ]
    header_tbl = Table(header_data, colWidths=[col_left, col_right])
    header_tbl.setStyle(TableStyle([
        ("ALIGN", (1, 0), (1, 0), "RIGHT"),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
    ]))
    story.append(header_tbl)
    story.append(Spacer(1, 3 * mm))

    # ── Shop identity (left) / Invoice meta (right) ──
    shop_lines = []
    if logo_flowable is not None and shop_name:
        # The logo replaced the name heading; keep the name in the identity block.
        shop_lines.append(f"<b>{shop_name}</b>")
    if shop_abn:
        shop_lines.append(f"ABN {shop_abn}")
    if shop_address:
        shop_lines.append(shop_address.replace("\n", "<br/>"))
    if shop_phone:
        shop_lines.append(shop_phone)
    if shop_email:
        shop_lines.append(shop_email)

    shop_para = Paragraph("<br/>".join(shop_lines), normal) if shop_lines else Spacer(1, 1)

    meta_lines = [
        f"<b>{number_label}</b> {document_number}",
        f"<b>Job #</b> {job_number}",
        f"<b>Date</b> {doc_date.strftime('%d %b %Y')}",
    ]
    meta_para = Paragraph("<br/>".join(meta_lines), normal)

    identity_data = [[shop_para, meta_para]]
    identity_tbl = Table(identity_data, colWidths=[col_left, col_right])
    identity_tbl.setStyle(TableStyle([
        ("ALIGN", (1, 0), (1, 0), "RIGHT"),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
    ]))
    story.append(identity_tbl)
    story.append(Spacer(1, 6 * mm))

    # ── Bill To ──
    story.append(Paragraph("BILL TO", label))
    story.append(Paragraph(customer_name, bold9))
    story.append(Spacer(1, 5 * mm))

    # ── Line items table ──
    col_desc = page_width - 30 * mm - 25 * mm - 25 * mm
    items_header = [
        Paragraph("Description", label),
        Paragraph("Qty", label),
        Paragraph("Unit Price", label),
        Paragraph("Amount", label),
    ]
    items_rows = [items_header]

    for li in line_items:
        desc = (li.get("description") or "Item").strip()
        qty = li.get("quantity", 1)
        unit_cents = int(li.get("unit_price_cents") or li.get("total_price_cents", 0) or 0)
        total_li_cents = int(li.get("total_price_cents") or 0)
        items_rows.append([
            Paragraph(desc, normal),
            Paragraph(str(qty), normal),
            Paragraph(f"{sym}{unit_cents / 100:.2f}", normal),
            Paragraph(f"{sym}{total_li_cents / 100:.2f}", normal),
        ])

    items_tbl = Table(
        items_rows,
        colWidths=[col_desc, 30 * mm, 25 * mm, 25 * mm],
    )
    items_tbl.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), _LIGHT_GREY),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, _LIGHT_GREY]),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTSIZE", (0, 0), (-1, -1), 9),
        ("ALIGN", (1, 0), (-1, -1), "RIGHT"),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("TOPPADDING", (0, 0), (-1, -1), 3),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
        ("LEFTPADDING", (0, 0), (-1, -1), 4),
        ("RIGHTPADDING", (0, 0), (-1, -1), 4),
        ("LINEBELOW", (0, 0), (-1, 0), 0.5, accent),
    ]))
    story.append(items_tbl)
    story.append(Spacer(1, 4 * mm))

    # ── Totals ──
    totals_col = 45 * mm
    totals_data = []
    if subtotal_cents and tax_cents:
        totals_data.append([
            Paragraph("Subtotal", normal),
            Paragraph(f"{sym}{subtotal_cents / 100:.2f}", normal),
        ])
        totals_data.append([
            Paragraph("Tax", normal),
            Paragraph(f"{sym}{tax_cents / 100:.2f}", normal),
        ])
    totals_data.append([
        Paragraph("<b>Total</b>", bold9),
        Paragraph(f"<b>{sym}{total_cents / 100:.2f}</b>", bold9),
    ])

    totals_tbl = Table(
        totals_data,
        colWidths=[page_width - totals_col, totals_col],
    )
    totals_tbl.setStyle(TableStyle([
        ("ALIGN", (1, 0), (1, -1), "RIGHT"),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("LINEABOVE", (0, -1), (-1, -1), 0.5, accent),
        ("TOPPADDING", (0, -1), (-1, -1), 4),
        ("FONTSIZE", (0, 0), (-1, -1), 9),
    ]))
    story.append(totals_tbl)

    # ── Footer note (payment details for invoices, terms for quotes) ──
    if footer_text and footer_text.strip():
        story.append(Spacer(1, 8 * mm))
        story.append(Paragraph(footer_label or "NOTES", label))
        story.append(Paragraph(footer_text.strip().replace("\n", "<br/>"), normal))

    doc.build(story)
    return buf.getvalue()
