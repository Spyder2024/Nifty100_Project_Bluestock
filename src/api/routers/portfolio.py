"""src/api/routers/portfolio.py — Portfolio Statistics & Clustering Endpoints.

Sprint 6, Day 38
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Dict

import pandas as pd
from fastapi import APIRouter, HTTPException

router = APIRouter(prefix="/portfolio", tags=["Portfolio"])

PROJECT_ROOT = Path(__file__).resolve().parents[3]


@router.get("/stats", summary="Get Portfolio-wide Distribution Statistics")
async def get_portfolio_stats() -> Dict[str, Any]:
    """Retrieve P10, P25, P50, P75, P90, Mean, and Std across all 92 constituents."""
    stats_csv = PROJECT_ROOT / "output" / "portfolio_stats.csv"
    if not stats_csv.exists():
        raise HTTPException(
            status_code=404,
            detail="Portfolio statistics not found. Please run profiling pipeline.",
        )

    df = pd.read_csv(stats_csv)
    return {
        "total_metrics": len(df),
        "statistics": df.to_dict(orient="records"),
    }


@router.get("/clusters", summary="Get KMeans Financial Cluster Assignments")
async def get_clusters() -> Dict[str, Any]:
    """Retrieve KMeans financial cluster labels and centroid distances for all companies."""
    clusters_csv = PROJECT_ROOT / "output" / "cluster_labels.csv"
    if not clusters_csv.exists():
        raise HTTPException(status_code=404, detail="Cluster labels not found.")

    df = pd.read_csv(clusters_csv)
    return {
        "total_companies": len(df),
        "clusters": df.to_dict(orient="records"),
    }


@router.get("/outliers", summary="Get Sector Z-Score Outlier Report")
async def get_outliers() -> Dict[str, Any]:
    """Retrieve companies flagged as sector outliers (|Z| > 3.0)."""
    outliers_csv = PROJECT_ROOT / "output" / "outlier_report.csv"
    if not outliers_csv.exists() or outliers_csv.stat().st_size < 5:
        return {"total_outliers": 0, "outliers": []}

    try:
        df = pd.read_csv(outliers_csv)
        return {
            "total_outliers": len(df),
            "outliers": df.to_dict(orient="records"),
        }
    except Exception:
        return {"total_outliers": 0, "outliers": []}
