"""Integration spot-checks across Sprint 3 modules."""

from __future__ import annotations

import sqlite3

import pandas as pd
import pytest

from src.screener.engine import FilterEngine
from src.screener.scoring import compute_all_scores
from src.analytics.peer import (
    compute_peer_percentiles,
    get_peer_group_members,
    save_peer_percentiles,
    load_peer_percentiles,
)


# ---------------------------------------------------------------------------
# Shared pipeline fixture — 6 companies, 3 sectors, 13 columns
# ---------------------------------------------------------------------------

@pytest.fixture()
def pipeline_df() -> pd.DataFrame:
    """Small multi-sector DataFrame for end-to-end spot checks."""
    return pd.DataFrame(
        {
            "company_name": [
                "TCS", "Infosys", "HDFC Bank",
                "KotakBank", "ITC", "HUL",
            ],
            "broad_sector": [
                "IT", "IT", "Financial Services",
                "Financial Services", "FMCG", "FMCG",
            ],
            "year": [2024] * 6,
            "roe": [45.0, 38.0, 16.0, 14.0, 26.0, 30.0],
            "roce": [60.0, 50.0, 11.0, 10.0, 30.0, 40.0],
            "net_profit_margin": [25.0, 22.0, 21.0, 18.0, 25.0, 16.0],
            "debt_to_equity": [0.05, 0.1, 6.0, 5.0, 0.02, 0.3],
            "interest_coverage_ratio": [100.0, 80.0, 2.2, 2.0, 40.0, 20.0],
            "revenue_cagr_5yr": [11.0, 9.0, 15.0, 14.0, 8.0, 10.0],
            "pat_cagr_5yr": [12.0, 10.0, 13.0, 11.0, 9.0, 10.0],
            "free_cash_flow": [1000, 800, 500, 300, 600, 700],
            "cfo_quality_score": [1.1, 1.05, 0.95, 0.9, 1.0, 1.02],
            "fcf_conversion_rate": [0.8, 0.75, 0.6, 0.55, 0.7, 0.72],
        }
    )


def _make_peer_df(pipeline_df: pd.DataFrame) -> pd.DataFrame:
    """Rename pipeline_df columns to match PEER_METRICS names."""
    peer_df = pipeline_df.rename(columns={
        "roe": "ROE",
        "roce": "ROCE",
        "net_profit_margin": "NPM",
        "debt_to_equity": "D/E",
        "interest_coverage_ratio": "ICR",
        "revenue_cagr_5yr": "Revenue CAGR 5Y",
        "pat_cagr_5yr": "PAT CAGR 5Y",
    })
    peer_df["OPM"] = pipeline_df["net_profit_margin"] * 0.8
    peer_df["CFO Quality"] = pipeline_df["cfo_quality_score"]
    peer_df["OCF Ratio"] = pipeline_df["fcf_conversion_rate"]
    return peer_df


# ---------------------------------------------------------------------------
# FilterEngine spot-checks
# ---------------------------------------------------------------------------

class TestFilterEngineSpotCheck:
    """Spot-check FilterEngine with real config."""

    def test_apply_returns_filtered_df(self, pipeline_df):
        engine = FilterEngine()
        result = engine.apply(pipeline_df, min_return_on_equity=10.0)
        assert isinstance(result, pd.DataFrame)
        assert len(result) <= len(pipeline_df)
        assert "composite_quality_score" in result.columns

    def test_apply_with_no_filters_returns_all(self, pipeline_df):
        engine = FilterEngine()
        result = engine.apply(pipeline_df)
        assert len(result) == len(pipeline_df)
        assert "composite_quality_score" in result.columns


# ---------------------------------------------------------------------------
# Scoring spot-checks
# ---------------------------------------------------------------------------

class TestScoringSpotCheck:
    """Spot-check compute_all_scores / compute_composite_score."""

    def test_composite_in_range(self, pipeline_df):
        scores = compute_all_scores(pipeline_df, sector_col="broad_sector")
        valid = scores["composite_score"].dropna()
        assert (valid >= 0).all() and (valid <= 100).all()

    def test_all_scores_has_five_columns(self, pipeline_df):
        scores = compute_all_scores(pipeline_df, sector_col="broad_sector")
        expected = {
            "composite_score", "profitability_score",
            "cash_quality_score", "growth_score", "leverage_score",
        }
        assert expected.issubset(set(scores.columns))

    def test_best_company_has_highest_composite(self, pipeline_df):
        scores = compute_all_scores(pipeline_df, sector_col="broad_sector")
        best_idx = scores["composite_score"].idxmax()
        # TCS has highest ROE (45), ROCE (60), NPM (25) — should win
        assert pipeline_df.loc[best_idx, "company_name"] == "TCS"


# ---------------------------------------------------------------------------
# Peer spot-checks
# ---------------------------------------------------------------------------

class TestPeerSpotCheck:
    """Spot-check peer percentile computation."""

    def test_peer_percentiles_saved(self, pipeline_df, tmp_path):
        db_path = tmp_path / "test_peer.db"
        conn = sqlite3.connect(str(db_path))

        peer_df = _make_peer_df(pipeline_df)
        pct = compute_peer_percentiles(peer_df)
        save_peer_percentiles(pct, conn)

        rows = conn.execute(
            "SELECT COUNT(*) FROM peer_percentiles"
        ).fetchone()[0]
        assert rows > 0
        conn.close()

    def test_peer_percentiles_in_range(self, pipeline_df):
        peer_df = _make_peer_df(pipeline_df)
        pct = compute_peer_percentiles(peer_df)
        # Column is "percentile_rank" (actual name from peer.py)
        valid = pct["percentile_rank"].dropna()
        assert (valid >= 0).all() and (valid <= 100).all()

    def test_it_has_three_members(self, pipeline_df):
        members = get_peer_group_members(pipeline_df, "IT", year=2024)
        assert len(members) == 2  # TCS + Infosys


# ---------------------------------------------------------------------------
# Data Quality spot-check
# ---------------------------------------------------------------------------

class TestDataQualitySpotCheck:
    """Spot-check DQ rules pass on a clean pipeline DataFrame."""

    def test_pipeline_df_passes_dq(self, pipeline_df):
        from src.analytics.data_quality import run_dq_checks
        # pipeline_df is clean — should have zero violations
        result = run_dq_checks(pipeline_df, sector_col="broad_sector")
        total = sum(len(v) for v in result.values())
        assert total == 0


# ---------------------------------------------------------------------------
# End-to-end pipeline spot-check
# ---------------------------------------------------------------------------

class TestEndToEndPipeline:
    """Filter → Score → Peer: cross-module consistency."""

    def test_filter_score_peer_consistent(self, pipeline_df):
        """Filter → Score: best company should be best everywhere."""
        engine = FilterEngine()
        filtered = engine.apply(pipeline_df, min_return_on_equity=10.0)
        scores = compute_all_scores(filtered, sector_col="broad_sector")
        best_idx = scores["composite_score"].idxmax()
        best_name = filtered.loc[best_idx, "company_name"]
        # TCS has highest ROE (45) and ROCE (60)
        assert best_name == "TCS"

    def test_peer_db_round_trip(self, pipeline_df, tmp_path):
        """Peer percentiles save → load round-trip."""
        db_path = tmp_path / "test_rt.db"
        conn = sqlite3.connect(str(db_path))

        peer_df = _make_peer_df(pipeline_df)
        pct = compute_peer_percentiles(peer_df)
        save_peer_percentiles(pct, conn)

        loaded = load_peer_percentiles(conn, company_name="TCS", year=2024)
        assert len(loaded) > 0
        assert "percentile_rank" in loaded.columns
        conn.close()