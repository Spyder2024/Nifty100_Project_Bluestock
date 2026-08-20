"""src/api/routers/documents.py — Generated Documents & Reports Metadata.

Sprint 6, Day 38
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, List

from fastapi import APIRouter, HTTPException

router = APIRouter(prefix="/documents", tags=["Documents & Reports"])

PROJECT_ROOT = Path(__file__).resolve().parents[3]


@router.get("", summary="List Generated PDF Reports & Artifacts")
async def list_documents() -> Dict[str, Any]:
    """List available generated reports including tearsheets, sector reports, and portfolio summaries."""
    reports_dir = PROJECT_ROOT / "reports"

    tearsheets = list(reports_dir.glob("tearsheets/*.pdf"))
    sector_reports = list(reports_dir.glob("sector/*.pdf"))
    portfolio_reports = list(reports_dir.glob("portfolio/*.pdf"))
    chart_images = list(reports_dir.glob("*.png"))

    return {
        "summary": {
            "tearsheets_count": len(tearsheets),
            "sector_reports_count": len(sector_reports),
            "portfolio_reports_count": len(portfolio_reports),
            "charts_count": len(chart_images),
        },
        "portfolio_summary_available": (reports_dir / "portfolio" / "portfolio_summary.pdf").exists(),
        "elbow_plot_available": (reports_dir / "elbow_plot.png").exists(),
        "correlation_heatmap_available": (reports_dir / "correlation_heatmap.png").exists(),
    }
