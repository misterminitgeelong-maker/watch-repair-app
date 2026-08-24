"""PDF export for the VSWT weekly report builder (reportlab, pure Python).

Lays out a hand-picked set of shops' numbers for one week — comprehensively: every KPI HQ
tracks, grouped the same way the rest of the VSWT Regional Reports UI groups them, each with a
value *and* a region rank. Built for a franchisee who wants a shareable, "paste into the group
chat" export that stands on its own, without anyone needing to flip back to the dashboard for
the rest of the picture.

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
from reportlab.platypus import KeepTogether, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

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
    groups: Sequence[str],
    kpis: Sequence[KpiDef],
    shops: Sequence[dict[str, Any]],
    totals: dict[str, Any],
    generated_on: Optional[date] = None,
) -> bytes:
    """Landscape-A4, multi-section: a headline summary table (sales $, rank, customers, jobs,
    overall avg rank, group total), followed by one table per KPI group with every KPI in that
    group as a "value (#rank)" cell — same grouping the Rankings/Directory tabs use."""
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
    section = ParagraphStyle("section", parent=normal, fontSize=11.5, fontName="Helvetica-Bold", textColor=_DARK, spaceBefore=6 * mm, spaceAfter=2 * mm)
    sub = ParagraphStyle("sub", parent=normal, fontSize=9.5, textColor=_MID_GREY)
    label = ParagraphStyle("label", parent=normal, fontSize=7.5, fontName="Helvetica-Bold", textColor=_MID_GREY)
    cell = ParagraphStyle("cell", parent=normal, fontSize=8.5)
    cell_bold = ParagraphStyle("cell_bold", parent=cell, fontName="Helvetica-Bold", textColor=_DARK)

    subtitle = f"Week {week} · {region_size} shops in region · {len(shops)} shop{'s' if len(shops) != 1 else ''} in this report"
    if generated_on:
        subtitle += f" · generated {generated_on.strftime('%d %b %Y')}"

    story: list[Any] = [
        Paragraph(title, heading),
        Paragraph(subtitle, sub),
    ]

    def _table_style(n_rows: int, has_totals: bool = False) -> TableStyle:
        # `has_totals` marks the last row as a totals row (accent rule above it, excluded from
        # the zebra striping) — only the Summary table has one; per-KPI-group tables don't.
        stripe_end = (n_rows - 2) if has_totals else (n_rows - 1)
        style = [
            ("BACKGROUND", (0, 0), (-1, 0), _LIGHT_GREY),
            ("ROWBACKGROUNDS", (0, 1), (-1, stripe_end), [colors.white, _LIGHT_GREY]),
            ("LINEBELOW", (0, 0), (-1, 0), 0.5, _ACCENT),
            ("TOPPADDING", (0, 0), (-1, -1), 4),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
            ("LEFTPADDING", (0, 0), (-1, -1), 5),
            ("RIGHTPADDING", (0, 0), (-1, -1), 5),
            ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ]
        if has_totals:
            style.append(("LINEABOVE", (0, -1), (-1, -1), 0.75, _ACCENT))
        return TableStyle(style)

    def _name_cell(s: dict[str, Any]) -> Paragraph:
        name = (s["shop_name"] or s["shop_number"] or "—") + (" (you)" if s["is_me"] else "")
        return Paragraph(name, cell_bold if s["is_me"] else cell)

    def _val_rank_cell(value: Optional[float], rank: Optional[int], kpi_type: str, bold: bool) -> Paragraph:
        text = _fmt_val(value, kpi_type)
        style = cell_bold if bold else cell
        if rank is not None:
            return Paragraph(f'{text}<br/><font size="6.5" color="#9ca3af">#{rank}</font>', style)
        return Paragraph(text, style)

    # ── Summary table: headline numbers + the composite "overall avg rank" ──
    story.append(Spacer(1, 4 * mm))
    story.append(Paragraph("Summary", section))
    summary_headers = ["Shop", "Area", "Sales $", "Sales Rank", "Customers", "Jobs", "Overall Avg Rank"]
    summary_rows: list[list[Any]] = [[Paragraph(h, label) for h in summary_headers]]
    for s in shops:
        bold = s["is_me"]
        style = cell_bold if bold else cell
        summary_rows.append([
            _name_cell(s),
            Paragraph(s["area_name"] or "—", style),
            Paragraph(_fmt_val(s["sales_value"], "currency"), style),
            Paragraph(f"#{s['sales_rank']}" if s["sales_rank"] is not None else "—", style),
            Paragraph(_fmt_val(s["customer_value"], "count"), style),
            Paragraph(_fmt_val(s["jobs_value"], "count"), style),
            Paragraph(f"#{s['overall_avg_rank']:.1f}" if s["overall_avg_rank"] is not None else "—", style),
        ])
    summary_rows.append([
        Paragraph("<b>Group total</b>", cell_bold),
        Paragraph("", cell),
        Paragraph(f"<b>{_fmt_val(totals.get('sales'), 'currency')}</b>", cell_bold),
        Paragraph(f"<b>avg #{totals['avg_sales_rank']:.1f}</b>" if totals.get("avg_sales_rank") is not None else "—", cell_bold),
        Paragraph(f"<b>{_fmt_val(totals.get('customers'), 'count')}</b>", cell_bold),
        Paragraph(f"<b>{_fmt_val(totals.get('jobs'), 'count')}</b>", cell_bold),
        Paragraph("", cell),
    ])
    page_width = landscape(A4)[0] - 28 * mm
    shop_col = 50 * mm
    area_col = 32 * mm
    n_other = len(summary_headers) - 2
    other_col = (page_width - shop_col - area_col) / n_other
    summary_tbl = Table(summary_rows, colWidths=[shop_col, area_col] + [other_col] * n_other, repeatRows=1)
    summary_tbl.setStyle(_table_style(len(summary_rows), has_totals=True))
    story.append(summary_tbl)

    # ── One table per KPI group, every KPI in it as a value+rank cell ──
    for group in groups:
        group_kpis = [k for k in kpis if k.group == group]
        if not group_kpis:
            continue
        story.append(Spacer(1, 2 * mm))
        headers = ["Shop"] + [k.label for k in group_kpis]
        rows: list[list[Any]] = [[Paragraph(h, label) for h in headers]]
        for s in shops:
            row = [_name_cell(s)]
            for k in group_kpis:
                row.append(_val_rank_cell(s["values"].get(k.key), s["ranks"].get(k.key), k.type, bold=s["is_me"]))
            rows.append(row)

        shop_col_g = 46 * mm
        other_col_g = (page_width - shop_col_g) / len(group_kpis)
        tbl = Table(rows, colWidths=[shop_col_g] + [other_col_g] * len(group_kpis), repeatRows=1)
        tbl.setStyle(_table_style(len(rows)))
        # Keep each group's heading with its table so a section never starts at the very bottom
        # of a page with the table stranded on the next one.
        story.append(KeepTogether([Paragraph(group, section), tbl]))

    doc.build(story)
    return buf.getvalue()
