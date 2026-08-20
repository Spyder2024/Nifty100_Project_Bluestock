"""src/api/routers/screener.py — Screener Endpoints (Day 40).

Sprint 6, Day 40

Endpoints:
1. GET /api/v1/screener — Multi-metric stock screener with validation and ranking.
   Parameters: min_roe, max_de, min_fcf, sector, min_rev_cagr_5yr, min_pat_cagr_5yr, max_pe, limit, offset.
   Returns HTTP 400 for invalid parameter values.
2. GET /api/v1/screener/presets — Curated screening strategy presets.
"""

from __future__ import annotations

import sqlite3
from typing import Any, Dict, Optional

from fastapi import APIRouter, HTTPException, Query

from src.api.routers.health import get_db_path

router = APIRouter(prefix="/screener", tags=["Screener"])


def _validate_screener_params(
    min_roe: Optional[float],
    max_de: Optional[float],
    min_fcf: Optional[float],
    min_rev_cagr_5yr: Optional[float],
    min_pat_cagr_5yr: Optional[float],
    max_pe: Optional[float],
) -> None:
    """Validate query parameters and raise HTTP 400 if invalid."""
    if min_roe is not None and (min_roe < -100.0 or min_roe > 1000.0):
        raise HTTPException(
            status_code=400,
            detail=f"Invalid min_roe value: {min_roe}. Expected value between -100 and 1000.",
        )
    if max_de is not None and (max_de < 0.0 or max_de > 100.0):
        raise HTTPException(
            status_code=400,
            detail=f"Invalid max_de value: {max_de}. Expected non-negative value <= 100.",
        )
    if max_pe is not None and max_pe <= 0.0:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid max_pe value: {max_pe}. Expected positive number.",
        )
    if min_rev_cagr_5yr is not None and (
        min_rev_cagr_5yr < -100.0 or min_rev_cagr_5yr > 10000.0
    ):
        raise HTTPException(
            status_code=400,
            detail=f"Invalid min_rev_cagr_5yr value: {min_rev_cagr_5yr}.",
        )
    if min_pat_cagr_5yr is not None and (
        min_pat_cagr_5yr < -100.0 or min_pat_cagr_5yr > 10000.0
    ):
        raise HTTPException(
            status_code=400,
            detail=f"Invalid min_pat_cagr_5yr value: {min_pat_cagr_5yr}.",
        )


@router.get("", summary="Run Multi-Metric Stock Screener")
async def run_screener(
    min_roe: Optional[float] = Query(None, description="Minimum Return on Equity (%)"),
    max_de: Optional[float] = Query(None, description="Maximum Debt to Equity"),
    min_fcf: Optional[float] = Query(
        None, description="Minimum Free Cash Flow in ₹ Cr"
    ),
    sector: Optional[str] = Query(None, description="Filter by sector name"),
    min_rev_cagr_5yr: Optional[float] = Query(
        None, description="Minimum 5-Yr Revenue CAGR (%)"
    ),
    min_pat_cagr_5yr: Optional[float] = Query(
        None, description="Minimum 5-Yr PAT/Net Profit CAGR (%)"
    ),
    max_pe: Optional[float] = Query(
        None, description="Maximum Price to Earnings multiple"
    ),
    limit: int = Query(50, ge=1, le=100, description="Limit results"),
    offset: int = Query(0, ge=0, description="Offset results"),
) -> Dict[str, Any]:
    """Execute ranked fundamental screener across Nifty 100 constituents."""
    # 1. Validation
    _validate_screener_params(
        min_roe=min_roe,
        max_de=max_de,
        min_fcf=min_fcf,
        min_rev_cagr_5yr=min_rev_cagr_5yr,
        min_pat_cagr_5yr=min_pat_cagr_5yr,
        max_pe=max_pe,
    )

    db_path = get_db_path()
    if not db_path.exists():
        raise HTTPException(status_code=503, detail="Database not available")

    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    try:
        # Fetch all companies with latest financials, CAGR, and valuation multiples
        companies = conn.execute("""
            SELECT c.company_id, c.company_name, s.sector_name AS sector
            FROM companies c
            LEFT JOIN sectors s ON c.sector_id = s.sector_id
            ORDER BY c.company_id ASC
            """).fetchall()

        ratios_all = conn.execute(
            "SELECT * FROM ratios ORDER BY company_id, year DESC"
        ).fetchall()
        is_all = conn.execute(
            "SELECT * FROM income_statement ORDER BY company_id, year ASC"
        ).fetchall()
        cf_all = conn.execute(
            "SELECT * FROM cash_flow ORDER BY company_id, year ASC"
        ).fetchall()
        mcap_all = conn.execute(
            "SELECT * FROM market_cap ORDER BY company_id, year DESC"
        ).fetchall()

        # Group data by company
        from collections import defaultdict

        ratios_by_co = defaultdict(list)
        for r in ratios_all:
            ratios_by_co[r["company_id"]].append(dict(r))

        is_by_co = defaultdict(list)
        for r in is_all:
            is_by_co[r["company_id"]].append(dict(r))

        cf_by_co = defaultdict(list)
        for r in cf_all:
            cf_by_co[r["company_id"]].append(dict(r))

        mcap_by_co = defaultdict(list)
        for r in mcap_all:
            mcap_by_co[r["company_id"]].append(dict(r))

        matched_records = []
        for comp in companies:
            cid = comp["company_id"]
            sec_name = comp["sector"] or "Unclassified"

            # Sector filter
            if sector and sector.lower() not in sec_name.lower():
                continue

            r_list = ratios_by_co.get(cid, [])
            is_list = is_by_co.get(cid, [])
            cf_list = cf_by_co.get(cid, [])
            mc_list = mcap_by_co.get(cid, [])

            latest_r = r_list[0] if r_list else {}
            latest_is = is_list[-1] if is_list else {}
            latest_cf = cf_list[-1] if cf_list else {}
            latest_mc = mc_list[0] if mc_list else {}

            # Metrics extraction
            roe = latest_r.get("roe")
            if roe is None and latest_is and latest_r.get("total_equity"):
                tot_eq = latest_r.get("total_equity") or 0.0
                if tot_eq > 0:
                    roe = ((latest_is.get("net_income") or 0.0) / tot_eq) * 100.0

            de = latest_r.get("debt_to_equity")
            opm = latest_r.get("opm")
            if opm is None and latest_is and latest_is.get("revenue"):
                rev_val = latest_is.get("revenue") or 0.0
                if rev_val > 0:
                    opm = ((latest_is.get("operating_income") or 0.0) / rev_val) * 100.0

            fcf = latest_cf.get("fcf")
            if fcf is None and latest_cf:
                fcf = (latest_cf.get("operating_cf") or 0.0) - (
                    latest_cf.get("capex") or 0.0
                )

            # Revenue 5Y CAGR
            rev_cagr = None
            if len(is_list) >= 6:
                s_rev = is_list[-6].get("revenue")
                e_rev = is_list[-1].get("revenue")
                if s_rev and e_rev and s_rev > 0 and e_rev > 0:
                    rev_cagr = ((e_rev / s_rev) ** (1.0 / 5.0) - 1.0) * 100.0
            elif len(is_list) >= 2:
                ny = len(is_list) - 1
                s_rev = is_list[0].get("revenue")
                e_rev = is_list[-1].get("revenue")
                if s_rev and e_rev and s_rev > 0 and e_rev > 0:
                    rev_cagr = ((e_rev / s_rev) ** (1.0 / ny) - 1.0) * 100.0

            # PAT 5Y CAGR
            pat_cagr = None
            if len(is_list) >= 6:
                s_pat = is_list[-6].get("net_income")
                e_pat = is_list[-1].get("net_income")
                if s_pat and e_pat and s_pat > 0 and e_pat > 0:
                    pat_cagr = ((e_pat / s_pat) ** (1.0 / 5.0) - 1.0) * 100.0
            elif len(is_list) >= 2:
                ny = len(is_list) - 1
                s_pat = is_list[0].get("net_income")
                e_pat = is_list[-1].get("net_income")
                if s_pat and e_pat and s_pat > 0 and e_pat > 0:
                    pat_cagr = ((e_pat / s_pat) ** (1.0 / ny) - 1.0) * 100.0

            # P/E Ratio
            pe = latest_r.get("price_to_earnings")
            if pe is None and latest_mc and latest_is:
                mcap = latest_mc.get("market_cap_cr")
                ni = latest_is.get("net_income")
                if mcap and ni and ni > 0:
                    pe = round(mcap / ni, 2)

            # Apply Filter Thresholds
            if min_roe is not None and (roe is None or roe < min_roe):
                continue
            if max_de is not None and (de is None or de > max_de):
                continue
            if min_fcf is not None and (fcf is None or fcf < min_fcf):
                continue
            if min_rev_cagr_5yr is not None and (
                rev_cagr is None or rev_cagr < min_rev_cagr_5yr
            ):
                continue
            if min_pat_cagr_5yr is not None and (
                pat_cagr is None or pat_cagr < min_pat_cagr_5yr
            ):
                continue
            if max_pe is not None and (pe is None or pe > max_pe):
                continue

            # Composite rank score (higher is better)
            score = (
                (roe or 0.0) * 0.4
                + (opm or 0.0) * 0.3
                + (rev_cagr or 0.0) * 0.3
                - (de or 0.0) * 5.0
            )

            matched_records.append(
                {
                    "company_id": cid,
                    "company_name": comp["company_name"],
                    "sector": sec_name,
                    "roe": round(roe, 2) if roe is not None else None,
                    "debt_to_equity": round(de, 2) if de is not None else None,
                    "fcf_cr": round(fcf, 2) if fcf is not None else None,
                    "revenue_cagr_5yr": (
                        round(rev_cagr, 2) if rev_cagr is not None else None
                    ),
                    "pat_cagr_5yr": (
                        round(pat_cagr, 2) if pat_cagr is not None else None
                    ),
                    "pe_ratio": round(pe, 2) if pe is not None else None,
                    "score": round(score, 2),
                }
            )

        # Sort by composite score descending
        matched_records.sort(key=lambda x: x["score"], reverse=True)

        for idx, rec in enumerate(matched_records, 1):
            rec["rank"] = idx

        paginated = matched_records[offset : offset + limit]

        return {
            "filters_applied": {
                "min_roe": min_roe,
                "max_de": max_de,
                "min_fcf": min_fcf,
                "sector": sector,
                "min_rev_cagr_5yr": min_rev_cagr_5yr,
                "min_pat_cagr_5yr": min_pat_cagr_5yr,
                "max_pe": max_pe,
            },
            "total_matched": len(matched_records),
            "count": len(paginated),
            "offset": offset,
            "limit": limit,
            "results": paginated,
        }
    finally:
        conn.close()


@router.get("/presets", summary="List Screener Preset Strategies")
async def list_presets() -> Dict[str, Any]:
    """Return available screener preset screening strategies."""
    presets = [
        {
            "id": "quality_compounders",
            "preset_id": "quality_compounders",
            "name": "Quality Compounders",
            "preset_name": "quality_compounders",
            "description": "High ROE, low leverage, strong operating profit margins",
            "filters": {"min_roe": 15.0, "max_de": 0.5, "min_rev_cagr_5yr": 10.0},
        },
        {
            "id": "debt_free_compounders",
            "preset_id": "debt_free_compounders",
            "name": "Debt-Free Compounders",
            "preset_name": "debt_free_compounders",
            "description": "Zero or negligible debt with solid return metrics",
            "filters": {"max_de": 0.0, "min_roe": 15.0},
        },
        {
            "id": "high_growth",
            "preset_id": "high_growth",
            "name": "High Growth Momentum",
            "preset_name": "high_growth",
            "description": "Rapid top-line and bottom-line compounding",
            "filters": {"min_rev_cagr_5yr": 15.0, "min_pat_cagr_5yr": 15.0},
        },
        {
            "id": "deep_value",
            "preset_id": "deep_value",
            "name": "Value with Margin of Safety",
            "preset_name": "deep_value",
            "description": "Reasonable valuation multiples with solid cash flow generation",
            "filters": {"max_pe": 25.0, "min_fcf": 100.0, "max_de": 1.0},
        },
        {
            "id": "cash_machines",
            "preset_id": "cash_machines",
            "name": "Free Cash Flow Machines",
            "preset_name": "cash_machines",
            "description": "Substantial positive free cash flow generation",
            "filters": {"min_fcf": 1000.0, "min_roe": 12.0},
        },
    ]
    return {"total_presets": len(presets), "presets": presets}
