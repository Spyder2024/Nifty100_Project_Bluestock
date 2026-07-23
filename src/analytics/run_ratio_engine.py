"""src/analytics/run_ratio_engine.py — Populate financial_ratios table.

Sprint 2, Day 12

Workflow:
    1. Create financial_ratios table if absent.
    2. Query income_statement, balance_sheet, cash_flow, companies.
    3. Compute all KPIs per company-year.
    4. Compute CAGRs per company (needs multi-year data).
    5. Generate output/capital_allocation.csv.
    6. Insert everything into financial_ratios.

Usage:
    python -m src.analytics.run_ratio_engine
"""

from __future__ import annotations

import csv
import logging
import sqlite3
import sys
from collections import defaultdict
from pathlib import Path
from typing import Any, Optional

from src.analytics.cagr import compute_all_cagrs
from src.analytics.cashflow_kpis import (
    ALLOCATION_CSV_COLUMNS,
    capex_intensity,
    classify_capital_allocation,
    cfo_quality_score,
    fcf_conversion_rate,
    free_cash_flow,
    generate_capital_allocation_csv,
)
from src.analytics.ratios import (
    asset_turnover,
    debt_to_equity,
    get_icr_label,
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

logger = logging.getLogger(__name__)

# ======================================================================
# CONFIG — adjust these to match YOUR database column names
# ======================================================================

# Path to the SQLite database (override via CLI arg)
DB_PATH = "db/nifty100.db"

# Column mapping: internal key → actual column name in your DB.
# Only change the VALUES if your columns are named differently.
IS = {  # income_statement columns
    "company_id":      "company_id",
    "year":            "year",
    "revenue":         "revenue",
    "net_income":      "net_income",
    "opm":             "opm",
    "eps":             "eps",
    "dps":             "dps",
    "operating_profit": "operating_profit",
    "other_income":    "other_income",
    "interest":        "interest",
    "tax":             "tax",
}

BS = {  # balance_sheet columns
    "company_id":      "company_id",
    "year":            "year",
    "equity_capital":  "equity_capital",
    "reserves":        "reserves_and_surplus",
    "borrowings":      "borrowings",
    "total_assets":    "total_assets",
    "total_liabilities": "total_liabilities",
    "investments":     "investments",
}

CF = {  # cash_flow columns
    "company_id":      "company_id",
    "year":            "year",
    "operating_cf":    "operating_activities",
    "investing_cf":    "investing_activities",
    "financing_cf":    "financing_activities",
}

CO = {  # companies columns
    "company_id":      "company_id",
    "broad_sector":    "broad_sector",
}

# ======================================================================
# financial_ratios table DDL
# ======================================================================

CREATE_TABLE_SQL = """
CREATE TABLE IF NOT EXISTS financial_ratios (
    company_id                 TEXT    NOT NULL,
    year                       TEXT    NOT NULL,
    broad_sector               TEXT,
    -- Profitability
    net_profit_margin_pct      REAL,
    operating_profit_margin_pct REAL,
    return_on_equity_pct       REAL,
    return_on_capital_employed_pct REAL,
    return_on_assets_pct       REAL,
    -- Leverage & Efficiency
    debt_to_equity             REAL,
    high_leverage_flag         INTEGER DEFAULT 0,
    interest_coverage          REAL,
    icr_label                  TEXT    DEFAULT '',
    low_icr_warning            INTEGER DEFAULT 0,
    net_debt                   REAL,
    asset_turnover             REAL,
    -- Cash Flow
    free_cash_flow             REAL,
    fcf_conversion_rate        REAL,
    cfo_quality_label          TEXT    DEFAULT '',
    capex_intensity_pct        REAL,
    capex_intensity_label      TEXT    DEFAULT '',
    -- Growth (3yr)
    revenue_cagr_3yr           REAL,
    revenue_cagr_3yr_flag      TEXT    DEFAULT '',
    pat_cagr_3yr               REAL,
    pat_cagr_3yr_flag          TEXT    DEFAULT '',
    eps_cagr_3yr               REAL,
    eps_cagr_3yr_flag          TEXT    DEFAULT '',
    -- Growth (5yr)
    revenue_cagr_5yr           REAL,
    revenue_cagr_5yr_flag      TEXT    DEFAULT '',
    pat_cagr_5yr               REAL,
    pat_cagr_5yr_flag          TEXT    DEFAULT '',
    eps_cagr_5yr               REAL,
    eps_cagr_5yr_flag          TEXT    DEFAULT '',
    -- Growth (10yr)
    revenue_cagr_10yr          REAL,
    revenue_cagr_10yr_flag     TEXT    DEFAULT '',
    pat_cagr_10yr              REAL,
    pat_cagr_10yr_flag         TEXT    DEFAULT '',
    eps_cagr_10yr              REAL,
    eps_cagr_10yr_flag         TEXT    DEFAULT '',
    -- Sourced values
    earnings_per_share         REAL,
    dividend_payout_ratio_pct  REAL,
    total_debt                 REAL,
    cash_from_operations       REAL,
    -- Composite
    composite_quality_score    REAL,
    PRIMARY KEY (company_id, year)
);
"""


# ======================================================================
# Helpers
# ======================================================================

def _get_existing_columns(conn: sqlite3.Connection, table: str) -> set[str]:
    """Return set of column names that actually exist in *table*."""
    try:
        rows = conn.execute(f"PRAGMA table_info({table})").fetchall()
        return {r[1].lower() for r in rows}
    except Exception:
        return set()


def _safe_float(row: dict, mapping: dict, key: str) -> Optional[float]:
    """Look up a value from a row dict, return float or None."""
    col = mapping.get(key, key)
    val = row.get(col)
    if val is None:
        return None
    try:
        return float(val)
    except (ValueError, TypeError):
        return None


# ======================================================================
# Data fetching
# ======================================================================

def _build_base_query(conn: sqlite3.Connection) -> str:
    """Build the big LEFT JOIN query using only columns that exist."""
    is_cols = _get_existing_columns(conn, "income_statement")
    bs_cols = _get_existing_columns(conn, "balance_sheet")
    cf_cols = _get_existing_columns(conn, "cash_flow")
    co_cols = _get_existing_columns(conn, "companies")

    # Determine which tables exist
    has_is = bool(is_cols)
    has_bs = bool(bs_cols)
    has_cf = bool(cf_cols)
    has_co = bool(co_cols)

    if not has_is and not has_bs:
        logger.error("Neither income_statement nor balance_sheet tables found!")
        sys.exit(1)

    # SELECT columns
    selects = []
    if has_is:
        for alias, col in IS.items():
            if col.lower() in is_cols or col.lower().replace(" ", "_") in is_cols:
                selects.append(f'is_table."{col}" AS {alias}')
    if has_bs:
        for alias, col in BS.items():
            if col.lower() in bs_cols or col.lower().replace(" ", "_") in bs_cols:
                selects.append(f'bs_table."{col}" AS {alias}')
    if has_cf:
        for alias, col in CF.items():
            if col.lower() in cf_cols or col.lower().replace(" ", "_") in cf_cols:
                selects.append(f'cf_table."{col}" AS {alias}')
    if has_co:
        for alias, col in CO.items():
            if col.lower() in co_cols or col.lower().replace(" ", "_") in co_cols:
                selects.append(f'co_table."{col}" AS {alias}')

    if not selects:
        logger.error("No matching columns found in any table!")
        sys.exit(1)

    # FROM clause with LEFT JOINs
    froms = ["income_statement AS is_table"] if has_is else []
    if has_bs:
        froms.append(
            "LEFT JOIN balance_sheet AS bs_table "
            "ON is_table.company_id = bs_table.company_id "
            "AND is_table.year = bs_table.year"
        )
    if has_cf:
        froms.append(
            "LEFT JOIN cash_flow AS cf_table "
            "ON is_table.company_id = cf_table.company_id "
            "AND is_table.year = cf_table.year"
        )
    if has_co:
        froms.append(
            "LEFT JOIN companies AS co_table "
            "ON is_table.company_id = co_table.company_id"
        )

    sql = f"SELECT {', '.join(selects)} FROM {' '.join(froms)}"
    return sql


def fetch_all_data(conn: sqlite3.Connection) -> list[dict]:
    """Fetch all company-year data as list of row dicts."""
    sql = _build_base_query(conn)
    logger.info("Executing ratio engine query...")
    rows = conn.execute(sql).fetchall()
    cols = [d[0] for d in conn.execute(sql).description]
    result = [dict(zip(cols, row)) for row in rows]
    logger.info("Fetched %d company-year rows", len(result))
    return result


# ======================================================================
# Per-company-year KPI computation
# ======================================================================

def compute_kpis(row: dict) -> dict:
    """Compute all KPIs for one company-year row dict."""
    # Extract values using mapping
    revenue     = _safe_float(row, IS, "revenue")
    net_income  = _safe_float(row, IS, "net_income")
    opm_source  = _safe_float(row, IS, "opm")
    eps         = _safe_float(row, IS, "eps")
    dps         = _safe_float(row, IS, "dps")
    op_profit   = _safe_float(row, IS, "operating_profit")
    other_inc   = _safe_float(row, IS, "other_income")
    interest    = _safe_float(row, IS, "interest")

    eq_cap      = _safe_float(row, BS, "equity_capital")
    reserves    = _safe_float(row, BS, "reserves")
    borrowings  = _safe_float(row, BS, "borrowings")
    total_ast   = _safe_float(row, BS, "total_assets")
    investments = _safe_float(row, BS, "investments")

    ocf         = _safe_float(row, CF, "operating_cf")
    icf         = _safe_float(row, CF, "investing_cf")
    fcf_val     = _safe_float(row, CF, "financing_cf")

    broad_sec   = row.get(CO.get("broad_sector", "broad_sector"))

    # Derive operating_profit if column missing (revenue × opm / 100)
    if op_profit is None and revenue is not None and opm_source is not None:
        op_profit = revenue * opm_source / 100.0

    # Derive EBIT for ROCE
    ebit = None
    if op_profit is not None and other_inc is not None:
        ebit = op_profit + other_inc
    elif op_profit is not None:
        ebit = op_profit

    # --- Profitability ---
    npm = net_profit_margin(net_income, revenue)
    computed_opm = operating_profit_margin(op_profit, revenue, opm_source)
    roe = return_on_equity(net_income, eq_cap, reserves)
    roce = return_on_capital_employed(
        ebit, eq_cap, reserves, borrowings, broad_sec
    )
    roa = return_on_assets(net_income, total_ast)

    # --- Leverage & Efficiency ---
    de = debt_to_equity(borrowings, eq_cap, reserves)
    high_lev = 1 if is_high_leverage(de, broad_sec) else 0
    icr = interest_coverage_ratio(op_profit, other_inc, interest)
    icr_lbl = get_icr_label(icr)
    low_icr = 1 if is_low_icr_warning(icr) else 0
    nd = net_debt(borrowings, investments)
    ato = asset_turnover(revenue, total_ast)

    # --- Cash Flow ---
    fcf = free_cash_flow(ocf, icf)
    fcf_cr = fcf_conversion_rate(fcf, op_profit)
    capex_pct, capex_lbl = capex_intensity(icf, revenue)
    # CFO quality computed later (needs multi-year)

    # --- Capital allocation pattern ---
    alloc = classify_capital_allocation(ocf, icf, fcf_val)

    # --- Sourced values ---
    div_payout = None
    if eps is not None and eps != 0 and dps is not None:
        div_payout = round((dps / eps) * 100, 2)

    # --- Composite quality score ---
    # Simple average of available profitability ratios (NPM, ROE, ROA)
    prof_ratios = [v for v in [npm, roe, roa] if v is not None]
    comp_score = (
        round(sum(prof_ratios) / len(prof_ratios), 2)
        if prof_ratios
        else None
    )

    return dict(
        company_id=row.get(IS["company_id"], row.get("company_id")),
        year=row.get(IS["year"], row.get("year")),
        broad_sector=broad_sec,
        # Profitability
        net_profit_margin_pct=npm,
        operating_profit_margin_pct=computed_opm,
        return_on_equity_pct=roe,
        return_on_capital_employed_pct=roce,
        return_on_assets_pct=roa,
        # Leverage
        debt_to_equity=de,
        high_leverage_flag=high_lev,
        interest_coverage=icr,
        icr_label=icr_lbl,
        low_icr_warning=low_icr,
        net_debt=nd,
        asset_turnover=ato,
        # Cash Flow
        free_cash_flow=fcf,
        fcf_conversion_rate=fcf_cr,
        capex_intensity_pct=capex_pct,
        capex_intensity_label=capex_lbl,
        # Capital allocation
        cfo_sign=alloc["cfo_sign"],
        cfi_sign=alloc["cfi_sign"],
        cff_sign=alloc["cff_sign"],
        pattern_label=alloc["pattern_label"],
        # Sourced
        earnings_per_share=eps,
        dividend_payout_ratio_pct=div_payout,
        total_debt=borrowings,
        cash_from_operations=ocf,
        # Composite
        composite_quality_score=comp_score,
    )


# ======================================================================
# CAGR computation (needs multi-year data per company)
# ======================================================================

def compute_company_cagrs(
    company_rows: list[dict],
) -> dict[str, tuple[Optional[float], str]]:
    """Compute 3/5/10-year CAGRs for revenue, PAT, EPS."""
    # Sort by year ascending
    sorted_rows = sorted(company_rows, key=lambda r: r.get("year", ""))

    revenue_series = [
        (r["year"], _safe_float(r, IS, "revenue"))
        for r in sorted_rows
    ]
    pat_series = [
        (r["year"], _safe_float(r, IS, "net_income"))
        for r in sorted_rows
    ]
    eps_series = [
        (r["year"], _safe_float(r, IS, "eps"))
        for r in sorted_rows
    ]

    return dict(
        revenue_cagrs=compute_all_cagrs(revenue_series),
        pat_cagrs=compute_all_cagrs(pat_series),
        eps_cagrs=compute_all_cagrs(eps_series),
    )


# ======================================================================
# CFO Quality (needs multi-year data per company)
# ======================================================================

def compute_company_cfo_quality(
    company_rows: list[dict],
) -> Optional[str]:
    """Compute CFO quality score from up to 5 years of data."""
    sorted_rows = sorted(company_rows, key=lambda r: r.get("year", ""))

    # Take last 5 years
    recent = sorted_rows[-5:]

    cfo_vals = [_safe_float(r, CF, "operating_cf") for r in recent]
    pat_vals = [_safe_float(r, IS, "net_income") for r in recent]

    return cfo_quality_score(cfo_vals, pat_vals)


# ======================================================================
# Main orchestration
# ======================================================================

def run_ratio_engine(
    db_path: str = DB_PATH,
    conn: sqlite3.Connection | None = None,
) -> dict:
    """Full ratio engine pipeline. Returns summary stats."""
    own_conn = False
    if conn is None:
        conn = sqlite3.connect(db_path)
        own_conn = True

    try:
        # 1. Create table
        conn.execute(CREATE_TABLE_SQL)
        conn.commit()
        logger.info("financial_ratios table ready")

        # 2. Fetch data
        rows = fetch_all_data(conn)
        if not rows:
            logger.error("No data fetched — check table names and column mapping")
            return dict(total_rows=0, error="no_data")

        # 3. Group by company for CAGR and CFO quality
        by_company: dict[str, list[dict]] = defaultdict(list)
        for r in rows:
            cid = r.get(IS["company_id"], r.get("company_id"))
            if cid:
                by_company[cid].append(r)

        # 4. Compute per-company CAGRs and CFO quality
        company_cagrs: dict[str, dict] = {}
        company_cfo: dict[str, Optional[str]] = {}
        for cid, c_rows in by_company.items():
            company_cagrs[cid] = compute_company_cagrs(c_rows)
            company_cfo[cid] = compute_company_cfo_quality(c_rows)

        # 5. Compute per-company-year KPIs
        all_records: list[dict] = []
        allocation_rows: list[dict] = []

        for row in rows:
            cid = row.get(IS["company_id"], row.get("company_id"))
            kpi = compute_kpis(row)

            # Merge CAGR values
            cagrs = company_cagrs.get(cid, {})
            for metric_prefix in ("revenue", "pat", "eps"):
                cagr_dict = cagrs.get(f"{metric_prefix}_cagrs", {})
                for window in ("3yr", "5yr", "10yr"):
                    val, flag = cagr_dict.get(f"cagr_{window}", (None, ""))
                    kpi[f"{metric_prefix}_cagr_{window}"] = val
                    kpi[f"{metric_prefix}_cagr_{window}_flag"] = flag

            # Merge CFO quality
            kpi["cfo_quality_label"] = company_cfo.get(cid) or ""

            all_records.append(kpi)

            # Capital allocation CSV row
            allocation_rows.append(dict(
                company_id=kpi["company_id"],
                year=kpi["year"],
                cfo_sign=kpi["cfo_sign"],
                cfi_sign=kpi["cfi_sign"],
                cff_sign=kpi["cff_sign"],
                pattern_label=kpi["pattern_label"],
            ))

        # 6. Insert into financial_ratios (upsert)
        insert_sql = """
            INSERT OR REPLACE INTO financial_ratios (
                company_id, year, broad_sector,
                net_profit_margin_pct, operating_profit_margin_pct,
                return_on_equity_pct, return_on_capital_employed_pct,
                return_on_assets_pct,
                debt_to_equity, high_leverage_flag,
                interest_coverage, icr_label, low_icr_warning,
                net_debt, asset_turnover,
                free_cash_flow, fcf_conversion_rate,
                cfo_quality_label, capex_intensity_pct, capex_intensity_label,
                revenue_cagr_3yr, revenue_cagr_3yr_flag,
                pat_cagr_3yr, pat_cagr_3yr_flag,
                eps_cagr_3yr, eps_cagr_3yr_flag,
                revenue_cagr_5yr, revenue_cagr_5yr_flag,
                pat_cagr_5yr, pat_cagr_5yr_flag,
                eps_cagr_5yr, eps_cagr_5yr_flag,
                revenue_cagr_10yr, revenue_cagr_10yr_flag,
                pat_cagr_10yr, pat_cagr_10yr_flag,
                eps_cagr_10yr, eps_cagr_10yr_flag,
                earnings_per_share, dividend_payout_ratio_pct,
                total_debt, cash_from_operations,
                composite_quality_score
            ) VALUES (
                :company_id, :year, :broad_sector,
                :net_profit_margin_pct, :operating_profit_margin_pct,
                :return_on_equity_pct, :return_on_capital_employed_pct,
                :return_on_assets_pct,
                :debt_to_equity, :high_leverage_flag,
                :interest_coverage, :icr_label, :low_icr_warning,
                :net_debt, :asset_turnover,
                :free_cash_flow, :fcf_conversion_rate,
                :cfo_quality_label, :capex_intensity_pct, :capex_intensity_label,
                :revenue_cagr_3yr, :revenue_cagr_3yr_flag,
                :pat_cagr_3yr, :pat_cagr_3yr_flag,
                :eps_cagr_3yr, :eps_cagr_3yr_flag,
                :revenue_cagr_5yr, :revenue_cagr_5yr_flag,
                :pat_cagr_5yr, :pat_cagr_5yr_flag,
                :eps_cagr_5yr, :eps_cagr_5yr_flag,
                :revenue_cagr_10yr, :revenue_cagr_10yr_flag,
                :pat_cagr_10yr, :pat_cagr_10yr_flag,
                :eps_cagr_10yr, :eps_cagr_10yr_flag,
                :earnings_per_share, :dividend_payout_ratio_pct,
                :total_debt, :cash_from_operations,
                :composite_quality_score
            )
        """
        conn.executemany(insert_sql, all_records)
        conn.commit()

        # 7. Generate capital allocation CSV
        generate_capital_allocation_csv(allocation_rows)

        # 8. Summary stats
        count = conn.execute(
            "SELECT COUNT(*) FROM financial_ratios"
        ).fetchone()[0]

        # Count non-null per KPI column
        kpi_columns = [
            "net_profit_margin_pct", "operating_profit_margin_pct",
            "return_on_equity_pct", "debt_to_equity",
            "interest_coverage", "asset_turnover",
            "free_cash_flow", "revenue_cagr_5yr",
            "pat_cagr_5yr", "eps_cagr_5yr",
        ]
        non_null_counts = {}
        for col in kpi_columns:
            cnt = conn.execute(
                f"SELECT COUNT(*) FROM financial_ratios WHERE {col} IS NOT NULL"
            ).fetchone()[0]
            non_null_counts[col] = cnt

        logger.info(
            "Ratio engine complete: %d rows, capital_allocation.csv written",
            count,
        )

        return dict(
            total_rows=count,
            non_null_counts=non_null_counts,
            allocation_rows=len(allocation_rows),
        )

    finally:
        if own_conn:
            conn.close()


# ======================================================================
# CLI entry point
# ======================================================================

if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )
    db = sys.argv[1] if len(sys.argv) > 1 else DB_PATH
    summary = run_ratio_engine(db)
    print(f"\n{'='*50}")
    print(f"  Rows in financial_ratios: {summary['total_rows']}")
    print(f"  Capital allocation rows:  {summary['allocation_rows']}")
    print(f"{'='*50}")
    if summary.get("non_null_counts"):
        print("\nNon-null counts per KPI:")
        for col, cnt in summary["non_null_counts"].items():
            print(f"  {col:40s} {cnt}")