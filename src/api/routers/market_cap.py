"""src/api/routers/market_cap.py — Market Capitalisation & Valuation Multiples (Day 40).

Sprint 6, Day 40

Endpoints:
1. GET /api/v1/market-cap/{ticker} — Historical valuation multiples (P/E, P/B, EV/EBITDA, dividend yield) from 2019 to 2024.
"""

from __future__ import annotations

import sqlite3
from typing import Any, Dict, List

from fastapi import APIRouter, HTTPException

from src.api.routers.health import get_db_path

router = APIRouter(prefix="/market-cap", tags=["Market Cap & Multiples"])


@router.get("/{ticker}", summary="Get Historical Valuation Multiples (2019-2024)")
async def get_historical_multiples(ticker: str) -> Dict[str, Any]:
    """Return historical valuation multiples (P/E, P/B, EV/EBITDA, dividend yield) from 2019 to 2024."""
    db_path = get_db_path()
    if not db_path.exists():
        raise HTTPException(status_code=503, detail="Database not available")

    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    try:
        cid = ticker.upper().strip()
        comp = conn.execute(
            """
            SELECT c.company_id, c.company_name, s.sector_name
            FROM companies c
            LEFT JOIN sectors s ON c.sector_id = s.sector_id
            WHERE UPPER(c.company_id) = ?
            """,
            (cid,),
        ).fetchone()

        if not comp:
            raise HTTPException(
                status_code=404,
                detail=f"Company with ticker '{ticker}' not found",
            )

        query = """
            SELECT m.company_id, m.year, m.market_cap_cr,
                   i.net_income, i.ebitda, i.operating_income,
                   b.total_equity, b.reserves, b.share_capital,
                   b.borrowings, b.cash_and_equiv,
                   c.dividend_paid,
                   r.price_to_earnings, r.price_to_book, r.dividend_payout
            FROM market_cap m
            LEFT JOIN income_statement i ON m.company_id = i.company_id AND m.year = i.year
            LEFT JOIN balance_sheet b ON m.company_id = b.company_id AND m.year = b.year
            LEFT JOIN cash_flow c ON m.company_id = c.company_id AND m.year = c.year
            LEFT JOIN ratios r ON m.company_id = r.company_id AND m.year = r.year
            WHERE UPPER(m.company_id) = ?
            ORDER BY m.year ASC
        """
        rows = conn.execute(query, (cid,)).fetchall()

        multiples = []
        for r in rows:
            yr = r["year"]
            mcap = r["market_cap_cr"]
            ni = r["net_income"]

            # Equity fallback
            eq = r["total_equity"]
            if (eq is None or eq <= 0) and r["reserves"] is not None:
                eq = (r["share_capital"] or 0.0) + r["reserves"]

            ebitda = r["ebitda"] if r["ebitda"] is not None else r["operating_income"]
            borr = r["borrowings"] or 0.0
            cash = r["cash_and_equiv"] or 0.0
            div = abs(r["dividend_paid"] or 0.0)

            # P/E Ratio
            pe = r["price_to_earnings"]
            if (pe is None or pe <= 0) and mcap and ni and ni > 0:
                pe = round(mcap / ni, 2)

            # P/B Ratio
            pb = r["price_to_book"]
            if (pb is None or pb <= 0) and mcap and eq and eq > 0:
                pb = round(mcap / eq, 2)

            # EV / EBITDA
            ev_ebitda = None
            if mcap and ebitda and ebitda > 0:
                ev = mcap + borr - cash
                ev_ebitda = round(ev / ebitda, 2)

            # Dividend Yield (%)
            div_yield = 0.0
            if mcap and mcap > 0 and div > 0:
                div_yield = round((div / mcap) * 100.0, 2)

            multiples.append({
                "year": yr,
                "market_cap_cr": round(mcap, 2) if mcap is not None else None,
                "pe_ratio": round(pe, 2) if pe is not None else None,
                "pb_ratio": round(pb, 2) if pb is not None else None,
                "ev_ebitda": round(ev_ebitda, 2) if ev_ebitda is not None else None,
                "dividend_yield_pct": div_yield,
            })

        return {
            "company_id": cid,
            "company_name": comp["company_name"],
            "sector": comp["sector_name"],
            "total_years": len(multiples),
            "multiples": multiples,
        }
    finally:
        conn.close()
