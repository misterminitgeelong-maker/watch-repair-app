"""Lead scoring 0-100 based on data quality and category importance."""

import logging
from typing import Optional

import pandas as pd

from config import CATEGORY_LABELS, HIGH_VALUE_CATEGORIES

logger = logging.getLogger(__name__)


def score_record(
    category: Optional[str],
    has_abn: bool,
    has_suburb: bool,
    has_postcode: bool,
    has_state: bool,
    business_name: str,
) -> int:
    """
    Compute lead score 0-100.
    Factors: category importance, ABN, suburb, postcode, state, name quality.
    """
    score = 0

    # Category (0-35)
    if category:
        if category in HIGH_VALUE_CATEGORIES:
            score += 35
        else:
            score += 20

    # ABN present (0-15)
    if has_abn:
        score += 15

    # Location completeness (0-25)
    if has_suburb:
        score += 8
    if has_postcode:
        score += 8
    if has_state:
        score += 9

    # Business name quality (0-25)
    name = (business_name or "").strip()
    if len(name) >= 3:
        score += 5
    if len(name) >= 5:
        score += 5
    if len(name) >= 10 and " " in name:
        score += 5
    if len(name) > 5 and not any(c in name.lower() for c in ["pty", "ltd"]):
        score += 5  # Looks like trading name

    return min(100, score)


def apply_scoring(df: pd.DataFrame) -> pd.DataFrame:
    """Add lead_score column to dataframe."""
    df = df.copy()

    def row_score(row: pd.Series) -> int:
        abn = row.get("abn_normalized") or row.get("abn")
        has_abn = bool(abn and str(abn).strip())

        suburb = row.get("suburb") or row.get("suburb_normalized")
        has_suburb = bool(suburb and str(suburb).strip())

        postcode = row.get("postcode") or row.get("postcode_normalized")
        has_postcode = bool(postcode and str(postcode).strip())

        state = row.get("state") or row.get("state_normalized")
        has_state = bool(state and str(state).strip())

        name = row.get("business_name_clean") or row.get("business_name", "")

        return score_record(
            row.get("category"),
            has_abn,
            has_suburb,
            has_postcode,
            has_state,
            str(name),
        )

    df["lead_score"] = df.apply(row_score, axis=1)
    return df
