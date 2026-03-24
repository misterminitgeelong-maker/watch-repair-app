"""Classify ABR records into automotive prospect categories."""

import logging
from typing import Optional

import pandas as pd

from config import CATEGORY_KEYWORDS
from src.utils import build_searchable_text, strip_punctuation_for_search

logger = logging.getLogger(__name__)

# Default columns that may contain business description / activity text
DEFAULT_TEXT_COLUMNS = ["business_name", "suburb", "Main trading name", "Business name", "Entity type"]


def get_text_columns_for_chunk(df: pd.DataFrame) -> list[str]:
    """Pick text-like columns from chunk for classification."""
    preferred = ["business_name", "suburb", "Business name", "Main trading name", "Entity type", "Entity name"]
    return [c for c in preferred if c in df.columns]


def classify_record(text: str) -> Optional[str]:
    """
    Classify text into best-matching category.
    Returns category key or None if no match.
    Prefer more specific categories (check specific before general).
    """
    if not text:
        return None
    searchable = strip_punctuation_for_search(text)
    searchable_lower = searchable.lower()

    # Order: check specific categories first, automotive_general last
    ordered = [
        k for k in CATEGORY_KEYWORDS.keys()
        if k != "automotive_general"
    ] + ["automotive_general"]

    for cat in ordered:
        keywords = CATEGORY_KEYWORDS[cat]
        for kw in keywords:
            if kw in searchable_lower:
                return cat

    return None


def classify_chunk(df: pd.DataFrame, text_columns: Optional[list[str]] = None) -> pd.DataFrame:
    """
    Add category column to chunk. Combines text from available columns.
    """
    if text_columns is None:
        text_columns = get_text_columns_for_chunk(df)
    if not text_columns:
        df = df.copy()
        df["category"] = None
        return df

    def get_text(row: pd.Series) -> str:
        cols = [c for c in text_columns if c in row.index]
        return build_searchable_text(row, cols)

    df = df.copy()
    df["_search_text"] = df.apply(get_text, axis=1)
    df["category"] = df["_search_text"].apply(classify_record)
    df = df.drop(columns=["_search_text"], errors="ignore")
    return df


def filter_automotive_only(df: pd.DataFrame) -> pd.DataFrame:
    """Keep only rows with a category (i.e. automotive-relevant)."""
    if "category" not in df.columns:
        return pd.DataFrame()
    return df[df["category"].notna() & (df["category"] != "")].copy()
