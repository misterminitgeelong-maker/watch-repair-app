"""Clean and normalize ABR records."""

import logging
import re
from typing import Any, Optional

import pandas as pd

from config import STATE_NORMALIZE
from src.utils import normalize_text

logger = logging.getLogger(__name__)


def normalize_abn(value: Any) -> Optional[str]:
    """Extract digits only from ABN. Return None if invalid."""
    if value is None or (isinstance(value, float) and pd.isna(value)):
        return None
    s = re.sub(r"\D", "", str(value))
    if len(s) == 11 or len(s) == 9:  # ABN can be 11 digits, ACN 9
        return s
    if 9 <= len(s) <= 11:
        return s
    return s if s else None


def normalize_postcode(value: Any) -> Optional[str]:
    """Extract 4-digit postcode for Australia."""
    if value is None or (isinstance(value, float) and pd.isna(value)):
        return None
    s = re.sub(r"\D", "", str(value))
    if len(s) == 4:
        return s
    if len(s) > 4:
        return s[:4]
    return s if s else None


def normalize_state(value: Any) -> Optional[str]:
    """Normalize state to 2-letter code (NSW, VIC, etc.)."""
    if value is None or (isinstance(value, float) and pd.isna(value)):
        return None
    s = normalize_text(str(value))
    s = re.sub(r"[^\w\s]", "", s)
    for key, code in STATE_NORMALIZE.items():
        if key in s or s == key[:2] or s == key[:3]:
            return code
    if len(s) >= 2:
        return s[:2].upper()
    return None


def normalize_suburb(value: Any) -> str:
    """Normalize suburb name for matching."""
    if value is None or (isinstance(value, float) and pd.isna(value)):
        return ""
    s = str(value).strip()
    s = re.sub(r"\s+", " ", s)
    return s


def clean_business_name(value: Any) -> str:
    """Clean business name for quality scoring."""
    if value is None or (isinstance(value, float) and pd.isna(value)):
        return ""
    s = str(value).strip()
    s = re.sub(r"\s+", " ", s)
    return s


def apply_cleaning(df: pd.DataFrame) -> pd.DataFrame:
    """
    Apply cleaning to ABR chunk. Creates/updates normalized columns.
    Expects logical column names: business_name, abn, state, postcode, suburb.
    """
    out = df.copy()
    if "business_name" in out.columns:
        out["business_name_clean"] = out["business_name"].apply(clean_business_name)
    else:
        out["business_name_clean"] = ""

    if "abn" in out.columns:
        out["abn_normalized"] = out["abn"].apply(normalize_abn)
    else:
        out["abn_normalized"] = None

    if "postcode" in out.columns:
        out["postcode_normalized"] = out["postcode"].apply(normalize_postcode)
    else:
        out["postcode_normalized"] = None

    if "state" in out.columns:
        out["state_normalized"] = out["state"].apply(normalize_state)
    else:
        out["state_normalized"] = None

    if "suburb" in out.columns:
        out["suburb_normalized"] = out["suburb"].apply(normalize_suburb)
    else:
        out["suburb_normalized"] = ""

    return out
