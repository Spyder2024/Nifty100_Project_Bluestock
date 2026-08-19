"""tests/analytics/test_profiling.py — Unit tests for Day 37 cluster profiling, correlation, and statistics.

Tests:
1. 10-KPI feature extraction for all 92 companies.
2. Cluster profiling calculation (mean and median per cluster).
3. Correlation heatmap generation and PNG file persistence.
4. Sector-level Z-score outlier detection.
5. Portfolio distribution statistics (P10, P25, P50, P75, P90, Mean, Std).
6. Full end-to-end run producing all deliverables.
"""

from pathlib import Path
import numpy as np
import pandas as pd
import pytest

from src.analytics.profiling import (
    DEFAULT_DB_PATH,
    KPI_10_COLUMNS,
    compute_portfolio_stats,
    detect_sector_outliers,
    generate_correlation_heatmap,
    load_10_kpis_data,
    profile_clusters,
    run_profiling_and_stats,
)


@pytest.fixture
def sample_kpis_df():
    """Synthetic dataset with known sector structure and financial metrics."""
    return pd.DataFrame({
        "company_id": [f"C{i}" for i in range(1, 11)],
        "company_name": [f"Company {i}" for i in range(1, 11)],
        "sector": ["Financials"] * 5 + ["Industrials"] * 5,
        "return_on_equity_pct": [15.0, 18.0, 12.0, 16.0, 50.0, 22.0, 25.0, 19.0, 21.0, 20.0],
        "return_on_capital_employed_pct": [12.0, 14.0, 10.0, 13.0, 15.0, 20.0, 24.0, 18.0, 19.0, 21.0],
        "operating_profit_margin_pct": [40.0, 45.0, 38.0, 42.0, 41.0, 18.0, 22.0, 19.0, 21.0, 20.0],
        "net_profit_margin_pct": [20.0, 22.0, 18.0, 21.0, 23.0, 10.0, 12.0, 9.0, 11.0, 10.0],
        "debt_to_equity": [6.0, 7.0, 5.5, 6.5, 7.5, 0.5, 0.4, 0.6, 0.5, 0.3],
        "interest_coverage_ratio": [2.5, 3.0, 2.2, 2.8, 3.1, 15.0, 18.0, 14.0, 16.0, 17.0],
        "asset_turnover": [0.15, 0.18, 0.14, 0.16, 0.17, 1.2, 1.4, 1.1, 1.3, 1.2],
        "dividend_payout_pct": [25.0, 30.0, 20.0, 28.0, 22.0, 35.0, 40.0, 32.0, 38.0, 36.0],
        "revenue_cagr_5yr": [12.0, 15.0, 11.0, 14.0, 13.0, 10.0, 12.0, 9.0, 11.0, 10.0],
        "fcf_cagr_5yr": [10.0, 14.0, 8.0, 12.0, 11.0, 16.0, 18.0, 15.0, 17.0, 16.0],
    })


def test_load_10_kpis_data():
    """Verify loading 10 KPIs returns 92 rows with all expected columns."""
    df = load_10_kpis_data(db_path=DEFAULT_DB_PATH)
    assert isinstance(df, pd.DataFrame)
    assert len(df) == 92
    assert "company_id" in df.columns
    assert "company_name" in df.columns
    assert "sector" in df.columns
    for col in KPI_10_COLUMNS:
        assert col in df.columns


def test_profile_clusters():
    """Verify cluster profiling computes mean and median per cluster."""
    df_clustered = pd.DataFrame({
        "company_id": ["A", "B", "C", "D"],
        "cluster_id": [0, 0, 1, 1],
        "return_on_equity_pct": [10.0, 20.0, 30.0, 40.0],
        "debt_to_equity": [0.5, 0.7, 1.0, 1.2],
        "revenue_cagr_5yr": [10.0, 12.0, 15.0, 17.0],
        "fcf_cagr_5yr": [8.0, 10.0, 12.0, 14.0],
        "operating_profit_margin_pct": [20.0, 22.0, 25.0, 27.0],
    })
    profiles = profile_clusters(df_clustered, feature_cols=["return_on_equity_pct", "debt_to_equity"])
    assert len(profiles) == 2
    assert "cluster_id" in profiles.columns
    assert "cluster_name" in profiles.columns
    assert "company_count" in profiles.columns
    assert "return_on_equity_pct_mean" in profiles.columns
    assert "return_on_equity_pct_median" in profiles.columns
    assert profiles.loc[profiles["cluster_id"] == 0, "return_on_equity_pct_mean"].iloc[0] == 15.0


def test_generate_correlation_heatmap(sample_kpis_df, tmp_path):
    """Verify correlation heatmap PNG creation."""
    out_png = tmp_path / "test_heatmap.png"
    result = generate_correlation_heatmap(sample_kpis_df, output_path=out_png, kpi_cols=KPI_10_COLUMNS)
    assert result.exists()
    assert result.stat().st_size > 1024


def test_detect_sector_outliers(sample_kpis_df):
    """Verify sector-level Z-score outlier detection."""
    df_outliers = detect_sector_outliers(sample_kpis_df, metric_cols=KPI_10_COLUMNS, threshold=1.8)
    assert isinstance(df_outliers, pd.DataFrame)
    if not df_outliers.empty:
        assert "company_id" in df_outliers.columns
        assert "sector" in df_outliers.columns
        assert "z_score" in df_outliers.columns
        assert "outlier_type" in df_outliers.columns
        assert (df_outliers["z_score"].abs() >= 1.8).all()


def test_compute_portfolio_stats(sample_kpis_df):
    """Verify portfolio statistics calculation with all quantiles and moments."""
    df_stats = compute_portfolio_stats(sample_kpis_df, metric_cols=KPI_10_COLUMNS)
    assert len(df_stats) == len(KPI_10_COLUMNS)
    assert list(df_stats.columns) == ["metric_name", "display_name", "P10", "P25", "P50", "P75", "P90", "Mean", "Std"]

    # Verify P10 <= P25 <= P50 <= P75 <= P90
    for _, row in df_stats.iterrows():
        assert row["P10"] <= row["P25"] <= row["P50"] <= row["P75"] <= row["P90"]


def test_run_profiling_and_stats_e2e(tmp_path):
    """Verify end-to-end execution and all deliverable artifacts."""
    heatmap_png = tmp_path / "correlation_heatmap.png"
    outlier_csv = tmp_path / "outlier_report.csv"
    stats_csv = tmp_path / "portfolio_stats.csv"
    cluster_labels_csv = tmp_path / "cluster_labels.csv"

    df_prof, df_kpis, df_out, df_stats = run_profiling_and_stats(
        db_path=DEFAULT_DB_PATH,
        heatmap_png=heatmap_png,
        outlier_csv=outlier_csv,
        stats_csv=stats_csv,
        cluster_labels_csv=cluster_labels_csv,
    )

    assert heatmap_png.exists()
    assert outlier_csv.exists()
    assert stats_csv.exists()
    assert cluster_labels_csv.exists()

    assert len(df_prof) == 5
    assert len(df_kpis) == 92
    assert len(df_stats) == 10

    # Verify cluster_labels.csv schema
    df_cl = pd.read_csv(cluster_labels_csv)
    assert len(df_cl) == 92
    assert set(df_cl["cluster_name"].unique()).issubset({
        "High-Quality Core Compounders",
        "Defensive High-ROE Leaders",
        "Emerging Growth & High Margin FinTech",
        "Financial Expansion & High-Leverage Growth",
        "Capital-Efficient Value Cyclicals",
    })
