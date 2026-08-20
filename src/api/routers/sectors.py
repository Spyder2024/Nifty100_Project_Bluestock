"""src/api/routers/sectors.py — Sector Analytics Endpoints (Day 40).

Sprint 6, Day 40

Endpoints:
1. GET /api/v1/sectors — return all sectors with company_count, median_roe, median_pe, median_de.
2. GET /api/v1/sectors/{sector}/companies — return all companies in a sector with latest year KPIs (404 for unknown sector).
"""

from __future__ import annotations

import sqlite3
from typing import Any, Dict

import numpy as np
import pandas as pd
from fastapi import APIRouter, HTTPException

from src.api.routers.health import get_db_path

router = APIRouter(prefix="/sectors", tags=["Sectors"])


@router.get("", summary="List All Sectors with Median KPIs")
async def list_sectors() -> Dict[str, Any]:
    """Retrieve all sectors with constituent company counts, median ROE, median P/E, and median D/E."""
    db_path = get_db_path()
    if not db_path.exists():
        raise HTTPException(status_code=503, detail="Database not available")

    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    try:
        # Load companies, sectors, latest ratios, latest income statement, and market cap
        df_comps = pd.read_sql(
            """
            SELECT c.company_id, c.company_name, c.sector_id, s.sector_name
            FROM companies c
            LEFT JOIN sectors s ON c.sector_id = s.sector_id
            """,
            conn,
        )

        df_r = pd.read_sql(
            """
            SELECT r.company_id, r.roe, r.debt_to_equity, r.price_to_earnings
            FROM ratios r
            WHERE r.year = (SELECT MAX(r2.year) FROM ratios r2 WHERE r2.company_id = r.company_id)
            """,
            conn,
        )

        df_is = pd.read_sql(
            """
            SELECT i.company_id, i.net_income
            FROM income_statement i
            WHERE i.year = (SELECT MAX(i2.year) FROM income_statement i2 WHERE i2.company_id = i.company_id)
            """,
            conn,
        )

        df_mc = pd.read_sql(
            """
            SELECT m.company_id, m.market_cap_cr
            FROM market_cap m
            WHERE m.year = (SELECT MAX(m2.year) FROM market_cap m2 WHERE m2.company_id = m.company_id)
            """,
            conn,
        )

        # Merge
        merged = df_comps.merge(df_r, on="company_id", how="left")
        merged = merged.merge(df_is, on="company_id", how="left")
        merged = merged.merge(df_mc, on="company_id", how="left")

        # Compute calculated PE if price_to_earnings is missing
        def calc_pe(row):
            pe = row.get("price_to_earnings")
            if pd.notna(pe) and pe > 0:
                return float(pe)
            mcap = row.get("market_cap_cr")
            ni = row.get("net_income")
            if pd.notna(mcap) and pd.notna(ni) and ni > 0:
                return float(mcap / ni)
            return np.nan

        merged["computed_pe"] = merged.apply(calc_pe, axis=1)

        sector_summary = []
        for sec_name, grp in merged.groupby("sector_name"):
            c_count = len(grp)
            med_roe = (
                float(grp["roe"].dropna().median())
                if not grp["roe"].dropna().empty
                else 0.0
            )
            med_de = (
                float(grp["debt_to_equity"].dropna().median())
                if not grp["debt_to_equity"].dropna().empty
                else 0.0
            )
            med_pe = (
                float(grp["computed_pe"].dropna().median())
                if not grp["computed_pe"].dropna().empty
                else 0.0
            )

            sec_id = grp["sector_id"].iloc[0] if not grp.empty else sec_name

            sector_summary.append(
                {
                    "sector_id": sec_id,
                    "sector_name": sec_name,
                    "company_count": c_count,
                    "median_roe": round(med_roe, 2),
                    "median_pe": round(med_pe, 2) if not np.isnan(med_pe) else None,
                    "median_de": round(med_de, 2),
                }
            )

        sector_summary.sort(key=lambda x: x["company_count"], reverse=True)

        return {
            "total_sectors": len(sector_summary),
            "sectors": sector_summary,
        }
    finally:
        conn.close()


SECTOR_ALIASES: Dict[str, str] = {
    "it": "Information Technology",
    "information technology": "Information Technology",
    "fmcg": "Consumer Staples",
    "pharma": "Healthcare",
    "banking": "Financials",
    "auto": "Consumer Discretionary",
    "telecom": "Communication Services",
    "metals": "Materials",
    "power": "Energy",
    "infra": "Industrials",
    "realty": "Real Estate",
}


@router.get("/{sector}", summary="Get All Companies in a Sector (Direct)")
@router.get("/{sector}/companies", summary="Get All Companies in a Sector")
async def get_sector_companies(sector: str) -> Dict[str, Any]:
    """Retrieve all companies in a specific sector with latest fundamental KPIs."""
    db_path = get_db_path()
    if not db_path.exists():
        raise HTTPException(status_code=503, detail="Database not available")

    # Resolve alias if present
    sec_query = sector.lower().strip()
    sec_target = SECTOR_ALIASES.get(sec_query, sec_query)

    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    try:
        # Check if sector exists
        sec_rows = conn.execute(
            """
            SELECT c.company_id, c.company_name, c.sector_id, s.sector_name,
                   r.roe, r.roce, r.opm, r.net_profit_margin, r.debt_to_equity,
                   r.interest_coverage, r.asset_turnover, r.year AS ratio_year,
                   cf.fcf AS latest_fcf, m.market_cap_cr
            FROM companies c
            LEFT JOIN sectors s ON c.sector_id = s.sector_id
            LEFT JOIN ratios r ON c.company_id = r.company_id
                 AND r.year = (SELECT MAX(r2.year) FROM ratios r2 WHERE r2.company_id = c.company_id)
            LEFT JOIN cash_flow cf ON c.company_id = cf.company_id
                 AND cf.year = (SELECT MAX(cf2.year) FROM cash_flow cf2 WHERE cf2.company_id = c.company_id)
            LEFT JOIN market_cap m ON c.company_id = m.company_id
                 AND m.year = (SELECT MAX(m2.year) FROM market_cap m2 WHERE m2.company_id = c.company_id)
            WHERE LOWER(s.sector_name) = ? OR LOWER(c.sector_id) = ? OR LOWER(s.sector_id) = ?
            ORDER BY r.roe DESC
            """,
            (sec_target.lower(), sec_target.lower(), sec_target.lower()),
        ).fetchall()

        if not sec_rows:
            # Check if sector name has partial match
            partial = conn.execute(
                """
                SELECT s.sector_name FROM sectors s
                WHERE LOWER(s.sector_name) LIKE ? OR LOWER(s.sector_id) LIKE ?
                """,
                (f"%{sec_target}%", f"%{sec_target}%"),
            ).fetchall()

            if not partial:
                raise HTTPException(
                    status_code=404,
                    detail=f"Sector '{sector}' not found in Nifty 100 database",
                )

            # If partial match exists, query with partial pattern
            sec_name_matched = partial[0]["sector_name"]
            sec_rows = conn.execute(
                """
                SELECT c.company_id, c.company_name, c.sector_id, s.sector_name,
                       r.roe, r.roce, r.opm, r.net_profit_margin, r.debt_to_equity,
                       r.interest_coverage, r.asset_turnover, r.year AS ratio_year,
                       cf.fcf AS latest_fcf, m.market_cap_cr
                FROM companies c
                LEFT JOIN sectors s ON c.sector_id = s.sector_id
                LEFT JOIN ratios r ON c.company_id = r.company_id
                     AND r.year = (SELECT MAX(r2.year) FROM ratios r2 WHERE r2.company_id = c.company_id)
                LEFT JOIN cash_flow cf ON c.company_id = cf.company_id
                     AND cf.year = (SELECT MAX(cf2.year) FROM cash_flow cf2 WHERE cf2.company_id = c.company_id)
                LEFT JOIN market_cap m ON c.company_id = m.company_id
                     AND m.year = (SELECT MAX(m2.year) FROM market_cap m2 WHERE m2.company_id = c.company_id)
                WHERE s.sector_name = ?
                ORDER BY r.roe DESC
                """,
                (sec_name_matched,),
            ).fetchall()

        sector_title = sec_rows[0]["sector_name"] if sec_rows else sector
        items = [dict(r) for r in sec_rows]

        return {
            "sector": sector_title,
            "company_count": len(items),
            "companies": items,
        }
    finally:
        conn.close()
