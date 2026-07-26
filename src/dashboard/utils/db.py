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
            c.broad_sector,
            c.sector_id,
            s.sector_name
        FROM companies c
        LEFT JOIN sectors s ON c.sector_id = s.sector_id
        WHERE c.nifty100 = 1
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
    if year:
        df = pd.read_sql_query(
            "SELECT * FROM financial_ratios WHERE company_id = ? AND year = ?",
            conn,
            params=(ticker, year),
        )
    else:
        df = pd.read_sql_query(
            "SELECT * FROM financial_ratios WHERE company_id = ? ORDER BY year",
            conn,
            params=(ticker,),
        )
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
        "SELECT * FROM income_statement WHERE company_id = ? ORDER BY year",
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
    df = pd.read_sql_query(
        """
        SELECT broad_sector, COUNT(DISTINCT company_id) AS company_count
        FROM companies
        WHERE nifty100 = 1 AND broad_sector IS NOT NULL
        GROUP BY broad_sector
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