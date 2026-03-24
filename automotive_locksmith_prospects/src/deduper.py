"""Deduplication logic using ABN, name+postcode, and optional fuzzy matching."""

import logging
from typing import Optional

import pandas as pd

from config import FUZZY_DUPLICATE_THRESHOLD, FUZZY_MIN_LENGTH
from src.utils import normalize_text

logger = logging.getLogger(__name__)

try:
    from rapidfuzz import fuzz
    RAPIDFUZZ_AVAILABLE = True
except ImportError:
    RAPIDFUZZ_AVAILABLE = False


def dedupe_by_abn(df: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    """
    Split into unique by ABN and duplicates.
    Keeps first occurrence when ABN duplicates.
    """
    if "abn_normalized" not in df.columns:
        return df, pd.DataFrame()

    valid_abn = df["abn_normalized"].notna() & (df["abn_normalized"] != "")
    with_abn = df[valid_abn].copy()
    without_abn = df[~valid_abn].copy()

    if with_abn.empty:
        return df, pd.DataFrame()

    first_abn = with_abn.drop_duplicates(subset=["abn_normalized"], keep="first")
    abn_dupes = with_abn[~with_abn.index.isin(first_abn.index)]

    result = pd.concat([first_abn, without_abn], ignore_index=True)
    return result, abn_dupes


def name_postcode_key(row: pd.Series) -> str:
    """Build key for name+postcode deduplication."""
    name = normalize_text(str(row.get("business_name_clean", row.get("business_name", ""))))
    postcode = str(row.get("postcode_normalized") or row.get("postcode", ""))[:4]
    return f"{name}|{postcode}"


def dedupe_by_name_postcode(df: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    """
    Split into unique by (normalized name, postcode) and duplicates.
    """
    df = df.copy()
    df["_np_key"] = df.apply(name_postcode_key, axis=1)
    first = df.drop_duplicates(subset=["_np_key"], keep="first")
    dupes = df[~df.index.isin(first.index)]
    first = first.drop(columns=["_np_key"], errors="ignore")
    dupes = dupes.drop(columns=["_np_key"], errors="ignore")
    return first, dupes


def fuzzy_duplicate_pairs(df: pd.DataFrame) -> list[tuple[int, int, float]]:
    """
    Find potential fuzzy duplicates. Returns list of (idx1, idx2, score).
    Only considers records with name length >= FUZZY_MIN_LENGTH.
    """
    if not RAPIDFUZZ_AVAILABLE:
        return []

    pairs: list[tuple[int, int, float]] = []
    names = df.get("business_name_clean", df.get("business_name", pd.Series([""] * len(df))))
    postcodes = df.get("postcode_normalized", df.get("postcode", pd.Series([""] * len(df))))

    for i in range(len(df)):
        n1 = str(names.iloc[i]) if i < len(names) else ""
        pc1 = str(postcodes.iloc[i]) if i < len(postcodes) else ""
        if len(n1) < FUZZY_MIN_LENGTH:
            continue
        for j in range(i + 1, len(df)):
            n2 = str(names.iloc[j]) if j < len(names) else ""
            pc2 = str(postcodes.iloc[j]) if j < len(postcodes) else ""
            if n1 == n2 and pc1 == pc2:
                continue
            if pc1 and pc2 and pc1 != pc2:
                continue  # Different postcode, likely not duplicate
            if len(n2) < FUZZY_MIN_LENGTH:
                continue
            score = fuzz.ratio(n1, n2)
            if score >= FUZZY_DUPLICATE_THRESHOLD:
                pairs.append((int(df.index[i]), int(df.index[j]), float(score)))

    return pairs


def run_deduplication(df: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    """
    Full deduplication pipeline.
    Returns (prospects_clean, duplicates_review).
    """
    working = df.copy()
    review_parts: list[pd.DataFrame] = []

    # 1. ABN dedupe
    working, abn_dupes = dedupe_by_abn(working)
    if not abn_dupes.empty:
        abn_dupes = abn_dupes.copy()
        abn_dupes["duplicate_reason"] = "abn_duplicate"
        review_parts.append(abn_dupes)

    # 2. Name+postcode dedupe
    working, np_dupes = dedupe_by_name_postcode(working)
    if not np_dupes.empty:
        np_dupes = np_dupes.copy()
        np_dupes["duplicate_reason"] = "name_postcode_duplicate"
        review_parts.append(np_dupes)

    # 3. Fuzzy duplicates -> add to review only (don't remove)
    if RAPIDFUZZ_AVAILABLE and len(working) < 10_000:
        pairs = fuzzy_duplicate_pairs(working)
        if pairs:
            seen = set()
            fuzzy_rows = []
            for i, j, score in pairs:
                if i not in seen and j not in seen:
                    row = working.loc[i].copy()
                    row["duplicate_reason"] = f"fuzzy_match_{score:.0f}"
                    row["fuzzy_match_score"] = score
                    fuzzy_rows.append(row)
            if fuzzy_rows:
                review_parts.append(pd.DataFrame(fuzzy_rows))

    duplicates_review = pd.concat(review_parts, ignore_index=True) if review_parts else pd.DataFrame()
    return working, duplicates_review
