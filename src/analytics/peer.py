"""Peer percentile ranking engine (Day 18).

Maps Nifty 100 companies into 11 broad peer groups, computes
percentile ranks (0–100) for 10 key metrics within each group,
and persists results to a ``peer_percentiles`` SQLite table.

Metrics where lower is better (D/E) are inverted so that a
high percentile always means "better than peers".
"""

import sqlite3
from typing import Optional

import numpy as np
import pandas as pd


# ── Peer Group Definitions ────────────────────────────────────────────────────

PEER_GROUP_MAP: dict[str, str] = {
    # IT
    "IT": "IT",
    "Information Technology": "IT",
    # Financial Services (7 sub-sectors → 1 peer group)
    "Banks": "Financial Services",
    "Banking": "Financial Services",
    "Finance": "Financial Services",
    "Financial Services": "Financial Services",
    "NBFC": "Financial Services",
    "Insurance": "Financial Services",
    "Asset Management": "Financial Services",
    # FMCG
    "FMCG": "FMCG",
    "Consumer Goods": "FMCG",
    # Healthcare
    "Pharma": "Healthcare",
    "Pharmaceuticals": "Healthcare",
    "Healthcare": "Healthcare",
    # Automobile
    "Auto": "Automobile",
    "Automobile": "Automobile",
    # Energy
    "Oil & Gas": "Energy",
    "Energy": "Energy",
    "Petroleum": "Energy",
    "Power": "Energy",
    # Metals & Mining
    "Metals": "Metals & Mining",
    "Mining": "Metals & Mining",
    "Steel": "Metals & Mining",
    # Capital Goods
    "Capital Goods": "Capital Goods",
    "Industrials": "Capital Goods",
    "Manufacturing": "Capital Goods",
    # Consumer Durables
    "Consumer Durables": "Consumer Durables",
    # Telecom
    "Telecom": "Telecom",
    # Cement & Construction
    "Cement": "Cement & Construction",
    "Construction": "Cement & Construction",
    "Infrastructure": "Cement & Construction",
}

ALL_PEER_GROUPS: list[str] = sorted(set(PEER_GROUP_MAP.values()))
"""11 broad peer groups used for percentile ranking."""

# ── Metrics ───────────────────────────────────────────────────────────────────

PEER_METRICS: list[str] = [
    "return_on_equity",
    "return_on_capital_employed",
    "net_profit_margin",
    "operating_profit_margin",
    "cfo_quality_score",
    "operating_cash_flow_ratio",
    "debt_to_equity",
    "interest_coverage_ratio",
    "revenue_cagr_5yr",
    "net_profit_cagr_5yr",
]

PEER_LOWER_IS_BETTER: set[str] = {"debt_to_equity"}


# ── Core Functions ────────────────────────────────────────────────────────────

def resolve_peer_group(sector_series: pd.Series) -> pd.Series:
    """Map sub-sector labels to broad peer groups.

    Unknown sectors pass through unchanged.
    """
    mapped = sector_series.map(PEER_GROUP_MAP)
    return mapped.fillna(sector_series)


def compute_peer_percentiles(
    df: pd.DataFrame,
    metrics: Optional[list[str]] = None,
    sector_col: str = "broad_sector",
    year_col: str = "year",
    name_col: str = "company_name",
    id_col: Optional[str] = None,
) -> pd.DataFrame:
    """Compute percentile ranks within peer groups for each metric."""
    if metrics is None:
        metrics = PEER_METRICS

    if sector_col not in df.columns:
        raise KeyError(f"sector_col '{sector_col}' not in DataFrame columns")

    df = df.copy()
    df["_peer_group"] = resolve_peer_group(df[sector_col])

    records: list[dict] = []

    for (peer_group, year), group in df.groupby(["_peer_group", year_col]):
        for metric in metrics:
            if metric not in group.columns:
                continue

            valid = group[[name_col, metric]].dropna(subset=[metric])

            if valid.empty:
                continue

            if len(valid) < 2:
                pct_ranks = pd.Series(50.0, index=valid.index)
            else:
                pct_ranks = valid[metric].rank(pct=True) * 100.0

            # Invert lower-is-better metrics AFTER computing ranks
            if metric in PEER_LOWER_IS_BETTER:
                pct_ranks = 100.0 - pct_ranks

            for idx in valid.index:
                row = df.loc[idx]
                records.append(
                    {
                        "company_id": (
                            row[id_col]
                            if id_col and id_col in df.columns
                            else ""
                        ),
                        "company_name": row[name_col],
                        "year": int(year),
                        "peer_group": peer_group,
                        "metric_name": metric,
                        "raw_value": row[metric],
                        "percentile_rank": round(float(pct_ranks.loc[idx]), 2),
                        "peer_count": len(valid),
                    }
                )

    result = pd.DataFrame(records)

    if not result.empty and "company_id" in result.columns and result["company_id"].eq("").all():
        result = result.drop(columns=["company_id"])

    return result

# ── SQLite Persistence ────────────────────────────────────────────────────────

def create_peer_table(conn: sqlite3.Connection) -> None:
    """Create the ``peer_percentiles`` table if it does not exist."""
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS peer_percentiles (
            id              INTEGER PRIMARY KEY AUTOINCREMENT,
            company_name    TEXT    NOT NULL,
            year            INTEGER NOT NULL,
            peer_group      TEXT    NOT NULL,
            metric_name     TEXT    NOT NULL,
            raw_value       REAL,
            percentile_rank REAL,
            peer_count      INTEGER,
            UNIQUE(company_name, year, metric_name)
        );
        """
    )
    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_peer_lookup "
        "ON peer_percentiles(company_name, year);"
    )
    conn.commit()


def save_peer_percentiles(
    conn: sqlite3.Connection,
    peer_df: pd.DataFrame,
) -> int:
    """Replace all rows in ``peer_percentiles`` with *peer_df*.

    Returns the number of rows inserted.
    """
    create_peer_table(conn)
    cols = [
        "company_name", "year", "peer_group", "metric_name",
        "raw_value", "percentile_rank", "peer_count",
    ]
    # Only keep columns that exist
    write_cols = [c for c in cols if c in peer_df.columns]
    conn.execute("DELETE FROM peer_percentiles")
    peer_df[write_cols].to_sql(
        "peer_percentiles", conn, if_exists="append", index=False
    )
    count = conn.execute("SELECT COUNT(*) FROM peer_percentiles").fetchone()[0]
    conn.commit()
    return count


def load_peer_percentiles(
    conn: sqlite3.Connection,
    company_name: Optional[str] = None,
    year: Optional[int] = None,
    metric_name: Optional[str] = None,
    peer_group: Optional[str] = None,
) -> pd.DataFrame:
    """Query ``peer_percentiles`` with optional filters."""
    clauses: list[str] = []
    params: list = []

    if company_name is not None:
        clauses.append("company_name = ?")
        params.append(company_name)
    if year is not None:
        clauses.append("year = ?")
        params.append(year)
    if metric_name is not None:
        clauses.append("metric_name = ?")
        params.append(metric_name)
    if peer_group is not None:
        clauses.append("peer_group = ?")
        params.append(peer_group)

    where = (" WHERE " + " AND ".join(clauses)) if clauses else ""
    query = f"SELECT * FROM peer_percentiles{where} ORDER BY company_name, metric_name"
    return pd.read_sql_query(query, conn, params=params)


# ── Query Helpers ─────────────────────────────────────────────────────────────

def get_peer_summary(
    conn: sqlite3.Connection,
    company_name: str,
    year: int,
) -> pd.DataFrame:
    """One-row-per-metric summary for a company in a given year."""
    return load_peer_percentiles(conn, company_name=company_name, year=year)


def get_peer_group_members(
    conn: sqlite3.Connection,
    peer_group: str,
    year: int,
) -> pd.DataFrame:
    """List of distinct companies in a peer group for a year."""
    query = (
        "SELECT DISTINCT company_name "
        "FROM peer_percentiles "
        "WHERE peer_group = ? AND year = ? "
        "ORDER BY company_name"
    )
    return pd.read_sql_query(query, conn, params=[peer_group, year])


def get_top_performers(
    conn: sqlite3.Connection,
    peer_group: str,
    metric_name: str,
    year: int,
    top_n: int = 5,
) -> pd.DataFrame:
    """Top-N companies in a peer group for a metric (highest percentile)."""
    query = (
        "SELECT company_name, raw_value, percentile_rank, peer_count "
        "FROM peer_percentiles "
        "WHERE peer_group = ? AND metric_name = ? AND year = ? "
        "ORDER BY percentile_rank DESC "
        "LIMIT ?"
    )
    return pd.read_sql_query(
        query, conn, params=[peer_group, metric_name, year, top_n]
    )


def get_bottom_performers(
    conn: sqlite3.Connection,
    peer_group: str,
    metric_name: str,
    year: int,
    bottom_n: int = 5,
) -> pd.DataFrame:
    """Bottom-N companies in a peer group for a metric (lowest percentile)."""
    query = (
        "SELECT company_name, raw_value, percentile_rank, peer_count "
        "FROM peer_percentiles "
        "WHERE peer_group = ? AND metric_name = ? AND year = ? "
        "ORDER BY percentile_rank ASC "
        "LIMIT ?"
    )
    return pd.read_sql_query(
        query, conn, params=[peer_group, metric_name, year, bottom_n]
    )