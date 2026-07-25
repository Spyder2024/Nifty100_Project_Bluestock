"""Tests for P10/P90 winsorised sector-relative scoring (Day 17)."""

import numpy as np
import pandas as pd
import pytest

from src.screener.scoring import (
    winsorise_series,
    sector_relative_score,
    compute_composite_score,
    compute_all_scores,
    CATEGORY_WEIGHTS,
    ALL_SCORING_METRICS,
    CATEGORY_MAP,
    LOWER_IS_BETTER,
    PROFITABILITY_METRICS,
    CASH_QUALITY_METRICS,
    GROWTH_METRICS,
    LEVERAGE_METRICS,
)


# ── Fixtures ──────────────────────────────────────────────────────────────────

@pytest.fixture
def single_sector_df():
    """4 companies, 1 sector, 2 metrics — basic scoring lab."""
    return pd.DataFrame(
        {
            "company_name": ["A", "B", "C", "D"],
            "sector": ["Tech"] * 4,
            "return_on_equity": [10.0, 15.0, 20.0, 25.0],
            "debt_to_equity": [0.5, 1.0, 1.5, 2.0],
        }
    )


@pytest.fixture
def multi_sector_df():
    """8 companies × 2 sectors × 11 metrics — cross-sector scoring."""
    return pd.DataFrame(
        {
            "company_name": ["A", "B", "C", "D", "E", "F", "G", "H"],
            "sector": ["Tech", "Tech", "Tech", "Tech",
                       "Bank", "Bank", "Bank", "Bank"],
            "return_on_equity":          [10, 15, 20, 25,  8, 12, 16, 20],
            "return_on_capital_employed": [12, 18, 24, 30, 10, 15, 20, 25],
            "net_profit_margin":         [10, 15, 20, 25,  8, 12, 16, 20],
            "operating_profit_margin":   [15, 20, 25, 30, 12, 16, 20, 24],
            "cfo_quality_score":        [0.6, 0.7, 0.8, 0.9, 0.5, 0.6, 0.7, 0.8],
            "operating_cash_flow_ratio": [0.8, 1.0, 1.2, 1.4, 0.6, 0.8, 1.0, 1.2],
            "revenue_cagr_5yr":         [5.0, 10, 15, 20,  3.0, 7.0, 11, 15],
            "net_profit_cagr_5yr":      [8.0, 12, 16, 20,  5.0, 9.0, 13, 17],
            "ebitda_cagr_5yr":          [6.0, 10, 14, 18,  4.0, 8.0, 12, 16],
            "debt_to_equity":           [0.5, 0.8, 1.2, 2.0, 0.3, 0.6, 1.0, 1.5],
            "interest_coverage_ratio":  [10,  15,  20, 25,   8,  12,  16, 20],
        }
    )


@pytest.fixture
def df_with_nan():
    """Some NaN metric values."""
    return pd.DataFrame(
        {
            "company_name": ["A", "B", "C"],
            "sector": ["Tech"] * 3,
            "return_on_equity": [15.0, np.nan, 25.0],
            "debt_to_equity": [0.5, 1.0, np.nan],
        }
    )


@pytest.fixture
def single_company_sector():
    """Edge case: sector with only 1 company."""
    return pd.DataFrame(
        {
            "company_name": ["Solo"],
            "sector": ["Niche"],
            "return_on_equity": [15.0],
            "debt_to_equity": [0.5],
        }
    )


# ── Winsorise ────────────────────────────────────────────────────────────────

class TestWinsoriseSeries:
    def test_clips_upper_outlier(self):
        s = pd.Series([1.0, 2.0, 3.0, 4.0, 100.0])
        w = winsorise_series(s)
        assert w.iloc[-1] < 100.0

    def test_clips_lower_outlier(self):
        s = pd.Series([-100.0, 2.0, 3.0, 4.0, 5.0])
        w = winsorise_series(s)
        assert w.iloc[0] > -100.0

    def test_preserves_middle_values(self):
        s = pd.Series([1.0, 2.0, 3.0, 4.0, 5.0])
        w = winsorise_series(s, lower_pct=0.2, upper_pct=0.8)
        assert w.iloc[2] == 3.0

    def test_preserves_nan(self):
        s = pd.Series([1.0, np.nan, 3.0])
        w = winsorise_series(s)
        assert pd.isna(w.iloc[1])

    def test_single_valid_value_returns_copy(self):
        s = pd.Series([5.0, np.nan, np.nan])
        w = winsorise_series(s)
        assert w.iloc[0] == 5.0 and pd.isna(w.iloc[1])

    def test_all_nan_returns_all_nan(self):
        s = pd.Series([np.nan, np.nan])
        w = winsorise_series(s)
        assert w.isna().all()


# ── Sector-Relative Score ────────────────────────────────────────────────────

class TestSectorRelativeScore:
    def test_scores_in_0_to_100(self, single_sector_df):
        scores = sector_relative_score(single_sector_df, "return_on_equity")
        valid = scores.dropna()
        assert (valid >= 0).all() and (valid <= 100).all()

    def test_higher_roe_gets_higher_score(self, single_sector_df):
        scores = sector_relative_score(single_sector_df, "return_on_equity")
        # D (ROE=25) > A (ROE=10)
        assert scores.iloc[3] > scores.iloc[0]

    def test_inverts_debt_to_equity(self, single_sector_df):
        scores = sector_relative_score(single_sector_df, "debt_to_equity")
        # D has highest D/E → should get LOWEST score (inverted)
        assert scores.iloc[3] < scores.iloc[0]

    def test_single_company_gets_neutral(self, single_company_sector):
        scores = sector_relative_score(single_company_sector, "return_on_equity")
        assert scores.iloc[0] == 50.0

    def test_nan_metric_stays_nan(self, df_with_nan):
        scores = sector_relative_score(df_with_nan, "return_on_equity")
        assert pd.isna(scores.iloc[1])

    def test_missing_column_returns_all_nan(self, single_sector_df):
        scores = sector_relative_score(single_sector_df, "nonexistent")
        assert scores.isna().all()

    def test_identical_values_same_score(self):
        df = pd.DataFrame({
            "company_name": ["X", "Y", "Z"],
            "sector": ["S"] * 3,
            "return_on_equity": [15.0, 15.0, 15.0],
        })
        scores = sector_relative_score(df, "return_on_equity").dropna()
        assert len(scores.unique()) == 1

    def test_cross_sector_independence(self, multi_sector_df):
        """Lowest in each sector should get the same percentile."""
        scores = sector_relative_score(multi_sector_df, "return_on_equity")
        tech_min = scores.iloc[:4].min()
        bank_min = scores.iloc[4:].min()
        # Both are the minimum of a 4-company sector → rank 0.125 → 12.5
        assert abs(tech_min - bank_min) < 1.0


# ── Composite Score ──────────────────────────────────────────────────────────

class TestCompositeScore:
    def test_returns_series(self, multi_sector_df):
        result = compute_composite_score(multi_sector_df)
        assert isinstance(result, pd.Series)
        assert len(result) == len(multi_sector_df)

    def test_scores_in_0_to_100(self, multi_sector_df):
        valid = compute_composite_score(multi_sector_df).dropna()
        assert (valid >= 0).all() and (valid <= 100).all()

    def test_best_company_scores_higher(self, multi_sector_df):
        result = compute_composite_score(multi_sector_df)
        # D (Tech, best metrics) should beat A (Tech, worst)
        assert result.iloc[3] > result.iloc[0]

    def test_empty_df_returns_empty_series(self):
        empty = pd.DataFrame({"company_name": [], "sector": []})
        assert len(compute_composite_score(empty)) == 0


# ── Compute All Scores ───────────────────────────────────────────────────────

class TestComputeAllScores:
    def test_returns_dataframe(self, multi_sector_df):
        assert isinstance(compute_all_scores(multi_sector_df), pd.DataFrame)

    def test_has_all_five_score_columns(self, multi_sector_df):
        cols = compute_all_scores(multi_sector_df).columns.tolist()
        for expected in [
            "composite_score", "profitability_score",
            "cash_quality_score", "growth_score", "leverage_score",
        ]:
            assert expected in cols

    def test_weights_reconstruct_composite(self, multi_sector_df):
        r = compute_all_scores(multi_sector_df)
        reconstructed = (
            0.35 * r["profitability_score"]
            + 0.30 * r["cash_quality_score"]
            + 0.20 * r["growth_score"]
            + 0.15 * r["leverage_score"]
        )
        np.testing.assert_allclose(r["composite_score"], reconstructed.round(2), atol=0.01)

    def test_empty_df_has_correct_columns(self):
        empty = pd.DataFrame({"company_name": [], "sector": []})
        r = compute_all_scores(empty)
        assert "composite_score" in r.columns and len(r) == 0

    def test_two_companies_get_50_and_100(self):
        df = pd.DataFrame({
            "company_name": ["Lo", "Hi"],
            "sector": ["S"] * 2,
            "return_on_equity": [10.0, 20.0],
        })
        scores = compute_all_scores(df)
        # Only profitability has data; others are 50.0
        assert scores["profitability_score"].iloc[0] == 50.0
        assert scores["profitability_score"].iloc[1] == 100.0
        assert scores["growth_score"].iloc[0] == 50.0


# ── Edge Cases ───────────────────────────────────────────────────────────────

class TestEdgeCases:
    def test_all_nan_metrics(self):
        df = pd.DataFrame({
            "company_name": ["A", "B"],
            "sector": ["S"] * 2,
            "return_on_equity": [np.nan, np.nan],
        })
        r = compute_all_scores(df)
        assert len(r) == 2 and "composite_score" in r.columns

    def test_missing_metrics_get_neutral(self):
        df = pd.DataFrame({
            "company_name": ["A", "B"],
            "sector": ["S"] * 2,
            "return_on_equity": [15.0, 12.0],
        })
        r = compute_all_scores(df)
        # No growth metrics → neutral 50
        assert r["growth_score"].iloc[0] == 50.0

    def test_different_metric_availability_per_sector(self):
        df = pd.DataFrame({
            "company_name": ["A", "B"],
            "sector": ["Tech", "Bank"],
            "return_on_equity": [15.0, 12.0],
        })
        r = compute_all_scores(df)
        # Each sector has 1 company → neutral 50 for all
        assert r["profitability_score"].iloc[0] == 50.0


# ── Constants ────────────────────────────────────────────────────────────────

class TestConstants:
    def test_weights_sum_to_one(self):
        assert abs(sum(CATEGORY_WEIGHTS.values()) - 1.0) < 1e-9

    def test_every_metric_has_category(self):
        for m in ALL_SCORING_METRICS:
            assert m in CATEGORY_MAP, f"{m} missing from CATEGORY_MAP"

    def test_de_in_lower_is_better(self):
        assert "debt_to_equity" in LOWER_IS_BETTER

    def test_icr_not_in_lower_is_better(self):
        assert "interest_coverage_ratio" not in LOWER_IS_BETTER

    def test_metric_counts(self):
        assert len(PROFITABILITY_METRICS) == 4
        assert len(CASH_QUALITY_METRICS) == 2
        assert len(GROWTH_METRICS) == 3
        assert len(LEVERAGE_METRICS) == 2
        assert len(ALL_SCORING_METRICS) == 11