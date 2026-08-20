"""src/api/routers/sectors.py — Sectors Endpoints.

Sprint 6, Day 38
"""

from __future__ import annotations

import sqlite3
from typing import Any, Dict, List

from fastapi import APIRouter, HTTPException

from src.api.routers.health import get_db_path

router = APIRouter(prefix="/sectors", tags=["Sectors"])


@router.get("", summary="List All Sectors with Company Counts")
async def list_sectors() -> Dict[str, Any]:
    """Retrieve all sectors with constituent company counts and industry details."""
    db_path = get_db_path()
    if not db_path.exists():
        raise HTTPException(status_code=503, detail="Database not available")

    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    try:
        rows = conn.execute(
            """
            SELECT s.sector_id, s.sector_name, COUNT(c.company_id) AS company_count
            FROM sectors s
            LEFT JOIN companies c ON s.sector_id = c.sector_id
            GROUP BY s.sector_id, s.sector_name
            ORDER BY company_count DESC, s.sector_name ASC
            """
        ).fetchall()

        items = [dict(row) for row in rows]
        return {
            "total_sectors": len(items),
            "sectors": items,
        }
    finally:
        conn.close()


@router.get("/{sector_id}", summary="Get Sector Detail and Constituents")
async def get_sector(sector_id: int) -> Dict[str, Any]:
    """Get single sector details and all constituent companies."""
    db_path = get_db_path()
    if not db_path.exists():
        raise HTTPException(status_code=503, detail="Database not available")

    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    try:
        sector = conn.execute(
            "SELECT sector_id, sector_name FROM sectors WHERE sector_id = ?",
            (sector_id,),
        ).fetchone()

        if not sector:
            raise HTTPException(status_code=404, detail=f"Sector with ID {sector_id} not found")

        companies = conn.execute(
            "SELECT company_id, company_name, nse_symbol FROM companies WHERE sector_id = ? ORDER BY company_id ASC",
            (sector_id,),
        ).fetchall()

        return {
            "sector": dict(sector),
            "company_count": len(companies),
            "companies": [dict(c) for c in companies],
        }
    finally:
        conn.close()
