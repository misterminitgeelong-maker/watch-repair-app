"""
Export a print-ready PDF price list for the Mobile Services point of sale.

Pulls together every pricing dataset behind the Mobile Services module so it
can be handed to shops for review before their pricing is loaded into
Mainspring:

  1. Mobile service price list (backend/seed/job_pricing.json).
  2. Full mobile services retail catalogue, as currently loaded in the app's
     `service_pricing` table (seeded by the 20260804 migration).
  3. OEM key pricing by vehicle make, as currently loaded in the app's
     `oem_key_pricing` table (seeded by the 20260804 and 20260805
     migrations).
  4. Garage door servicing price list (`garage_servicing_pricing` table).

All prices are retail only and charm-priced to the nearest xx.95.

Usage (from repo root or backend/):
  python scripts/export_mobile_services_price_list_pdf.py [--output PATH]
"""
from __future__ import annotations

import argparse
import ast
import json
import re
from collections import defaultdict
from datetime import date
from pathlib import Path

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import (
    KeepTogether,
    PageBreak,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)

REPO_ROOT = Path(__file__).resolve().parents[2]
SEED_DIR = REPO_ROOT / "backend" / "seed"
ALEMBIC_DIR = REPO_ROOT / "backend" / "alembic" / "versions"

GOLD = colors.HexColor("#C9A248")
DARK = colors.HexColor("#1E1410")
LIGHT_ROW = colors.HexColor("#F7F2E7")
WHITE = colors.white


def _extract_python_list(path: Path, varname: str) -> list[dict]:
    """Pull a top-level `VARNAME = [...]` literal out of an Alembic migration
    file without importing it (migrations aren't meant to be imported)."""
    src = path.read_text(encoding="utf-8")
    start = src.index(f"{varname} = [")
    start_bracket = src.index("[", start)
    depth = 0
    i = start_bracket
    while True:
        if src[i] == "[":
            depth += 1
        elif src[i] == "]":
            depth -= 1
            if depth == 0:
                break
        i += 1
    list_src = src[start_bracket : i + 1]
    # uuid.UUID("...") -> "..." so ast.literal_eval can parse it
    list_src = re.sub(r'uuid\.UUID\("([^"]+)"\)', r'"\1"', list_src)
    return ast.literal_eval(list_src)


def load_wholesale_price_list() -> list[dict]:
    data = json.loads((SEED_DIR / "job_pricing.json").read_text(encoding="utf-8"))
    return data["entries"]


def load_catalogue_tables() -> tuple[list[dict], list[dict], list[dict]]:
    oem = _extract_python_list(
        ALEMBIC_DIR / "20260804_seed_mobile_services_pricing.py", "OEM_KEY_PRICING_ROWS"
    )
    oem += _extract_python_list(
        ALEMBIC_DIR / "20260805_seed_new_makes_pricing.py", "NEW_MAKE_PRICING_ROWS"
    )
    service = _extract_python_list(
        ALEMBIC_DIR / "20260804_seed_mobile_services_pricing.py", "SERVICE_PRICING_ROWS"
    )
    garage = _extract_python_list(
        ALEMBIC_DIR / "20260804_seed_mobile_services_pricing.py", "GARAGE_SERVICING_PRICING_ROWS"
    )
    return oem, service, garage


def round_to_95(value: float) -> float:
    """Charm-price to the nearest xx.95 (e.g. 400.00 -> 399.95, 15.10 -> 14.95)."""
    return round(value) - 0.05


def money(value) -> str:
    if value is None:
        return "POA"
    return f"${round_to_95(value):,.2f}"


def yesno(value) -> str:
    return "Yes" if value else "No"


def build_styles():
    styles = getSampleStyleSheet()
    styles.add(
        ParagraphStyle(
            "DocTitle",
            parent=styles["Title"],
            fontName="Helvetica-Bold",
            fontSize=26,
            textColor=DARK,
            spaceAfter=6,
        )
    )
    styles.add(
        ParagraphStyle(
            "DocSubtitle",
            parent=styles["Normal"],
            fontName="Helvetica",
            fontSize=13,
            textColor=colors.HexColor("#5A4632"),
            spaceAfter=4,
        )
    )
    styles.add(
        ParagraphStyle(
            "CoverNote",
            parent=styles["Normal"],
            fontName="Helvetica",
            fontSize=10.5,
            textColor=colors.HexColor("#3A2E22"),
            leading=15,
        )
    )
    styles.add(
        ParagraphStyle(
            "SectionHeading",
            parent=styles["Heading1"],
            fontName="Helvetica-Bold",
            fontSize=17,
            textColor=DARK,
            spaceBefore=0,
            spaceAfter=4,
        )
    )
    styles.add(
        ParagraphStyle(
            "SectionIntro",
            parent=styles["Normal"],
            fontName="Helvetica",
            fontSize=9.5,
            textColor=colors.HexColor("#4A3B2C"),
            spaceAfter=10,
            leading=13,
        )
    )
    styles.add(
        ParagraphStyle(
            "CategoryHeading",
            parent=styles["Heading2"],
            fontName="Helvetica-Bold",
            fontSize=11,
            textColor=WHITE,
            backColor=DARK,
            spaceBefore=10,
            spaceAfter=0,
            leftIndent=4,
            borderPadding=(4, 4, 4, 4),
        )
    )
    styles.add(
        ParagraphStyle(
            "Cell",
            parent=styles["Normal"],
            fontName="Helvetica",
            fontSize=7.6,
            leading=9.2,
        )
    )
    styles.add(
        ParagraphStyle(
            "CellBold",
            parent=styles["Cell"],
            fontName="Helvetica-Bold",
        )
    )
    styles.add(
        ParagraphStyle(
            "Header",
            parent=styles["Normal"],
            fontName="Helvetica-Bold",
            fontSize=7.8,
            textColor=WHITE,
            leading=9.5,
        )
    )
    return styles


def make_table(header: list[str], rows: list[list], col_widths: list[float], styles) -> Table:
    header_row = [Paragraph(h, styles["Header"]) for h in header]
    data = [header_row] + rows
    tbl = Table(data, colWidths=col_widths, repeatRows=1)
    style_cmds = [
        ("BACKGROUND", (0, 0), (-1, 0), GOLD),
        ("TEXTCOLOR", (0, 0), (-1, 0), DARK),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("GRID", (0, 0), (-1, -1), 0.4, colors.HexColor("#D9CBB0")),
        ("LEFTPADDING", (0, 0), (-1, -1), 4),
        ("RIGHTPADDING", (0, 0), (-1, -1), 4),
        ("TOPPADDING", (0, 0), (-1, -1), 3),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [WHITE, LIGHT_ROW]),
    ]
    tbl.setStyle(TableStyle(style_cmds))
    return tbl


def category_groups(rows: list[dict], key: str) -> dict[str, list[dict]]:
    grouped: dict[str, list[dict]] = defaultdict(list)
    for row in rows:
        grouped[row.get(key) or "Uncategorised"].append(row)
    return dict(sorted(grouped.items(), key=lambda kv: kv[0].lower()))


def cell(text, styles, bold=False):
    if text is None:
        text = ""
    return Paragraph(str(text), styles["CellBold"] if bold else styles["Cell"])


def build_wholesale_section(story, styles, entries):
    story.append(Paragraph("1. Mobile Service Price List", styles["SectionHeading"]))
    story.append(
        Paragraph(
            "Retail price is what the mobile service charges the public. Confirm "
            "these figures with the shop before they are loaded into Mainspring.",
            styles["SectionIntro"],
        )
    )
    grouped = category_groups(entries, "category")
    col_widths = [60 * mm, 22 * mm, 22 * mm, 66 * mm]
    header = ["Service", "Unit", "Retail", "Notes"]
    for category, items in grouped.items():
        rows = []
        for it in items:
            rows.append(
                [
                    cell(it["service"], styles),
                    cell(it.get("unit"), styles),
                    cell(money(it.get("retail_2026")), styles),
                    cell(it.get("notes"), styles),
                ]
            )
        block = [
            Paragraph(category, styles["CategoryHeading"]),
            make_table(header, rows, col_widths, styles),
        ]
        story.append(KeepTogether(block))
        story.append(Spacer(1, 6))


def build_service_catalogue_section(story, styles, rows):
    story.append(PageBreak())
    story.append(Paragraph("2. Full Mobile Services Retail Catalogue", styles["SectionHeading"]))
    story.append(
        Paragraph(
            "This is every line item currently loaded in the live Mobile Services "
            "pricing catalogue. It includes callout fees and a few job types not "
            "covered in the price list above.",
            styles["SectionIntro"],
        )
    )
    grouped = category_groups(rows, "category")
    col_widths = [55 * mm, 20 * mm, 20 * mm, 20 * mm, 55 * mm]
    header = ["Service", "Unit", "Retail", "Callout Incl.", "Notes"]
    for category, items in grouped.items():
        rows_out = []
        for it in sorted(items, key=lambda r: r.get("service_name") or ""):
            rows_out.append(
                [
                    cell(it["service_name"], styles),
                    cell(it.get("unit"), styles),
                    cell(money(it.get("retail_price")), styles),
                    cell(yesno(it.get("callout_inclusive")), styles),
                    cell(it.get("notes"), styles),
                ]
            )
        block = [
            Paragraph(category, styles["CategoryHeading"]),
            make_table(header, rows_out, col_widths, styles),
        ]
        story.append(KeepTogether(block))
        story.append(Spacer(1, 6))


def build_oem_section(story, styles, rows):
    story.append(PageBreak())
    story.append(Paragraph("3. OEM Key Pricing by Vehicle Make", styles["SectionHeading"]))
    story.append(
        Paragraph(
            "Vehicle-specific key pricing. “From” prices marked POA vary by vehicle "
            "condition/options and should be confirmed at time of quote.",
            styles["SectionIntro"],
        )
    )
    grouped = category_groups(rows, "make")
    col_widths = [30 * mm, 16 * mm, 14 * mm, 16 * mm, 20 * mm, 18 * mm, 16 * mm, 15 * mm, 41 * mm]
    header = [
        "Model / Variant",
        "Job Type",
        "Chip",
        "Key Type",
        "Location",
        "Tool Req.",
        "Retail",
        "Callout Incl.",
        "Notes",
    ]
    for make, items in grouped.items():
        job_order = {"Add Key": 0, "AKL": 1}
        items_sorted = sorted(
            items,
            key=lambda r: (job_order.get(r.get("job_type"), 2), r.get("model_variant") or ""),
        )
        rows_out = []
        for it in items_sorted:
            rows_out.append(
                [
                    cell(it.get("model_variant"), styles),
                    cell(it.get("job_type"), styles),
                    cell(it.get("chip_type"), styles),
                    cell(it.get("key_type"), styles),
                    cell(it.get("service_location"), styles),
                    cell(it.get("tool_required"), styles),
                    cell(money(it.get("retail_price")), styles),
                    cell(yesno(it.get("callout_inclusive")), styles),
                    cell(it.get("notes"), styles),
                ]
            )
        block = [
            Paragraph(make, styles["CategoryHeading"]),
            make_table(header, rows_out, col_widths, styles),
        ]
        story.append(KeepTogether(block))
        story.append(Spacer(1, 6))


def build_garage_section(story, styles, rows):
    story.append(PageBreak())
    story.append(Paragraph("4. Garage Door Servicing Price List", styles["SectionHeading"]))
    story.append(
        Paragraph(
            "Retail pricing for garage door servicing jobs.",
            styles["SectionIntro"],
        )
    )
    col_widths = [34 * mm, 40 * mm, 28 * mm, 18 * mm, 16 * mm, 16 * mm, 30 * mm]
    header = ["Service", "Description", "Part Cost Notes", "Labour Time", "Retail", "Callout Incl.", "Notes"]
    rows_out = []
    for it in sorted(rows, key=lambda r: r.get("service_name") or ""):
        rows_out.append(
            [
                cell(it.get("service_name"), styles),
                cell(it.get("description"), styles),
                cell(it.get("part_cost_notes"), styles),
                cell(it.get("labour_time"), styles),
                cell(money(it.get("retail_price")), styles),
                cell(yesno(it.get("callout_inclusive")), styles),
                cell(it.get("notes"), styles),
            ]
        )
    story.append(make_table(header, rows_out, col_widths, styles))


def build_cover(story, styles, counts):
    story.append(Spacer(1, 60 * mm))
    story.append(Paragraph("Mobile Services Price List", styles["DocTitle"]))
    story.append(Paragraph("Full pricing export — point of sale data", styles["DocSubtitle"]))
    story.append(Spacer(1, 14))
    story.append(
        Paragraph(
            f"Prepared: {date.today().strftime('%d %B %Y')}<br/>"
            f"Purpose: shop review copy, ahead of loading pricing into Mainspring<br/><br/>"
            f"Contents:<br/>"
            f"1. Mobile service price list — {counts['wholesale']} services (retail)<br/>"
            f"2. Full mobile services retail catalogue — {counts['service']} line items<br/>"
            f"3. OEM key pricing by vehicle make — {counts['oem']} entries across "
            f"{counts['oem_makes']} makes<br/>"
            f"4. Garage door servicing price list — {counts['garage']} services<br/><br/>"
            "All prices are retail, rounded to the nearest 95c. Current mobile-service "
            "seed data — confirm before final sign-off with each shop.",
            styles["CoverNote"],
        )
    )
    story.append(PageBreak())


def header_footer(canvas, doc):
    canvas.saveState()
    canvas.setFont("Helvetica", 7.5)
    canvas.setFillColor(colors.HexColor("#8A7A63"))
    canvas.drawString(15 * mm, 10 * mm, "Mobile Services Price List — internal shop review copy")
    canvas.drawRightString(A4[0] - 15 * mm, 10 * mm, f"Page {doc.page}")
    canvas.restoreState()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--output",
        default=str(REPO_ROOT / "docs" / "exports" / "mobile_services_price_list.pdf"),
    )
    args = parser.parse_args()
    out_path = Path(args.output)
    out_path.parent.mkdir(parents=True, exist_ok=True)

    wholesale = load_wholesale_price_list()
    oem, service, garage = load_catalogue_tables()
    oem_makes = {r["make"] for r in oem}

    styles = build_styles()
    doc = SimpleDocTemplate(
        str(out_path),
        pagesize=A4,
        leftMargin=15 * mm,
        rightMargin=15 * mm,
        topMargin=15 * mm,
        bottomMargin=18 * mm,
        title="Mobile Services Price List",
        author="Mainspring",
    )

    story = []
    build_cover(
        story,
        styles,
        {
            "wholesale": len(wholesale),
            "service": len(service),
            "oem": len(oem),
            "oem_makes": len(oem_makes),
            "garage": len(garage),
        },
    )
    build_wholesale_section(story, styles, wholesale)
    build_service_catalogue_section(story, styles, service)
    build_oem_section(story, styles, oem)
    build_garage_section(story, styles, garage)

    doc.build(story, onFirstPage=header_footer, onLaterPages=header_footer)
    print(f"Wrote {out_path}")
    print(
        f"Wholesale entries: {len(wholesale)} | "
        f"Service catalogue: {len(service)} | "
        f"OEM key pricing: {len(oem)} across {len(oem_makes)} makes | "
        f"Garage servicing: {len(garage)}"
    )


if __name__ == "__main__":
    main()
