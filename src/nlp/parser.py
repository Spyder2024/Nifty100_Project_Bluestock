"""
Analysis text parser — extracts structured CAGR / metric values from the
free-text fields in analysis.xlsx.

Regex strategy:
  Primary:   (\d+)\s*Years?:?\s*(-?[\d.]+)%      — "10 Years: 21%", "5 Year  14%"
  Extended:  (TTM|1 Year|Last Year):?\s*(-?[\d.]+)% — "TTM: 43%", "1 Year: -2%"

Outputs:
  output/analysis_parsed.csv       — successfully parsed rows
  output/parse_failures.csv        — rows / fields that did not match
  output/cross_validation.csv      — divergence flags (>5%) against DB
"""

from __future__ import annotations

import csv
import re
import sqlite3
import sys
from pathlib import Path
from typing import Optional

import pandas as pd

# ── Paths ───────────────────────────────────────────────────────────────────
PROJECT_ROOT = Path(__file__).resolve().parents[2]
OUTPUT_DIR = PROJECT_ROOT / "output"
OUTPUT_DIR.mkdir(exist_ok=True)

# ── Auto-discover analysis.xlsx ────────────────────────────────────────────
# Search order: data/raw/ > output/ > upload/nifty100_extracted/data/raw/
_CANDIDATE_PATHS = [
    PROJECT_ROOT / "data" / "raw" / "analysis.xlsx",
    PROJECT_ROOT / "output" / "analysis.xlsx",
    PROJECT_ROOT / "upload" / "nifty100_extracted" / "data" / "raw" / "analysis.xlsx",
]


def _find_analysis_file() -> Path:
    """Locate analysis.xlsx by searching common project locations."""
    for p in _CANDIDATE_PATHS:
        if p.exists():
            return p
    raise FileNotFoundError(
        "analysis.xlsx not found in any of:\n"
        + "\n".join(f"  - {p}" for p in _CANDIDATE_PATHS)
    )


def _find_db() -> Path:
    """Locate nifty100.db by searching common project locations."""
    candidates = [
        PROJECT_ROOT / "db" / "nifty100.db",
        PROJECT_ROOT / "output" / "nifty100.db",
    ]
    for p in candidates:
        if p.exists():
            return p
    return PROJECT_ROOT / "db" / "nifty100.db"  # default even if missing


ANALYSIS_XLSX: Path = _find_analysis_file()
DB_PATH: Path = _find_db()

# ── Regex patterns ──────────────────────────────────────────────────────────
# Primary: matches "10 Years: 21%", "5 Year  14%", "3Years 18%"
RE_YEARS = re.compile(r"(\d+)\s*Years?:?\s*(-?[\d.]+)%", re.IGNORECASE)

# Extended: matches "TTM: 43%", "1 Year: -2%", "Last Year: 12%"
RE_EXTENDED = re.compile(r"(TTM|1\s*Year|Last\s*Year):?\s*(-?[\d.]+)%", re.IGNORECASE)

# Map extended period labels to canonical string
_EXTENDED_PERIOD_MAP = {
    "ttm": "TTM",
    "1 year": "1",
    "last year": "Last",
}

# ── Metric → DB column mapping for cross-validation ────────────────────────
_DB_CAGR_MAP: dict[tuple[str, str], str] = {
    ("compounded_sales_growth", "3"): "revenue_cagr_3yr",
    ("compounded_sales_growth", "5"): "revenue_cagr_5yr",
    ("compounded_sales_growth", "10"): "revenue_cagr_10yr",
    ("compounded_profit_growth", "3"): "pat_cagr_3yr",
    ("compounded_profit_growth", "5"): "pat_cagr_5yr",
    ("compounded_profit_growth", "10"): "pat_cagr_10yr",
}

TARGET_FIELDS = [
    "compounded_sales_growth",
    "compounded_profit_growth",
    "stock_price_cagr",
    "roe",
]


# ── Parsing logic ───────────────────────────────────────────────────────────


def parse_single_cell(text: str) -> tuple[Optional[str], Optional[float]] | None:
    """Extract (period, value) from a single text cell.

    Returns None if neither regex matches.
    """
    if not isinstance(text, str) or not text.strip():
        return None

    text = text.strip()

    # Try primary: "10 Years: 21%"
    m = RE_YEARS.search(text)
    if m:
        period = m.group(1)
        value = float(m.group(2))
        return (period, value)

    # Try extended: "TTM: 43%", "1 Year: -2%", "Last Year: 12%"
    m = RE_EXTENDED.search(text)
    if m:
        period_label = m.group(1).strip().lower()
        period = _EXTENDED_PERIOD_MAP.get(period_label, period_label.title())
        value = float(m.group(2))
        return (period, value)

    return None


def load_analysis() -> pd.DataFrame:
    """Load analysis.xlsx, auto-detecting and skipping any title banner row."""
    global ANALYSIS_XLSX

    # Read raw to detect banner
    raw = pd.read_excel(ANALYSIS_XLSX, header=None, nrows=2)

    # Row 0 is a banner if it contains non-numeric text spanning columns
    first_cell = str(raw.iloc[0, 0]).strip() if not pd.isna(raw.iloc[0, 0]) else ""
    is_banner = any(
        kw in first_cell.lower()
        for kw in ("bluestock", "fintech", "nifty", "analysis", "records")
    )

    if is_banner:
        df = pd.read_excel(ANALYSIS_XLSX, header=1)
    else:
        df = pd.read_excel(ANALYSIS_XLSX, header=0)

    df.columns = df.columns.str.strip().str.lower().str.replace(" ", "_")
    return df


def parse_all(df: pd.DataFrame) -> tuple[list[dict], list[dict]]:
    """Parse every target field for every row."""
    parsed: list[dict] = []
    failures: list[dict] = []

    for _, row in df.iterrows():
        company_id = str(row.get("company_id", "")).strip()
        row_id = str(row.get("id", "")).strip()

        for metric in TARGET_FIELDS:
            raw_text = str(row.get(metric, "")).strip()

            result = parse_single_cell(raw_text)
            if result is not None:
                period_str, value = result
                parsed.append(
                    {
                        "row_id": row_id,
                        "company_id": company_id,
                        "metric_type": metric,
                        "raw_text": raw_text,
                        "period_label": period_str,
                        "value_pct": value,
                    }
                )
            elif raw_text and raw_text.lower() not in ("nan", "none", ""):
                failures.append(
                    {
                        "row_id": row_id,
                        "company_id": company_id,
                        "metric_type": metric,
                        "raw_text": raw_text,
                        "reason": "No regex match",
                    }
                )

    return parsed, failures


# ── Cross-validation against DB ────────────────────────────────────────────


def cross_validate(
    parsed: list[dict],
    divergence_pct: float = 5.0,
) -> list[dict]:
    """Compare parsed CAGR values against financial_ratios in the DB."""
    if not DB_PATH.exists():
        print(f"  [SKIP] DB not found at {DB_PATH} — skipping cross-validation.")
        return []

    try:
        conn = sqlite3.connect(str(DB_PATH))
    except Exception as e:
        print(f"  [SKIP] Cannot connect to DB: {e}")
        return []

    try:
        fr_df = pd.read_sql("SELECT * FROM financial_ratios", conn)
    except Exception:
        # Table may be named 'ratios' instead of 'financial_ratios'
        try:
            fr_df = pd.read_sql("SELECT * FROM ratios", conn)
        except Exception as e2:
            print(f"  [SKIP] Cannot read ratios table: {e2}")
            conn.close()
            return []

    conn.close()

    if fr_df.empty:
        print("  [SKIP] Ratios table is empty — skipping cross-validation.")
        return []

    divergences: list[dict] = []

    for entry in parsed:
        metric = entry["metric_type"]
        period = entry["period_label"]
        company = entry["company_id"]
        parsed_val = entry["value_pct"]

        # Only validate numeric year periods
        if period not in ("3", "5", "10"):
            continue

        db_col = _DB_CAGR_MAP.get((metric, period))
        if db_col is None:
            continue

        company_rows = fr_df[fr_df["company_id"] == company]
        if company_rows.empty:
            continue

        valid = company_rows.dropna(subset=[db_col])
        if valid.empty:
            continue

        latest = valid.sort_values("year", ascending=False, na_position="last").iloc[0]
        db_val = float(latest[db_col])
        latest_year = latest["year"]

        diff = abs(parsed_val - db_val)
        if diff > divergence_pct:
            divergences.append(
                {
                    "company_id": company,
                    "metric_type": metric,
                    "period_years": period,
                    "parsed_value": parsed_val,
                    "db_column": db_col,
                    "db_value": db_val,
                    "db_year": latest_year,
                    "divergence_pct": round(diff, 2),
                    "flag": "REVIEW",
                }
            )

    return divergences


# ── Output writers ──────────────────────────────────────────────────────────


def write_parsed(records: list[dict], path: Path) -> None:
    """Write parsed results to CSV."""
    if not records:
        print(f"  [WARN] No parsed records to write — {path.name} not created.")
        return
    columns = [
        "row_id",
        "company_id",
        "metric_type",
        "raw_text",
        "period_label",
        "value_pct",
    ]
    with open(path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=columns, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(records)
    print(f"  [OK] {len(records)} parsed rows → {path.name}")


def write_failures(records: list[dict], path: Path) -> None:
    """Write parse failures to CSV."""
    columns = ["row_id", "company_id", "metric_type", "raw_text", "reason"]
    with open(path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=columns, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(records)
    if records:
        print(f"  [WARN] {len(records)} entries unmatched → {path.name}")
    else:
        print(f"  [OK] 0 failures → {path.name}")


def write_cross_validation(records: list[dict], path: Path) -> None:
    """Write cross-validation divergence report — only if there are results."""
    if not records:
        print(f"  [OK] No divergences (or DB empty) — {path.name} not created.")
        return
    columns = [
        "company_id",
        "metric_type",
        "period_years",
        "parsed_value",
        "db_column",
        "db_value",
        "db_year",
        "divergence_pct",
        "flag",
    ]
    with open(path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=columns, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(records)
    print(f"  [FLAG] {len(records)} divergences > 5% → {path.name}")


# ── Main ────────────────────────────────────────────────────────────────────


def main() -> None:
    print("=" * 60)
    print("  NLP Analysis Text Parser — Day 29")
    print("=" * 60)

    # 1. Load
    print("\n[1/4] Loading analysis.xlsx ...")
    print(f"       Path: {ANALYSIS_XLSX}")
    try:
        df = load_analysis()
        print(f"       {len(df)} rows × {len(df.columns)} cols")
        print(f"       Columns: {list(df.columns)}")
    except FileNotFoundError as e:
        print(f"       ERROR: {e}")
        sys.exit(1)

    # 2. Parse
    cells_to_parse = len(df) * len(TARGET_FIELDS)
    print(f"\n[2/4] Parsing {cells_to_parse} cells ...")
    parsed, failures = parse_all(df)
    print(f"       Matched: {len(parsed)}  |  Failed: {len(failures)}")

    # 3. Cross-validate
    print("\n[3/4] Cross-validating against DB ...")
    print(f"       DB path: {DB_PATH}")
    divergences = cross_validate(parsed)

    # 4. Write outputs
    print(f"\n[4/4] Writing outputs to {OUTPUT_DIR}/ ...")
    write_parsed(parsed, OUTPUT_DIR / "analysis_parsed.csv")
    write_failures(failures, OUTPUT_DIR / "parse_failures.csv")
    write_cross_validation(divergences, OUTPUT_DIR / "cross_validation.csv")

    # Summary
    print(f"\n{'=' * 60}")
    print(
        f"  Parsed: {len(parsed)} | Failures: {len(failures)} | Divergences: {len(divergences)}"
    )
    print(f"{'=' * 60}")


if __name__ == "__main__":
    main()
