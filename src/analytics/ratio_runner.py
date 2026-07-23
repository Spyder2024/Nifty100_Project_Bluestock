"""
Day 12 — Ratio Runner
Populates financial_ratios table for all 92 companies using Days 8-11 functions.
Handles: schema creation, Excel loading, ratio computation, DB write, verification.
"""

from __future__ import annotations

import logging
import sqlite3
import sys
from pathlib import Path
from typing import Optional

import numpy as np
import pandas as pd

# --- Add project root to path so src.* imports work ---
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from src.analytics.ratios import (
    asset_turnover,
    interest_coverage_ratio,
    is_high_leverage,
    is_low_icr_warning,
    net_debt,
    net_profit_margin,
    operating_profit_margin,
    return_on_assets,
    return_on_capital_employed,
    return_on_equity,
)
from src.analytics.cagr import compute_all_cagrs
from src.analytics.cashflow_kpis import (
    capex_intensity,
    free_cash_flow,
    capital_allocation_pattern,
    classify_capital_allocation,
    fcf_conversion_rate,
    cfo_quality_score,
)

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------
DB_PATH = PROJECT_ROOT / "db" / "nifty100.db"
SCHEMA_PATH = PROJECT_ROOT / "db" / "schema.sql"
DATA_DIR = PROJECT_ROOT / "data"  # Excel files live here

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)
log = logging.getLogger(__name__)


# =========================================================================
# STEP 1 — Schema bootstrapper
# =========================================================================
def ensure_schema(conn: sqlite3.Connection) -> None:
    """Create all tables defined in schema.sql if they don't already exist."""
    if SCHEMA_PATH.exists():
        sql = SCHEMA_PATH.read_text(encoding="utf-8")
        conn.executescript(sql)
        conn.commit()
        log.info("Schema applied from %s", SCHEMA_PATH)
    else:
        log.warning("schema.sql not found at %s — creating minimal tables", SCHEMA_PATH)
        _create_minimal_tables(conn)


def _create_minimal_tables(conn: sqlite3.Connection) -> None:
    """Fallback: create the 4 source tables + financial_ratios if schema.sql is missing."""
    conn.executescript("""
    CREATE TABLE IF NOT EXISTS companies (
        id            TEXT PRIMARY KEY,
        company_name  TEXT NOT NULL,
        face_value    REAL DEFAULT 1,
        sector_id     TEXT
    );
    CREATE TABLE IF NOT EXISTS income_statement (
        company_id   TEXT NOT NULL,
        year         TEXT NOT NULL,
        sales        REAL,
        expenses     REAL,
        operating_profit REAL,
        opm_percentage  REAL,
        other_income REAL,
        interest     REAL,
        depreciation REAL,
        profit_before_tax REAL,
        tax_percentage   REAL,
        net_profit   REAL,
        eps          REAL,
        dividend_payout REAL,
        PRIMARY KEY (company_id, year)
    );
    CREATE TABLE IF NOT EXISTS balance_sheet (
        company_id   TEXT NOT NULL,
        year         TEXT NOT NULL,
        equity_capital   REAL,
        reserves     REAL,
        borrowings   REAL,
        other_liabilities REAL,
        total_liabilities REAL,
        fixed_assets REAL,
        cwip         REAL,
        investments  REAL,
        other_asset  REAL,
        total_assets REAL,
        PRIMARY KEY (company_id, year)
    );
    CREATE TABLE IF NOT EXISTS cash_flow (
        company_id   TEXT NOT NULL,
        year         TEXT NOT NULL,
        operating_activity  REAL,
        investing_activity  REAL,
        financing_activity  REAL,
        net_cash_flow       REAL,
        PRIMARY KEY (company_id, year)
    );
    CREATE TABLE IF NOT EXISTS financial_ratios (
        company_id   TEXT NOT NULL,
        year         TEXT NOT NULL,
        net_profit_margin_pct       REAL,
        operating_profit_margin_pct REAL,
        return_on_equity_pct        REAL,
        return_on_capital_employed_pct REAL,
        return_on_assets_pct        REAL,
        debt_to_equity              REAL,
        interest_coverage           REAL,
        is_high_leverage            INTEGER,
        is_low_icr_warning          INTEGER,
        net_debt_cr                 REAL,
        asset_turnover              REAL,
        free_cash_flow_cr           REAL,
        capex_intensity             REAL,
        fcf_conversion_rate         REAL,
        cfo_quality_score           REAL,
        capital_allocation_pattern  TEXT,
        earnings_per_share          REAL,
        book_value_per_share        REAL,
        dividend_payout_ratio_pct   REAL,
        total_debt_cr               REAL,
        cash_from_operations_cr     REAL,
        revenue_cagr_3yr            REAL,
        revenue_cagr_5yr            REAL,
        revenue_cagr_10yr           REAL,
        pat_cagr_3yr                REAL,
        pat_cagr_5yr                REAL,
        pat_cagr_10yr               REAL,
        eps_cagr_3yr                REAL,
        eps_cagr_5yr                REAL,
        eps_cagr_10yr               REAL,
        composite_quality_score     REAL,
        PRIMARY KEY (company_id, year)
    );
    """)
    conn.commit()
    log.info("Minimal tables created (fallback)")


# =========================================================================
# STEP 2 — Excel loader
# =========================================================================
def _normalize_year(year_val) -> str:
    """Convert various year formats to YYYY-MM string.

    Handles: 'Mar-23', 'March 2023', '2023-03', '2023', datetime objects, etc.
    """
    if pd.isna(year_val):
        return ""
    s = str(year_val).strip()

    # Already YYYY-MM
    if len(s) == 7 and s[4] == "-":
        return s

    # "Mar-23" or "Mar-2023"
    month_map = {
        "jan": "01", "feb": "02", "mar": "03", "apr": "04",
        "may": "05", "jun": "06", "jul": "07", "aug": "08",
        "sep": "09", "oct": "10", "nov": "11", "dec": "12",
    }
    parts = s.replace("-", " ").replace("/", " ").split()
    for p in parts:
        lp = p.lower()
        if lp in month_map:
            mm = month_map[lp]
            # find the year part
            for p2 in parts:
                if p2.lower() not in month_map:
                    yr = p2
                    if len(yr) == 2:
                        yr = "20" + yr
                    return f"{yr}-{mm}"
    # Fallback: "2023" → "2023-03" (assume March year-end)
    if s.isdigit() and len(s) == 4:
        return f"{s}-03"

    # Try pandas parsing
    try:
        dt = pd.to_datetime(s)
        return dt.strftime("%Y-%m")
    except Exception:
        return s


def _safe_float(val) -> Optional[float]:
    """Convert a value to float; return None for NaN/empty/invalid."""
    if val is None or (isinstance(val, float) and np.isnan(val)):
        return None
    try:
        return float(val)
    except (ValueError, TypeError):
        return None


def load_companies(conn: sqlite3.Connection) -> int:
    """Load companies from companies.xlsx into SQLite. Returns row count."""
    path = DATA_DIR / "companies.xlsx"
    if not path.exists():
        log.error("companies.xlsx not found at %s", path)
        return 0

    df = pd.read_excel(path, header=1)  # Row 0 is metadata; Row 1 = headers
    df.columns = [c.strip().lower().replace(" ", "_") for c in df.columns]

    # Normalize
    df["id"] = df["id"].astype(str).str.strip().str.upper()
    df["company_name"] = df["company_name"].astype(str).str.replace("\n", " ").str.strip()

    count = 0
    for _, row in df.iterrows():
        try:
            conn.execute(
                """INSERT OR REPLACE INTO companies (id, company_name, face_value)
                   VALUES (?, ?, ?)""",
                (row["id"], row["company_name"], _safe_float(row.get("face_value", 1)) or 1),
            )
            count += 1
        except Exception as e:
            log.warning("Skip company %s: %s", row.get("id", "?"), e)

    conn.commit()
    log.info("Loaded %d companies", count)
    return count


def load_income_statements(conn: sqlite3.Connection) -> int:
    """Load profitandloss.xlsx → income_statement table. Returns row count."""
    path = DATA_DIR / "profitandloss.xlsx"
    if not path.exists():
        log.error("profitandloss.xlsx not found at %s", path)
        return 0

    df = pd.read_excel(path, header=1)
    df.columns = [c.strip().lower().replace(" ", "_") for c in df.columns]
    df["company_id"] = df["company_id"].astype(str).str.strip().str.upper()
    df["year"] = df["year"].apply(_normalize_year)

    numeric_cols = [
        "sales", "expenses", "operating_profit", "opm_percentage",
        "other_income", "interest", "depreciation", "profit_before_tax",
        "tax_percentage", "net_profit", "eps", "dividend_payout",
    ]

    count = 0
    for _, row in df.iterrows():
        cid = row.get("company_id", "")
        yr = row.get("year", "")
        if not cid or not yr:
            continue
        try:
            vals = {c: _safe_float(row.get(c)) for c in numeric_cols}
            conn.execute(
                """INSERT OR REPLACE INTO income_statement
                   (company_id, year, sales, expenses, operating_profit,
                    opm_percentage, other_income, interest, depreciation,
                    profit_before_tax, tax_percentage, net_profit, eps,
                    dividend_payout)
                   VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                (cid, yr, *[vals[c] for c in numeric_cols]),
            )
            count += 1
        except Exception as e:
            log.warning("Skip IS %s %s: %s", cid, yr, e)

    conn.commit()
    log.info("Loaded %d income_statement rows", count)
    return count


def load_balance_sheets(conn: sqlite3.Connection) -> int:
    """Load balancesheet.xlsx → balance_sheet table. Returns row count."""
    path = DATA_DIR / "balancesheet.xlsx"
    if not path.exists():
        log.error("balancesheet.xlsx not found at %s", path)
        return 0

    df = pd.read_excel(path, header=1)
    df.columns = [c.strip().lower().replace(" ", "_") for c in df.columns]
    df["company_id"] = df["company_id"].astype(str).str.strip().str.upper()
    df["year"] = df["year"].apply(_normalize_year)

    numeric_cols = [
        "equity_capital", "reserves", "borrowings", "other_liabilities",
        "total_liabilities", "fixed_assets", "cwip", "investments",
        "other_asset", "total_assets",
    ]

    count = 0
    for _, row in df.iterrows():
        cid = row.get("company_id", "")
        yr = row.get("year", "")
        if not cid or not yr:
            continue
        try:
            vals = {c: _safe_float(row.get(c)) for c in numeric_cols}
            conn.execute(
                """INSERT OR REPLACE INTO balance_sheet
                   (company_id, year, equity_capital, reserves, borrowings,
                    other_liabilities, total_liabilities, fixed_assets, cwip,
                    investments, other_asset, total_assets)
                   VALUES (?,?,?,?,?,?,?,?,?,?,?,?)""",
                (cid, yr, *[vals[c] for c in numeric_cols]),
            )
            count += 1
        except Exception as e:
            log.warning("Skip BS %s %s: %s", cid, yr, e)

    conn.commit()
    log.info("Loaded %d balance_sheet rows", count)
    return count


def load_cash_flows(conn: sqlite3.Connection) -> int:
    """Load cashflow.xlsx → cash_flow table. Returns row count."""
    path = DATA_DIR / "cashflow.xlsx"
    if not path.exists():
        log.error("cashflow.xlsx not found at %s", path)
        return 0

    df = pd.read_excel(path, header=1)
    df.columns = [c.strip().lower().replace(" ", "_") for c in df.columns]
    df["company_id"] = df["company_id"].astype(str).str.strip().str.upper()
    df["year"] = df["year"].apply(_normalize_year)

    numeric_cols = [
        "operating_activity", "investing_activity",
        "financing_activity", "net_cash_flow",
    ]

    count = 0
    for _, row in df.iterrows():
        cid = row.get("company_id", "")
        yr = row.get("year", "")
        if not cid or not yr:
            continue
        try:
            vals = {c: _safe_float(row.get(c)) for c in numeric_cols}
            conn.execute(
                """INSERT OR REPLACE INTO cash_flow
                   (company_id, year, operating_activity, investing_activity,
                    financing_activity, net_cash_flow)
                   VALUES (?,?,?,?,?,?)""",
                (cid, yr, *[vals[c] for c in numeric_cols]),
            )
            count += 1
        except Exception as e:
            log.warning("Skip CF %s %s: %s", cid, yr, e)

    conn.commit()
    log.info("Loaded %d cash_flow rows", count)
    return count


def load_all_data(conn: sqlite3.Connection) -> dict[str, int]:
    """Load all 4 source Excel files. Returns counts dict."""
    counts = {}
    counts["companies"] = load_companies(conn)
    counts["income_statement"] = load_income_statements(conn)
    counts["balance_sheet"] = load_balance_sheets(conn)
    counts["cash_flow"] = load_cash_flows(conn)
    return counts


# =========================================================================
# STEP 3 — Ratio computation for a single company-year row
# =========================================================================
def compute_row(
    is_row: dict[str, Optional[float]],
    bs_row: dict[str, Optional[float]],
    cf_row: dict[str, Optional[float]],
    company_id: str,
    year: str,
) -> dict:
    """Compute all 30+ KPIs for one company-year. Returns flat dict."""
    sales = is_row.get("sales")
    net_profit = is_row.get("net_profit")
    operating_profit = is_row.get("operating_profit")
    other_income = is_row.get("other_income")
    interest = is_row.get("interest")
    depreciation = is_row.get("depreciation")
    eps = is_row.get("eps")
    dividend_payout = is_row.get("dividend_payout")

    equity_capital = bs_row.get("equity_capital") or 0
    reserves = bs_row.get("reserves") or 0
    borrowings = bs_row.get("borrowings") or 0
    total_assets = bs_row.get("total_assets")
    face_value = bs_row.get("face_value") or 1  # fetch from companies later

    total_equity = equity_capital + reserves
    ebit = (operating_profit or 0) - (depreciation or 0) if operating_profit and depreciation else None

    cfo = cf_row.get("operating_activity")
    cfi = cf_row.get("investing_activity")
    cff = cf_row.get("financing_activity")

    # --- Profitability ratios ---
    npm = net_profit_margin(net_profit, sales)
    opm = operating_profit_margin(operating_profit, sales)
    roe = return_on_equity(net_profit, total_equity)
    roce = return_on_capital_employed(ebit, total_equity, borrowings)
    roa = return_on_assets(net_profit, total_assets)

    # --- Leverage & coverage ---
    de = borrowings / total_equity if total_equity and total_equity > 0 else 0.0
    icr = interest_coverage_ratio(operating_profit, other_income, interest)
    high_lev = 1 if is_high_leverage(de) else 0
    low_icr = 1 if is_low_icr_warning(icr) else 0
    nd = net_debt(borrowings, bs_row.get("investments"))
    at = asset_turnover(sales, total_assets)

    # --- Cash flow KPIs ---
    fcf = free_cash_flow(cfo, cfi)
    capex_int = capex_intensity(cfi, cfo)
    fcf_conv = fcf_conversion_rate(fcf, operating_profit)
    cfo_qs = cfo_quality_score(cfo, net_profit)
    cap_alloc = capital_allocation_pattern(cfo, cfi, cff)

    # --- Book value per share ---
    shares_outstanding = (equity_capital / face_value) if face_value and face_value > 0 else None
    bvps = (total_equity / shares_outstanding) if shares_outstanding and shares_outstanding > 0 else None

    return {
        "company_id": company_id,
        "year": year,
        "net_profit_margin_pct": npm,
        "operating_profit_margin_pct": opm,
        "return_on_equity_pct": roe,
        "return_on_capital_employed_pct": roce,
        "return_on_assets_pct": roa,
        "debt_to_equity": de,
        "interest_coverage": icr,
        "is_high_leverage": high_lev,
        "is_low_icr_warning": low_icr,
        "net_debt_cr": nd,
        "asset_turnover": at,
        "free_cash_flow_cr": fcf,
        "capex_intensity": capex_int,
        "fcf_conversion_rate": fcf_conv,
        "cfo_quality_score": cfo_qs,
        "capital_allocation_pattern": cap_alloc,
        "earnings_per_share": eps,
        "book_value_per_share": bvps,
        "dividend_payout_ratio_pct": dividend_payout,
        "total_debt_cr": borrowings,
        "cash_from_operations_cr": cfo,
        # CAGR placeholders — filled in STEP 4
        "revenue_cagr_3yr": None,
        "revenue_cagr_5yr": None,
        "revenue_cagr_10yr": None,
        "pat_cagr_3yr": None,
        "pat_cagr_5yr": None,
        "pat_cagr_10yr": None,
        "eps_cagr_3yr": None,
        "eps_cagr_5yr": None,
        "eps_cagr_10yr": None,
        "composite_quality_score": None,
    }


# =========================================================================
# STEP 4 — CAGR computation (per company across all years)
# =========================================================================
def _cagr_column(is_rows: list[dict], metric: str) -> list[Optional[float]]:
    """Extract a column of values from income_statement rows sorted by year."""
    sorted_rows = sorted(is_rows, key=lambda r: r.get("year", ""))
    return [_safe_float(r.get(metric)) for r in sorted_rows]


def enrich_with_cagrs(
    rows: list[dict], all_is_for_company: list[dict]
) -> None:
    """Add CAGR columns to rows in-place using the company's full IS history."""
    revenue_series = _cagr_column(all_is_for_company, "sales")
    pat_series = _cagr_column(all_is_for_company, "net_profit")
    eps_series = _cagr_column(all_is_for_company, "eps")

    years_sorted = sorted(
        {r.get("year", "") for r in all_is_for_company if r.get("year")}
    )

    # Compute CAGRs
    rev_cagrs = compute_all_cagrs(revenue_series, years_sorted)
    pat_cagrs = compute_all_cagrs(pat_series, years_sorted)
    eps_cagrs = compute_all_cagrs(eps_series, years_sorted)

    # Map year → CAGR values
    for row in rows:
        yr = row["year"]
        row["revenue_cagr_3yr"] = rev_cagrs.get("cagr_3yr")
        row["revenue_cagr_5yr"] = rev_cagrs.get("cagr_5yr")
        row["revenue_cagr_10yr"] = rev_cagrs.get("cagr_10yr")
        row["pat_cagr_3yr"] = pat_cagrs.get("cagr_3yr")
        row["pat_cagr_5yr"] = pat_cagrs.get("cagr_5yr")
        row["pat_cagr_10yr"] = pat_cagrs.get("cagr_10yr")
        row["eps_cagr_3yr"] = eps_cagrs.get("cagr_3yr")
        row["eps_cagr_5yr"] = eps_cagrs.get("cagr_5yr")
        row["eps_cagr_10yr"] = eps_cagrs.get("cagr_10yr")


# =========================================================================
# STEP 5 — Composite Quality Score
# =========================================================================
def compute_composite_score(row: dict) -> Optional[float]:
    """Weighted composite score: ROE 25%, NPM 20%, ICR 15%, D/E inv 15%,
    FCF conversion 15%, Asset Turnover 10%. Returns 0-100 or None."""
    weights = {
        "roe": 0.25,
        "npm": 0.20,
        "icr": 0.15,
        "de_inv": 0.15,
        "fcf_conv": 0.15,
        "at": 0.10,
    }

    def _score(val, good_threshold, bad_threshold):
        """Linear interpolation: good=100, bad=0, clamped."""
        if val is None:
            return None
        if val >= good_threshold:
            return 100.0
        if val <= bad_threshold:
            return 0.0
        return 100.0 * (val - bad_threshold) / (good_threshold - bad_threshold)

    scores = {}
    scores["roe"] = _score(row.get("return_on_equity_pct"), 20, 0)
    scores["npm"] = _score(row.get("net_profit_margin_pct"), 20, 0)
    scores["icr"] = _score(row.get("interest_coverage"), 10, 1)
    # D/E inverse: lower is better
    de = row.get("debt_to_equity")
    if de is not None:
        scores["de_inv"] = _score(1.0 / (de + 0.01), 10, 0.1)  # 1/DE proxy
    else:
        scores["de_inv"] = None
    scores["fcf_conv"] = _score(row.get("fcf_conversion_rate"), 80, 20)
    scores["at"] = _score(row.get("asset_turnover"), 1.0, 0.2)

    total_weight = 0.0
    weighted_sum = 0.0
    for key, w in weights.items():
        s = scores[key]
        if s is not None:
            weighted_sum += s * w
            total_weight += w

    if total_weight == 0:
        return None
    return round(weighted_sum / total_weight, 2)


# =========================================================================
# STEP 6 — Main runner
# =========================================================================
def _fetch_dict(conn: sqlite3.Connection, query: str, params=()) -> list[dict]:
    """Run query and return list of dicts."""
    cursor = conn.execute(query, params)
    cols = [d[0] for d in cursor.description]
    return [dict(zip(cols, row)) for row in cursor.fetchall()]


def run() -> dict:
    """Main entry point. Returns summary dict."""
    conn = sqlite3.connect(str(DB_PATH))
    conn.execute("PRAGMA journal_mode=WAL")

    # Step 1: Ensure schema
    ensure_schema(conn)

    # Step 2: Load Excel data (skip if tables already have data)
    existing = _fetch_dict(conn, "SELECT COUNT(*) as cnt FROM income_statement")
    if existing and existing[0]["cnt"] > 0:
        log.info("Source tables already populated (%d IS rows). Skipping Excel load.", existing[0]["cnt"])
    else:
        log.info("Source tables empty. Loading from Excel...")
        counts = load_all_data(conn)
        log.info("Load counts: %s", counts)

    # Verify source data
    companies = _fetch_dict(conn, "SELECT id, face_value FROM companies")
    if not companies:
        log.error("No companies in DB. Aborting.")
        conn.close()
        return {"error": "No companies loaded"}

    # Build face_value lookup
    fv_lookup = {c["id"]: (c["face_value"] or 1) for c in companies}

    # Step 3: Get all income_statement years per company
    all_is = _fetch_dict(conn, "SELECT * FROM income_statement ORDER BY company_id, year")
    all_bs = _fetch_dict(conn, "SELECT * FROM balance_sheet ORDER BY company_id, year")
    all_cf = _fetch_dict(conn, "SELECT * FROM cash_flow ORDER BY company_id, year")

    # Index by (company_id, year)
    bs_index = {(r["company_id"], r["year"]): r for r in all_bs}
    cf_index = {(r["company_id"], r["year"]): r for r in all_cf}

    # Group IS rows by company
    from collections import defaultdict
    is_by_company = defaultdict(list)
    for r in all_is:
        is_by_company[r["company_id"]].append(r)

    # Step 4: Compute ratios per company-year
    output_rows: list[dict] = []
    for is_row in all_is:
        cid = is_row["company_id"]
        yr = is_row["year"]
        bs_row = bs_index.get((cid, yr), {})
        cf_row = cf_index.get((cid, yr), {})

        # Inject face_value for BVPS calculation
        bs_row["face_value"] = fv_lookup.get(cid, 1)

        row = compute_row(is_row, bs_row, cf_row, cid, yr)
        output_rows.append(row)

    # Step 5: Enrich with CAGRs (per company)
    for cid, company_is_rows in is_by_company.items():
        company_output = [r for r in output_rows if r["company_id"] == cid]
        if company_output:
            enrich_with_cagrs(company_output, company_is_rows)

    # Step 6: Compute composite quality score
    for row in output_rows:
        row["composite_quality_score"] = compute_composite_score(row)

    # Step 7: Write to financial_ratios table (UPSERT)
    cols = [
        "company_id", "year",
        "net_profit_margin_pct", "operating_profit_margin_pct",
        "return_on_equity_pct", "return_on_capital_employed_pct",
        "return_on_assets_pct", "debt_to_equity", "interest_coverage",
        "is_high_leverage", "is_low_icr_warning", "net_debt_cr",
        "asset_turnover", "free_cash_flow_cr", "capex_intensity",
        "fcf_conversion_rate", "cfo_quality_score",
        "capital_allocation_pattern", "earnings_per_share",
        "book_value_per_share", "dividend_payout_ratio_pct",
        "total_debt_cr", "cash_from_operations_cr",
        "revenue_cagr_3yr", "revenue_cagr_5yr", "revenue_cagr_10yr",
        "pat_cagr_3yr", "pat_cagr_5yr", "pat_cagr_10yr",
        "eps_cagr_3yr", "eps_cagr_5yr", "eps_cagr_10yr",
        "composite_quality_score",
    ]
    placeholders = ", ".join(["?"] * len(cols))
    col_str = ", ".join(cols)
    update_str = ", ".join(f"{c}=excluded.{c}" for c in cols[2:])  # skip PK cols

    insert_sql = f"""
        INSERT INTO financial_ratios ({col_str})
        VALUES ({placeholders})
        ON CONFLICT(company_id, year) DO UPDATE SET {update_str}
    """

    written = 0
    skipped = 0
    for row in output_rows:
        try:
            vals = [row.get(c) for c in cols]
            conn.execute(insert_sql, vals)
            written += 1
        except Exception as e:
            log.warning("Skip ratio %s %s: %s", row["company_id"], row["year"], e)
            skipped += 1

    conn.commit()
    log.info("Wrote %d rows to financial_ratios (skipped %d)", written, skipped)

    # Step 8: Verification
    total = _fetch_dict(conn, "SELECT COUNT(*) as cnt FROM financial_ratios")
    companies_count = _fetch_dict(
        conn, "SELECT COUNT(DISTINCT company_id) as cnt FROM financial_ratios"
    )
    years_count = _fetch_dict(
        conn, "SELECT COUNT(DISTINCT year) as cnt FROM financial_ratios"
    )
    null_stats = _fetch_dict(conn, """
        SELECT
            COUNT(*) as total,
            SUM(CASE WHEN net_profit_margin_pct IS NULL THEN 1 ELSE 0 END) as npm_nulls,
            SUM(CASE WHEN return_on_equity_pct IS NULL THEN 1 ELSE 0 END) as roe_nulls,
            SUM(CASE WHEN debt_to_equity IS NULL THEN 1 ELSE 0 END) as de_nulls,
            SUM(CASE WHEN composite_quality_score IS NULL THEN 1 ELSE 0 END) as qs_nulls
        FROM financial_ratios
    """)

    summary = {
        "total_rows": total[0]["cnt"] if total else 0,
        "distinct_companies": companies_count[0]["cnt"] if companies_count else 0,
        "distinct_years": years_count[0]["cnt"] if years_count else 0,
        "written": written,
        "skipped": skipped,
        "null_stats": null_stats[0] if null_stats else {},
    }

    log.info("=== VERIFICATION ===")
    log.info("Total rows: %d (target: >=1100)", summary["total_rows"])
    log.info("Distinct companies: %d (target: 92)", summary["distinct_companies"])
    log.info("Distinct years: %d", summary["distinct_years"])
    log.info("Null stats: %s", summary["null_stats"])

    conn.close()
    return summary


# =========================================================================
# STEP 7 — Spot-check utility
# =========================================================================
def spot_check(conn: sqlite3.Connection, company_ids: list[str]) -> None:
    """Print key ratios for specified companies for manual verification."""
    for cid in company_ids:
        rows = _fetch_dict(
            conn,
            """SELECT company_id, year, net_profit_margin_pct, return_on_equity_pct,
                      debt_to_equity, interest_coverage, free_cash_flow_cr,
                      composite_quality_score
               FROM financial_ratios
               WHERE company_id = ? ORDER BY year DESC LIMIT 5""",
            (cid,),
        )
        if not rows:
            log.warning("No data for %s", cid)
            continue
        print(f"\n{'='*60}")
        print(f"  SPOT CHECK: {cid}")
        print(f"{'='*60}")
        for r in rows:
            print(f"  {r['year']}  NPM={r['net_profit_margin_pct']:.1f}%  "
                  f"ROE={r['return_on_equity_pct']:.1f}%  "
                  f"D/E={r['debt_to_equity']:.2f}  "
                  f"ICR={r['interest_coverage']}  "
                  f"FCF={r['free_cash_flow_cr']}  "
                  f"Score={r['composite_quality_score']}")


if __name__ == "__main__":
    result = run()
    print(f"\n{'='*60}")
    print(f"  RATIO RUNNER COMPLETE")
    print(f"{'='*60}")
    print(f"  Rows written   : {result.get('written', 0)}")
    print(f"  Total in DB    : {result.get('total_rows', 0)}")
    print(f"  Companies      : {result.get('distinct_companies', 0)}")
    print(f"  Years covered  : {result.get('distinct_years', 0)}")

    if result.get("total_rows", 0) < 1100:
        print(f"\n  ⚠ WARNING: {result['total_rows']} rows < 1100 target!")
    else:
        print(f"\n  ✓ Target of 1,100+ rows MET!")

    # Spot-check 3 companies
    conn = sqlite3.connect(str(DB_PATH))
    spot_check(conn, ["TCS", "RELIANCE", "HDFCBANK"])
    conn.close()