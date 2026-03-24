"""Load suburb master and stream ABR bulk extract in chunks."""

import logging
from pathlib import Path
from typing import Generator, Optional

import pandas as pd

from config import CHUNKSIZE
from src.utils import get_abr_column_map, get_suburb_column_map

logger = logging.getLogger(__name__)


def load_suburbs(path: Path) -> pd.DataFrame:
    """Load suburb master CSV. Normalize column names to logical names."""
    path = Path(path)
    if not path.exists():
        raise FileNotFoundError(f"Suburb file not found: {path}")

    df = pd.read_csv(path, encoding="utf-8", on_bad_lines="skip")
    mapping = get_suburb_column_map(path)
    rename = {v: k for k, v in mapping.items() if v}
    if rename:
        df = df.rename(columns=rename)
    logger.info("Loaded %d suburb records from %s", len(df), path.name)
    return df


def stream_abr_chunks(
    path: Path,
    column_map: dict[str, Optional[str]],
    chunksize: int = CHUNKSIZE,
) -> Generator[pd.DataFrame, None, None]:
    """
    Stream ABR CSV in chunks. Each chunk has logical column names applied.
    Only yields chunks that have at least one mapped text column.
    """
    path = Path(path)
    if not path.exists():
        raise FileNotFoundError(f"ABR file not found: {path}")

    rename = {v: k for k, v in column_map.items() if v}
    for chunk in pd.read_csv(
        path,
        chunksize=chunksize,
        encoding="utf-8",
        on_bad_lines="skip",
        low_memory=False,
    ):
        if rename:
            chunk = chunk.rename(columns={k: v for k, v in rename.items() if k in chunk.columns})
        yield chunk


def inspect_abr_columns(path: Path) -> dict[str, Optional[str]]:
    """Inspect ABR file and return column mapping. Log what was found."""
    mapping = get_abr_column_map(path)
    for logical, actual in mapping.items():
        if actual:
            logger.info("ABR column mapping: %s -> %s", logical, actual)
        else:
            logger.warning("ABR column not found: %s", logical)
    return mapping
