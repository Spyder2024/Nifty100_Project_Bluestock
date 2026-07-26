"""Tests for the 14 data quality rules (Day 21)."""

import numpy as np
import pandas as pd
import pytest

from src.analytics.data_quality import (
    ALL_DQ_RULES,
    DQ_RULE_NAMES,
    FINANCIAL_METRICS,
    check_cagr_range,
    check_cfo_quality_range,
    check_de_non_negative,
    check_icr_non_negative,
    check_npm_range,
    check_no_duplicate_company_year,
    check_no_negative_market_cap,
    check_no_negative_revenue,
    check_not_all_null_metrics,
    check_ocf_ratio_range,
    check_roce_range,
    check_roe_range,
    check_sector_not_null,
    check_year_range,
    dq_summary,
    run_dq_checks,
)


# ── Clean fixture ──────────────────────────────────────────────────────────────

@pytest.fixture
def clean_df():
    """4 rows, all values within acceptable ranges."""
    return pd.DataFrame(
        {
            "company_name": ["A", "B", "C", "D"],
            "sector": ["IT", "FMCG", "Bank", "Auto"],
            "year": [2022, 2023, 2024, 2023],
            "market_cap": [1000, 2000, 3000, 4000],
            "revenue_from_operations": [500, 600, 700, 800],
            "return_on_equity": [15.0, 20.0, -5.0, 30.0],
            "return_on_capital_employed": [18.0, 22.0, -3.0, 25.0],
            "net_profit_margin": [10.0, 15.0, -2.0, 20.0],
            "debt_to_equity": [0.5, 0.3, 1.0, 0.0],
            "interest_coverage_ratio": [10.0, 15.0, 2.0, 20.0],
            "cfo_quality_score": [0.8, 0.9, 0.6, 0.85],
            "operating_cash_flow_ratio": [1.0, 1.2, 0.5, 1.4],
            "revenue_cagr_5yr": [10.0, 15.0, 5.0, 20.0],
            "net_profit_cagr_5yr": [12.0, 18.0, 3.0, 22.0],
        }
    )


# ── Rule 1: No negative market cap ────────────────────────────────────────────

class TestNoNegativeMarketCap:
    def test_catches_negative(self):
        df = pd.DataFrame({"market_cap": [100, -50, 200]})
        result = check_no_negative_market_cap(df)
        assert 1 in result

    def test_passes_clean(self, clean_df):
        assert check_no_negative_market_cap(clean_df) == []

    def test_missing_column_returns_empty(self):
        df = pd.DataFrame({"x": [1, 2]})
        assert check_no_negative_market_cap(df) == []


# ── Rule 2: No negative revenue ───────────────────────────────────────────────

class TestNoNegativeRevenue:
    def test_catches_negative(self):
        df = pd.DataFrame({"revenue_from_operations": [100, -10]})
        result = check_no_negative_revenue(df)
        assert 1 in result

    def test_passes_clean(self, clean_df):
        assert check_no_negative_revenue(clean_df) == []


# ── Rule 3: ROE range ────────────────────────────────────────────────────────

class TestROERange:
    def test_catches_too_high(self):
        df = pd.DataFrame({"return_on_equity": [15.0, 600.0]})
        assert 1 in check_roe_range(df)

    def test_catches_too_low(self):
        df = pd.DataFrame({"return_on_equity": [-150.0, 10.0]})
        assert 0 in check_roe_range(df)

    def test_boundary_passes(self):
        df = pd.DataFrame({"return_on_equity": [-100.0, 500.0]})
        assert check_roe_range(df) == []

    def test_passes_clean(self, clean_df):
        assert check_roe_range(clean_df) == []


# ── Rule 4: ROCE range ───────────────────────────────────────────────────────

class TestROCERange:
    def test_catches_out_of_range(self):
        df = pd.DataFrame({"return_on_capital_employed": [10.0, 501.0]})
        assert 1 in check_roce_range(df)

    def test_passes_clean(self, clean_df):
        assert check_roce_range(clean_df) == []


# ── Rule 5: D/E non-negative ────────────────────────────────────────────────

class TestDENonNegative:
    def test_catches_negative(self):
        df = pd.DataFrame({"debt_to_equity": [0.5, -1.0, 0.3]})
        assert 1 in check_de_non_negative(df)

    def test_zero_is_valid(self):
        df = pd.DataFrame({"debt_to_equity": [0.0, 0.0]})
        assert check_de_non_negative(df) == []

    def test_passes_clean(self, clean_df):
        assert check_de_non_negative(clean_df) == []


# ── Rule 6: ICR non-negative ────────────────────────────────────────────────

class TestICRNonNegative:
    def test_catches_negative(self):
        df = pd.DataFrame({"interest_coverage_ratio": [5.0, -2.0]})
        assert 1 in check_icr_non_negative(df)

    def test_passes_clean(self, clean_df):
        assert check_icr_non_negative(clean_df) == []


# ── Rule 7: CFO quality range ───────────────────────────────────────────────

class TestCFOQualityRange:
    def test_catches_negative(self):
        df = pd.DataFrame({"cfo_quality_score": [0.5, -0.1]})
        assert 1 in check_cfo_quality_range(df)

    def test_catches_above_max(self):
        df = pd.DataFrame({"cfo_quality_score": [0.8, 2.5]})
        assert 1 in check_cfo_quality_range(df)

    def test_passes_clean(self, clean_df):
        assert check_cfo_quality_range(clean_df) == []


# ── Rule 8: OCF ratio range ────────────────────────────────────────────────

class TestOCFRatioRange:
    def test_catches_above_max(self):
        df = pd.DataFrame({"operating_cash_flow_ratio": [1.0, 6.0]})
        assert 1 in check_ocf_ratio_range(df)

    def test_passes_clean(self, clean_df):
        assert check_ocf_ratio_range(clean_df) == []


# ── Rule 9: CAGR range ──────────────────────────────────────────────────────

class TestCAGRRange:
    def test_catches_extreme_positive(self):
        df = pd.DataFrame({"revenue_cagr_5yr": [10.0, 400.0]})
        assert 1 in check_cagr_range(df)

    def test_catches_extreme_negative(self):
        df = pd.DataFrame({"net_profit_cagr_5yr": [-90.0, 5.0]})
        assert 0 in check_cagr_range(df)

    def test_checks_all_cagr_columns(self):
        df = pd.DataFrame({
            "revenue_cagr_5yr": [10.0, 500.0],
            "net_profit_cagr_5yr": [5.0, 500.0],
            "ebitda_cagr_5yr": [3.0, 500.0],
        })
        result = check_cagr_range(df)
        assert 1 in result

    def test_passes_clean(self, clean_df):
        assert check_cagr_range(clean_df) == []


# ── Rule 10: NPM range ──────────────────────────────────────────────────────

class TestNPMRange:
    def test_catches_out_of_range(self):
        df = pd.DataFrame({"net_profit_margin": [-150.0, 10.0]})
        assert 0 in check_npm_range(df)

    def test_passes_clean(self, clean_df):
        assert check_npm_range(clean_df) == []


# ── Rule 11: No duplicate company-year ──────────────────────────────────────

class TestNoDuplicateCompanyYear:
    def test_catches_dupes(self):
        df = pd.DataFrame({
            "company_name": ["A", "A", "B"],
            "year": [2024, 2024, 2024],
        })
        result = check_no_duplicate_company_year(df)
        assert len(result) == 2  # both rows 0 and 1 are flagged

    def test_passes_unique(self, clean_df):
        assert check_no_duplicate_company_year(clean_df) == []


# ── Rule 12: Sector not null ────────────────────────────────────────────────

class TestSectorNotNull:
    def test_catches_null(self):
        df = pd.DataFrame({"sector": ["IT", None, "FMCG"]})
        result = check_sector_not_null(df)
        assert 1 in result

    def test_catches_empty_string(self):
        df = pd.DataFrame({"sector": ["IT", "", "FMCG"]})
        result = check_sector_not_null(df)
        assert 1 in result

    def test_passes_clean(self, clean_df):
        assert check_sector_not_null(clean_df) == []


# ── Rule 13: Year range ─────────────────────────────────────────────────────

class TestYearRange:
    def test_catches_too_old(self):
        df = pd.DataFrame({"year": [2005, 2024]})
        assert 0 in check_year_range(df)

    def test_catches_future(self):
        df = pd.DataFrame({"year": [2024, 2099]})
        assert 1 in check_year_range(df)

    def test_passes_clean(self, clean_df):
        assert check_year_range(clean_df) == []


# ── Rule 14: Not all-null metrics ───────────────────────────────────────────

class TestNotNullAllMetrics:
    def test_catches_all_null_row(self):
        df = pd.DataFrame({
            "return_on_equity": [15.0, np.nan],
            "debt_to_equity": [0.5, np.nan],
            "net_profit_margin": [10.0, np.nan],
        })
        result = check_not_all_null_metrics(df)
        assert 1 in result

    def test_partial_null_passes(self):
        df = pd.DataFrame({
            "return_on_equity": [15.0, np.nan],
            "debt_to_equity": [0.5, 1.0],
        })
        result = check_not_all_null_metrics(df)
        assert 1 not in result

    def test_passes_clean(self, clean_df):
        assert check_not_all_null_metrics(clean_df) == []


# ── Runner & summary ──────────────────────────────────────────────────────────

class TestRunDQChecks:
    def test_returns_all_rule_names(self, clean_df):
        result = run_dq_checks(clean_df)
        assert set(result.keys()) == set(DQ_RULE_NAMES)

    def test_clean_df_all_pass(self, clean_df):
        result = run_dq_checks(clean_df)
        for rule, violations in result.items():
            assert violations == [], f"{rule} failed on clean data: {violations}"


class TestDQSummary:
    def test_all_pass_summary(self, clean_df):
        result = run_dq_checks(clean_df)
        summary = dq_summary(result)
        assert summary["rules_failed"] == 0
        assert summary["rules_passed"] == 14
        assert summary["total_violations"] == 0

    def test_failed_rules_listed(self):
        df = pd.DataFrame({
            "market_cap": [-100],
            "return_on_equity": [600],
        })
        result = run_dq_checks(df)
        summary = dq_summary(result)
        assert summary["rules_failed"] >= 2
        assert "check_no_negative_market_cap" in summary["failed_rules"]
        assert "check_roe_range" in summary["failed_rules"]

    def test_total_violations(self):
        df = pd.DataFrame({
            "market_cap": [-100, -200, 300],
        })
        result = run_dq_checks(df)
        summary = dq_summary(result)
        assert summary["total_violations"] == 2


class TestRegistry:
    def test_fourteen_rules(self):
        assert len(ALL_DQ_RULES) == 14

    def test_all_rules_callable(self):
        for rule in ALL_DQ_RULES:
            assert callable(rule)

    def test_rule_names_unique(self):
        assert len(DQ_RULE_NAMES) == len(set(DQ_RULE_NAMES))