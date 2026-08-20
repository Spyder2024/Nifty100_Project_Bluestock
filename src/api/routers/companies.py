"""src/api/routers/companies.py — Comprehensive Company Data Endpoints (Day 39).

Sprint 6, Day 39

Endpoints:
1. GET /api/v1/companies — list all 92 companies with id, company_name, broad_sector, sub_sector, roe_pct, roce_pct (filters: sector, market_cap_category, search, pagination).
2. GET /api/v1/companies/{ticker} — full company profile: company fields + latest year KPIs + sector data.
3. GET /api/v1/companies/{ticker}/pl — P&L / Income statement history (filters: from_year, to_year).
4. GET /api/v1/companies/{ticker}/bs — Balance sheet history (filters: from_year, to_year).
5. GET /api/v1/companies/{ticker}/cashflow — Cash flow history (filters: from_year, to_year).
6. GET /api/v1/companies/{ticker}/ratios — Computed KPI ratios history (filters: optional single year or all years).
7. GET /api/v1/companies/{ticker}/tearsheet — Binary PDF download of pre-generated tearsheet.
"""

from __future__ import annotations

import sqlite3
from pathlib import Path
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import FileResponse

from src.api.routers.health import get_db_path

router = APIRouter(prefix="/companies", tags=["Companies"])
PROJECT_ROOT = Path(__file__).resolve().parents[3]


def _get_company_or_404(conn: sqlite3.Connection, ticker: str) -> sqlite3.Row:
    """Helper to verify company existence and return base row or raise 404."""
    cid = ticker.upper().strip()
    comp = conn.execute(
        """
        SELECT c.company_id, c.company_name, c.sector_id, c.nse_symbol,
               c.bse_code, c.isin, c.series, c.face_value,
               s.sector_name AS broad_sector,
               s.sector_name AS sub_sector
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
    return comp


# ===========================================================================
# 1. GET /api/v1/companies
# ===========================================================================

@router.get("", summary="List All Nifty 100 Companies")
async def list_companies(
    sector: Optional[str] = Query(None, description="Filter by sector or broad_sector"),
    market_cap_category: Optional[str] = Query(None, description="Filter by Large Cap / Mid Cap"),
    search: Optional[str] = Query(None, description="Partial search by ticker or company name"),
    limit: int = Query(100, ge=1, le=200, description="Max items per page"),
    offset: int = Query(0, ge=0, description="Offset for pagination"),
) -> Dict[str, Any]:
    """Return list of all 92 companies with id, company_name, broad_sector, sub_sector, roe_pct, roce_pct."""
    db_path = get_db_path()
    if not db_path.exists():
        raise HTTPException(status_code=503, detail="Database not available")

    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    try:
        # Base query with latest ratios and latest market cap
        query = """
            WITH LatestRatios AS (
                SELECT r.company_id, r.roe, r.roce, r.opm, r.debt_to_equity, r.year
                FROM ratios r
                WHERE r.year = (SELECT MAX(r2.year) FROM ratios r2 WHERE r2.company_id = r.company_id)
            ),
            LatestMCap AS (
                SELECT m.company_id, m.market_cap_cr, m.year
                FROM market_cap m
                WHERE m.year = (SELECT MAX(m2.year) FROM market_cap m2 WHERE m2.company_id = m.company_id)
            )
            SELECT
                c.company_id AS id,
                c.company_name,
                s.sector_name AS broad_sector,
                s.sector_name AS sub_sector,
                COALESCE(lr.roe, 0.0) AS roe_pct,
                COALESCE(lr.roce, 0.0) AS roce_pct,
                COALESCE(lm.market_cap_cr, 0.0) AS market_cap_cr
            FROM companies c
            LEFT JOIN sectors s ON c.sector_id = s.sector_id
            LEFT JOIN LatestRatios lr ON c.company_id = lr.company_id
            LEFT JOIN LatestMCap lm ON c.company_id = lm.company_id
            WHERE 1=1
        """
        params: List[Any] = []

        if sector:
            query += " AND (LOWER(s.sector_name) LIKE ? OR LOWER(c.sector_id) LIKE ?)"
            params.extend([f"%{sector.lower()}%", f"%{sector.lower()}%"])

        if search:
            query += " AND (LOWER(c.company_id) LIKE ? OR LOWER(c.company_name) LIKE ?)"
            params.extend([f"%{search.lower()}%", f"%{search.lower()}%"])

        query += " ORDER BY c.company_id ASC"

        all_rows = conn.execute(query, params).fetchall()

        items = []
        for r in all_rows:
            d = dict(r)
            mcap_val = d.pop("market_cap_cr", 0.0)
            cat = "Large Cap" if mcap_val >= 20000.0 or mcap_val == 0.0 else "Mid Cap"
            d["market_cap_category"] = cat

            # Filter by market_cap_category if provided
            if market_cap_category and cat.lower() != market_cap_category.lower():
                continue

            items.append(d)

        total_matching = len(items)
        paginated_items = items[offset : offset + limit]

        return {
            "total": total_matching,
            "count": len(paginated_items),
            "offset": offset,
            "limit": limit,
            "companies": paginated_items,
        }
    finally:
        conn.close()


# ===========================================================================
# 2. GET /api/v1/companies/{ticker}
# ===========================================================================

@router.get("/{ticker}", summary="Get Full Company Profile")
async def get_company_profile(ticker: str) -> Dict[str, Any]:
    """Return full company profile: company fields + latest year KPIs + sector data."""
    db_path = get_db_path()
    if not db_path.exists():
        raise HTTPException(status_code=503, detail="Database not available")

    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    try:
        comp = _get_company_or_404(conn, ticker)
        cid = comp["company_id"]

        # Latest ratios
        latest_ratio = conn.execute(
            "SELECT * FROM ratios WHERE UPPER(company_id) = ? ORDER BY year DESC LIMIT 1",
            (cid,),
        ).fetchone()

        # Latest income statement
        latest_is = conn.execute(
            "SELECT * FROM income_statement WHERE UPPER(company_id) = ? ORDER BY year DESC LIMIT 1",
            (cid,),
        ).fetchone()

        # Latest balance sheet
        latest_bs = conn.execute(
            "SELECT * FROM balance_sheet WHERE UPPER(company_id) = ? ORDER BY year DESC LIMIT 1",
            (cid,),
        ).fetchone()

        # Latest cash flow
        latest_cf = conn.execute(
            "SELECT * FROM cash_flow WHERE UPPER(company_id) = ? ORDER BY year DESC LIMIT 1",
            (cid,),
        ).fetchone()

        # Latest market cap
        latest_mcap = conn.execute(
            "SELECT * FROM market_cap WHERE UPPER(company_id) = ? ORDER BY year DESC LIMIT 1",
            (cid,),
        ).fetchone()

        mcap_cr = latest_mcap["market_cap_cr"] if latest_mcap and latest_mcap["market_cap_cr"] else None
        mcap_cat = "Large Cap" if (mcap_cr is None or mcap_cr >= 20000.0) else "Mid Cap"

        return {
            "id": comp["company_id"],
            "company_name": comp["company_name"],
            "broad_sector": comp["broad_sector"],
            "sub_sector": comp["sub_sector"],
            "sector_id": comp["sector_id"],
            "isin": comp["isin"],
            "nse_symbol": comp["nse_symbol"] or comp["company_id"],
            "series": comp["series"],
            "face_value": comp["face_value"],
            "market_cap_category": mcap_cat,
            "market_cap_cr": mcap_cr,
            "latest_kpis": {
                "year": latest_ratio["year"] if latest_ratio else (latest_is["year"] if latest_is else None),
                "roe_pct": latest_ratio["roe"] if latest_ratio else None,
                "roce_pct": latest_ratio["roce"] if latest_ratio else None,
                "opm_pct": latest_ratio["opm"] if latest_ratio else None,
                "net_profit_margin_pct": latest_ratio["net_profit_margin"] if latest_ratio else None,
                "debt_to_equity": latest_ratio["debt_to_equity"] if latest_ratio else None,
                "interest_coverage": latest_ratio["interest_coverage"] if latest_ratio else None,
                "asset_turnover": latest_ratio["asset_turnover"] if latest_ratio else None,
                "price_to_earnings": latest_ratio["price_to_earnings"] if latest_ratio else None,
                "price_to_book": latest_ratio["price_to_book"] if latest_ratio else None,
                "revenue_latest_cr": latest_is["revenue"] if latest_is else None,
                "net_income_latest_cr": latest_is["net_income"] if latest_is else None,
                "total_equity_latest_cr": latest_bs["total_equity"] if latest_bs else None,
                "operating_cf_latest_cr": latest_cf["operating_cf"] if latest_cf else None,
                "fcf_latest_cr": latest_cf["fcf"] if latest_cf else None,
            },
        }
    finally:
        conn.close()


# ===========================================================================
# 3. GET /api/v1/companies/{ticker}/pl
# ===========================================================================

@router.get("/{ticker}/pl", summary="Get Profit & Loss / Income Statement History")
async def get_company_pl(
    ticker: str,
    from_year: Optional[str] = Query(None, description="Start year in YYYY-MM or YYYY format"),
    to_year: Optional[str] = Query(None, description="End year in YYYY-MM or YYYY format"),
) -> Dict[str, Any]:
    """Return historical Profit & Loss / Income Statement data for the given company."""
    db_path = get_db_path()
    if not db_path.exists():
        raise HTTPException(status_code=503, detail="Database not available")

    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    try:
        comp = _get_company_or_404(conn, ticker)
        cid = comp["company_id"]

        query = "SELECT * FROM income_statement WHERE UPPER(company_id) = ?"
        params: List[Any] = [cid]

        if from_year:
            query += " AND year >= ?"
            params.append(from_year)
        if to_year:
            query += " AND year <= ?"
            params.append(to_year)

        query += " ORDER BY year ASC"
        rows = conn.execute(query, params).fetchall()

        return {
            "company_id": cid,
            "company_name": comp["company_name"],
            "count": len(rows),
            "income_statement": [dict(r) for r in rows],
        }
    finally:
        conn.close()


# ===========================================================================
# 4. GET /api/v1/companies/{ticker}/bs
# ===========================================================================

@router.get("/{ticker}/bs", summary="Get Balance Sheet History")
async def get_company_bs(
    ticker: str,
    from_year: Optional[str] = Query(None, description="Start year in YYYY-MM or YYYY format"),
    to_year: Optional[str] = Query(None, description="End year in YYYY-MM or YYYY format"),
) -> Dict[str, Any]:
    """Return historical Balance Sheet data for the given company."""
    db_path = get_db_path()
    if not db_path.exists():
        raise HTTPException(status_code=503, detail="Database not available")

    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    try:
        comp = _get_company_or_404(conn, ticker)
        cid = comp["company_id"]

        query = "SELECT * FROM balance_sheet WHERE UPPER(company_id) = ?"
        params: List[Any] = [cid]

        if from_year:
            query += " AND year >= ?"
            params.append(from_year)
        if to_year:
            query += " AND year <= ?"
            params.append(to_year)

        query += " ORDER BY year ASC"
        rows = conn.execute(query, params).fetchall()

        return {
            "company_id": cid,
            "company_name": comp["company_name"],
            "count": len(rows),
            "balance_sheet": [dict(r) for r in rows],
        }
    finally:
        conn.close()


# ===========================================================================
# 5. GET /api/v1/companies/{ticker}/cashflow
# ===========================================================================

@router.get("/{ticker}/cashflow", summary="Get Cash Flow History")
async def get_company_cashflow(
    ticker: str,
    from_year: Optional[str] = Query(None, description="Start year in YYYY-MM or YYYY format"),
    to_year: Optional[str] = Query(None, description="End year in YYYY-MM or YYYY format"),
) -> Dict[str, Any]:
    """Return historical Cash Flow statement data for the given company."""
    db_path = get_db_path()
    if not db_path.exists():
        raise HTTPException(status_code=503, detail="Database not available")

    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    try:
        comp = _get_company_or_404(conn, ticker)
        cid = comp["company_id"]

        query = "SELECT * FROM cash_flow WHERE UPPER(company_id) = ?"
        params: List[Any] = [cid]

        if from_year:
            query += " AND year >= ?"
            params.append(from_year)
        if to_year:
            query += " AND year <= ?"
            params.append(to_year)

        query += " ORDER BY year ASC"
        rows = conn.execute(query, params).fetchall()

        return {
            "company_id": cid,
            "company_name": comp["company_name"],
            "count": len(rows),
            "cash_flow": [dict(r) for r in rows],
        }
    finally:
        conn.close()


# ===========================================================================
# 6. GET /api/v1/companies/{ticker}/ratios
# ===========================================================================

@router.get("/{ticker}/ratios", summary="Get Computed KPIs and Financial Ratios History")
async def get_company_ratios(
    ticker: str,
    year: Optional[str] = Query(None, description="Filter for a specific year (e.g. 2024-03)"),
) -> Dict[str, Any]:
    """Return computed KPI ratios across all years (or single year if specified)."""
    db_path = get_db_path()
    if not db_path.exists():
        raise HTTPException(status_code=503, detail="Database not available")

    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    try:
        comp = _get_company_or_404(conn, ticker)
        cid = comp["company_id"]

        query = "SELECT * FROM ratios WHERE UPPER(company_id) = ?"
        params: List[Any] = [cid]

        if year:
            query += " AND year LIKE ?"
            params.append(f"{year}%")

        query += " ORDER BY year ASC"
        rows = conn.execute(query, params).fetchall()

        return {
            "company_id": cid,
            "company_name": comp["company_name"],
            "count": len(rows),
            "ratios": [dict(r) for r in rows],
        }
    finally:
        conn.close()


# ===========================================================================
# 7. GET /api/v1/companies/{ticker}/tearsheet
# ===========================================================================

@router.get("/{ticker}/tearsheet", summary="Download Company Tearsheet PDF")
async def get_company_tearsheet(ticker: str) -> FileResponse:
    """Return pre-generated 2-page company tearsheet PDF as binary file download."""
    db_path = get_db_path()
    if not db_path.exists():
        raise HTTPException(status_code=503, detail="Database not available")

    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    try:
        comp = _get_company_or_404(conn, ticker)
        cid = comp["company_id"]
    finally:
        conn.close()

    # Locate tearsheet PDF
    tearsheet_dir = PROJECT_ROOT / "reports" / "tearsheets"
    pdf_path = tearsheet_dir / f"{cid}_tearsheet.pdf"

    if not pdf_path.exists():
        # Fallback search case-insensitive
        matches = list(tearsheet_dir.glob(f"*{cid}*.pdf"))
        if matches:
            pdf_path = matches[0]
        else:
            raise HTTPException(
                status_code=404,
                detail=f"Tearsheet PDF for '{ticker}' not found at {pdf_path.name}",
            )

    return FileResponse(
        path=str(pdf_path),
        media_type="application/pdf",
        filename=f"{cid}_tearsheet.pdf",
        headers={"Content-Disposition": f"attachment; filename={cid}_tearsheet.pdf"},
    )
