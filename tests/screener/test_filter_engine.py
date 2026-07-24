"""Tests for src/screener/engine.py — Sprint 3 Day 15 Filter Engine.

Covers:
  1. Config loading and validation
  2. All 15 filterable metrics (min and max direction)
  3. D/E Financials sector auto-skip
  4. ICR debt-free = infinity handling
  5. Composite quality score computation
  6. Sorting behaviour
  7. Empty DataFrame handling
  8. Preset loading and application
  9. Override mechanism
  10. Edge cases (NaN, None, missing columns)
"""

from __future__ import annotations

from pathlib import Path
from textwrap import dedent

import numpy as np
import pandas as pd
import pytest
import yaml

from src.screener.engine import FilterEngine, apply_filters, load_preset


# ==================================================================
# Fixtures
# ==================================================================


@pytest.fixture()
def tmp_config(tmp_path: Path) -> Path:
    """Write a minimal screener_config.yaml to tmp_path."""
    config = {
        "filters": {
            "roe": {"column": "roe", "display_name": "ROE", "direction": "min", "default": None, "unit": "%"},
            "debt_to_equity": {"column": "debt_to_equity", "display_name": "D/E", "direction": "max", "default": None, "unit": "x", "skip_sectors": ["Financials", "FIN"]},
            "free_cash_flow": {"column": "free_cash_flow", "display_name": "FCF", "direction": "min", "default": None, "unit": "Cr"},
            "revenue_cagr_5yr": {"column": "revenue_cagr_5yr", "display_name": "Rev CAGR 5Y", "direction": "min", "default": None, "unit": "%"},
            "pat_cagr_5yr": {"column": "pat_cagr_5yr", "display_name": "PAT CAGR 5Y", "direction": "min", "default": None, "unit": "%"},
            "operating_profit_margin": {"column": "operating_profit_margin", "display_name": "OPM", "direction": "min", "default": None, "unit": "%"},
            "pe_ratio": {"column": "pe_ratio", "display_name": "P/E", "direction": "max", "default": None, "unit": "x"},
            "pb_ratio": {"column": "pb_ratio", "display_name": "P/B", "direction": "max", "default": None, "unit": "x"},
            "dividend_yield": {"column": "dividend_yield", "display_name": "Div Yield", "direction": "min", "default": None, "unit": "%"},
            "interest_coverage_ratio": {"column": "interest_coverage_ratio", "display_name": "ICR", "direction": "min", "default": None, "unit": "x", "debt_free_passes": True},
            "market_cap": {"column": "market_cap", "display_name": "Mkt Cap", "direction": "min", "default": None, "unit": "Cr"},
            "net_profit": {"column": "net_profit", "display_name": "Net Profit", "direction": "min", "default": None, "unit": "Cr"},
            "eps_cagr_5yr": {"column": "eps_cagr_5yr", "display_name": "EPS CAGR 5Y", "direction": "min", "default": None, "unit": "%"},
            "asset_turnover": {"column": "asset_turnover", "display_name": "Asset Turn", "direction": "min", "default": None, "unit": "x"},
            "net_sales": {"column": "net_sales", "display_name": "Sales", "direction": "min", "default": None, "unit": "Cr"},
        },
        "presets": {
            "quality_compounder": {
                "display_name": "Quality Compounder",
                "filters": {"roe": 15.0, "debt_to_equity": 1.0, "free_cash_flow": 0.0, "revenue_cagr_5yr": 10.0},
            },
            "value_pick": {
                "display_name": "Value Pick",
                "filters": {"pe_ratio": 20.0, "pb_ratio": 3.0, "debt_to_equity": 2.0, "dividend_yield": 1.0},
            },
        },
        "financial_sectors": ["Financials", "FIN", "NBFC", "Banks"],
    }
    cfg_file = tmp_path / "screener_config.yaml"
    cfg_file.write_text(yaml.dump(config, default_flow_style=False), encoding="utf-8")
    return cfg_file


@pytest.fixture()
def sample_df() -> pd.DataFrame:
    """Realistic 8-company financial_ratios DataFrame for testing."""
    data = [
        # TCS — debt-free, high ROE, IT sector
        {
            "company_id": "TCS", "company_name": "Tata Consultancy Services",
            "year": "2024", "sector_id": "IT", "broad_sector": "IT",
            "roe": 48.5, "roce": 62.3, "net_profit_margin": 19.2,
            "operating_profit_margin": 26.4, "interest_coverage_ratio": None,
            "debt_to_equity": 0.0, "asset_turnover": 0.92,
            "pe_ratio": 32.5, "pb_ratio": 14.8, "dividend_yield": 1.2,
            "dividend_payout_ratio": 38.0, "market_cap": 1450000,
            "net_sales": 240000, "net_profit": 46000, "eps": 126.0,
            "free_cash_flow": 38000, "cfo_quality_score": 115.0,
            "fcf_conversion_rate": 65.0, "revenue_cagr_5yr": 11.5,
            "pat_cagr_5yr": 10.2, "eps_cagr_5yr": 10.0,
            "is_debt_free": 1, "composite_quality_score": None,
        },
        # RELIANCE — leveraged, high revenue, Energy
        {
            "company_id": "RELIANCE", "company_name": "Reliance Industries",
            "year": "2024", "sector_id": "OIL", "broad_sector": "Energy",
            "roe": 8.5, "roce": 10.2, "net_profit_margin": 8.1,
            "operating_profit_margin": 14.5, "interest_coverage_ratio": 4.2,
            "debt_to_equity": 0.65, "asset_turnover": 0.75,
            "pe_ratio": 28.0, "pb_ratio": 2.5, "dividend_yield": 0.3,
            "dividend_payout_ratio": 10.0, "market_cap": 2100000,
            "net_sales": 980000, "net_profit": 79500, "eps": 118.0,
            "free_cash_flow": 15000, "cfo_quality_score": 95.0,
            "fcf_conversion_rate": 25.0, "revenue_cagr_5yr": 12.0,
            "pat_cagr_5yr": 8.5, "eps_cagr_5yr": 8.0,
            "is_debt_free": 0, "composite_quality_score": None,
        },
        # HDFCBANK — Financials, high D/E (normal for bank)
        {
            "company_id": "HDFCBANK", "company_name": "HDFC Bank",
            "year": "2024", "sector_id": "Banks", "broad_sector": "Financials",
            "roe": 16.8, "roce": 7.5, "net_profit_margin": 22.0,
            "operating_profit_margin": 42.0, "interest_coverage_ratio": None,
            "debt_to_equity": 5.8, "asset_turnover": 0.08,
            "pe_ratio": 19.5, "pb_ratio": 2.8, "dividend_yield": 1.1,
            "dividend_payout_ratio": 21.0, "market_cap": 1250000,
            "net_sales": 285000, "net_profit": 62700, "eps": 118.5,
            "free_cash_flow": 45000, "cfo_quality_score": 125.0,
            "fcf_conversion_rate": 72.0, "revenue_cagr_5yr": 18.0,
            "pat_cagr_5yr": 16.5, "eps_cagr_5yr": 14.0,
            "is_debt_free": 0, "composite_quality_score": None,
        },
        # ITC — moderate ROE, high dividend, FMCG
        {
            "company_id": "ITC", "company_name": "ITC Limited",
            "year": "2024", "sector_id": "FMCG", "broad_sector": "FMCG",
            "roe": 26.0, "roce": 30.5, "net_profit_margin": 26.8,
            "operating_profit_margin": 42.0, "interest_coverage_ratio": 12.5,
            "debt_to_equity": 0.01, "asset_turnover": 0.55,
            "pe_ratio": 25.5, "pb_ratio": 6.5, "dividend_yield": 3.2,
            "dividend_payout_ratio": 82.0, "market_cap": 560000,
            "net_sales": 70000, "net_profit": 18800, "eps": 24.0,
            "free_cash_flow": 15000, "cfo_quality_score": 130.0,
            "fcf_conversion_rate": 70.0, "revenue_cagr_5yr": 8.0,
            "pat_cagr_5yr": 9.0, "eps_cagr_5yr": 8.5,
            "is_debt_free": 1, "composite_quality_score": None,
        },
        # VODAIDEA — loss-making, negative equity, Telecom
        {
            "company_id": "VODAIDEA", "company_name": "Vodafone Idea",
            "year": "2024", "sector_id": "TELECOM", "broad_sector": "Telecom",
            "roe": None, "roce": None, "net_profit_margin": -15.0,
            "operating_profit_margin": 22.0, "interest_coverage_ratio": 0.5,
            "debt_to_equity": 8.5, "asset_turnover": 0.35,
            "pe_ratio": None, "pb_ratio": 0.3, "dividend_yield": 0.0,
            "dividend_payout_ratio": None, "market_cap": 85000,
            "net_sales": 45000, "net_profit": -6750, "eps": -8.5,
            "free_cash_flow": -5000, "cfo_quality_score": None,
            "fcf_conversion_rate": None, "revenue_cagr_5yr": -5.0,
            "pat_cagr_5yr": None, "eps_cagr_5yr": None,
            "is_debt_free": 0, "composite_quality_score": None,
        },
        # INFY — high ROE, debt-free, IT
        {
            "company_id": "INFY", "company_name": "Infosys Limited",
            "year": "2024", "sector_id": "IT", "broad_sector": "IT",
            "roe": 31.2, "roce": 42.5, "net_profit_margin": 17.5,
            "operating_profit_margin": 23.0, "interest_coverage_ratio": None,
            "debt_to_equity": 0.0, "asset_turnover": 0.85,
            "pe_ratio": 24.0, "pb_ratio": 7.2, "dividend_yield": 2.5,
            "dividend_payout_ratio": 55.0, "market_cap": 680000,
            "net_sales": 165000, "net_profit": 28800, "eps": 69.0,
            "free_cash_flow": 22000, "cfo_quality_score": 120.0,
            "fcf_conversion_rate": 58.0, "revenue_cagr_5yr": 12.0,
            "pat_cagr_5yr": 11.0, "eps_cagr_5yr": 11.5,
            "is_debt_free": 1, "composite_quality_score": None,
        },
        # HINDUNILVR — moderate, FMCG, positive FCF
        {
            "company_id": "HINDUNILVR", "company_name": "Hindustan Unilever",
            "year": "2024", "sector_id": "FMCG", "broad_sector": "FMCG",
            "roe": 18.0, "roce": 22.0, "net_profit_margin": 10.5,
            "operating_profit_margin": 16.0, "interest_coverage_ratio": 15.0,
            "debt_to_equity": 0.35, "asset_turnover": 1.2,
            "pe_ratio": 55.0, "pb_ratio": 10.0, "dividend_yield": 1.8,
            "dividend_payout_ratio": 95.0, "market_cap": 590000,
            "net_sales": 56000, "net_profit": 5900, "eps": 25.0,
            "free_cash_flow": 7000, "cfo_quality_score": 105.0,
            "fcf_conversion_rate": 48.0, "revenue_cagr_5yr": 5.0,
            "pat_cagr_5yr": 8.0, "eps_cagr_5yr": 7.0,
            "is_debt_free": 0, "composite_quality_score": None,
        },
        # SBIN — Financials (bank), high D/E
        {
            "company_id": "SBIN", "company_name": "State Bank of India",
            "year": "2024", "sector_id": "Banks", "broad_sector": "Financials",
            "roe": 18.5, "roce": 8.0, "net_profit_margin": 12.0,
            "operating_profit_margin": 35.0, "interest_coverage_ratio": 1.5,
            "debt_to_equity": 7.2, "asset_turnover": 0.06,
            "pe_ratio": 10.5, "pb_ratio": 1.8, "dividend_yield": 1.5,
            "dividend_payout_ratio": 16.0, "market_cap": 680000,
            "net_sales": 355000, "net_profit": 42600, "eps": 48.0,
            "free_cash_flow": 35000, "cfo_quality_score": 110.0,
            "fcf_conversion_rate": 60.0, "revenue_cagr_5yr": 14.0,
            "pat_cagr_5yr": 22.0, "eps_cagr_5yr": 18.0,
            "is_debt_free": 0, "composite_quality_score": None,
        },
    ]
    return pd.DataFrame(data)


@pytest.fixture()
def engine(tmp_config: Path) -> FilterEngine:
    """FilterEngine initialised with tmp_config."""
    return FilterEngine(config_path=tmp_config)


# ==================================================================
# 1. Config Loading
# ==================================================================


class TestConfigLoading:
    """Config loading and validation tests."""

    def test_loads_config_successfully(self, tmp_config: Path) -> None:
        engine = FilterEngine(config_path=tmp_config)
        assert len(engine.filters) == 15
        assert len(engine.presets) == 2
        assert "Financials" in engine.financial_sectors

    def test_missing_config_raises_error(self, tmp_path: Path) -> None:
        bad_path = tmp_path / "nonexistent.yaml"
        with pytest.raises(FileNotFoundError, match="Screener config not found"):
            FilterEngine(config_path=bad_path)

    def test_list_filters_returns_all_15(self, engine: FilterEngine) -> None:
        filters = engine.list_filters()
        assert len(filters) == 15
        names = {f["name"] for f in filters}
        assert "roe" in names
        assert "debt_to_equity" in names
        assert "net_sales" in names

    def test_list_presets_returns_names(self, engine: FilterEngine) -> None:
        presets = engine.list_presets()
        assert "quality_compounder" in presets
        assert "value_pick" in presets

    def test_reload_refreshes_config(self, tmp_config: Path) -> None:
        engine = FilterEngine(config_path=tmp_config)
        original_count = len(engine.filters)
        # Modify the file
        with open(tmp_config, "a", encoding="utf-8") as f:
            f.write("\nnew_test_filter:\n  column: test_col\n  display_name: Test\n  direction: min\n  default: null\n  unit: ''\n")
        engine.reload()
        # The new entry isn't under 'filters:' key so filter count unchanged
        assert len(engine.filters) == original_count


# ==================================================================
# 2. Basic Filtering — Min Direction
# ==================================================================


class TestMinFilters:
    """Tests for min-direction filters (keep >= threshold)."""

    def test_roe_min_filter(self, engine: FilterEngine, sample_df: pd.DataFrame) -> None:
        result = engine.apply(sample_df, add_score=False, roe=20.0)
        ids = result["company_id"].tolist()
        # TCS (48.5), ITC (26.0), INFY (31.2), HINDUNILVR (18.0 excluded), HDFCBANK (16.8 excluded)
        # VODAIDEA has None ROE -> excluded
        assert "TCS" in ids
        assert "ITC" in ids
        assert "INFY" in ids
        assert "HINDUNILVR" not in ids
        assert "VODAIDEA" not in ids

    def test_fcf_min_filter(self, engine: FilterEngine, sample_df: pd.DataFrame) -> None:
        result = engine.apply(sample_df, add_score=False, free_cash_flow=10000)
        ids = result["company_id"].tolist()
        assert "TCS" in ids  # 38000
        assert "INFY" in ids  # 22000
        assert "VODAIDEA" not in ids  # -5000

    def test_revenue_cagr_5yr_min(self, engine: FilterEngine, sample_df: pd.DataFrame) -> None:
        result = engine.apply(sample_df, add_score=False, revenue_cagr_5yr=10.0)
        ids = result["company_id"].tolist()
        # TCS 11.5, RELIANCE 12.0, HDFCBANK 18.0, INFY 12.0, SBIN 14.0
        assert "TCS" in ids
        assert "RELIANCE" in ids
        assert "HDFCBANK" in ids
        assert "INFY" in ids
        assert "SBIN" in ids
        assert "ITC" not in ids  # 8.0
        assert "VODAIDEA" not in ids  # -5.0

    def test_pat_cagr_5yr_min(self, engine: FilterEngine, sample_df: pd.DataFrame) -> None:
        result = engine.apply(sample_df, add_score=False, pat_cagr_5yr=10.0)
        ids = result["company_id"].tolist()
        assert "TCS" in ids  # 10.2
        assert "HDFCBANK" in ids  # 16.5
        assert "INFY" in ids  # 11.0
        assert "SBIN" in ids  # 22.0
        assert "RELIANCE" not in ids  # 8.5

    def test_opm_min_filter(self, engine: FilterEngine, sample_df: pd.DataFrame) -> None:
        result = engine.apply(sample_df, add_score=False, operating_profit_margin=25.0)
        ids = result["company_id"].tolist()
        # TCS 26.4, HDFCBANK 42.0, ITC 42.0, INFY 23.0 (excluded), SBIN 35.0
        assert "TCS" in ids
        assert "HDFCBANK" in ids
        assert "ITC" in ids
        assert "SBIN" in ids
        assert "INFY" not in ids

    def test_market_cap_min(self, engine: FilterEngine, sample_df: pd.DataFrame) -> None:
        result = engine.apply(sample_df, add_score=False, market_cap=1000000)
        ids = result["company_id"].tolist()
        assert "TCS" in ids  # 1450000
        assert "RELIANCE" in ids  # 2100000
        assert "HDFCBANK" in ids  # 1250000
        assert "ITC" not in ids  # 560000

    def test_net_profit_min(self, engine: FilterEngine, sample_df: pd.DataFrame) -> None:
        result = engine.apply(sample_df, add_score=False, net_profit=30000)
        ids = result["company_id"].tolist()
        assert "TCS" in ids  # 46000
        assert "RELIANCE" in ids  # 79500
        assert "HDFCBANK" in ids  # 62700
        assert "INFY" not in ids  # 28800

    def test_eps_cagr_5yr_min(self, engine: FilterEngine, sample_df: pd.DataFrame) -> None:
        result = engine.apply(sample_df, add_score=False, eps_cagr_5yr=10.0)
        ids = result["company_id"].tolist()
        assert "TCS" in ids  # 10.0
        assert "INFY" in ids  # 11.5
        assert "SBIN" in ids  # 18.0
        assert "HDFCBANK" in ids  # 14.0
        assert "RELIANCE" not in ids  # 8.0

    def test_asset_turnover_min(self, engine: FilterEngine, sample_df: pd.DataFrame) -> None:
        result = engine.apply(sample_df, add_score=False, asset_turnover=0.8)
        ids = result["company_id"].tolist()
        assert "TCS" in ids  # 0.92
        assert "INFY" in ids  # 0.85
        assert "RELIANCE" not in ids  # 0.75

    def test_net_sales_min(self, engine: FilterEngine, sample_df: pd.DataFrame) -> None:
        result = engine.apply(sample_df, add_score=False, net_sales=100000)
        ids = result["company_id"].tolist()
        assert "TCS" in ids  # 240000
        assert "RELIANCE" in ids  # 980000
        assert "INFY" in ids  # 165000
        assert "ITC" not in ids  # 70000

    def test_dividend_yield_min(self, engine: FilterEngine, sample_df: pd.DataFrame) -> None:
        result = engine.apply(sample_df, add_score=False, dividend_yield=2.0)
        ids = result["company_id"].tolist()
        assert "ITC" in ids  # 3.2
        assert "INFY" in ids  # 2.5
        assert "TCS" not in ids  # 1.2


# ==================================================================
# 3. Max Direction Filters
# ==================================================================


class TestMaxFilters:
    """Tests for max-direction filters (keep <= threshold)."""

    def test_pe_ratio_max(self, engine: FilterEngine, sample_df: pd.DataFrame) -> None:
        result = engine.apply(sample_df, add_score=False, pe_ratio=25.0)
        ids = result["company_id"].tolist()
        # VODAIDEA has None PE -> excluded
        # RELIANCE 28.0 excluded, HDFCBANK 19.5, SBIN 10.5, INFY 24.0, ITC 25.5 excluded
        assert "HDFCBANK" in ids  # 19.5
        assert "SBIN" in ids  # 10.5
        assert "INFY" in ids  # 24.0
        assert "RELIANCE" not in ids  # 28.0
        assert "ITC" not in ids  # 25.5
        assert "VODAIDEA" not in ids

    def test_pb_ratio_max(self, engine: FilterEngine, sample_df: pd.DataFrame) -> None:
        result = engine.apply(sample_df, add_score=False, pb_ratio=5.0)
        ids = result["company_id"].tolist()
        assert "RELIANCE" in ids  # 2.5
        assert "HDFCBANK" in ids  # 2.8
        assert "VODAIDEA" in ids  # 0.3
        assert "TCS" not in ids  # 14.8
        assert "ITC" not in ids  # 6.5


# ==================================================================
# 4. D/E Financials Auto-Skip
# ==================================================================


class TestDeFinancialsSkip:
    """D/E filter automatically skips Financials sector companies."""

    def test_financials_excluded_from_de_filter(self, engine: FilterEngine, sample_df: pd.DataFrame) -> None:
        """HDFCBANK (D/E 5.8) and SBIN (D/E 7.2) should survive D/E < 1.0 filter."""
        result = engine.apply(sample_df, add_score=False, debt_to_equity=1.0)
        ids = result["company_id"].tolist()
        # Financials companies pass regardless of D/E
        assert "HDFCBANK" in ids  # D/E 5.8, broad_sector=Financials
        assert "SBIN" in ids  # D/E 7.2, sector_id=Banks
        # Non-financials must actually pass
        assert "TCS" in ids  # D/E 0.0
        assert "ITC" in ids  # D/E 0.01
        assert "RELIANCE" in ids  # D/E 0.65
        assert "VODAIDEA" not in ids  # D/E 8.5, NOT financial

    def test_financials_with_nbfc_alias(self, engine: FilterEngine, sample_df: pd.DataFrame) -> None:
        """Test that sector_id matching works for alias 'NBMC' etc."""
        df = sample_df.copy()
        # Add a NBFC company
        nbfc_row = {
            "company_id": "BAJFINANCE", "company_name": "Bajaj Finance",
            "year": "2024", "sector_id": "NBFC", "broad_sector": "Financials",
            "roe": 22.0, "roce": 12.0, "net_profit_margin": 22.0,
            "operating_profit_margin": 55.0, "interest_coverage_ratio": 2.0,
            "debt_to_equity": 6.5, "asset_turnover": 0.12,
            "pe_ratio": 35.0, "pb_ratio": 5.5, "dividend_yield": 0.5,
            "dividend_payout_ratio": 18.0, "market_cap": 450000,
            "net_sales": 55000, "net_profit": 12100, "eps": 212.0,
            "free_cash_flow": 8000, "cfo_quality_score": 100.0,
            "fcf_conversion_rate": 35.0, "revenue_cagr_5yr": 25.0,
            "pat_cagr_5yr": 22.0, "eps_cagr_5yr": 20.0,
            "is_debt_free": 0, "composite_quality_score": None,
        }
        df = pd.concat([df, pd.DataFrame([nbfc_row])], ignore_index=True)

        result = engine.apply(df, add_score=False, debt_to_equity=1.0)
        ids = result["company_id"].tolist()
        assert "BAJFINANCE" in ids  # NBFC sector -> auto-skipped from D/E

    def test_non_financials_filtered_by_de(self, engine: FilterEngine, sample_df: pd.DataFrame) -> None:
        """Non-financial companies with high D/E are correctly filtered."""
        result = engine.apply(sample_df, add_score=False, debt_to_equity=0.5)
        ids = result["company_id"].tolist()
        # Only D/E <= 0.5 non-financials pass (plus all Financials)
        assert "TCS" in ids  # D/E 0.0
        assert "ITC" in ids  # D/E 0.01
        assert "HDFCBANK" in ids  # Financials, exempt
        assert "SBIN" in ids  # Financials, exempt
        assert "RELIANCE" not in ids  # D/E 0.65 > 0.5, not Financials
        assert "VODAIDEA" not in ids  # D/E 8.5

    def test_de_zero_filter_keeps_only_debt_free(self, engine: FilterEngine, sample_df: pd.DataFrame) -> None:
        """D/E = 0 should keep only debt-free non-financial companies."""
        result = engine.apply(sample_df, add_score=False, debt_to_equity=0.0)
        ids = result["company_id"].tolist()
        # Financials always pass
        assert "HDFCBANK" in ids
        assert "SBIN" in ids
        # Non-financials: only TCS (0.0) and ITC (0.01... wait, 0.01 > 0.0)
        # Actually 0.01 > 0.0, so ITC is excluded
        assert "TCS" in ids  # D/E exactly 0.0
        assert "INFY" in ids  # D/E 0.0
        assert "ITC" not in ids  # D/E 0.01 > 0.0
        assert "RELIANCE" not in ids  # D/E 0.65
        assert "VODAIDEA" not in ids


# ==================================================================
# 5. ICR Debt-Free = Infinity
# ==================================================================


class TestIcrDebtFreeHandling:
    """ICR filter: debt-free companies always pass any ICR threshold."""

    def test_debt_free_passes_any_icr_threshold(self, engine: FilterEngine, sample_df: pd.DataFrame) -> None:
        """TCS (debt-free, ICR=None) should pass ICR >= 5.0."""
        result = engine.apply(sample_df, add_score=False, interest_coverage_ratio=5.0)
        ids = result["company_id"].tolist()
        assert "TCS" in ids  # debt-free, always passes
        assert "INFY" in ids  # debt-free, always passes
        assert "ITC" in ids  # ICR 12.5 >= 5
        assert "HINDUNILVR" in ids  # ICR 15.0 >= 5
        assert "RELIANCE" not in ids  # ICR 4.2 < 5
        assert "VODAIDEA" not in ids  # ICR 0.5 < 5

    def test_debt_free_with_zero_de_passes_icr(self, engine: FilterEngine, sample_df: pd.DataFrame) -> None:
        """Companies with D/E = 0 (but is_debt_free not set) still pass."""
        result = engine.apply(sample_df, add_score=False, interest_coverage_ratio=10.0)
        ids = result["company_id"].tolist()
        assert "TCS" in ids  # D/E 0 -> treated as debt-free
        assert "INFY" in ids  # D/E 0
        assert "ITC" in ids  # ICR 12.5 >= 10

    def test_non_debt_free_fails_low_icr(self, engine: FilterEngine, sample_df: pd.DataFrame) -> None:
        """VODAIDEA (ICR 0.5, not debt-free) fails ICR >= 5.0."""
        result = engine.apply(sample_df, add_score=False, interest_coverage_ratio=5.0)
        ids = result["company_id"].tolist()
        assert "VODAIDEA" not in ids

    def test_financials_with_null_icr_handled(self, engine: FilterEngine, sample_df: pd.DataFrame) -> None:
        """HDFCBANK (ICR=None, D/E 5.8, not debt-free) fails ICR filter."""
        result = engine.apply(sample_df, add_score=False, interest_coverage_ratio=5.0)
        ids = result["company_id"].tolist()
        # HDFCBANK: ICR is None, not debt-free -> fails
        assert "HDFCBANK" not in ids


# ==================================================================
# 6. Composite Quality Score
# ==================================================================


class TestCompositeScore:
    """Composite quality score computation tests."""

    def test_score_column_added(self, engine: FilterEngine, sample_df: pd.DataFrame) -> None:
        result = engine.apply(sample_df, add_score=True)
        assert "composite_quality_score" in result.columns

    def test_score_range_0_to_100(self, engine: FilterEngine, sample_df: pd.DataFrame) -> None:
        result = engine.apply(sample_df, add_score=True)
        valid_scores = result["composite_quality_score"].dropna()
        if len(valid_scores) > 0:
            assert valid_scores.min() >= 0, f"Score below 0: {valid_scores.min()}"
            assert valid_scores.max() <= 100, f"Score above 100: {valid_scores.max()}"

    def test_tcs_higher_than_vodaidea(self, engine: FilterEngine, sample_df: pd.DataFrame) -> None:
        """TCS (strong fundamentals) should score higher than VODAIDEA (loss-making)."""
        result = engine.apply(sample_df, add_score=True)
        tcs_score = result.loc[result["company_id"] == "TCS", "composite_quality_score"].iloc[0]
        voda_score = result.loc[result["company_id"] == "VODAIDEA", "composite_quality_score"].iloc[0]
        assert tcs_score > voda_score

    def test_sorted_by_score_descending(self, engine: FilterEngine, sample_df: pd.DataFrame) -> None:
        result = engine.apply(sample_df, add_score=True)
        scores = result["composite_quality_score"].tolist()
        # NaN values go to end; check that non-NaN values are descending
        non_nan = [s for s in scores if not np.isnan(s)]
        assert non_nan == sorted(non_nan, reverse=True)

    def test_nan_score_for_insufficient_data(self, engine: FilterEngine) -> None:
        """Company with too many missing metrics should get NaN score."""
        df = pd.DataFrame([{
            "company_id": "EMPTY_CO", "company_name": "Empty Corp",
            "year": "2024", "sector_id": "X", "broad_sector": "X",
            "roe": None, "roce": None, "net_profit_margin": None,
            "operating_profit_margin": None, "interest_coverage_ratio": None,
            "debt_to_equity": None, "asset_turnover": None,
            "pe_ratio": None, "pb_ratio": None, "dividend_yield": None,
            "dividend_payout_ratio": None, "market_cap": None,
            "net_sales": None, "net_profit": None, "eps": None,
            "free_cash_flow": None, "cfo_quality_score": None,
            "fcf_conversion_rate": None, "revenue_cagr_5yr": None,
            "pat_cagr_5yr": None, "eps_cagr_5yr": None,
            "is_debt_free": 0, "composite_quality_score": None,
        }])
        result = engine.apply(df, add_score=True)
        assert pd.isna(result["composite_quality_score"].iloc[0])

    def test_score_not_negative(self, engine: FilterEngine, sample_df: pd.DataFrame) -> None:
        result = engine.apply(sample_df, add_score=True)
        valid = result["composite_quality_score"].dropna()
        assert (valid >= 0).all()


# ==================================================================
# 7. Sorting Behaviour
# ==================================================================


class TestSorting:
    """Sorting and ordering tests."""

    def test_default_sort_desc_by_score(self, engine: FilterEngine, sample_df: pd.DataFrame) -> None:
        result = engine.apply(sample_df, add_score=True)
        non_nan = result["composite_quality_score"].dropna()
        assert list(non_nan) == sorted(non_nan, reverse=True)

    def test_custom_sort_column(self, engine: FilterEngine, sample_df: pd.DataFrame) -> None:
        result = engine.apply(sample_df, add_score=False, sort_by="roe")
        valid_roe = result["roe"].dropna()
        assert list(valid_roe) == sorted(valid_roe, reverse=True)

    def test_ascending_sort(self, engine: FilterEngine, sample_df: pd.DataFrame) -> None:
        result = engine.apply(sample_df, add_score=False, sort_by="debt_to_equity", ascending=True)
        valid_de = result["debt_to_equity"].dropna()
        assert list(valid_de) == sorted(valid_de)

    def test_nan_at_end_when_descending(self, engine: FilterEngine, sample_df: pd.DataFrame) -> None:
        result = engine.apply(sample_df, add_score=False, sort_by="roe")
        # ROE=None (VODAIDEA) should be at the end
        last_row = result.iloc[-1]
        assert pd.isna(last_row["roe"])


# ==================================================================
# 8. Empty DataFrame
# ==================================================================


class TestEmptyDataFrame:
    """Edge case: empty input DataFrame."""

    def test_empty_df_returns_empty(self, engine: FilterEngine) -> None:
        df = pd.DataFrame(columns=[
            "company_id", "roe", "debt_to_equity", "free_cash_flow",
            "revenue_cagr_5yr", "pat_cagr_5yr", "operating_profit_margin",
            "pe_ratio", "pb_ratio", "dividend_yield", "interest_coverage_ratio",
            "market_cap", "net_profit", "eps_cagr_5yr", "asset_turnover",
            "net_sales", "broad_sector", "is_debt_free",
        ])
        result = engine.apply(df, roe=15)
        assert len(result) == 0

    def test_empty_df_preserves_columns(self, engine: FilterEngine) -> None:
        cols = ["company_id", "roe", "debt_to_equity"]
        df = pd.DataFrame(columns=cols)
        result = engine.apply(df, add_score=False)
        assert set(result.columns) == set(cols)


# ==================================================================
# 9. Preset Loading & Application
# ==================================================================


class TestPresets:
    """Preset screener loading and application."""

    def test_get_preset_returns_thresholds(self, engine: FilterEngine) -> None:
        thresholds = engine.get_preset("quality_compounder")
        assert "roe" in thresholds
        assert thresholds["roe"] == 15.0
        assert thresholds["debt_to_equity"] == 1.0
        assert thresholds["free_cash_flow"] == 0.0
        assert thresholds["revenue_cagr_5yr"] == 10.0

    def test_unknown_preset_raises_key_error(self, engine: FilterEngine) -> None:
        with pytest.raises(KeyError, match="not found"):
            engine.get_preset("nonexistent_preset")

    def test_apply_preset_filters_correctly(self, engine: FilterEngine, sample_df: pd.DataFrame) -> None:
        result = engine.apply_preset(sample_df, "quality_compounder")
        ids = result["company_id"].tolist()
        # Quality Compounder: ROE>15, D/E<1, FCF>0, Rev CAGR 5yr>10
        # TCS: ROE 48.5✓, D/E 0.0✓, FCF 38000✓, Rev CAGR 11.5✓ -> IN
        # INFY: ROE 31.2✓, D/E 0.0✓, FCF 22000✓, Rev CAGR 12.0✓ -> IN
        # ITC: ROE 26.0✓, D/E 0.01✓, FCF 15000✓, Rev CAGR 8.0✗ -> OUT
        # HDFCBANK: ROE 16.8✓, D/E 5.8 but Financials✓, FCF 45000✓, Rev CAGR 18.0✓ -> IN
        # RELIANCE: ROE 8.5✗ -> OUT
        assert "TCS" in ids
        assert "INFY" in ids
        assert "HDFCBANK" in ids  # Financials, D/E exempt
        assert "ITC" not in ids  # Revenue CAGR 8.0 < 10
        assert "RELIANCE" not in ids  # ROE 8.5 < 15

    def test_value_pick_preset(self, engine: FilterEngine, sample_df: pd.DataFrame) -> None:
        result = engine.apply_preset(sample_df, "value_pick")
        ids = result["company_id"].tolist()
        # Value Pick: P/E<20, P/B<3, D/E<2, Div Yield>1%
        # RELIANCE: P/E 28✗ -> OUT
        # HDFCBANK: P/E 19.5✓, P/B 2.8✓, D/E 5.8 but Financials✓, Div Yield 1.1✓ -> IN
        # SBIN: P/E 10.5✓, P/B 1.8✓, D/E 7.2 Financials✓, Div Yield 1.5✓ -> IN
        # TCS: P/E 32.5✗ -> OUT
        # HINDUNILVR: P/E 55✗ -> OUT
        assert "HDFCBANK" in ids
        assert "SBIN" in ids
        assert "TCS" not in ids
        assert "HINDUNILVR" not in ids

    def test_load_preset_convenience_function(self, tmp_config: Path) -> None:
        thresholds = load_preset("quality_compounder", config_path=tmp_config)
        assert thresholds["roe"] == 15.0


# ==================================================================
# 10. Multiple Filters Combined
# ==================================================================


class TestMultipleFilters:
    """Test combining multiple filter overrides."""

    def test_combined_roe_and_de_filters(self, engine: FilterEngine, sample_df: pd.DataFrame) -> None:
        result = engine.apply(sample_df, add_score=False, roe=15.0, debt_to_equity=1.0)
        ids = result["company_id"].tolist()
        # ROE >= 15: TCS 48.5, HDFCBANK 16.8, ITC 26.0, INFY 31.2, HINDUNILVR 18.0, SBIN 18.5
        # D/E <= 1 (non-financials): TCS 0✓, ITC 0.01✓, INFY 0✓, HINDUNILVR 0.35✓, RELIANCE 0.65✓
        # Combined: TCS✓, HDFCBANK✓(Financials), ITC✓, INFY✓, HINDUNILVR✓, SBIN✓(Financials)
        # RELIANCE: ROE 8.5 < 15 -> OUT
        assert "TCS" in ids
        assert "HDFCBANK" in ids
        assert "ITC" in ids
        assert "INFY" in ids
        assert "HINDUNILVR" in ids
        assert "SBIN" in ids
        assert "RELIANCE" not in ids
        assert "VODAIDEA" not in ids

    def test_all_15_filters_applied(self, engine: FilterEngine, sample_df: pd.DataFrame) -> None:
        """Apply all 15 filters simultaneously — very restrictive."""
        result = engine.apply(
            sample_df, add_score=False,
            roe=20.0, debt_to_equity=1.0, free_cash_flow=10000,
            revenue_cagr_5yr=10.0, pat_cagr_5yr=8.0,
            operating_profit_margin=20.0, pe_ratio=30.0, pb_ratio=10.0,
            dividend_yield=1.0, interest_coverage_ratio=5.0,
            market_cap=500000, net_profit=10000, eps_cagr_5yr=8.0,
            asset_turnover=0.5, net_sales=50000,
        )
        # Very restrictive — TCS excluded (P/E 32.5 > 30), only INFY passes
        # INFY: ROE 31.2✓, D/E 0✓, FCF 22000✓, RevCAGR 12✓, PATCAGR 11✓,
        #        OPM 23✓, PE 24≤30✓, PB 7.2≤10✓, DivYield 2.5≥1✓, ICR None but debt-free✓,
        #        MktCap 680000✓, NP 28800✓, EPSCAGR 11.5✓, AT 0.85✓, Sales 165000✓
        ids = result["company_id"].tolist()
        assert "INFY" in ids
        assert "TCS" not in ids  # P/E 32.5 > 30.0 max


# ==================================================================
# 11. Edge Cases
# ==================================================================


class TestEdgeCases:
    """Edge case handling."""

    def test_nan_in_filter_column_excluded(self, engine: FilterEngine) -> None:
        """Rows with NaN in the filtered column should be excluded."""
        df = pd.DataFrame([
            {"company_id": "A", "roe": 20.0, "debt_to_equity": 0.5, "broad_sector": "Tech", "is_debt_free": 0},
            {"company_id": "B", "roe": None, "debt_to_equity": 0.5, "broad_sector": "Tech", "is_debt_free": 0},
            {"company_id": "C", "roe": 25.0, "debt_to_equity": 0.5, "broad_sector": "Tech", "is_debt_free": 0},
        ])
        result = engine.apply(df, add_score=False, roe=15.0)
        ids = result["company_id"].tolist()
        assert "A" in ids
        assert "C" in ids
        assert "B" not in ids  # NaN ROE

    def test_missing_column_ignored(self, engine: FilterEngine) -> None:
        """Filtering on a column that doesn't exist should not crash."""
        df = pd.DataFrame([
            {"company_id": "A", "roe": 20.0, "broad_sector": "X", "is_debt_free": 0},
        ])
        # Should not raise — column 'nonexistent_col' not in df, so filter is a no-op
        result = engine.apply(df, add_score=False, **{"nonexistent_col": 10.0})
        assert len(result) == 1

    def test_none_override_ignored(self, engine: FilterEngine, sample_df: pd.DataFrame) -> None:
        """Passing None as override value should be skipped."""
        result = engine.apply(sample_df, add_score=False, roe=None)
        assert len(result) == len(sample_df)

    def test_does_not_mutate_input(self, engine: FilterEngine, sample_df: pd.DataFrame) -> None:
        """Original DataFrame should not be modified."""
        original_len = len(sample_df)
        original_cols = list(sample_df.columns)
        engine.apply(sample_df, roe=15.0)
        assert len(sample_df) == original_len
        assert list(sample_df.columns) == original_cols
        assert "composite_quality_score" not in sample_df.columns or sample_df["composite_quality_score"].isna().all()

    def test_sector_detection_falls_back_to_sector_id(self, engine: FilterEngine) -> None:
        """If broad_sector is missing, fall back to sector_id for sector detection."""
        df = pd.DataFrame([
            {
                "company_id": "FINCO", "company_name": "Fin Corp",
                "year": "2024", "sector_id": "Financials", "broad_sector": None,
                "roe": 15.0, "roce": 10.0, "net_profit_margin": 10.0,
                "operating_profit_margin": 20.0, "interest_coverage_ratio": 3.0,
                "debt_to_equity": 5.0, "asset_turnover": 0.1,
                "pe_ratio": 15.0, "pb_ratio": 2.0, "dividend_yield": 2.0,
                "dividend_payout_ratio": 30.0, "market_cap": 100000,
                "net_sales": 50000, "net_profit": 5000, "eps": 10.0,
                "free_cash_flow": 3000, "cfo_quality_score": 100.0,
                "fcf_conversion_rate": 40.0, "revenue_cagr_5yr": 10.0,
                "pat_cagr_5yr": 10.0, "eps_cagr_5yr": 10.0,
                "is_debt_free": 0, "composite_quality_score": None,
            },
        ])
        result = engine.apply(df, add_score=False, debt_to_equity=1.0)
        # Should pass D/E filter because sector_id="Financials"
        assert len(result) == 1
        assert result.iloc[0]["company_id"] == "FINCO"


# ==================================================================
# 12. Convenience Functions
# ==================================================================


class TestConvenienceFunctions:
    """Module-level convenience functions."""

    def test_apply_filters_returns_filtered(self, tmp_config: Path, sample_df: pd.DataFrame) -> None:
        result = apply_filters(sample_df, config_path=tmp_config, roe=20.0)
        assert len(result) < len(sample_df)
        assert "composite_quality_score" in result.columns

    def test_apply_filters_no_overrides(self, tmp_config: Path, sample_df: pd.DataFrame) -> None:
        """No overrides = no filtering, but score still added and sorted."""
        result = apply_filters(sample_df, config_path=tmp_config)
        assert len(result) == len(sample_df)
        assert "composite_quality_score" in result.columns

    def test_load_preset_returns_dict(self, tmp_config: Path) -> None:
        result = load_preset("value_pick", config_path=tmp_config)
        assert isinstance(result, dict)
        assert "pe_ratio" in result
        assert result["pe_ratio"] == 20.0


# ==================================================================
# 13. Financials Sector Aliases
# ==================================================================


class TestFinancialSectorAliases:
    """Verify all financial sector aliases work for D/E skip."""

    @pytest.mark.parametrize("sector", ["Financials", "FIN", "NBFC", "Banks"])
    def test_sector_alias_skips_de(self, engine: FilterEngine, sector: str) -> None:
        df = pd.DataFrame([{
            "company_id": f"TEST_{sector}", "company_name": f"Test {sector}",
            "year": "2024", "sector_id": sector, "broad_sector": "X",
            "roe": 10.0, "roce": 10.0, "net_profit_margin": 10.0,
            "operating_profit_margin": 20.0, "interest_coverage_ratio": 2.0,
            "debt_to_equity": 10.0, "asset_turnover": 0.1,
            "pe_ratio": 15.0, "pb_ratio": 2.0, "dividend_yield": 1.0,
            "dividend_payout_ratio": 30.0, "market_cap": 50000,
            "net_sales": 10000, "net_profit": 1000, "eps": 10.0,
            "free_cash_flow": 500, "cfo_quality_score": 100.0,
            "fcf_conversion_rate": 30.0, "revenue_cagr_5yr": 5.0,
            "pat_cagr_5yr": 5.0, "eps_cagr_5yr": 5.0,
            "is_debt_free": 0, "composite_quality_score": None,
        }])
        result = engine.apply(df, add_score=False, debt_to_equity=1.0)
        assert len(result) == 1  # Should pass despite D/E 10.0
