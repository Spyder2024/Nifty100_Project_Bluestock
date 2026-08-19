"""src/analytics/cashflow_kpis.py — Cash flow KPIs and capital allocation classifier.

Sprint 2, Day 11 & Sprint 5, Day 31-32

Functions:
    free_cash_flow              — FCF = CFO + CFI
    cfo_quality_score           — Average CFO/PAT over years → quality label
    capex_intensity             — |CFI| / sales × 100 → intensity label
    fcf_conversion_rate         — FCF / operating_profit × 100
    capital_allocation_pattern  — 8-pattern classifier from (CFO, CFI, CFF) signs
    classify_capital_allocation — Full classification dict for one company-year
    generate_capital_allocation_csv — Writes output/capital_allocation.csv
    generate_pattern_changes    — Writes output/pattern_changes.csv
"""

from __future__ import annotations

import csv
import glob
import logging
import sqlite3
import sys
import warnings
from pathlib import Path
from typing import Optional

import numpy as np
import pandas as pd

warnings.filterwarnings("ignore")
logger = logging.getLogger(__name__)

# ── ensure UTF-8 output ───────────────────────────────────────
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

# ── resolve project root ──────────────────────────────────────
PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

# ── auto-discover paths ───────────────────────────────────────
DB_CANDIDATES = [
    PROJECT_ROOT / "output" / "nifty100.db",
    PROJECT_ROOT / "data" / "output" / "nifty100.db",
    PROJECT_ROOT / "db" / "nifty100.db",
    "output/nifty100.db",
    "data/output/nifty100.db",
    "nifty100.db",
    "db/nifty100.db",
]
CSV_CANDIDATES = [
    PROJECT_ROOT / "data" / "raw" / "cashflow.xlsx",
    PROJECT_ROOT / "data" / "cash_flow.csv",
    "data/raw/cashflow.xlsx",
    "data/cash_flow.csv",
    "cash_flow.csv",
    "output/cash_flow.csv",
]


def _find(paths, pattern=None):
    """Find first existing path, or glob if pattern given."""
    for p in paths:
        if Path(p).exists():
            return Path(p)
    if pattern:
        for f in glob.glob(pattern, recursive=True):
            return Path(f)
    return None


DB_PATH = _find(DB_CANDIDATES)
CF_CSV = _find(CSV_CANDIDATES, "**/*cash*flow*.xlsx")
OUT_DIR = PROJECT_ROOT / "output"

# ── column aliases (CSV → canonical) ──────────────────────────
_CF_ALIASES = {
    "operating_activity": "operating_cf",
    "operating_cf": "operating_cf",
    "cash_from_operating_activity": "operating_cf",
    "investing_activity": "investing_cf",
    "investing_cf": "investing_cf",
    "cash_from_investing_activity": "investing_cf",
    "financing_activity": "financing_cf",
    "financing_cf": "financing_cf",
    "cash_from_financing_activity": "financing_cf",
    "net_cash_flow": "net_cash_flow",
    "net_cashflow": "net_cash_flow",
}


# ===========================================================================
# Core cash-flow KPIs (Sprint 2 Unit-Tested Functions)
# ===========================================================================

def free_cash_flow(
    operating_cf: Optional[float],
    investing_cf: Optional[float],
) -> Optional[float]:
    """Free Cash Flow = operating_cf + investing_cf.

    Negative values are allowed (company spending more than it generates).
    Returns None if either input is missing.
    """
    if operating_cf is None or investing_cf is None:
        return None
    try:
        ocf = float(operating_cf)
        icf = float(investing_cf)
        if np.isnan(ocf) or np.isnan(icf):
            return None
        return round(ocf + icf, 2)
    except (ValueError, TypeError):
        return None


def cfo_quality_score(
    cfo_values: list[Optional[float]],
    pat_values: list[Optional[float]],
) -> Optional[str]:
    """CFO Quality based on average CFO/PAT ratio over available years.

    Classification:
        > 1.0   → ``"High Quality"``
        0.5-1.0 → ``"Moderate"``
        < 0.5   → ``"Accrual Risk"``

    Returns None if no valid (non-zero PAT) year-pairs exist.
    """
    ratios: list[float] = []
    for cfo, pat in zip(cfo_values, pat_values):
        if cfo is None or pat is None:
            continue
        try:
            cfo_f = float(cfo)
            pat_f = float(pat)
            if np.isnan(cfo_f) or np.isnan(pat_f) or pat_f == 0:
                continue
            ratios.append(cfo_f / pat_f)
        except (ValueError, TypeError):
            continue

    if not ratios:
        return None

    avg_ratio = sum(ratios) / len(ratios)

    if avg_ratio > 1.0:
        return "High Quality"
    if avg_ratio >= 0.5:
        return "Moderate"
    return "Accrual Risk"


def capex_intensity(
    investing_cf: Optional[float],
    sales: Optional[float],
) -> tuple[Optional[float], str]:
    """CapEx Intensity = |investing_cf| / sales × 100.

    Classification:
        < 3%   → ``"Asset Light"``
        3-8%   → ``"Moderate"``
        > 8%   → ``"Capital Intensive"``

    Returns ``(None, "")`` if sales is zero or any input is missing.
    """
    if investing_cf is None or sales is None:
        return None, ""
    try:
        inv = float(investing_cf)
        s = float(sales)
        if np.isnan(inv) or np.isnan(s) or s == 0:
            return None, ""
        intensity = round(abs(inv) / s * 100, 2)
        if intensity < 3.0:
            return intensity, "Asset Light"
        if intensity <= 8.0:
            return intensity, "Moderate"
        return intensity, "Capital Intensive"
    except (ValueError, TypeError):
        return None, ""


def fcf_conversion_rate(
    fcf: Optional[float],
    operating_profit: Optional[float],
) -> Optional[float]:
    """FCF Conversion Rate = (FCF / operating_profit) × 100.

    Returns None if operating_profit is zero or any input is missing.
    """
    if fcf is None or operating_profit is None:
        return None
    try:
        fcf_f = float(fcf)
        op_f = float(operating_profit)
        if np.isnan(fcf_f) or np.isnan(op_f) or op_f == 0:
            return None
        return round((fcf_f / op_f) * 100, 2)
    except (ValueError, TypeError):
        return None


# ===========================================================================
# Capital allocation 8-pattern classifier
# ===========================================================================

_SIGN_PATTERN_MAP: dict[tuple[int, int, int], str] = {
    ( 1, -1, -1): "Reinvestor",                # (+,-,-)
    ( 1,  1, -1): "Liquidating Assets",         # (+,+,-)
    (-1,  1,  1): "Distress Signal",            # (-,+,+)
    (-1, -1,  1): "Growth Funded by Debt",     # (-,-,+)
    ( 1,  1,  1): "Cash Accumulator",           # (+,+,+)
    (-1, -1, -1): "Pre-Revenue",                # (-,-,-)
    ( 1, -1,  1): "Mixed",                      # (+,-,+)
    (-1,  1, -1): "Unusual",                    # (-,+,-)
}


def _sign(value: Optional[float]) -> int:
    """Return +1, -1, or 0 for a numeric value."""
    if value is None:
        return 0
    try:
        v = float(value)
        if np.isnan(v) or v == 0:
            return 0
        return 1 if v > 0 else -1
    except (ValueError, TypeError):
        return 0


def capital_allocation_pattern(
    cfo: Optional[float],
    cfi: Optional[float],
    cff: Optional[float],
    cfo_pat_ratio: Optional[float] = None,
    high_cfo_pat_threshold: float = 1.5,
) -> str:
    """Classify a company-year into one of 8 capital-allocation patterns.

    Parameters
    ----------
    cfo, cfi, cff   : Cash flow from operating / investing / financing.
    cfo_pat_ratio   : Pre-computed CFO ÷ PAT ratio (optional).
    high_cfo_pat_threshold : Ratio above which a Reinvestor is
                      reclassified as *Shareholder Returns* (default 1.5).

    Returns
    -------
    Pattern label string.
    """
    s_cfo = _sign(cfo)
    s_cfi = _sign(cfi)
    s_cff = _sign(cff)

    key = (s_cfo, s_cfi, s_cff)
    label = _SIGN_PATTERN_MAP.get(key, "Unclassified")

    # Override: (+,-,-) with high CFO/PAT → Shareholder Returns
    if (
        label == "Reinvestor"
        and cfo_pat_ratio is not None
        and cfo_pat_ratio > high_cfo_pat_threshold
    ):
        label = "Shareholder Returns"

    return label


def classify_capital_allocation(
    cfo: Optional[float],
    cfi: Optional[float],
    cff: Optional[float],
    cfo_pat_ratio: Optional[float] = None,
) -> dict:
    """Return a full classification dict for one company-year.

    Returns ``{cfo_sign, cfi_sign, cff_sign, pattern_label}``.
    """
    return dict(
        cfo_sign=_sign(cfo),
        cfi_sign=_sign(cfi),
        cff_sign=_sign(cff),
        pattern_label=capital_allocation_pattern(
            cfo, cfi, cff, cfo_pat_ratio
        ),
    )


ALLOCATION_CSV_COLUMNS = [
    "company_id", "year",
    "cfo_sign", "cfi_sign", "cff_sign",
    "pattern_label",
]


def generate_capital_allocation_csv(
    rows: list[dict],
    output_path: str | Path = "output/capital_allocation.csv",
) -> None:
    """Write capital-allocation classifications to CSV.

    Parameters
    ----------
    rows : List of dicts, each containing at least
           ``company_id``, ``year``, ``cfo_sign``,
           ``cfi_sign``, ``cff_sign``, ``pattern_label``.
    """
    p = Path(output_path)
    if not p.is_absolute():
        p = PROJECT_ROOT / p
    p.parent.mkdir(parents=True, exist_ok=True)
    with open(p, "w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=ALLOCATION_CSV_COLUMNS)
        writer.writeheader()
        for row in rows:
            writer.writerow({k: row.get(k, "") for k in ALLOCATION_CSV_COLUMNS})

    logger.info(
        "Capital allocation CSV written: %d rows → %s",
        len(rows), p,
    )


# ===========================================================================
# Group-Level Helpers & Analytics
# ===========================================================================

def _f(val):
    """Safely convert value to float or None."""
    if val is None:
        return None
    try:
        v = float(val)
        return v if np.isfinite(v) else None
    except (ValueError, TypeError):
        return None


def _load_cashflow_csv() -> pd.DataFrame:
    """Load cash flow data from DB table cash_flow or Excel/CSV source file."""
    # 1. Prefer database table if available & populated
    if DB_PATH and Path(DB_PATH).exists():
        try:
            conn = sqlite3.connect(DB_PATH)
            cur = conn.cursor()
            cur.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='cash_flow'")
            if cur.fetchone():
                df_db = pd.read_sql_query("SELECT * FROM cash_flow", conn)
                
                # Check if ATGL is missing in DB but AGTL is in raw Excel, auto-backfill
                cur.execute("SELECT count(*) FROM cash_flow WHERE company_id='ATGL'")
                if cur.fetchone()[0] == 0 and CF_CSV and Path(CF_CSV).exists():
                    try:
                        raw_df = pd.read_excel(CF_CSV, skiprows=1)
                        if "company_id" in raw_df.columns:
                            atgl_raw = raw_df[raw_df["company_id"] == "AGTL"]
                            if not atgl_raw.empty:
                                from src.etl.normaliser import normalize_year
                                for _, r in atgl_raw.iterrows():
                                    yr = normalize_year(str(r["year"])) or str(r["year"]).strip()
                                    cur.execute("""
                                        INSERT OR REPLACE INTO cash_flow 
                                        (company_id, year, operating_cf, investing_cf, financing_cf, net_cash_flow)
                                        VALUES (?, ?, ?, ?, ?, ?)
                                    """, ("ATGL", yr, float(r["operating_activity"]), float(r["investing_activity"]), float(r["financing_activity"]), float(r["net_cash_flow"])))
                                conn.commit()
                                df_db = pd.read_sql_query("SELECT * FROM cash_flow", conn)
                    except Exception as exc:
                        logger.debug("ATGL backfill note: %s", exc)

                conn.close()
                if not df_db.empty and "operating_cf" in df_db.columns and df_db["operating_cf"].notna().any():
                    logger.info("Loaded %d cash flow rows directly from DB (%s)", len(df_db), DB_PATH)
                    co_col = "company_name" if "company_name" in df_db.columns else "company_id"
                    df_db.rename(columns={co_col: "company_name"}, inplace=True)
                    df_db["company_name"] = df_db["company_name"].astype(str).str.strip()
                    df_db["year"] = df_db["year"].astype(str).str.strip()
                    for c in ("operating_cf", "investing_cf", "financing_cf", "net_cash_flow"):
                        if c in df_db.columns:
                            df_db[c] = pd.to_numeric(df_db[c], errors="coerce")
                    return df_db
            conn.close()
        except Exception as err:
            logger.warning("Error reading cash_flow table from DB: %s", err)

    if not CF_CSV:
        sys.exit("[ERROR] cash_flow data source not found.")

    # 2. Fallback to file (.xlsx or .csv)
    str_path = str(CF_CSV).lower()
    if str_path.endswith((".xlsx", ".xls")):
        try:
            preview = pd.read_excel(CF_CSV, nrows=2)
            col0 = str(preview.columns[0]).lower() if len(preview.columns) > 0 else ""
            if "cash flow" in col0:
                df = pd.read_excel(CF_CSV, skiprows=1)
            else:
                df = pd.read_excel(CF_CSV)
        except Exception as err:
            sys.exit(f"[ERROR] Failed to read Excel file {CF_CSV}: {err}")
    else:
        try:
            df = pd.read_csv(CF_CSV)
        except (UnicodeDecodeError, pd.errors.ParserError):
            df = pd.read_excel(CF_CSV, skiprows=1)

    company_col = None
    for ck in ("company_name", "company_id", "company_", "name", "company"):
        if ck in df.columns:
            company_col = ck
            break
    if company_col is None:
        sys.exit(f"[ERROR] No company column in file. Columns: {list(df.columns)}")

    df.rename(columns={company_col: "company_name"}, inplace=True)

    rename_map = {}
    for col in df.columns:
        cl = str(col).strip().lower()
        if cl in _CF_ALIASES:
            rename_map[col] = _CF_ALIASES[cl]
    df.rename(columns=rename_map, inplace=True)

    for c in ("operating_cf", "investing_cf", "financing_cf", "net_cash_flow"):
        if c in df.columns:
            df[c] = pd.to_numeric(df[c], errors="coerce")

    df["company_name"] = df["company_name"].astype(str).str.strip()
    df["company_name"] = df["company_name"].replace({"AGTL": "ATGL"})

    try:
        from src.etl.normaliser import normalize_year
        df["year"] = df["year"].apply(lambda y: normalize_year(str(y)) or str(y).strip())
    except Exception:
        df["year"] = df["year"].astype(str).str.strip()

    return df


def _load_db_data():
    """Load ratios and balance_sheet for cross-referencing."""
    if not DB_PATH or not Path(DB_PATH).exists():
        return pd.DataFrame(), pd.DataFrame()

    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute(
        "SELECT name FROM sqlite_master "
        "WHERE type='table' AND name IN ('ratios','financial_ratios') LIMIT 1"
    )
    row = cur.fetchone()
    ratios_table = row[0] if row else None

    ratios_df = pd.DataFrame()
    if ratios_table:
        ratios_df = pd.read_sql_query(f"SELECT * FROM {ratios_table}", conn)
        co_col = "company_name" if "company_name" in ratios_df.columns else "company_id"
        if co_col in ratios_df.columns:
            ratios_df.rename(columns={co_col: "company_name"}, inplace=True)
            ratios_df["company_name"] = ratios_df["company_name"].astype(str).str.strip()
        if "year" in ratios_df.columns:
            ratios_df["year"] = ratios_df["year"].astype(str).str.strip()

    bs_df = pd.DataFrame()
    cur.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name='balance_sheet' LIMIT 1"
    )
    if cur.fetchone():
        bs_df = pd.read_sql_query("SELECT * FROM balance_sheet", conn)
        co_col = "company_name" if "company_name" in bs_df.columns else "company_id"
        if co_col in bs_df.columns:
            bs_df.rename(columns={co_col: "company_name"}, inplace=True)
            bs_df["company_name"] = bs_df["company_name"].astype(str).str.strip()
        if "year" in bs_df.columns:
            bs_df["year"] = bs_df["year"].astype(str).str.strip()
        for c in ("borrowings", "total_assets", "reserves"):
            if c in bs_df.columns:
                bs_df[c] = pd.to_numeric(bs_df[c], errors="coerce")

    # income statement for revenue / PAT
    cur.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name='income_statement' LIMIT 1"
    )
    if cur.fetchone():
        is_df = pd.read_sql_query("SELECT company_id, year, revenue, net_income FROM income_statement", conn)
        if not is_df.empty:
            co_col = "company_name" if "company_name" in is_df.columns else "company_id"
            is_df.rename(columns={co_col: "company_name", "net_income": "net_profit"}, inplace=True)
            is_df["company_name"] = is_df["company_name"].astype(str).str.strip()
            is_df["year"] = is_df["year"].astype(str).str.strip()
            if ratios_df.empty:
                ratios_df = is_df
            else:
                for c in ("revenue", "net_profit"):
                    if c not in ratios_df.columns and c in is_df.columns:
                        ratios_df = ratios_df.merge(is_df[["company_name", "year", c]], on=["company_name", "year"], how="left")

    conn.close()
    return ratios_df, bs_df


def compute_cfo_quality(group: pd.DataFrame) -> tuple[Optional[float], str]:
    """Compute CFO Quality Score = mean(operating_cf / PAT) over available years."""
    ocf_vals = group["operating_cf"].dropna()
    if ocf_vals.empty:
        return None, "Data Unavailable"

    pat_col = None
    for c in ("net_profit", "net_income", "pat", "profit_after_tax"):
        if c in group.columns and group[c].notna().any():
            pat_col = c
            break

    if pat_col is None:
        if "net_profit_margin" in group.columns and "revenue" in group.columns:
            group["_pat"] = group["net_profit_margin"] * group["revenue"] / 100.0
            pat_col = "_pat"
        else:
            ocf_recent = ocf_vals.tail(3).mean()
            ocf_older = ocf_vals.head(3).mean() if len(ocf_vals) > 3 else ocf_recent
            if ocf_recent is None or pd.isna(ocf_recent):
                return None, "Data Unavailable"
            if ocf_recent > 0:
                return round(min(ocf_recent / (abs(ocf_older) + 1), 1.5), 2), "Proxy (no PAT)"
            return round(ocf_recent / (abs(ocf_older) + 1), 2), "Proxy (no PAT)"

    ratios = []
    for _, r in group.iterrows():
        ocf = _f(r.get("operating_cf"))
        pat = _f(r.get(pat_col))
        if ocf is not None and pat is not None and pat != 0:
            ratios.append(ocf / pat)

    if not ratios:
        return None, "Data Unavailable"

    avg_ratio = round(float(np.mean(ratios)), 2)

    if avg_ratio > 1.0:
        label = "High Quality"
    elif avg_ratio >= 0.5:
        label = "Moderate"
    else:
        label = "Accrual Risk"

    return avg_ratio, label


def compute_capex_intensity(group: pd.DataFrame) -> tuple[Optional[float], str]:
    """CapEx Intensity = mean(|investing_cf| / revenue * 100)."""
    inv_vals = group["investing_cf"].dropna()
    if inv_vals.empty:
        return None, "Data Unavailable"

    rev_col = None
    for c in ("revenue", "sales", "net_sales", "total_revenue"):
        if c in group.columns and group[c].notna().any():
            rev_col = c
            break

    if rev_col is None:
        avg_abs_inv = inv_vals.abs().mean()
        return round(avg_abs_inv, 2), "No Revenue Data"

    intensities = []
    for _, r in group.iterrows():
        inv = _f(r.get("investing_cf"))
        rev = _f(r.get(rev_col))
        if inv is not None and rev is not None and rev != 0:
            intensities.append(abs(inv) / rev * 100)

    if not intensities:
        return None, "Data Unavailable"

    avg_intensity = round(float(np.mean(intensities)), 2)

    if avg_intensity < 3:
        label = "Asset Light"
    elif avg_intensity <= 8:
        label = "Moderate"
    else:
        label = "Capital Intensive"

    return avg_intensity, label


def check_distress_signal(group: pd.DataFrame) -> tuple[Optional[bool], str]:
    """Distress Signal: operating_cf < 0 AND financing_cf > 0 in the latest year."""
    latest = group.sort_values("year", ascending=False).head(1)
    if latest.empty:
        return False, "N/A"

    row = latest.iloc[0]
    ocf = _f(row.get("operating_cf"))
    fcf_fin = _f(row.get("financing_cf"))

    if ocf is None or fcf_fin is None:
        return None, "Data Unavailable"

    if ocf < 0 and fcf_fin > 0:
        return True, "ALERT"
    return False, "Healthy"


def check_deleveraging(group: pd.DataFrame, bs_df: Optional[pd.DataFrame] = None) -> tuple[Optional[bool], str]:
    """Deleveraging: financing_cf < 0 (paying down debt) AND borrowings declining YoY."""
    latest = group.sort_values("year", ascending=False).head(1)
    if latest.empty:
        return None, "N/A"

    row = latest.iloc[0]
    fin_cf = _f(row.get("financing_cf"))
    if fin_cf is None:
        return None, "Data Unavailable"

    if fin_cf >= 0:
        return False, "Not Deleveraging"

    company = row.get("company_name", "")

    if bs_df is not None and not bs_df.empty and "borrowings" in bs_df.columns:
        co_bs = bs_df[bs_df["company_name"].str.lower() == str(company).lower()]
        if len(co_bs) >= 2:
            co_bs = co_bs.sort_values("year", ascending=False)
            latest_borrow = _f(co_bs.iloc[0].get("borrowings"))
            prev_borrow = _f(co_bs.iloc[1].get("borrowings"))
            if latest_borrow is not None and prev_borrow is not None:
                if latest_borrow < prev_borrow:
                    return True, "Deleveraging"
                return False, "Paying but Borrowings Up"
            return True, "Likely Deleveraging"

    return True, "Likely Deleveraging (no BS data)"


# ===========================================================================
# Day 32 Deliverables: Distribution & YoY Pattern Changes
# ===========================================================================

def generate_pattern_changes(
    df_alloc: pd.DataFrame,
    output_path: str | Path = "output/pattern_changes.csv",
) -> pd.DataFrame:
    """Build a report showing companies that changed their pattern year-over-year.

    Parameters
    ----------
    df_alloc : DataFrame containing columns [company_id, year, pattern_label]
    output_path : destination path for CSV report

    Returns
    -------
    DataFrame of pattern changes.
    """
    changes = []
    for cid, grp in df_alloc.groupby("company_id"):
        grp = grp.sort_values("year").reset_index(drop=True)
        for i in range(1, len(grp)):
            prev_p = grp.loc[i - 1, "pattern_label"]
            curr_p = grp.loc[i, "pattern_label"]
            prev_y = grp.loc[i - 1, "year"]
            curr_y = grp.loc[i, "year"]
            if prev_p != curr_p:
                changes.append({
                    "company_id": cid,
                    "from_year": prev_y,
                    "to_year": curr_y,
                    "from_pattern": prev_p,
                    "to_pattern": curr_p,
                    "change_description": f"{cid} moved from {prev_p} ({prev_y}) to {curr_p} ({curr_y})",
                })

    chg_df = pd.DataFrame(changes)
    p = Path(output_path)
    if not p.is_absolute():
        p = PROJECT_ROOT / p
    p.parent.mkdir(parents=True, exist_ok=True)
    chg_df.to_csv(p, index=False)
    logger.info("Pattern changes report saved: %d changes → %s", len(chg_df), p)
    return chg_df


def get_pattern_distribution(
    df_alloc: pd.DataFrame,
    latest_only: bool = True,
) -> pd.DataFrame:
    """Generate distribution count and percentage across all 8 patterns.

    Parameters
    ----------
    df_alloc : DataFrame containing columns [company_id, year, pattern_label]
    latest_only : if True, filters for the latest available year per company.

    Returns
    -------
    DataFrame with columns [pattern_label, count, percentage]
    """
    data = df_alloc.copy()
    if latest_only:
        data = data.sort_values("year").groupby("company_id").last().reset_index()

    total = len(data)
    all_patterns = [
        "Reinvestor",
        "Shareholder Returns",
        "Liquidating Assets",
        "Distress Signal",
        "Growth Funded by Debt",
        "Cash Accumulator",
        "Pre-Revenue",
        "Mixed",
        "Unusual",
        "Unclassified",
    ]

    counts = data["pattern_label"].value_counts().to_dict()
    dist_rows = []
    for pat in all_patterns:
        cnt = counts.get(pat, 0)
        pct = round((cnt / total * 100), 2) if total > 0 else 0.0
        dist_rows.append({
            "pattern_label": pat,
            "count": cnt,
            "percentage": pct,
        })

    return pd.DataFrame(dist_rows)


# ===========================================================================
# Main Execution Orchestrator
# ===========================================================================

def main():
    print("=" * 70)
    print("Day 32 — Capital Allocation Report & Cash Flow Intelligence")
    print("=" * 70)

    # 1. Load data
    cf_df = _load_cashflow_csv()
    ratios_df, bs_df = _load_db_data()

    print(f"[INFO] Cash flow records : {len(cf_df)} rows")
    print(f"[INFO] Ratios records    : {len(ratios_df)} rows")
    print(f"[INFO] Balance sheet rows: {len(bs_df)} rows")

    # Merge ratios / PAT for CFO/PAT ratio override
    if not ratios_df.empty and "company_name" in ratios_df.columns:
        merge_cols = ["company_name", "year"]
        if "year" in ratios_df.columns:
            for df in (cf_df, ratios_df):
                df["year"] = df["year"].astype(str).str.strip()
            
            keep_cols = ["company_name", "year"]
            for c in ("net_profit", "net_income", "net_profit_margin", "revenue", "roe"):
                if c in ratios_df.columns and c not in keep_cols:
                    keep_cols.append(c)

            cf_df = cf_df.merge(
                ratios_df[keep_cols],
                on=merge_cols,
                how="left",
                suffixes=("", "_ratio"),
            )

    # 2. Compute Capital Allocation Pattern for all 92 companies x all years
    alloc_rows = []
    for _, r in cf_df.iterrows():
        cid = r["company_name"]
        yr = r["year"]
        ocf = _f(r.get("operating_cf"))
        icf = _f(r.get("investing_cf"))
        cff = _f(r.get("financing_cf"))
        
        pat = _f(r.get("net_profit") or r.get("net_income"))
        cfo_pat = (ocf / pat) if (pat is not None and pat != 0 and ocf is not None) else None

        classification = classify_capital_allocation(ocf, icf, cff, cfo_pat_ratio=cfo_pat)
        alloc_rows.append({
            "company_id": cid,
            "year": yr,
            "cfo_sign": classification["cfo_sign"],
            "cfi_sign": classification["cfi_sign"],
            "cff_sign": classification["cff_sign"],
            "pattern_label": classification["pattern_label"],
            "cfo_pat_ratio": round(cfo_pat, 2) if cfo_pat is not None else None,
        })

    alloc_df = pd.DataFrame(alloc_rows)

    # 3. Save capital_allocation.csv
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    cap_alloc_csv_path = OUT_DIR / "capital_allocation.csv"
    generate_capital_allocation_csv(alloc_rows, output_path=cap_alloc_csv_path)
    print(f"[OUTPUT] {cap_alloc_csv_path} ({len(alloc_df)} rows for {alloc_df['company_id'].nunique()} companies)")

    # 4. Generate Distribution Summary for Latest Year
    dist_latest = get_pattern_distribution(alloc_df, latest_only=True)
    print("\n" + "─" * 50)
    print("Latest Year Capital Allocation Distribution (92 Companies):")
    print("─" * 50)
    for _, r in dist_latest[dist_latest["count"] > 0].iterrows():
        print(f"  {r['pattern_label']:<24} : {int(r['count']):>2} companies ({r['percentage']:>5.1f}%)")
    print("─" * 50)

    # 5. Build YoY Pattern Changes Report
    pattern_changes_path = OUT_DIR / "pattern_changes.csv"
    chg_df = generate_pattern_changes(alloc_df, output_path=pattern_changes_path)
    print(f"[OUTPUT] {pattern_changes_path} ({len(chg_df)} YoY pattern shifts recorded)")

    # 6. Compute company-level KPIs & include capital_allocation for cashflow_intelligence.xlsx
    results = []
    distress_rows = []

    # Map latest pattern to each company
    latest_patterns = (
        alloc_df.sort_values("year")
        .groupby("company_id")
        .last()[["pattern_label", "cfo_sign", "cfi_sign", "cff_sign"]]
        .to_dict(orient="index")
    )

    for company, group in cf_df.groupby("company_name"):
        group = group.sort_values("year").copy()
        if len(group) < 1:
            continue

        cfo_score, cfo_label = compute_cfo_quality(group)
        capex_int, capex_label = compute_capex_intensity(group)
        is_distress, distress_label = check_distress_signal(group)
        is_delev, delev_label = check_deleveraging(group, bs_df)

        latest = group.iloc[-1]
        latest_ocf = _f(latest.get("operating_cf"))
        latest_inv = _f(latest.get("investing_cf"))
        latest_fin = _f(latest.get("financing_cf"))
        latest_ncf = _f(latest.get("net_cash_flow"))
        latest_year = latest.get("year", "")

        pat_info = latest_patterns.get(company, {})
        cap_pattern = pat_info.get("pattern_label", "Unclassified")

        ocf_series = group["operating_cf"].dropna()
        ocf_trend = "N/A"
        if len(ocf_series) >= 2:
            recent_avg = ocf_series.tail(3).mean()
            older_avg = ocf_series.head(max(1, len(ocf_series) - 3)).mean()
            if pd.notna(recent_avg) and pd.notna(older_avg) and older_avg != 0:
                change = (recent_avg - older_avg) / abs(older_avg) * 100
                ocf_trend = f"{'↑' if change > 0 else '↓'} {abs(change):.1f}%"

        row = {
            "company_name": company,
            "latest_year": latest_year,
            "capital_allocation_pattern": cap_pattern,
            "operating_cf": latest_ocf,
            "investing_cf": latest_inv,
            "financing_cf": latest_fin,
            "net_cash_flow": latest_ncf,
            "cfo_quality_score": cfo_score,
            "cfo_quality_label": cfo_label,
            "capex_intensity_pct": capex_int,
            "capex_intensity_label": capex_label,
            "distress_signal": is_distress,
            "distress_label": distress_label,
            "deleveraging_flag": is_delev,
            "deleveraging_label": delev_label,
            "ocf_5yr_trend": ocf_trend,
            "data_years": len(group),
        }
        results.append(row)

        if is_distress is True:
            distress_rows.append({
                "company_name": company,
                "latest_year": latest_year,
                "operating_cf": latest_ocf,
                "financing_cf": latest_fin,
                "signal": "DISTRESS",
                "reason": f"CFO={latest_ocf}, CFF={latest_fin}",
            })

    result_df = pd.DataFrame(results)

    # Sort: distress first, then by CFO quality descending
    result_df["_distress_sort"] = result_df["distress_signal"].apply(
        lambda x: 0 if x is True else 1
    )
    result_df = result_df.sort_values(
        ["_distress_sort", "cfo_quality_score"],
        ascending=[True, False],
        na_position="last",
    ).drop(columns=["_distress_sort"]).reset_index(drop=True)

    # 7. Write cashflow_intelligence.xlsx with enhanced sheets
    xlsx_path = OUT_DIR / "cashflow_intelligence.xlsx"
    with pd.ExcelWriter(xlsx_path, engine="openpyxl") as writer:
        result_df.to_excel(writer, sheet_name="Cashflow Intelligence", index=False)

        # Summary sheet
        summary_rows = [
            {"Metric": "Total Companies Analyzed", "Count": len(result_df)},
            {"Metric": "High Quality CFO", "Count": len(result_df[result_df["cfo_quality_label"] == "High Quality"])},
            {"Metric": "Moderate CFO", "Count": len(result_df[result_df["cfo_quality_label"] == "Moderate"])},
            {"Metric": "Accrual Risk", "Count": len(result_df[result_df["cfo_quality_label"] == "Accrual Risk"])},
            {"Metric": "Asset Light", "Count": len(result_df[result_df["capex_intensity_label"] == "Asset Light"])},
            {"Metric": "Capital Intensive", "Count": len(result_df[result_df["capex_intensity_label"] == "Capital Intensive"])},
            {"Metric": "Distress Alerts", "Count": len(result_df[result_df["distress_signal"] == True])},
            {"Metric": "Deleveraging", "Count": len(result_df[result_df["deleveraging_flag"] == True])},
        ]
        pd.DataFrame(summary_rows).to_excel(writer, sheet_name="Summary", index=False)

        # Capital Allocation Distribution sheet
        dist_latest.to_excel(writer, sheet_name="Capital Allocation Dist", index=False)

        # Pattern Changes sheet (YoY)
        chg_df.to_excel(writer, sheet_name="Pattern Changes YoY", index=False)

    print(f"[OUTPUT] {xlsx_path} (updated with capital_allocation_pattern & distribution)")

    # 8. Distress alerts CSV
    distress_path = OUT_DIR / "distress_alerts.csv"
    if distress_rows:
        distress_df = pd.DataFrame(distress_rows)
        distress_df.to_csv(distress_path, index=False)
        print(f"[OUTPUT] {distress_path} ({len(distress_df)} alerts)")
    else:
        pd.DataFrame(columns=["company_name", "latest_year", "operating_cf", "financing_cf", "signal", "reason"]).to_csv(distress_path, index=False)
        print(f"[OUTPUT] {distress_path} (0 alerts)")

    print(f"\n{'─' * 50}")
    print(f"Companies analysed : {len(result_df)}")
    print(f"CFO High Quality   : {len(result_df[result_df['cfo_quality_label'] == 'High Quality'])}")
    print(f"Distress Signals   : {len(distress_rows)}")
    print(f"Deleveraging       : {len(result_df[result_df['deleveraging_flag'] == True])}")
    print(f"{'─' * 50}")
    print("[DONE] Day 32 Capital Allocation Report generated successfully.")


if __name__ == "__main__":
    main()