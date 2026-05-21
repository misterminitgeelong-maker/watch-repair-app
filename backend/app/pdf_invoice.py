"""
PDF invoice generator using reportlab (pure Python, no system dependencies).

Produces a byte string suitable for attaching to a SendGrid email.
"""
from __future__ import annotations

import io
from datetime import date
from typing import Sequence

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import mm
from reportlab.platypus import (
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)

_DARK = colors.HexColor("#1a1a2e")
_ACCENT = colors.HexColor("#4f46e5")
_LIGHT_GREY = colors.HexColor("#f3f4f6")
_MID_GREY = colors.HexColor("#9ca3af")


def _currency_symbol(currency: str) -> str:
    return "$" if (currency or "AUD").upper() in ("AUD", "USD", "NZD", "CAD") else f"{currency} "


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
    line_items: Sequence[dict],
    subtotal_cents: int = 0,
    tax_cents: int = 0,
    total_cents: int,
    currency: str = "AUD",
) -> bytes:
    """Return PDF bytes for an invoice."""
    buf = io.BytesIO()
    sym = _currency_symbol(currency)
    doc_date = invoice_date or date.today()

    doc = SimpleDocTemplate(
        buf,
        pagesize=A4,
        leftMargin=20 * mm,
        rightMargin=20 * mm,
        topMargin=20 * mm,
        bottomMargin=20 * mm,
        title=f"Invoice {invoice_number}",
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

    # ── Header row: shop name (left) / INVOICE label (right) ──
    header_data = [
        [
            Paragraph(shop_name, heading),
            Paragraph("INVOICE", heading),
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
        f"<b>Invoice #</b> {invoice_number}",
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
        ("LINEBELOW", (0, 0), (-1, 0), 0.5, _ACCENT),
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
        ("LINEABOVE", (0, -1), (-1, -1), 0.5, _ACCENT),
        ("TOPPADDING", (0, -1), (-1, -1), 4),
        ("FONTSIZE", (0, 0), (-1, -1), 9),
    ]))
    story.append(totals_tbl)

    # ── Payment instructions ──
    if payment_instructions and payment_instructions.strip():
        story.append(Spacer(1, 8 * mm))
        story.append(Paragraph("PAYMENT DETAILS", label))
        story.append(Paragraph(payment_instructions.strip().replace("\n", "<br/>"), normal))

    doc.build(story)
    return buf.getvalue()
