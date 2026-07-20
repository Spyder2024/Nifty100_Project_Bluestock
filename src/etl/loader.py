"""Excel file loader for Nifty 100 ETL pipeline."""

import logging
from pathlib import Path
from typing import Optional

import pandas as pd

from src.etl.normaliser import normalize_ticker, normalize_year

logger = logging.getLogger(__name__)

# Project root (one level up from src/)
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent

# File paths
RAW_DIR = PROJECT_ROOT / "data" / "raw"
SUPPORT_DIR = PROJECT_ROOT / "data" / "supporting"

# Core files: Row 0 is metadata, Row 1 is actual headers
CORE_FILES: list[dict[str, str]] = [
    {"name": "companies", "file": "companies.xlsx"},
    {"name": "profitandloss", "file": "profitandloss.xlsx"},
    {"name": "balancesheet", "file": "balancesheet.xlsx"},
    {"name": "cashflow", "file": "cashflow.xlsx"},
    {"name": "analysis", "file": "analysis.xlsx"},
    {"name": "documents", "file": "documents.xlsx"},
    {"name": "prosandcons", "file": "prosandcons.xlsx"},
]

# Supplementary files: Row 0 IS the header
SUPPORT_FILES: list[dict[str, str]] = [
    {"name": "sectors", "file": "sectors.xlsx"},
    {"name": "stock_prices", "file": "stock_prices.xlsx"},
    {"name": "market_cap", "file": "market_cap.xlsx"},
    {"name": "financial_ratios", "file": "financial_ratios.xlsx"},
    {"name": "peer_groups", "file": "peer_groups.xlsx"},
]


def load_excel(
    file_path: Path,
    header_row: int = 0,
    sheet_name: Optional[str] = None,
) -> pd.DataFrame:
    """Load a single Excel file into a DataFrame.

    Args:
        file_path: Absolute path to .xlsx file.
        header_row: Row number to use as column headers (0-indexed).
        sheet_name: Specific sheet name. None = first sheet.

    Returns:
        Loaded DataFrame.

    Raises:
        FileNotFoundError: If file does not exist.
    """
    if not file_path.exists():
        raise FileNotFoundError(f"Data file not found: {file_path}")

    df = pd.read_excel(file_path, header=header_row, sheet_name=0)
    logger.info(
        "Loaded %s — %d rows, %d cols (header_row=%d)",
        file_path.name,
        len(df),
        len(df.columns),
        header_row,
    )
    return df


def load_core_file(name: str) -> pd.DataFrame:
    """Load a core dataset file (header=1).

    Args:
        name: Dataset name, e.g. 'companies', 'profitandloss'.

    Returns:
        Loaded DataFrame with metadata row skipped.
    """
    file_info = next((f for f in CORE_FILES if f["name"] == name), None)
    if file_info is None:
        raise ValueError(
            f"Unknown core dataset: '{name}'. "
            f"Valid: {[f['name'] for f in CORE_FILES]}"
        )
    file_path = RAW_DIR / file_info["file"]
    return load_excel(file_path, header_row=1)


def load_support_file(name: str) -> pd.DataFrame:
    """Load a supplementary dataset file (header=0).

    Args:
        name: Dataset name, e.g. 'sectors', 'stock_prices'.

    Returns:
        Loaded DataFrame.
    """
    file_info = next((f for f in SUPPORT_FILES if f["name"] == name), None)
    if file_info is None:
        raise ValueError(
            f"Unknown supporting dataset: '{name}'. "
            f"Valid: {[f['name'] for f in SUPPORT_FILES]}"
        )
    file_path = SUPPORT_DIR / file_info["file"]
    return load_excel(file_path, header_row=0)


def load_all_core() -> dict[str, pd.DataFrame]:
    """Load all 7 core Excel files into a dictionary of DataFrames.

    Returns:
        Dict mapping dataset name → DataFrame.
    """
    datasets: dict[str, pd.DataFrame] = {}
    for file_info in CORE_FILES:
        try:
            df = load_excel(RAW_DIR / file_info["file"], header_row=1)
            datasets[file_info["name"]] = df
        except FileNotFoundError:
            logger.error("Core file missing: %s", file_info["file"])
    return datasets


def load_all_supporting() -> dict[str, pd.DataFrame]:
    """Load all 5 supplementary Excel files into a dictionary of DataFrames.

    Returns:
        Dict mapping dataset name → DataFrame.
    """
    datasets: dict[str, pd.DataFrame] = {}
    for file_info in SUPPORT_FILES:
        try:
            df = load_excel(SUPPORT_DIR / file_info["file"], header_row=0)
            datasets[file_info["name"]] = df
        except FileNotFoundError:
            logger.error("Supporting file missing: %s", file_info["file"])
    return datasets


def normalise_company_id(df: pd.DataFrame) -> pd.DataFrame:
    """Normalise company_id column: strip, uppercase, validate length.

    Args:
        df: DataFrame with a 'company_id' column.

    Returns:
        DataFrame with normalised company_id. Invalid rows dropped.
    """
    if "company_id" not in df.columns:
        logger.warning("No 'company_id' column found — skipping normalisation")
        return df

    original_count = len(df)
    df["company_id"] = df["company_id"].apply(normalize_ticker)
    df = df.dropna(subset=["company_id"])
    dropped = original_count - len(df)
    if dropped > 0:
        logger.warning("Dropped %d rows with invalid company_id", dropped)
    return df


def normalise_year_column(df: pd.DataFrame) -> pd.DataFrame:
    """Normalise 'year' column using normalize_year().

    Args:
        df: DataFrame with a 'year' column.

    Returns:
        DataFrame with normalised year. Unparseable rows dropped.
    """
    if "year" not in df.columns:
        logger.warning("No 'year' column found — skipping normalisation")
        return df

    original_count = len(df)
    # Convert year to string before parsing
    df["year"] = df["year"].astype(str).apply(normalize_year)
    df = df.dropna(subset=["year"])
    dropped = original_count - len(df)
    if dropped > 0:
        logger.warning("Dropped %d rows with unparseable year values", dropped)
    return df
