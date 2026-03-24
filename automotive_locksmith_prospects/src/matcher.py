"""Match records to suburb master."""

import logging
from typing import Optional

import pandas as pd

from src.utils import normalize_text

logger = logging.getLogger(__name__)


def build_suburb_lookup(suburbs_df: pd.DataFrame) -> dict[tuple[str, str], dict]:
    """
    Build lookup from (suburb_normalized, state) -> suburb record.
    suburb_df should have columns: suburb, state, postcode (logical names).
    """
    lookup: dict[tuple[str, str], dict] = {}
    for _, row in suburbs_df.iterrows():
        sub_raw = row.get("suburb", row.get("locality", ""))
        state_raw = row.get("state", row.get("state_code", ""))
        sub = normalize_text(str(sub_raw))
        state = normalize_text(str(state_raw))
        if len(state) >= 2:
            state = state[:2].upper()
        if sub:
            state = state or "  "
            key = (sub, state)
            if key not in lookup:
                lookup[key] = {
                    "suburb": sub_raw if sub_raw else sub,
                    "state": state_raw if state_raw else state,
                    "postcode": row.get("postcode"),
                }
    logger.info("Built suburb lookup with %d (suburb,state) keys", len(lookup))
    return lookup


def match_to_suburb(
    suburb_raw: str,
    state_raw: Optional[str],
    postcode_raw: Optional[str],
    lookup: dict[tuple[str, str], dict],
) -> Optional[dict]:
    """
    Try to match a record to suburb master.
    Returns suburb record dict or None.
    """
    sub_norm = normalize_text(suburb_raw) if suburb_raw else ""
    state_norm = None
    if state_raw:
        s = normalize_text(str(state_raw))
        if len(s) >= 2:
            state_norm = s[:2].upper()

    if not sub_norm:
        return None

    if state_norm:
        key = (sub_norm, state_norm)
        if key in lookup:
            return lookup[key]

    # Try without state
    for (s, st), rec in lookup.items():
        if s == sub_norm:
            return rec

    return None


def enrich_chunk_with_suburb(
    df: pd.DataFrame,
    lookup: dict[tuple[str, str], dict],
) -> pd.DataFrame:
    """
    Enrich chunk with matched suburb/state/postcode from master.
    Adds suburb_matched, state_matched, postcode_matched when found.
    """
    def match_row(row: pd.Series) -> Optional[dict]:
        sub = row.get("suburb_normalized") or row.get("suburb", "")
        state = row.get("state_normalized") or row.get("state")
        postcode = row.get("postcode_normalized") or row.get("postcode")
        return match_to_suburb(str(sub), state, postcode, lookup)

    df = df.copy()
    matches = df.apply(match_row, axis=1)
    df["suburb_matched"] = [m["suburb"] if m else None for m in matches]
    df["state_matched"] = [m["state"] if m else None for m in matches]
    df["postcode_matched"] = [m["postcode"] if m else None for m in matches]
    # Prefer matched values for final suburb/state/postcode
    df["suburb"] = df["suburb_matched"].fillna(df.get("suburb_normalized", ""))
    df["state"] = df["state_matched"].fillna(df.get("state_normalized", ""))
    df["postcode"] = df["postcode_matched"].fillna(df.get("postcode_normalized", ""))
    return df
