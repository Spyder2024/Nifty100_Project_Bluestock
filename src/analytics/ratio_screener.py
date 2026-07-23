"""
Day 13 — Ratio Screener
Query helpers for the financial_ratios table.
Foundation for Sprint 3 full Screener module.
"""

from __future__ import annotations

import sqlite3
from typing import Optional


def _fetch_dict(
    conn: sqlite3.Connection, query: str, params: tuple = ()
) -> list[dict]:
    """Execute query and return list of row-dicts."""
    cursor = conn.execute(query, params)
    cols = [d[0] for d in cursor.description]
    return [dict(zip(cols, row)) for row in cursor.fetchall()]


# ------------------------------------------------------------------
# Screener functions
# ------------------------------------------------------------------

def screen_debt_free(
    conn: sqlite3.Connection,
    year: Optional[str] = None,
) -> list[dict]:
    """Companies with zero total debt."""
    if year:
        sql = (
            "SELECT company_id, year, debt_to_equity, total_debt_cr, net_debt_cr "
            "FROM financial_ratios "
            "WHERE total_debt_cr = 0 AND year = ? "
            "ORDER BY company_id"
        )
        return _fetch_dict(conn, sql, (year,))
    sql = (
        "SELECT company_id, year, debt_to_equity, total_debt_cr, net_debt_cr "
        "FROM financial_ratios "
        "WHERE total_debt_cr = 0 "
        "ORDER BY company_id, year"
    )
    return _fetch_dict(conn, sql)


def screen_high_roe(
    conn: sqlite3.Connection,
    threshold: float = 20.0,
    year: Optional[str] = None,
    limit: int = 50,
) -> list[dict]:
    """Companies with ROE above threshold."""
    cols = (
        "company_id, year, return_on_equity_pct, "
        "net_profit_margin_pct, debt_to_equity, composite_quality_score"
    )
    if year:
        sql = (
            f"SELECT {cols} FROM financial_ratios "
            "WHERE return_on_equity_pct > ? AND year = ? "
            "ORDER BY return_on_equity_pct DESC LIMIT ?"
        )
        return _fetch_dict(conn, sql, (threshold, year, limit))
    sql = (
        f"SELECT {cols} FROM financial_ratios "
        "WHERE return_on_equity_pct > ? "
        "ORDER BY return_on_equity_pct DESC LIMIT ?"
    )
    return _fetch_dict(conn, sql, (threshold, limit))


def screen_low_leverage(
    conn: sqlite3.Connection,
    max_de: float = 0.5,
    year: Optional[str] = None,
    limit: int = 50,
) -> list[dict]:
    """Companies with debt-to-equity at or below max_de."""
    cols = (
        "company_id, year, debt_to_equity, total_debt_cr, "
        "return_on_equity_pct, interest_coverage"
    )
    if year:
        sql = (
            f"SELECT {cols} FROM financial_ratios "
            "WHERE debt_to_equity <= ? AND debt_to_equity >= 0 AND year = ? "
            "ORDER BY debt_to_equity ASC LIMIT ?"
        )
        return _fetch_dict(conn, sql, (max_de, year, limit))
    sql = (
        f"SELECT {cols} FROM financial_ratios "
        "WHERE debt_to_equity <= ? AND debt_to_equity >= 0 "
        "ORDER BY debt_to_equity ASC LIMIT ?"
    )
    return _fetch_dict(conn, sql, (max_de, limit))


def screen_positive_fcf(
    conn: sqlite3.Connection,
    min_years: int = 3,
    year: Optional[str] = None,
) -> list[dict]:
    """Companies with positive FCF for at least min_years total."""
    if year:
        sql = (
            "SELECT company_id, COUNT(*) as positive_years, year "
            "FROM financial_ratios "
            "WHERE free_cash_flow_cr > 0 AND year <= ? "
            "GROUP BY company_id "
            "HAVING positive_years >= ? "
            "ORDER BY positive_years DESC"
        )
        return _fetch_dict(conn, sql, (year, min_years))
    sql = (
        "SELECT company_id, COUNT(*) as positive_years "
        "FROM financial_ratios "
        "WHERE free_cash_flow_cr > 0 "
        "GROUP BY company_id "
        "HAVING positive_years >= ? "
        "ORDER BY positive_years DESC"
    )
    return _fetch_dict(conn, sql, (min_years,))


def top_n_by_kpi(
    conn: sqlite3.Connection,
    kpi_column: str,
    n: int = 10,
    ascending: bool = False,
    year: Optional[str] = None,
) -> list[dict]:
    """Get top / bottom N companies by any KPI column.

    Raises ValueError for unrecognised columns (SQL injection guard).
    """
    allowed = {
        "net_profit_margin_pct",
        "operating_profit_margin_pct",
        "return_on_equity_pct",
        "return_on_capital_employed_pct",
        "return_on_assets_pct",
        "debt_to_equity",
        "interest_coverage",
        "asset_turnover",
        "free_cash_flow_cr",
        "capex_intensity",
        "fcf_conversion_rate",
        "cfo_quality_score",
        "earnings_per_share",
        "book_value_per_share",
        "dividend_payout_ratio_pct",
        "composite_quality_score",
        "revenue_cagr_3yr",
        "revenue_cagr_5yr",
        "revenue_cagr_10yr",
        "pat_cagr_3yr",
        "pat_cagr_5yr",
        "pat_cagr_10yr",
        "eps_cagr_3yr",
        "eps_cagr_5yr",
        "eps_cagr_10yr",
    }
    if kpi_column not in allowed:
        raise ValueError(
            f"Invalid KPI column: {kpi_column}. "
            f"Allowed: {sorted(allowed)}"
        )

    order = "ASC" if ascending else "DESC"
    if year:
        sql = (
            f"SELECT company_id, year, {kpi_column} "
            f"FROM financial_ratios "
            f"WHERE year = ? AND {kpi_column} IS NOT NULL "
            f"ORDER BY {kpi_column} {order} LIMIT ?"
        )
        return _fetch_dict(conn, sql, (year, n))
    sql = (
        f"SELECT company_id, year, {kpi_column} "
        f"FROM financial_ratios "
        f"WHERE {kpi_column} IS NOT NULL "
        f"ORDER BY {kpi_column} {order} LIMIT ?"
    )
    return _fetch_dict(conn, sql, (n,))


def get_company_ratios(
    conn: sqlite3.Connection,
    company_id: str,
    start_year: Optional[str] = None,
    end_year: Optional[str] = None,
) -> list[dict]:
    """All ratios for one company, optionally filtered by year range."""
    if start_year and end_year:
        sql = (
            "SELECT * FROM financial_ratios "
            "WHERE company_id = ? AND year >= ? AND year <= ? "
            "ORDER BY year"
        )
        return _fetch_dict(conn, sql, (company_id, start_year, end_year))
    if start_year:
        sql = (
            "SELECT * FROM financial_ratios "
            "WHERE company_id = ? AND year >= ? ORDER BY year"
        )
        return _fetch_dict(conn, sql, (company_id, start_year))
    if end_year:
        sql = (
            "SELECT * FROM financial_ratios "
            "WHERE company_id = ? AND year <= ? ORDER BY year"
        )
        return _fetch_dict(conn, sql, (company_id, end_year))
    return _fetch_dict(
        conn,
        "SELECT * FROM financial_ratios WHERE company_id = ? ORDER BY year",
        (company_id,),
    )


def get_sector_stats(
    conn: sqlite3.Connection,
    year: str,
    sector_col: str = "broad_sector",
) -> list[dict]:
    """Aggregate KPI stats per sector for a given year.

    Requires the sectors table to be populated.
    """
    sql = (
        f"SELECT s.{sector_col} as sector, "
        f"  COUNT(r.company_id) as company_count, "
        f"  AVG(r.return_on_equity_pct) as avg_roe, "
        f"  AVG(r.net_profit_margin_pct) as avg_npm, "
        f"  AVG(r.debt_to_equity) as avg_de, "
        f"  AVG(r.composite_quality_score) as avg_quality_score "
        f"FROM financial_ratios r "
        f"JOIN sectors s ON r.company_id = s.company_id "
        f"WHERE r.year = ? "
        f"GROUP BY s.{sector_col} "
        f"ORDER BY avg_quality_score DESC"
    )
    return _fetch_dict(conn, sql, (year,))


def ratio_summary(conn: sqlite3.Connection) -> dict:
    """High-level summary of the financial_ratios table."""
    total = _fetch_dict(
        conn, "SELECT COUNT(*) as cnt FROM financial_ratios"
    )
    companies = _fetch_dict(
        conn, "SELECT COUNT(DISTINCT company_id) as cnt FROM financial_ratios"
    )
    years = _fetch_dict(
        conn, "SELECT COUNT(DISTINCT year) as cnt FROM financial_ratios"
    )
    nulls = _fetch_dict(conn, """
        SELECT
            SUM(CASE WHEN net_profit_margin_pct IS NULL THEN 1 ELSE 0 END)
                AS npm_nulls,
            SUM(CASE WHEN return_on_equity_pct IS NULL THEN 1 ELSE 0 END)
                AS roe_nulls,
            SUM(CASE WHEN debt_to_equity IS NULL THEN 1 ELSE 0 END)
                AS de_nulls,
            SUM(CASE WHEN free_cash_flow_cr IS NULL THEN 1 ELSE 0 END)
                AS fcf_nulls,
            SUM(CASE WHEN composite_quality_score IS NULL THEN 1 ELSE 0 END)
                AS qs_nulls
        FROM financial_ratios
    """)
    top_q = _fetch_dict(conn, """
        SELECT company_id, year, composite_quality_score
        FROM financial_ratios
        WHERE composite_quality_score IS NOT NULL
        ORDER BY composite_quality_score DESC LIMIT 5
    """)
    return {
        "total_rows": total[0]["cnt"] if total else 0,
        "distinct_companies": companies[0]["cnt"] if companies else 0,
        "distinct_years": years[0]["cnt"] if years else 0,
        "null_counts": nulls[0] if nulls else {},
        "top_5_quality": top_q,
    }