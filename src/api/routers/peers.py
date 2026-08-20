"""src/api/routers/peers.py — Peer Comparison Endpoints.

Sprint 6, Day 38
"""

from __future__ import annotations

import sqlite3
from typing import Any, Dict, List

from fastapi import APIRouter, HTTPException

from src.api.routers.health import get_db_path

router = APIRouter(prefix="/peers", tags=["Peers"])


@router.get("/{company_id}", summary="Get Sector Peers & Metric Comparison")
async def get_company_peers(company_id: str) -> Dict[str, Any]:
    """Retrieve peer group companies within the same sector with key fundamental comparison."""
    db_path = get_db_path()
    if not db_path.exists():
        raise HTTPException(status_code=503, detail="Database not available")

    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    try:
        cid = company_id.upper().strip()
        target = conn.execute(
            """
            SELECT c.company_id, c.company_name, c.sector_id, s.sector_name
            FROM companies c
            LEFT JOIN sectors s ON c.sector_id = s.sector_id
            WHERE UPPER(c.company_id) = ?
            """,
            (cid,),
        ).fetchone()

        if not target:
            raise HTTPException(status_code=404, detail=f"Company '{company_id}' not found")

        sec_id = target["sector_id"]
        peers = conn.execute(
            """
            SELECT c.company_id, c.company_name, r.roe, r.roce, r.opm, r.debt_to_equity
            FROM companies c
            LEFT JOIN ratios r ON c.company_id = r.company_id
                 AND r.year = (SELECT MAX(r2.year) FROM ratios r2 WHERE r2.company_id = c.company_id)
            WHERE c.sector_id = ?
            ORDER BY r.roe DESC
            """,
            (sec_id,),
        ).fetchall()

        return {
            "target_company": dict(target),
            "sector": target["sector_name"],
            "peer_count": len(peers),
            "peers": [dict(p) for p in peers],
        }
    finally:
        conn.close()
