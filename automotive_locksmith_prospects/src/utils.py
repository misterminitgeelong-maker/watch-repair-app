"""Utility helpers for text normalization, column mapping, and inspection."""

import logging
import re
from pathlib import Path
from typing import Any, Optional

import pandas as pd

from config import ABR_COLUMN_CANDIDATES, SUBURB_COLUMN_CANDIDATES

logger = logging.getLogger(__name__)


def normalize_text(value: Any) -> str:
    """Convert value to lowercase string, strip whitespace, collapse spaces."""
    if value is None or (isinstance(value, float) and pd.isna(value)):
        return ""
    s = str(value).strip().lower()
    s = re.sub(r"\s+", " ", s)
    return s


def strip_punctuation_for_search(text: str) -> str:
    """Remove punctuation that might interfere with keyword matching."""
    if not text:
        return ""
    return re.sub(r"[^\w\s]", " ", text)


def build_searchable_text(row: pd.Series, columns: list[str]) -> str:
    """Combine values from specified columns into one searchable string."""
    parts: list[str] = []
    for col in columns:
        if col in row.index:
            val = row[col]
            if val is not None and not (isinstance(val, float) and pd.isna(val)):
                parts.append(str(val))
    return normalize_text(" ".join(parts))


def map_columns(df: pd.DataFrame, candidates: dict[str, list[str]]) -> dict[str, Optional[str]]:
    """
    Map logical column names to actual column names.
    Returns dict of logical_name -> actual_column_name (or None if not found).
    """
    result: dict[str, Optional[str]] = {}
    col_lower = {str(c).strip().lower(): str(c) for c in df.columns}

    for logical, names in candidates.items():
        found = None
        for candidate in names:
            key = candidate.strip().lower()
            if key in col_lower:
                found = col_lower[key]
                break
        result[logical] = found

    return result


def inspect_csv_columns(path: Path, n_rows: int = 5) -> list[str]:
    """Inspect first rows of CSV to discover column names."""
    path = Path(path)
    if not path.exists():
        raise FileNotFoundError(f"File not found: {path}")
    try:
        df = pd.read_csv(path, nrows=n_rows, encoding="utf-8", on_bad_lines="skip")
        cols = list(df.columns)
        logger.info("Found columns in %s: %s", path.name, cols)
        return cols
    except Exception as e:
        logger.error("Failed to inspect %s: %s", path, e)
        raise


def get_abr_column_map(path: Path) -> dict[str, Optional[str]]:
    """Inspect ABR file and return mapping of logical -> actual column names."""
    df = pd.read_csv(path, nrows=1, encoding="utf-8", on_bad_lines="skip")
    return map_columns(df, ABR_COLUMN_CANDIDATES)


def get_suburb_column_map(path: Path) -> dict[str, Optional[str]]:
    """Inspect suburb file and return mapping of logical -> actual column names."""
    df = pd.read_csv(path, encoding="utf-8", on_bad_lines="skip")
    return map_columns(df, SUBURB_COLUMN_CANDIDATES)
