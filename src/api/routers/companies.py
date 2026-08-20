"""src/api/routers/companies.py — Companies Endpoints.

Sprint 6, Day 38
"""

from __future__ import annotations

import sqlite3
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, HTTPException, Query

from src.api.routers.health import get_db_path

router = APIRouter(prefix="/companies", tags=["Companies"])


@router.get("", summary="List Nifty 100 Companies")
async def list_companies(
    sector: Optional[str] = Query(None, description="Filter by sector name"),
    search: Optional[str] = Query(None, description="Search by ticker or name"),
    limit: int = Query(100, ge=1, le=200),
    offset: int = Query(0, ge=0),
) -> Dict[str, Any]:
    """Retrieve list of companies with optional sector filtering and keyword search."""
    db_path = get_db_path()
    if not db_path.exists():
        raise HTTPException(status_code=503, detail="Database not available")

    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    try:
        query = """
            SELECT c.company_id, c.company_name, c.nse_symbol, c.isin, s.sector_name
            FROM companies c
            LEFT JOIN sectors s ON c.sector_id = s.sector_id
            WHERE 1=1
        """
        params: List[Any] = []
        if sector:
            query += " AND LOWER(s.sector_name) LIKE ?"
            params.append(f"%{sector.lower()}%")
        if search:
            query += " AND (LOWER(c.company_id) LIKE ? OR LOWER(c.company_name) LIKE ?)"
            params.extend([f"%{search.lower()}%", f"%{search.lower()}%"])

        query += " ORDER BY c.company_id ASC LIMIT ? OFFSET ?"
        params.extend([limit, offset])

        rows = conn.execute(query, params).fetchall()
        total_count = conn.execute("SELECT COUNT(*) FROM companies").fetchone()[0]

        items = [dict(row) for row in rows]
        return {
            "total": total_count,
            "count": len(items),
            "offset": offset,
            "limit": limit,
            "items": items,
        }
    finally:
        conn.close()


@router.get("/{company_id}", summary="Get Company Overview & Financials")
async def get_company(company_id: str) -> Dict[str, Any]:
    """Get single company details, sector, and latest financial summary."""
    db_path = get_db_path()
    if not db_path.exists():
        raise HTTPException(status_code=503, detail="Database not available")

    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    try:
        cid = company_id.upper().strip()
        comp = conn.execute(
            """
            SELECT c.company_id, c.company_name, c.nse_symbol, c.isin, s.sector_name
            FROM companies c
            LEFT JOIN sectors s ON c.sector_id = s.sector_id
            WHERE UPPER(c.company_id) = ?
            """,
            (cid,),
        ).fetchone()

        if not comp:
            raise HTTPException(status_code=404, detail=f"Company '{company_id}' not found")

        ratios = conn.execute(
            "SELECT * FROM ratios WHERE UPPER(company_id) = ? ORDER BY year DESC LIMIT 1",
            (cid,),
        ).fetchone()

        return {
            "company": dict(comp),
            "latest_ratios": dict(ratios) if ratios else None,
        }
    finally:
        conn.close()
