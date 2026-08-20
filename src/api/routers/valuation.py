"""src/api/routers/valuation.py — Valuation Models Endpoints.

Sprint 6, Day 38
"""

from __future__ import annotations

import sqlite3
from typing import Any, Dict, List

from fastapi import APIRouter, HTTPException

from src.api.routers.health import get_db_path

router = APIRouter(prefix="/valuation", tags=["Valuation"])


@router.get("", summary="List Valuation Summary for All Companies")
async def list_valuations() -> Dict[str, Any]:
    """Retrieve intrinsic valuation estimates across Graham, DCF, DDM, and Relative models."""
    db_path = get_db_path()
    if not db_path.exists():
        raise HTTPException(status_code=503, detail="Database not available")

    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    try:
        rows = conn.execute(
            """
            SELECT v.company_id, c.company_name, s.sector_name,
                   v.graham_number, v.dcf_intrinsic_value, v.ddm_intrinsic_value,
                   v.relative_avg_value, v.growth_rate_used, v.wacc_used
            FROM valuation v
            LEFT JOIN companies c ON v.company_id = c.company_id
            LEFT JOIN sectors s ON c.sector_id = s.sector_id
            ORDER BY v.company_id ASC
            """
        ).fetchall()

        items = [dict(row) for row in rows]
        return {
            "total": len(items),
            "valuations": items,
        }
    finally:
        conn.close()


@router.get("/{company_id}", summary="Get Intrinsic Valuation for Company")
async def get_company_valuation(company_id: str) -> Dict[str, Any]:
    """Get multi-model valuation details for a specific company."""
    db_path = get_db_path()
    if not db_path.exists():
        raise HTTPException(status_code=503, detail="Database not available")

    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    try:
        cid = company_id.upper().strip()
        val = conn.execute(
            """
            SELECT v.*, c.company_name, s.sector_name
            FROM valuation v
            LEFT JOIN companies c ON v.company_id = c.company_id
            LEFT JOIN sectors s ON c.sector_id = s.sector_id
            WHERE UPPER(v.company_id) = ?
            """,
            (cid,),
        ).fetchone()

        if not val:
            raise HTTPException(status_code=404, detail=f"Valuation data for '{company_id}' not found")

        return {"valuation": dict(val)}
    finally:
        conn.close()
