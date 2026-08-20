"""src/api/routers/screener.py — Screener Endpoints.

Sprint 6, Day 38
"""

from __future__ import annotations

import sqlite3
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, HTTPException, Query

from src.api.routers.health import get_db_path

router = APIRouter(prefix="/screener", tags=["Screener"])


@router.get("", summary="Run Stock Screener Filter")
async def run_screener(
    min_roe: Optional[float] = Query(None, description="Minimum Return on Equity (%)"),
    max_de: Optional[float] = Query(None, description="Maximum Debt to Equity"),
    min_opm: Optional[float] = Query(None, description="Minimum Operating Profit Margin (%)"),
    sector: Optional[str] = Query(None, description="Sector filter"),
    limit: int = Query(50, ge=1, le=100),
) -> Dict[str, Any]:
    """Screen Nifty 100 stocks by custom financial metrics and ratio thresholds."""
    db_path = get_db_path()
    if not db_path.exists():
        raise HTTPException(status_code=503, detail="Database not available")

    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    try:
        query = """
            SELECT c.company_id, c.company_name, s.sector_name,
                   r.roe, r.debt_to_equity, r.opm, r.roce, r.year
            FROM companies c
            LEFT JOIN sectors s ON c.sector_id = s.sector_id
            LEFT JOIN ratios r ON c.company_id = r.company_id
            WHERE r.year = (SELECT MAX(r2.year) FROM ratios r2 WHERE r2.company_id = c.company_id)
        """
        params: List[Any] = []

        if min_roe is not None:
            query += " AND r.roe >= ?"
            params.append(min_roe)
        if max_de is not None:
            query += " AND r.debt_to_equity <= ?"
            params.append(max_de)
        if min_opm is not None:
            query += " AND r.opm >= ?"
            params.append(min_opm)
        if sector:
            query += " AND LOWER(s.sector_name) LIKE ?"
            params.append(f"%{sector.lower()}%")

        query += " ORDER BY r.roe DESC LIMIT ?"
        params.append(limit)

        rows = conn.execute(query, params).fetchall()
        items = [dict(row) for row in rows]

        return {
            "filters_applied": {
                "min_roe": min_roe,
                "max_de": max_de,
                "min_opm": min_opm,
                "sector": sector,
            },
            "matched_count": len(items),
            "results": items,
        }
    finally:
        conn.close()


@router.get("/presets", summary="List Screener Preset Strategies")
async def list_presets() -> Dict[str, Any]:
    """Return available screener preset screening strategies."""
    presets = [
        {"id": "quality_compounders", "name": "Quality Compounders", "criteria": "ROE > 15%, D/E < 0.5, OPM > 18%"},
        {"id": "high_growth", "name": "High Growth Momentum", "criteria": "Rev CAGR 5Y > 15%, FCF CAGR > 15%"},
        {"id": "deep_value", "name": "Deep Value & Dividend", "criteria": "P/E < 20, Dividend Payout > 30%"},
        {"id": "defensive_leaders", "name": "Defensive Market Leaders", "criteria": "Low Debt, Stable Margins > 20%"},
    ]
    return {"total_presets": len(presets), "presets": presets}
