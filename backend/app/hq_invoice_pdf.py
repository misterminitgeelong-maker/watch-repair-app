"""PDF for an issued HQ bundled invoice (reportlab, from the frozen snapshot)."""
from __future__ import annotations

import io
from xml.sax.saxutils import escape

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

from .money import format_cents

SUPPLIER_NAME = "Unamigo Pty Ltd"
SUPPLIER_ABN = "41 652 728 320"
SUPPLIER_TRADING = "Mainspring (mainspring.au)"


def build_hq_invoice_pdf(*, invoice_number: str, status: str, bill_to: str, snapshot: dict,
                         issued_on: str | None, due_on: str | None) -> bytes:
    ss = getSampleStyleSheet()
    body = ParagraphStyle("b", parent=ss["Normal"], fontSize=9, leading=12)
    small = ParagraphStyle("s", parent=body, fontSize=8, textColor=colors.HexColor("#6b7280"))
    h1 = ParagraphStyle("h", parent=ss["Title"], fontSize=20, alignment=0, spaceAfter=4)
    cur = "AUD"
    fmt = lambda c: format_cents(c, cur)  # noqa: E731
    buf = io.BytesIO()
    doc = SimpleDocTemplate(buf, pagesize=A4, leftMargin=18 * mm, rightMargin=18 * mm, topMargin=16 * mm, bottomMargin=16 * mm,
                            title=f"Tax invoice {invoice_number}")
    month = snapshot.get("billing_month", "")
    story = [
        Paragraph("TAX INVOICE" + (" (VOID)" if status == "void" else ""), h1),
        Paragraph(f"{escape(SUPPLIER_NAME)} · ABN {SUPPLIER_ABN}<br/>{escape(SUPPLIER_TRADING)}", body),
        Spacer(1, 6 * mm),
        Paragraph(
            f"<b>Invoice</b> {escape(invoice_number)}<br/><b>Billing month</b> {escape(month)}<br/>"
            + (f"<b>Issued</b> {escape(issued_on)}<br/>" if issued_on else "")
            + (f"<b>Due</b> {escape(due_on)}<br/>" if due_on else "")
            + f"<br/><b>Bill to</b><br/>{escape(bill_to)}", body),
        Spacer(1, 6 * mm),
    ]
    rows = [["Shop", "Operator", "Core", "Routing", "Prospecting", "Ex GST", "GST", "Total"]]
    for l in snapshot.get("lines", []):
        gst = l["gst_cents"]
        rows.append([l.get("shop_number") or "", Paragraph(escape(l["name"]), body), fmt(l["core_cents"]),
                     fmt(l["routing_cents"]), fmt(l["prospecting_cents"]), fmt(l["subtotal_ex_gst_cents"]),
                     fmt(gst), fmt(l["subtotal_ex_gst_cents"] + gst)])
    rows.append(["", "Total", "", "", "", fmt(snapshot.get("subtotal_ex_gst_cents", 0)),
                 fmt(snapshot.get("gst_total_cents", 0)), fmt(snapshot.get("total_inc_gst_cents", 0))])
    t = Table(rows, repeatRows=1, colWidths=[14 * mm, 46 * mm, 16 * mm, 16 * mm, 20 * mm, 18 * mm, 16 * mm, 20 * mm])
    t.setStyle(TableStyle([
        ("FONTSIZE", (0, 0), (-1, -1), 8), ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTNAME", (0, -1), (-1, -1), "Helvetica-Bold"),
        ("ALIGN", (2, 0), (-1, -1), "RIGHT"), ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("LINEBELOW", (0, 0), (-1, 0), 0.6, colors.HexColor("#111827")),
        ("LINEABOVE", (0, -1), (-1, -1), 0.6, colors.HexColor("#111827")),
        ("ROWBACKGROUNDS", (0, 1), (-1, -2), [colors.white, colors.HexColor("#f6f7f9")]),
    ]))
    story += [t, Spacer(1, 5 * mm)]
    for g in snapshot.get("gst", []):
        story.append(Paragraph(f"{escape(g['label'])} {g['rate_percent']:g}%: {fmt(g['amount_cents'])}", body))
    story += [Spacer(1, 4 * mm), Paragraph(
        f"Core platform {fmt(5500)} per operator per month. Routing and Prospecting add-ons "
        f"{fmt(snapshot.get('addon_unit_cents', 0))} each per operator per month when included. "
        "Amounts in AUD. NZ operators are charged GST at 15%.", small)]
    doc.build(story)
    return buf.getvalue()
