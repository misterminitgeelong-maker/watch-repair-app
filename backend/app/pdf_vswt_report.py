"""PDF export for the VSWT weekly report builder (reportlab, pure Python).

Lays out a hand-picked set of shops' numbers for one week side by side — built for a franchisee
who wants a shareable, "paste into the group chat" export of the region's weekly numbers for just
their own group of shops, rather than the whole regional dashboard.

`shops`/`totals` here are exactly the shapes `_weekly_report_data()` in routes/vswt_reports.py
builds — that function feeds both this PDF and the JSON preview endpoint, so the two always agree.
"""
from __future__ import annotations

import io
from datetime import date
from typing import Any, Optional, Sequence

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

from .vswt_kpis import KpiDef

_DARK = colors.HexColor("#1a1a2e")
_ACCENT = colors.HexColor("#4f46e5")
_LIGHT_GREY = colors.HexColor("#f3f4f6")
_MID_GREY = colors.HexColor("#9ca3af")


def _fmt_val(value: Optional[float], kpi_type: str) -> str:
    if value is None:
        return "—"
    if kpi_type == "currency":
        return f"${value:,.0f}"
    if kpi_type == "percent":
        return f"{'+' if value >= 0 else ''}{value * 100:.1f}%"
    if kpi_type == "ratio":
        return f"{value:.1f}"
    return f"{value:,.0f}"


def build_weekly_report_pdf(
    *,
    title: str,
    week: int,
    region_size: int,
    kpis: Sequence[KpiDef],
    shops: Sequence[dict[str, Any]],
    totals: dict[str, Any],
    generated_on: Optional[date] = None,
) -> bytes:
    """One landscape-A4 table: a row per selected shop (best sales first), sales $ and sales
    rank always shown, plus every KPI in the chosen group as extra columns, and a totals row for
    the group as a whole."""
    buf = io.BytesIO()
    doc = SimpleDocTemplate(
        buf,
        pagesize=landscape(A4),
        leftMargin=14 * mm, rightMargin=14 * mm, topMargin=14 * mm, bottomMargin=14 * mm,
        title=title,
    )

    styles = getSampleStyleSheet()
    normal = styles["Normal"]
    normal.fontName = "Helvetica"
    normal.fontSize = 8.5
    normal.leading = 11

    heading = ParagraphStyle("heading", parent=normal, fontSize=18, fontName="Helvetica-Bold", textColor=_DARK, spaceAfter=1 * mm)
    sub = ParagraphStyle("sub", parent=normal, fontSize=9.5, textColor=_MID_GREY)
    label = ParagraphStyle("label", parent=normal, fontSize=7.5, fontName="Helvetica-Bold", textColor=_MID_GREY)
    cell = ParagraphStyle("cell", parent=normal, fontSize=8.5)
    cell_bold = ParagraphStyle("cell_bold", parent=cell, fontName="Helvetica-Bold", textColor=_DARK)

    subtitle = f"Week {week} · {region_size} shops in region · {len(shops)} shop{'s' if len(shops) != 1 else ''} in this report"
    if generated_on:
        subtitle += f" · generated {generated_on.strftime('%d %b %Y')}"

    story = [
        Paragraph(title, heading),
        Paragraph(subtitle, sub),
        Spacer(1, 5 * mm),
    ]

    extra_kpis = [k for k in kpis if k.key != "sales_ty"]
    headers = ["Shop", "Area", "Sales $", "Sales Rank"] + [k.label for k in extra_kpis]
    rows: list[list[Any]] = [[Paragraph(h, label) for h in headers]]

    for s in shops:
        name = (s["shop_name"] or s["shop_number"] or "—") + (" (you)" if s["is_me"] else "")
        style = cell_bold if s["is_me"] else cell
        row = [
            Paragraph(name, style),
            Paragraph(s["area_name"] or "—", style),
            Paragraph(_fmt_val(s["sales_value"], "currency"), style),
            Paragraph(f"#{s['sales_rank']}" if s["sales_rank"] is not None else "—", style),
        ]
        for k in extra_kpis:
            row.append(Paragraph(_fmt_val(s["values"].get(k.key), k.type), style))
        rows.append(row)

    totals_row = [
        Paragraph("<b>Group total</b>", cell_bold),
        Paragraph("", cell),
        Paragraph(f"<b>{_fmt_val(totals.get('sales'), 'currency')}</b>", cell_bold),
        Paragraph(
            f"<b>avg #{totals['avg_sales_rank']:.1f}</b>" if totals.get("avg_sales_rank") is not None else "—",
            cell_bold,
        ),
    ]
    for k in extra_kpis:
        if k.key == "customer_ty":
            totals_row.append(Paragraph(f"<b>{_fmt_val(totals.get('customers'), 'count')}</b>", cell_bold))
        elif k.key == "jobs_ty":
            totals_row.append(Paragraph(f"<b>{_fmt_val(totals.get('jobs'), 'count')}</b>", cell_bold))
        else:
            totals_row.append(Paragraph("", cell))
    rows.append(totals_row)

    n_cols = len(headers)
    page_width = landscape(A4)[0] - 28 * mm
    shop_col = 46 * mm
    area_col = 30 * mm
    other_col = (page_width - shop_col - area_col) / (n_cols - 2)
    col_widths = [shop_col, area_col] + [other_col] * (n_cols - 2)

    tbl = Table(rows, colWidths=col_widths, repeatRows=1)
    tbl.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), _LIGHT_GREY),
        ("ROWBACKGROUNDS", (0, 1), (-1, -2), [colors.white, _LIGHT_GREY]),
        ("LINEBELOW", (0, 0), (-1, 0), 0.5, _ACCENT),
        ("LINEABOVE", (0, -1), (-1, -1), 0.75, _ACCENT),
        ("TOPPADDING", (0, 0), (-1, -1), 4),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
        ("LEFTPADDING", (0, 0), (-1, -1), 5),
        ("RIGHTPADDING", (0, 0), (-1, -1), 5),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
    ]))
    story.append(tbl)

    doc.build(story)
    return buf.getvalue()
