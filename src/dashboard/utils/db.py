"""Shared data-loader for the Nifty 100 Streamlit dashboard.

Every query function is decorated with ``@st.cache_data(ttl=600)`` so
repeated sidebar clicks within 10 minutes hit the cache instead of the DB.
"""

from __future__ import annotations

import sqlite3
from pathlib import Path

import pandas as pd
import streamlit as st

# Resolve to <project_root>/db/nifty100.db regardless of CWD.
_PROJECT_ROOT = Path(__file__).resolve().parents[3]
_DB_PATH = _PROJECT_ROOT / "output" / "nifty100.db"


def _get_conn() -> sqlite3.Connection:
    """Return a read-only connection to the SQLite database."""
    if not _DB_PATH.exists():
        raise FileNotFoundError(
            f"Database not found at {_DB_PATH}. "
            "Run the ETL pipeline first to create it."
        )
    conn = sqlite3.connect(str(_DB_PATH))
    conn.row_factory = sqlite3.Row
    return conn


def _relation_exists(conn: sqlite3.Connection, name: str) -> bool:
    row = conn.execute(
        "SELECT 1 FROM sqlite_master WHERE name = ? AND type IN ('table', 'view')",
        (name,),
    ).fetchone()
    return row is not None


# ------------------------------------------------------------------
# 1. Company list
# ------------------------------------------------------------------


@st.cache_data(ttl=600)
def get_companies() -> pd.DataFrame:
    """All Nifty-100 companies with sector info."""
    conn = _get_conn()
    df = pd.read_sql_query(
        """
        SELECT
            c.company_id,
            c.company_name,
            c.sector_id,
            s.sector_name AS sector_name,
            s.sector_name AS broad_sector
        FROM companies c
        LEFT JOIN sectors s ON c.sector_id = s.sector_id
        ORDER BY c.company_name
        """,
        conn,
    )
    conn.close()
    return df


# ------------------------------------------------------------------
# 2. Financial ratios (main analytical table — 30 columns)
# ------------------------------------------------------------------


@st.cache_data(ttl=600)
def get_ratios(ticker: str, year: str | None = None) -> pd.DataFrame:
    """Return financial_ratios rows for *ticker*, optionally for one *year*."""
    conn = _get_conn()
    if _relation_exists(conn, "financial_ratios"):
        if year:
            df = pd.read_sql_query(
                "SELECT * FROM financial_ratios WHERE company_id = ? AND year LIKE ?",
                conn,
                params=(ticker, f"{year}%"),
            )
        else:
            df = pd.read_sql_query(
                "SELECT * FROM financial_ratios WHERE company_id = ? ORDER BY year",
                conn,
                params=(ticker,),
            )
    else:
        query = """
            SELECT
                r.company_id,
                c.company_name,
                c.sector_id,
                s.sector_name AS sector_name,
                s.sector_name AS broad_sector,
                r.year,
                r.roe,
                r.roa,
                r.roce,
                r.debt_to_equity,
                r.current_ratio,
                r.quick_ratio,
                r.interest_coverage,
                r.asset_turnover,
                r.net_profit_margin,
                r.opm,
                r.dividend_payout,
                r.earning_yield,
                r.book_value_per_share,
                r.price_to_book,
                r.price_to_earnings AS pe_ratio,
                r.price_to_earnings,
                CASE WHEN COALESCE(r.debt_to_equity, 0) = 0 THEN 1 ELSE 0 END AS is_debt_free,
                NULL AS revenue_cagr_5yr,
                NULL AS net_profit_cagr_5yr,
                NULL AS eps_cagr_5yr,
                NULL AS composite_quality_score,
                cf.fcf AS free_cash_flow
            FROM ratios r
            LEFT JOIN companies c ON r.company_id = c.company_id
            LEFT JOIN sectors s ON c.sector_id = s.sector_id
            LEFT JOIN cash_flow cf ON r.company_id = cf.company_id AND r.year = cf.year
            WHERE r.company_id = ?
        """
        if year:
            query += " AND r.year LIKE ?"
            params = (ticker, f"{year}%")
        else:
            params = (ticker,)
        query += " ORDER BY r.year"
        df = pd.read_sql_query(query, conn, params=params)
    conn.close()
    return df


# ------------------------------------------------------------------
# 3-5. Raw financial statements
# ------------------------------------------------------------------


@st.cache_data(ttl=600)
def get_pl(ticker: str) -> pd.DataFrame:
    """Income-statement rows for *ticker*, ordered by year."""
    conn = _get_conn()
    df = pd.read_sql_query(
        """
        SELECT
            company_id,
            year,
            revenue AS net_sales,
            net_income AS net_profit,
            operating_income,
            other_income,
            total_expenses,
            interest_expense,
            depreciation,
            tax_expense,
            eps,
            opm,
            npm,
            ebitda,
            ebit
        FROM income_statement
        WHERE company_id = ?
        ORDER BY year
        """,
        conn,
        params=(ticker,),
    )
    conn.close()
    return df


@st.cache_data(ttl=600)
def get_bs(ticker: str) -> pd.DataFrame:
    """Balance-sheet rows for *ticker*, ordered by year."""
    conn = _get_conn()
    df = pd.read_sql_query(
        "SELECT * FROM balance_sheet WHERE company_id = ? ORDER BY year",
        conn,
        params=(ticker,),
    )
    conn.close()
    return df


@st.cache_data(ttl=600)
def get_cf(ticker: str) -> pd.DataFrame:
    """Cash-flow rows for *ticker*, ordered by year."""
    conn = _get_conn()
    df = pd.read_sql_query(
        "SELECT * FROM cash_flow WHERE company_id = ? ORDER BY year",
        conn,
        params=(ticker,),
    )
    conn.close()
    return df


# ------------------------------------------------------------------
# 6. Sector list (broad_sector with company counts)
# ------------------------------------------------------------------


@st.cache_data(ttl=600)
def get_sectors() -> pd.DataFrame:
    """Distinct broad_sector values with company counts."""
    conn = _get_conn()
    if _relation_exists(conn, "financial_ratios"):
        df = pd.read_sql_query(
            """
            SELECT broad_sector, COUNT(DISTINCT company_id) AS company_count
            FROM financial_ratios
            WHERE broad_sector IS NOT NULL
            GROUP BY broad_sector
            ORDER BY company_count DESC
            """,
            conn,
        )
    else:
        df = pd.read_sql_query(
            """
            SELECT
                s.sector_name AS broad_sector,
                COUNT(DISTINCT c.company_id) AS company_count
            FROM sectors s
            LEFT JOIN companies c ON c.sector_id = s.sector_id
            GROUP BY s.sector_name
            ORDER BY company_count DESC
            """,
            conn,
        )
    conn.close()
    return df


# ------------------------------------------------------------------
# 7. Peer group data
# ------------------------------------------------------------------


@st.cache_data(ttl=600)
def get_peers(group_name: str, year: str | None = None) -> pd.DataFrame:
    """All companies in a peer group, joined with financial_ratios."""
    conn = _get_conn()
    if _relation_exists(conn, "financial_ratios") and _relation_exists(
        conn, "peer_groups"
    ):
        query = """
            SELECT
                fr.*,
                pg.benchmark_company_id
            FROM financial_ratios fr
            JOIN peer_groups pg ON fr.company_id = pg.company_id
            WHERE pg.peer_group_name = ?
        """
        params: list = [group_name]
        if year:
            query += " AND fr.year = ?"
            params.append(year)
        query += " ORDER BY fr.year, fr.company_name"
        df = pd.read_sql_query(query, conn, params=params)
    else:
        df = pd.DataFrame()
    conn.close()
    return df


# ------------------------------------------------------------------
# 8. Valuation (stub — populated on Day 26)
# ------------------------------------------------------------------


@st.cache_data(ttl=600)
def get_valuation(ticker: str) -> pd.DataFrame:
    """Valuation data for *ticker*.

    The ``valuation`` table is created on Day 26.  Until then this
    returns an empty DataFrame so screens never crash.
    """
    conn = _get_conn()
    try:
        df = pd.read_sql_query(
            "SELECT * FROM valuation WHERE company_id = ?",
            conn,
            params=(ticker,),
        )
    except Exception:
        df = pd.DataFrame()
    finally:
        conn.close()
    return df


# ------------------------------------------------------------------
# 9. All ratios for one year (Home screen KPIs)
# ------------------------------------------------------------------


@st.cache_data(ttl=600)
def get_all_ratios(year: str) -> pd.DataFrame:
    """Return every company's financial_ratios row for a single year."""
    conn = _get_conn()
    if _relation_exists(conn, "financial_ratios"):
        df = pd.read_sql_query(
            "SELECT * FROM financial_ratios WHERE year LIKE ?",
            conn,
            params=(f"{year}%",),
        )
    else:
        df = pd.read_sql_query(
            """
            SELECT
                r.company_id,
                c.company_name,
                c.sector_id,
                s.sector_name AS sector_name,
                s.sector_name AS broad_sector,
                r.year,
                r.roe,
                r.roa,
                r.roce,
                r.debt_to_equity,
                r.current_ratio,
                r.quick_ratio,
                r.interest_coverage,
                r.asset_turnover,
                r.net_profit_margin,
                r.opm,
                r.dividend_payout,
                r.earning_yield,
                r.book_value_per_share,
                r.price_to_book,
                r.price_to_earnings AS pe_ratio,
                r.price_to_earnings,
                CASE WHEN COALESCE(r.debt_to_equity, 0) = 0 THEN 1 ELSE 0 END AS is_debt_free,
                NULL AS revenue_cagr_5yr,
                NULL AS net_profit_cagr_5yr,
                NULL AS eps_cagr_5yr,
                NULL AS composite_quality_score,
                cf.fcf AS free_cash_flow
            FROM ratios r
            LEFT JOIN companies c ON r.company_id = c.company_id
            LEFT JOIN sectors s ON c.sector_id = s.sector_id
            LEFT JOIN cash_flow cf ON r.company_id = cf.company_id AND r.year = cf.year
            WHERE r.year LIKE ?
            ORDER BY c.company_name
            """,
            conn,
            params=(f"{year}%",),
        )
    conn.close()
    return df


# ------------------------------------------------------------------
# 10. Pros & cons
# ------------------------------------------------------------------


@st.cache_data(ttl=600)
def get_pros_cons(ticker: str) -> pd.DataFrame:
    """Return pros/cons items for a company."""
    conn = _get_conn()
    info = conn.execute("PRAGMA table_info(prosandcons)").fetchall()
    columns = {row[1] for row in info}
    if {"category", "item", "sentiment"}.issubset(columns):
        df = pd.read_sql_query(
            "SELECT category, item, sentiment FROM prosandcons WHERE company_id = ?",
            conn,
            params=(ticker,),
        )
    elif {"pros", "cons"}.issubset(columns):
        rows = conn.execute(
            "SELECT pros, cons FROM prosandcons WHERE company_id = ?",
            (ticker,),
        ).fetchall()
        records: list[dict[str, str]] = []
        for pros, cons in rows:
            if pros:
                records.append({"item": pros, "sentiment": "positive"})
            if cons:
                records.append({"item": cons, "sentiment": "negative"})
        df = pd.DataFrame(records)
    else:
        df = pd.DataFrame(columns=["item", "sentiment"])
    conn.close()
    return df


# ── 11. Valuation (populated on Day 26) ────────────────────────────


@st.cache_data(ttl=600)
def get_all_valuations(year: str) -> pd.DataFrame:
    """Return valuation estimates for all companies in a given year."""
    conn = _get_conn()
    try:
        df = pd.read_sql_query(
            "SELECT * FROM valuation WHERE year LIKE ?",
            conn,
            params=(f"{year}%",),
        )
    except Exception:
        df = pd.DataFrame()
    finally:
        conn.close()
    return df
