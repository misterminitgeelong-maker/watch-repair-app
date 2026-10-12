"""
PDF invoice generator using reportlab (pure Python, no system dependencies).

Produces a byte string suitable for attaching to a SendGrid email.
"""
from __future__ import annotations

import io
import logging
import re
from xml.sax.saxutils import escape as xml_escape
from datetime import date
from typing import Sequence

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.enums import TA_RIGHT
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import mm
from reportlab.platypus import (
    Image,
    KeepTogether,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)

from .money import format_cents

logger = logging.getLogger(__name__)

_DARK = colors.HexColor("#111827")
_BODY = colors.HexColor("#374151")
_RULE = colors.HexColor("#e5e7eb")
_ACCENT = colors.HexColor("#4f46e5")
_LIGHT_GREY = colors.HexColor("#f6f7f9")
_MID_GREY = colors.HexColor("#6b7280")

# Lenient hex colour: #RGB, #RRGGBB or #RRGGBBAA (alpha ignored by reportlab).
_HEX_COLOR_RE = re.compile(r"^#(?:[0-9a-fA-F]{3}|[0-9a-fA-F]{6}|[0-9a-fA-F]{8})$")
# Cap logo height in the header to keep the layout tidy.
_LOGO_MAX_H = 16 * mm
_LOGO_MAX_W = 60 * mm



def _escape(text: str | None) -> str:
    return xml_escape(text or "")


def _luminance(c: colors.Color) -> float:
    return 0.299 * c.red + 0.587 * c.green + 0.114 * c.blue


def _resolve_accent(brand_color: str | None) -> colors.Color:
    cleaned = (brand_color or "").strip()
    if cleaned and _HEX_COLOR_RE.match(cleaned):
        try:
            return colors.HexColor(cleaned[:7])
        except Exception:
            return _ACCENT
    return _ACCENT


def _sized_logo(data: bytes) -> Image | None:
    img = Image(io.BytesIO(data))
    iw, ih = img.imageWidth, img.imageHeight
    if not iw or not ih:
        return None
    scale = min(_LOGO_MAX_H / ih, _LOGO_MAX_W / iw, 1.0)
    img.drawHeight = ih * scale
    img.drawWidth = iw * scale
    img.hAlign = "LEFT"
    return img


def _load_logo_file(path: str) -> Image | None:
    """Load a logo bundled with the app (e.g. Mister Minit's); never raise."""
    try:
        with open(path, "rb") as fh:
            return _sized_logo(fh.read())
    except Exception:
        logger.warning("Bundled logo %s could not be rendered; using text header", path, exc_info=True)
        return None


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
        return _sized_logo(resp.content)
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
    logo_path: str | None = None,
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
        logo_path=logo_path,
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
    logo_path: str | None = None,
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
        logo_path=logo_path,
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
    logo_path: str | None = None,
    brand_color: str | None = None,
) -> bytes:
    """Shared invoice/quote PDF renderer."""
    buf = io.BytesIO()
    accent = _resolve_accent(brand_color)
    on_accent = colors.white if _luminance(accent) < 0.6 else _DARK
    esc = _escape
    is_nz = (currency or "").upper() == "NZD"

    doc = SimpleDocTemplate(
        buf,
        pagesize=A4,
        leftMargin=20 * mm,
        rightMargin=20 * mm,
        topMargin=24 * mm,
        bottomMargin=22 * mm,
        title=f"{doc_type.title()} {document_number}",
        author=shop_name,
    )

    base = ParagraphStyle("base", fontName="Helvetica", fontSize=9, leading=13, textColor=_BODY)
    title_style = ParagraphStyle(
        "title", parent=base, fontName="Helvetica-Bold", fontSize=26, leading=28,
        textColor=accent if _luminance(accent) < 0.75 else _DARK, alignment=TA_RIGHT,
    )
    shop_title = ParagraphStyle("shop", parent=base, fontName="Helvetica-Bold", fontSize=17, leading=20, textColor=_DARK)
    label = ParagraphStyle(
        "label", parent=base, fontName="Helvetica-Bold", fontSize=7.5, leading=10,
        textColor=_MID_GREY, spaceAfter=1.5 * mm,
    )
    name_style = ParagraphStyle("name", parent=base, fontName="Helvetica-Bold", fontSize=11, leading=14, textColor=_DARK)
    small = ParagraphStyle("small", parent=base, fontSize=8.5, leading=12, textColor=_MID_GREY)
    right = ParagraphStyle("right", parent=base, alignment=TA_RIGHT)
    right_bold = ParagraphStyle("rightb", parent=right, fontName="Helvetica-Bold", textColor=_DARK)
    th = ParagraphStyle("th", parent=base, fontName="Helvetica-Bold", fontSize=8, textColor=on_accent)
    th_right = ParagraphStyle("thr", parent=th, alignment=TA_RIGHT)

    page_width = A4[0] - 40 * mm
    story: list = []

    # ── Header: logo / shop name (left), document type (right) ──
    logo_flowable = _load_logo_file(logo_path) if logo_path else _fetch_logo(logo_url)
    left_header = logo_flowable if logo_flowable is not None else Paragraph(esc(shop_name), shop_title)
    header_tbl = Table(
        [[left_header, Paragraph(esc(doc_type), title_style)]],
        colWidths=[page_width * 0.55, page_width * 0.45],
    )
    header_tbl.setStyle(TableStyle([
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("LEFTPADDING", (0, 0), (-1, -1), 0),
        ("RIGHTPADDING", (0, 0), (-1, -1), 0),
    ]))
    story.append(header_tbl)
    story.append(Spacer(1, 4 * mm))
    rule = Table([[""]], colWidths=[page_width], rowHeights=[1])
    rule.setStyle(TableStyle([("LINEABOVE", (0, 0), (-1, 0), 1.2, accent)]))
    story.append(rule)
    story.append(Spacer(1, 6 * mm))

    # ── From / Bill to / Document details ──
    from_lines = []
    if logo_flowable is not None and shop_name:
        from_lines.append(f"<b>{esc(shop_name)}</b>")
    if shop_abn:
        from_lines.append(f"{'GST No.' if is_nz else 'ABN'} {esc(shop_abn)}")
    if shop_address:
        from_lines.append(esc(shop_address).replace("\n", "<br/>"))
    if shop_phone:
        from_lines.append(esc(shop_phone))
    if shop_email:
        from_lines.append(esc(shop_email))

    from_cell: list = [Paragraph("FROM", label)]
    from_cell.append(Paragraph("<br/>".join(from_lines), base) if from_lines else Paragraph(esc(shop_name), base))
    bill_cell = [Paragraph("BILL TO", label), Paragraph(esc(customer_name), name_style)]

    meta_rows = [
        [Paragraph(esc(number_label.replace(" #", "").upper()), label), Paragraph(esc(document_number), right_bold)],
        [Paragraph("JOB", label), Paragraph(esc(job_number), right_bold)],
        [Paragraph("DATE", label), Paragraph(doc_date.strftime("%d %b %Y"), right_bold)],
    ]
    meta_tbl = Table(meta_rows, colWidths=[22 * mm, page_width * 0.28 - 22 * mm - 8 * mm])
    meta_tbl.setStyle(TableStyle([
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("TOPPADDING", (0, 0), (-1, -1), 1),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 1),
        ("LEFTPADDING", (0, 0), (-1, -1), 0),
        ("RIGHTPADDING", (0, 0), (-1, -1), 0),
    ]))
    meta_box = Table([[meta_tbl]], colWidths=[page_width * 0.28])
    meta_box.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), _LIGHT_GREY),
        ("LEFTPADDING", (0, 0), (-1, -1), 4 * mm),
        ("RIGHTPADDING", (0, 0), (-1, -1), 4 * mm),
        ("TOPPADDING", (0, 0), (-1, -1), 3 * mm),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 3 * mm),
        ("LINEBEFORE", (0, 0), (0, -1), 2, accent),
    ]))
    info_tbl = Table(
        [[from_cell, bill_cell, meta_box]],
        colWidths=[page_width * 0.36, page_width * 0.32, page_width * 0.32],
    )
    info_tbl.setStyle(TableStyle([
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("LEFTPADDING", (0, 0), (-1, -1), 0),
        ("RIGHTPADDING", (0, 0), (1, 0), 6 * mm),
        ("RIGHTPADDING", (2, 0), (2, 0), 0),
        ("ALIGN", (2, 0), (2, 0), "RIGHT"),
    ]))
    story.append(info_tbl)
    story.append(Spacer(1, 9 * mm))

    # ── Line items ──
    w_qty, w_unit, w_amt = 16 * mm, 28 * mm, 30 * mm
    w_desc = page_width - w_qty - w_unit - w_amt
    rows = [[
        Paragraph("DESCRIPTION", th),
        Paragraph("QTY", th_right),
        Paragraph("UNIT PRICE", th_right),
        Paragraph("AMOUNT", th_right),
    ]]
    for li in line_items:
        desc = esc((li.get("description") or "Item").strip())
        qty = li.get("quantity", 1)
        unit_cents = int(li.get("unit_price_cents") or li.get("total_price_cents", 0) or 0)
        total_li_cents = int(li.get("total_price_cents") or 0)
        rows.append([
            Paragraph(desc, base),
            Paragraph(esc(str(qty)), right),
            Paragraph(format_cents(unit_cents, currency), right),
            Paragraph(format_cents(total_li_cents, currency), right_bold),
        ])
    items_tbl = Table(rows, colWidths=[w_desc, w_qty, w_unit, w_amt], repeatRows=1)
    items_tbl.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), accent),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("TOPPADDING", (0, 0), (-1, -1), 5),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
        ("LEFTPADDING", (0, 0), (-1, -1), 6),
        ("RIGHTPADDING", (0, 0), (-1, -1), 6),
        ("LINEBELOW", (0, 1), (-1, -1), 0.4, _RULE),
    ]))
    story.append(items_tbl)
    story.append(Spacer(1, 4 * mm))

    # ── Totals (right-aligned block) ──
    tax_label = "GST" if (is_nz or tax_cents) else "Tax"
    totals_w = 78 * mm
    totals_rows = []
    if subtotal_cents and tax_cents:
        totals_rows.append([Paragraph("Subtotal", base), Paragraph(format_cents(subtotal_cents, currency), right)])
        totals_rows.append([Paragraph(tax_label, base), Paragraph(format_cents(tax_cents, currency), right)])
    totals_tbl = Table(totals_rows or [[Paragraph("", base), Paragraph("", base)]], colWidths=[totals_w - 32 * mm, 32 * mm])
    totals_tbl.setStyle(TableStyle([
        ("TOPPADDING", (0, 0), (-1, -1), 2),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 2),
        ("LEFTPADDING", (0, 0), (-1, -1), 6),
        ("RIGHTPADDING", (0, 0), (-1, -1), 6),
    ]))
    total_label = "TOTAL DUE" if doc_type == "INVOICE" else "TOTAL"
    cur = (currency or "AUD").upper()
    total_style_l = ParagraphStyle("tl", parent=base, fontName="Helvetica-Bold", fontSize=9, textColor=on_accent)
    total_style_r = ParagraphStyle("tr", parent=total_style_l, fontSize=13, leading=16, alignment=TA_RIGHT)
    total_tbl = Table(
        [[Paragraph(f"{total_label} ({cur})", total_style_l), Paragraph(format_cents(total_cents, currency), total_style_r)]],
        colWidths=[totals_w - 40 * mm, 40 * mm],
    )
    total_tbl.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), accent),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("TOPPADDING", (0, 0), (-1, -1), 6),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
        ("LEFTPADDING", (0, 0), (-1, -1), 6),
        ("RIGHTPADDING", (0, 0), (-1, -1), 6),
    ]))
    block = Table([[totals_tbl], [total_tbl]], colWidths=[totals_w])
    block.setStyle(TableStyle([
        ("LEFTPADDING", (0, 0), (-1, -1), 0),
        ("RIGHTPADDING", (0, 0), (-1, -1), 0),
        ("TOPPADDING", (0, 0), (-1, -1), 0),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 2),
    ]))
    outer = Table([["", block]], colWidths=[page_width - totals_w, totals_w])
    outer.setStyle(TableStyle([
        ("LEFTPADDING", (0, 0), (-1, -1), 0),
        ("RIGHTPADDING", (0, 0), (-1, -1), 0),
        ("TOPPADDING", (0, 0), (-1, -1), 0),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 0),
    ]))
    story.append(KeepTogether(outer))

    # ── Footer note (payment details for invoices, terms for quotes) ──
    if footer_text and footer_text.strip():
        story.append(Spacer(1, 10 * mm))
        note = Table(
            [[[Paragraph(esc(footer_label or "NOTES"), label),
               Paragraph(esc(footer_text.strip()).replace("\n", "<br/>"), base)]]],
            colWidths=[page_width],
        )
        note.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, -1), _LIGHT_GREY),
            ("LINEBEFORE", (0, 0), (0, -1), 2, accent),
            ("LEFTPADDING", (0, 0), (-1, -1), 5 * mm),
            ("RIGHTPADDING", (0, 0), (-1, -1), 5 * mm),
            ("TOPPADDING", (0, 0), (-1, -1), 4 * mm),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 4 * mm),
        ]))
        story.append(KeepTogether(note))

    def _decorate(canvas, d):
        canvas.saveState()
        canvas.setFillColor(accent)
        canvas.rect(0, A4[1] - 6 * mm, A4[0], 6 * mm, stroke=0, fill=1)
        canvas.setStrokeColor(_RULE)
        canvas.setLineWidth(0.4)
        canvas.line(20 * mm, 15 * mm, A4[0] - 20 * mm, 15 * mm)
        canvas.setFont("Helvetica", 7.5)
        canvas.setFillColor(_MID_GREY)
        canvas.drawString(20 * mm, 10.5 * mm, f"{doc_type.title()} {document_number} · {shop_name}"[:90])
        canvas.drawRightString(A4[0] - 20 * mm, 10.5 * mm, f"Page {d.page}")
        canvas.restoreState()

    doc.build(story, onFirstPage=_decorate, onLaterPages=_decorate)
    return buf.getvalue()
