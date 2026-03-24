#!/usr/bin/env python3
"""
Automotive Locksmith Prospects Pipeline

Processes suburb master CSV and ABR bulk extract to produce a clean Excel
workbook of B2B prospects for an automotive locksmith business.

Usage:
  python main.py --suburbs data/input/suburbs_master.csv --abr data/input/abr_bulk_extract.csv --output data/output/prospects.xlsx
"""

import argparse
import logging
import sys
from pathlib import Path

import pandas as pd

from config import CHUNKSIZE
from src.cleaner import apply_cleaning
from src.classifier import classify_chunk, filter_automotive_only
from src.deduper import run_deduplication
from src.exporter import export_workbook
from src.loader import inspect_abr_columns, load_suburbs, stream_abr_chunks
from src.matcher import build_suburb_lookup, enrich_chunk_with_suburb
from src.scorer import apply_scoring

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S",
    handlers=[logging.StreamHandler(sys.stdout)],
)
logger = logging.getLogger(__name__)


def run_pipeline(
    suburbs_path: Path,
    abr_path: Path,
    output_path: Path,
    chunksize: int = CHUNKSIZE,
) -> None:
    """
    Main pipeline: load suburbs, stream ABR, classify, clean, match, dedupe, score, export.
    """
    logger.info("Starting prospect pipeline")
    logger.info("Suburbs: %s", suburbs_path)
    logger.info("ABR: %s", abr_path)
    logger.info("Output: %s", output_path)

    if not suburbs_path.exists():
        raise FileNotFoundError(f"Suburb file not found: {suburbs_path}")
    if not abr_path.exists():
        raise FileNotFoundError(f"ABR file not found: {abr_path}")

    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    # 1. Load suburbs
    suburbs_df = load_suburbs(suburbs_path)
    suburb_lookup = build_suburb_lookup(suburbs_df)

    # 2. Inspect ABR columns
    abr_column_map = inspect_abr_columns(abr_path)
    text_cols = None
    if abr_column_map.get("business_name"):
        text_cols = ["business_name"]
        if abr_column_map.get("suburb"):
            text_cols.append("suburb")

    # 3. Stream ABR, process chunks
    chunks_processed = 0
    all_filtered: list[pd.DataFrame] = []

    for chunk in stream_abr_chunks(abr_path, abr_column_map, chunksize):
        chunks_processed += 1
        if chunks_processed % 10 == 0:
            logger.info("Processed %d chunks...", chunks_processed)

        chunk = apply_cleaning(chunk)
        chunk = classify_chunk(chunk, text_cols)
        chunk = filter_automotive_only(chunk)
        if chunk.empty:
            continue

        chunk = enrich_chunk_with_suburb(chunk, suburb_lookup)
        all_filtered.append(chunk)

    if not all_filtered:
        logger.warning("No automotive prospects found in ABR file")
        raw_filtered = pd.DataFrame()
        prospects = pd.DataFrame()
        duplicates = pd.DataFrame()
    else:
        combined = pd.concat(all_filtered, ignore_index=True)
        logger.info("Combined %d automotive records", len(combined))

        raw_filtered = combined.copy()

        combined = apply_scoring(combined)
        prospects, duplicates = run_deduplication(combined)

        # Ensure prospects_clean has required columns for output
        if "business_name_clean" in prospects.columns:
            prospects["business_name"] = prospects["business_name_clean"].fillna(prospects.get("business_name", ""))
        elif "business_name" not in prospects.columns:
            prospects["business_name"] = ""

        if "abn_normalized" in prospects.columns:
            prospects["abn"] = prospects["abn_normalized"]
        elif "abn" not in prospects.columns:
            prospects["abn"] = None

        for col in ["category", "suburb", "postcode", "state", "lead_score"]:
            if col not in prospects.columns:
                prospects[col] = None

        logger.info("Prospects: %d | Duplicates for review: %d", len(prospects), len(duplicates))

    export_workbook(
        suburbs_df=suburbs_df,
        raw_filtered_df=raw_filtered,
        prospects_df=prospects,
        duplicates_df=duplicates,
        output_path=output_path,
    )
    logger.info("Done. Output: %s", output_path)


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Build automotive locksmith prospect database from suburb + ABR data",
    )
    parser.add_argument(
        "--suburbs",
        type=Path,
        required=True,
        help="Path to suburb master CSV",
    )
    parser.add_argument(
        "--abr",
        type=Path,
        required=True,
        help="Path to ABR bulk extract CSV",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("data/output/prospects.xlsx"),
        help="Output Excel path (default: data/output/prospects.xlsx)",
    )
    parser.add_argument(
        "--chunksize",
        type=int,
        default=CHUNKSIZE,
        help=f"ABR chunk size (default: {CHUNKSIZE})",
    )
    args = parser.parse_args()

    try:
        run_pipeline(
            suburbs_path=args.suburbs,
            abr_path=args.abr,
            output_path=args.output,
            chunksize=args.chunksize,
        )
        return 0
    except FileNotFoundError as e:
        logger.error("%s", e)
        return 1
    except Exception as e:
        logger.exception("Pipeline failed: %s", e)
        return 1


if __name__ == "__main__":
    sys.exit(main())
