"""Tests for src/screener/presets.py — Sprint 3 Day 16.

Tests all 6 preset screeners on a 20-company multi-year fixture.
Each preset is validated for correct filtering logic.
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd
import pytest
import yaml

from src.screener.presets import (
    ALL_PRESETS,
    PRESET_FUNCTIONS,
    _get_de_declining_company_ids,
    get_latest_year,
    get_previous_year,
    run_all_presets,
    run_preset,
    screen_debt_free_blue_chip,
    screen_dividend_champion,
    screen_growth_accelerator,
    screen_quality_compounder,
    screen_turnaround_watch,
    screen_value_pick,
    validate_preset_counts,
)


# ==================================================================
# Column order for the *args-based _make_company helper
# ==================================================================
_COMPANY_COLS = [
    "company_id", "company_name", "sector_id", "broad_sector",
    "year", "roe", "debt_to_equity", "free_cash_flow",
    "revenue_cagr_5yr", "pat_cagr_5yr", "net_profit_margin",
    "operating_profit_margin", "pe_ratio", "pb_ratio", "dividend_yield",
    "dividend_payout_ratio", "market_cap", "net_sales", "net_profit", "eps",
    "interest_coverage_ratio", "roce", "cfo_quality_score",
    "fcf_conversion_rate", "eps_cagr_5yr", "is_debt_free",
]

_DEFAULT_ROW = {
    "asset_turnover": 0.5,
    "composite_quality_score": None,
}


def _make_company(*args):
    """Build a company-year row dict from positional arguments.

    Maps each positional arg to _COMPANY_COLS by index.
    Uses *args to avoid any Python version parameter-count issues.
    Extra columns (asset_turnover, composite_quality_score) are
    filled from _DEFAULT_ROW.
    """
    row = {}
    for i, val in enumerate(args):
        if i < len(_COMPANY_COLS):
            row[_COMPANY_COLS[i]] = val
    row.update(_DEFAULT_ROW)
    return row


# ==================================================================
# Config fixture
# ==================================================================


@pytest.fixture()
def tmp_config(tmp_path: Path) -> Path:
    config = {
        "filters": {
            "roe": {"column": "roe", "display_name": "ROE", "direction": "min", "default": None, "unit": "%"},
            "debt_to_equity": {"column": "debt_to_equity", "display_name": "D/E", "direction": "max", "default": None, "unit": "x"},
            "free_cash_flow": {"column": "free_cash_flow", "display_name": "FCF", "direction": "min", "default": None, "unit": "Cr"},
            "revenue_cagr_5yr": {"column": "revenue_cagr_5yr", "display_name": "Rev CAGR 5Y", "direction": "min", "default": None, "unit": "%"},
            "pat_cagr_5yr": {"column": "pat_cagr_5yr", "display_name": "PAT CAGR 5Y", "direction": "min", "default": None, "unit": "%"},
            "operating_profit_margin": {"column": "operating_profit_margin", "display_name": "OPM", "direction": "min", "default": None, "unit": "%"},
            "pe_ratio": {"column": "pe_ratio", "display_name": "P/E", "direction": "max", "default": None, "unit": "x"},
            "pb_ratio": {"column": "pb_ratio", "display_name": "P/B", "direction": "max", "default": None, "unit": "x"},
            "dividend_yield": {"column": "dividend_yield", "display_name": "Div Yield", "direction": "min", "default": None, "unit": "%"},
            "dividend_payout_ratio": {"column": "dividend_payout_ratio", "display_name": "Payout", "direction": "max", "default": None, "unit": "%"},
            "interest_coverage_ratio": {"column": "interest_coverage_ratio", "display_name": "ICR", "direction": "min", "default": None, "unit": "x"},
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
            "growth_accelerator": {
                "display_name": "Growth Accelerator",
                "filters": {"pat_cagr_5yr": 20.0, "revenue_cagr_5yr": 15.0, "debt_to_equity": 2.0},
            },
            "dividend_champion": {
                "display_name": "Dividend Champion",
                "filters": {"dividend_yield": 2.0, "dividend_payout_ratio": 80.0, "free_cash_flow": 0.0},
            },
            "debt_free_blue_chip": {
                "display_name": "Debt-Free Blue Chip",
                "filters": {"debt_to_equity": 0.0, "roe": 12.0, "net_sales": 5000.0},
            },
            "turnaround_watch": {
                "display_name": "Turnaround Watch",
                "filters": {"revenue_cagr_5yr": 10.0, "free_cash_flow": 0.0},
            },
        },
        "financial_sectors": ["Financials", "FIN", "NBFC", "Banks"],
    }
    cfg_file = tmp_path / "screener_config.yaml"
    cfg_file.write_text(yaml.dump(config, default_flow_style=False), encoding="utf-8")
    return cfg_file


# ==================================================================
# 20-company multi-year fixture (2 years per company)
# ==================================================================
# Company profiles (Year 2024):
#   TCS       — debt-free, ROE 48, high FCF, IT
#   INFY      — debt-free, ROE 31, good FCF, IT
#   WIPRO     — debt-free, ROE 18, FCF+, IT
#   HDFCBANK  — Financials, D/E 5.8, ROE 17
#   SBIN      — Financials, D/E 7.2, ROE 18.5
#   ITC       — D/E 0.01, ROE 26, DivY 3.2, Payout 82%
#   HINDUNILVR— D/E 0.35, ROE 18, P/E 55
#   RELIANCE  — D/E 0.65, ROE 8.5
#   BAJFINANCE— NBFC/Financials, D/E 6.5, ROE 22, PATCAGR 22
#   TITAN     — D/E 0.1, ROE 28, P/E 65
#   MARUTI    — D/E 0.08, ROE 22, P/E 28
#   HCLTECH   — D/E 0.0, ROE 24
#   ASIANPAINT— D/E 0.05, ROE 20, RevCAGR 8
#   ULTRACEMCO— D/E 0.3, ROE 14, PATCAGR 22
#   LTIMIND   — D/E 0.0, ROE 30, RevCAGR 18
#   VODAIDEA  — D/E 7.0, RevCAGR 12 (D/E declining 8.5->7.0)
#   TATASTEEL — D/E 0.5, RevCAGR 8  (D/E declining 0.8->0.5)
#   ADANIENT  — D/E 0.9, RevCAGR 18 (D/E declining 1.5->0.9)
#   POWERGRID — D/E 1.2, ROE 15, DivY 4.0
#   COALINDIA — D/E 0.0, ROE 25, DivY 5.0
#
# _make_company positional order:
#   cid, name, sector, broad, year, roe, de, fcf,
#   rev_cagr, pat_cagr, npm, opm, pe, pb, div_yield,
#   payout, mcap, sales, np, eps, icr, roce,
#   cfo_q, fcf_conv, eps_cagr, is_df
# ==================================================================


@pytest.fixture()
def multi_year_df() -> pd.DataFrame:
    """20-company, 2-year (2023, 2024) financial_ratios DataFrame."""
    rows = []

    # --- Year 2024 (latest) ---
    y24 = "2024"
    #        cid        name                          sector  broad       yr    roe   de    fcf    revc  patc  npm   opm  pe    pb   divy pay  mcap     sales   np     eps    icr   roce  cfoq  fcfconv epsc df
    rows.append(_make_company("TCS",       "Tata Consultancy Services", "IT",  "IT",         y24, 48.5, 0.0,  38000, 11.5, 10.2, 19.2, 26.4, 32.5, 14.8, 1.2, 38.0, 1450000, 240000, 46000, 126.0, None, None, 62.3, 115.0, 65.0, 10.0, 1))
    rows.append(_make_company("INFY",      "Infosys Limited",          "IT",  "IT",         y24, 31.2, 0.0,  22000, 12.0, 11.0, 17.5, 23.0, 24.0,  7.2, 2.5, 55.0,  680000, 165000, 28800,  69.0, None, None, 42.5, 120.0, 58.0, 11.5, 1))
    rows.append(_make_company("WIPRO",     "Wipro Limited",           "IT",  "IT",         y24, 18.0, 0.0,   8000, 12.0,  8.0, 12.0, 18.0, 22.0, 20.0, 0.3, 30.0,  280000,  90000, 10800,  22.0, None, None, 18.0, 110.0, 45.0,  7.0, 1))
    rows.append(_make_company("HDFCBANK",  "HDFC Bank",              "Banks","Financials", y24, 16.8, 5.8,  45000, 18.0, 16.5, 22.0, 42.0, 19.5,  2.8, 1.1, 21.0, 1250000, 285000, 62700, 118.5, None, None,  7.5, 125.0, 72.0, 14.0, 0))
    rows.append(_make_company("SBIN",      "State Bank of India",     "Banks","Financials", y24, 18.5, 7.2,  35000, 14.0, 22.0, 12.0, 35.0, 10.5,  1.8, 1.5, 16.0,  680000, 355000, 42600,  48.0,   1.5, None,  8.0, 110.0, 60.0, 18.0, 0))
    rows.append(_make_company("ITC",       "ITC Limited",            "FMCG", "FMCG",       y24, 26.0, 0.01, 15000,  8.0,  9.0, 26.8, 42.0, 25.5,  6.5, 3.2, 82.0,  560000,  70000, 18800,  24.0,  12.5, None, 30.5, 130.0, 70.0,  8.5, 1))
    rows.append(_make_company("HINDUNILVR", "Hindustan Unilever",      "FMCG", "FMCG",       y24, 18.0, 0.35,  7000,  5.0,  8.0, 10.5, 16.0, 55.0, 10.0, 1.8, 95.0,  590000,  56000,  5900,  25.0,  15.0, None, 22.0, 105.0, 48.0,  7.0, 0))
    rows.append(_make_company("RELIANCE",  "Reliance Industries",     "OIL",  "Energy",     y24,  8.5, 0.65, 15000, 12.0,  8.5,  8.1, 14.5, 28.0,  2.5, 0.3, 10.0, 2100000, 980000, 79500, 118.0,   4.2, None, 10.2,  95.0, 25.0,  8.0, 0))
    rows.append(_make_company("BAJFINANCE", "Bajaj Finance",           "NBFC", "Financials", y24, 22.0, 6.5,   8000, 25.0, 22.0, 22.0, 55.0, 35.0,  5.5, 0.5, 18.0,  450000,  55000, 12100, 212.0,   2.0, None, 12.0, 100.0, 35.0, 20.0, 0))
    rows.append(_make_company("TITAN",     "Titan Company",           "Consumer","Consumer", y24, 28.0, 0.1,   5000, 15.0, 18.0, 10.0, 18.0, 65.0, 12.0, 1.2, 28.0,  320000,  48000,  4800, 135.0,   8.0, None, 26.0, 110.0, 40.0, 16.0, 0))
    rows.append(_make_company("MARUTI",    "Maruti Suzuki",           "Auto", "Auto",       y24, 22.0, 0.08, 12000, 14.0, 12.0,  8.5, 12.0, 28.0,  6.0, 0.8, 25.0,  390000, 132000, 11200, 365.0,  10.0, None, 16.0, 105.0, 50.0, 11.0, 0))
    rows.append(_make_company("HCLTECH",   "HCL Technologies",        "IT",   "IT",         y24, 24.0, 0.0,  10000, 13.0, 10.5, 14.0, 22.0, 26.0,  5.5, 2.8, 35.0,  450000, 110000, 15400,  54.0, None, None, 20.0, 115.0, 52.0, 10.0, 1))
    rows.append(_make_company("ASIANPAINT", "Asian Paints",           "Consumer","Consumer", y24, 20.0, 0.05,  6000,  8.0,  7.0, 11.0, 16.0, 55.0,  8.0, 1.3, 50.0,  280000,  35000,  3850, 103.0,   9.0, None, 19.0, 108.0, 42.0,  6.0, 0))
    rows.append(_make_company("ULTRACEMCO", "UltraTech Cement",       "Cement","Infrastructure",y24, 14.0, 0.3,  9000, 12.0, 22.0, 10.0, 18.0, 38.0,  4.5, 0.5, 20.0,  330000,  72000,  7200, 234.0,   5.0, None, 11.0, 100.0, 45.0, 18.0, 0))
    rows.append(_make_company("LTIMIND",   "LTIMindtree",             "IT",   "IT",         y24, 30.0, 0.0,   9500, 18.0, 25.0, 16.0, 25.0, 30.0,  9.0, 1.5, 30.0,  180000,  42000,  6300, 130.0, None, None, 35.0, 118.0, 55.0, 22.0, 1))
    rows.append(_make_company("VODAIDEA",  "Vodafone Idea",           "TELECOM","Telecom",  y24,  6.0, 7.0,   2000, 12.0, 15.0,  2.0, 24.0, None,  0.2, 0.0, None,   85000,  45000,   900,   2.5,   0.4, None,  3.0,  80.0, 15.0, 12.0, 0))
    rows.append(_make_company("TATASTEEL", "Tata Steel",             "Steel","Infrastructure",y24, 16.0, 0.5,  5000,  8.0, 10.0,  6.0, 12.0, 12.0,  1.5, 1.0, 20.0,  180000, 145000,  8700,  75.0,   3.0, None, 10.0,  95.0, 30.0,  8.0, 0))
    rows.append(_make_company("ADANIENT",  "Adani Enterprises",       "Conglomerate","Conglomerate",y24,12.0, 0.9,  3000, 18.0, 30.0,  5.0, 10.0, 80.0,  4.0, 0.2, 15.0,  310000, 120000,  6000, 200.0,   2.5, None,  8.0,  90.0, 20.0, 25.0, 0))
    rows.append(_make_company("POWERGRID", "Power Grid Corp",        "Power","Utilities",   y24, 15.0, 1.2,   8500, 10.0, 12.0, 14.0, 30.0, 17.0,  2.5, 4.0, 45.0,  330000,  55000,  7700,  27.0,   4.5, None, 12.0, 115.0, 55.0, 10.0, 0))
    rows.append(_make_company("COALINDIA", "Coal India",             "Mining","Resources",  y24, 25.0, 0.0,  18000,  5.0,  8.0, 22.0, 35.0,  8.5,  2.2, 5.0, 65.0,  320000,  40000,  8800,  54.0,  10.0, None, 28.0, 130.0, 70.0,  7.0, 1))

    # --- Year 2023 (previous) ---
    # D/E values for YoY comparison (turnaround watch needs declining D/E):
    #   VODAIDEA:  8.5 -> 7.0 (declining)      ITC:       0.05 -> 0.01 (declining)
    #   TATASTEEL: 0.8 -> 0.5 (declining)      ADANIENT:  1.5  -> 0.9  (declining)
    #   TCS:       0.0 -> 0.0 (flat)           POWERGRID: 1.0  -> 1.2  (RISING)
    #   HINDUNILVR: 0.2 -> 0.35 (RISING)
    y23 = "2023"
    de_prev = {
        "TCS": 0.0, "INFY": 0.0, "WIPRO": 0.0, "HDFCBANK": 5.5, "SBIN": 7.5,
        "ITC": 0.05, "HINDUNILVR": 0.2, "RELIANCE": 0.65, "BAJFINANCE": 6.8,
        "TITAN": 0.15, "MARUTI": 0.1, "HCLTECH": 0.0, "ASIANPAINT": 0.05,
        "ULTRACEMCO": 0.4, "LTIMIND": 0.0, "VODAIDEA": 8.5, "TATASTEEL": 0.8,
        "ADANIENT": 1.5, "POWERGRID": 1.0, "COALINDIA": 0.0,
    }
    for cid in list(de_prev.keys()):
        df_flag = 1 if de_prev[cid] == 0 else 0
        #         cid  name  sector broad yr   roe  de         fcf   revc patc npm  opm  pe   pb  divy pay  mcap   sales  np   eps  icr roce cfoq fcfconv epsc df
        rows.append(_make_company(cid, cid, "X",  "X",  y23, 15.0, de_prev[cid], 5000, 10.0, 10.0, 10.0, 15.0, 20.0, 3.0, 1.0, 40.0, 100000, 50000, 5000, 50.0, 5.0, 12.0, 100.0, 40.0, 10.0, df_flag))

    return pd.DataFrame(rows)


# ==================================================================
# 1. Helper functions
# ==================================================================


class TestHelpers:
    """Test get_latest_year, get_previous_year, _get_de_declining_company_ids."""

    def test_get_latest_year_selects_2024(self, multi_year_df):
        latest = get_latest_year(multi_year_df)
        assert len(latest) == 20
        assert (latest["year"] == "2024").all()

    def test_get_latest_year_single_row_per_company(self, multi_year_df):
        latest = get_latest_year(multi_year_df)
        assert latest["company_id"].nunique() == 20

    def test_get_previous_year_selects_2023(self, multi_year_df):
        prev = get_previous_year(multi_year_df)
        assert len(prev) == 20
        assert (prev["year"] == "2023").all()

    def test_get_latest_empty_df(self):
        df = pd.DataFrame(columns=["company_id", "year"])
        latest = get_latest_year(df)
        assert len(latest) == 0

    def test_de_declining_identifies_correct_companies(self, multi_year_df):
        declining = _get_de_declining_company_ids(multi_year_df)
        assert "VODAIDEA" in declining     # 8.5 -> 7.0
        assert "TATASTEEL" in declining     # 0.8 -> 0.5
        assert "ADANIENT" in declining      # 1.5 -> 0.9
        assert "ITC" in declining           # 0.05 -> 0.01
        assert "TCS" not in declining       # 0.0 -> 0.0 (flat)
        assert "POWERGRID" not in declining # 1.0 -> 1.2 (rising)
        assert "HINDUNILVR" not in declining # 0.2 -> 0.35 (rising)

    def test_de_declining_single_year_returns_empty(self):
        df = pd.DataFrame([
            {"company_id": "A", "year": "2024", "debt_to_equity": 1.0},
            {"company_id": "B", "year": "2024", "debt_to_equity": 0.5},
        ])
        declining = _get_de_declining_company_ids(df)
        assert len(declining) == 0


# ==================================================================
# 2. Quality Compounder
# ==================================================================


class TestQualityCompounder:
    """Quality Compounder: ROE > 15%, D/E < 1.0, FCF > 0, Revenue CAGR 5yr > 10%."""

    def test_passes_expected_companies(self, multi_year_df, tmp_config):
        result = screen_quality_compounder(multi_year_df, config_path=tmp_config)
        ids = result["company_id"].tolist()
        assert "TCS" in ids
        assert "INFY" in ids
        assert "WIPRO" in ids
        assert "HDFCBANK" in ids
        assert "LTIMIND" in ids
        assert "TITAN" in ids
        assert "RELIANCE" not in ids
        assert "ITC" not in ids

    def test_returns_multiple_companies(self, multi_year_df, tmp_config):
        result = screen_quality_compounder(multi_year_df, config_path=tmp_config)
        assert len(result) >= 5

    def test_result_sorted_by_composite_score(self, multi_year_df, tmp_config):
        result = screen_quality_compounder(multi_year_df, config_path=tmp_config)
        scores = result["composite_quality_score"].dropna().tolist()
        assert scores == sorted(scores, reverse=True)


# ==================================================================
# 3. Value Pick
# ==================================================================


class TestValuePick:
    """Value Pick: P/E < 20, P/B < 3.0, D/E < 2.0, Dividend Yield > 1%."""

    def test_passes_expected_companies(self, multi_year_df, tmp_config):
        result = screen_value_pick(multi_year_df, config_path=tmp_config)
        ids = result["company_id"].tolist()
        assert "SBIN" in ids
        assert "HDFCBANK" in ids
        assert "POWERGRID" in ids
        assert "COALINDIA" in ids
        assert "TCS" not in ids
        assert "BAJFINANCE" not in ids

    def test_returns_multiple_companies(self, multi_year_df, tmp_config):
        result = screen_value_pick(multi_year_df, config_path=tmp_config)
        assert len(result) >= 3


# ==================================================================
# 4. Growth Accelerator
# ==================================================================


class TestGrowthAccelerator:
    """Growth Accelerator: PAT CAGR 5yr > 20%, Revenue CAGR 5yr > 15%, D/E < 2.0."""

    def test_passes_expected_companies(self, multi_year_df, tmp_config):
        result = screen_growth_accelerator(multi_year_df, config_path=tmp_config)
        ids = result["company_id"].tolist()
        assert "BAJFINANCE" in ids
        assert "LTIMIND" in ids
        assert "ADANIENT" in ids
        assert "HDFCBANK" not in ids
        assert "TCS" not in ids

    def test_excludes_low_growth(self, multi_year_df, tmp_config):
        result = screen_growth_accelerator(multi_year_df, config_path=tmp_config)
        ids = result["company_id"].tolist()
        assert "ITC" not in ids
        assert "ASIANPAINT" not in ids


# ==================================================================
# 5. Dividend Champion
# ==================================================================


class TestDividendChampion:
    """Dividend Champion: Dividend Yield > 2%, Payout < 80%, FCF > 0."""

    def test_passes_expected_companies(self, multi_year_df, tmp_config):
        result = screen_dividend_champion(multi_year_df, config_path=tmp_config)
        ids = result["company_id"].tolist()
        assert "INFY" in ids
        assert "COALINDIA" in ids
        assert "POWERGRID" in ids
        assert "HCLTECH" in ids
        assert "ITC" not in ids
        assert "TCS" not in ids

    def test_excludes_high_payout(self, multi_year_df, tmp_config):
        result = screen_dividend_champion(multi_year_df, config_path=tmp_config)
        ids = result["company_id"].tolist()
        assert "ITC" not in ids
        assert "HINDUNILVR" not in ids


# ==================================================================
# 6. Debt-Free Blue Chip
# ==================================================================


class TestDebtFreeBlueChip:
    """Debt-Free Blue Chip: D/E = 0, ROE > 12%, Revenue > 5000 Cr."""

    def test_passes_expected_companies(self, multi_year_df, tmp_config):
        result = screen_debt_free_blue_chip(multi_year_df, config_path=tmp_config)
        ids = result["company_id"].tolist()
        assert "TCS" in ids
        assert "INFY" in ids
        assert "COALINDIA" in ids
        assert "LTIMIND" in ids
        assert "HCLTECH" in ids
        assert "WIPRO" in ids
        assert "RELIANCE" not in ids
        assert "ITC" not in ids

    def test_excludes_near_zero_de(self, multi_year_df, tmp_config):
        result = screen_debt_free_blue_chip(multi_year_df, config_path=tmp_config)
        ids = result["company_id"].tolist()
        assert "ITC" not in ids
        assert "TITAN" not in ids

    def test_excludes_financials_with_debt(self, multi_year_df, tmp_config):
        result = screen_debt_free_blue_chip(multi_year_df, config_path=tmp_config)
        ids = result["company_id"].tolist()
        assert "HDFCBANK" not in ids


# ==================================================================
# 7. Turnaround Watch (custom logic)
# ==================================================================


class TestTurnaroundWatch:
    """Turnaround Watch: Revenue CAGR 5yr > 10%, FCF > 0, D/E declining YoY."""

    def test_requires_de_declining(self, multi_year_df, tmp_config):
        result = screen_turnaround_watch(multi_year_df, config_path=tmp_config)
        ids = result["company_id"].tolist()
        assert "VODAIDEA" in ids
        assert "ADANIENT" in ids
        assert "ITC" not in ids
        assert "TATASTEEL" not in ids

    def test_excludes_rising_de(self, multi_year_df, tmp_config):
        result = screen_turnaround_watch(multi_year_df, config_path=tmp_config)
        ids = result["company_id"].tolist()
        assert "POWERGRID" not in ids
        assert "HINDUNILVR" not in ids

    def test_excludes_flat_de(self, multi_year_df, tmp_config):
        result = screen_turnaround_watch(multi_year_df, config_path=tmp_config)
        ids = result["company_id"].tolist()
        assert "TCS" not in ids

    def test_excludes_negative_fcf(self):
        """Companies with negative FCF in latest year should be excluded."""
        df = pd.DataFrame([
            {"company_id": "A", "year": "2024", "debt_to_equity": 1.0, "free_cash_flow": -5000,
             "revenue_cagr_5yr": 15.0, "roe": 10.0, "roce": 10.0, "net_profit_margin": 10.0,
             "operating_profit_margin": 20.0, "interest_coverage_ratio": 3.0, "asset_turnover": 0.5,
             "pe_ratio": 15.0, "pb_ratio": 2.0, "dividend_yield": 1.0,
             "dividend_payout_ratio": 30.0, "market_cap": 50000, "net_sales": 50000,
             "net_profit": 5000, "eps": 10.0, "cfo_quality_score": 100.0,
             "fcf_conversion_rate": 30.0, "pat_cagr_5yr": 10.0, "eps_cagr_5yr": 10.0,
             "is_debt_free": 0, "composite_quality_score": None, "sector_id": "X", "broad_sector": "X"},
            {"company_id": "A", "year": "2023", "debt_to_equity": 2.0, "free_cash_flow": 1000,
             "revenue_cagr_5yr": 10.0, "roe": 8.0, "roce": 8.0, "net_profit_margin": 8.0,
             "operating_profit_margin": 15.0, "interest_coverage_ratio": 2.0, "asset_turnover": 0.4,
             "pe_ratio": 12.0, "pb_ratio": 1.5, "dividend_yield": 0.5,
             "dividend_payout_ratio": 25.0, "market_cap": 40000, "net_sales": 40000,
             "net_profit": 3200, "eps": 6.0, "cfo_quality_score": 90.0,
             "fcf_conversion_rate": 25.0, "pat_cagr_5yr": 8.0, "eps_cagr_5yr": 8.0,
             "is_debt_free": 0, "composite_quality_score": None, "sector_id": "X", "broad_sector": "X"},
        ])
        result = screen_turnaround_watch(df)
        assert len(result) == 0


# ==================================================================
# 8. Dispatcher and batch runner
# ==================================================================


class TestDispatcher:
    """Test run_preset dispatcher and run_all_presets batch runner."""

    def test_run_preset_dispatches_correctly(self, multi_year_df, tmp_config):
        qc = run_preset("quality_compounder", multi_year_df, config_path=tmp_config)
        direct = screen_quality_compounder(multi_year_df, config_path=tmp_config)
        assert qc.equals(direct)

    def test_run_preset_unknown_raises(self, multi_year_df):
        with pytest.raises(KeyError, match="Unknown preset"):
            run_preset("nonexistent", multi_year_df)

    def test_run_all_presets_returns_all_six(self, multi_year_df, tmp_config):
        results = run_all_presets(multi_year_df, config_path=tmp_config)
        assert len(results) == 6
        for name in ALL_PRESETS:
            assert name in results
            assert isinstance(results[name], pd.DataFrame)

    def test_all_presets_have_composite_score(self, multi_year_df, tmp_config):
        results = run_all_presets(multi_year_df, config_path=tmp_config)
        for name, df in results.items():
            if not df.empty:
                assert "composite_quality_score" in df.columns


# ==================================================================
# 9. Validation
# ==================================================================


class TestValidation:
    """Test validate_preset_counts helper."""

    def test_passing_validation(self):
        results = {
            "qc": pd.DataFrame({"a": range(10)}),
            "vp": pd.DataFrame({"a": range(5)}),
        }
        v = validate_preset_counts(results, min_count=3, max_count=20)
        assert v["qc"]["pass"] is True
        assert v["vp"]["pass"] is True

    def test_too_few_warning(self):
        results = {"qc": pd.DataFrame({"a": range(2)})}
        v = validate_preset_counts(results, min_count=5)
        assert v["qc"]["pass"] is False
        assert "TOO FEW" in v["qc"]["message"]

    def test_too_many_warning(self):
        results = {"qc": pd.DataFrame({"a": range(60)})}
        v = validate_preset_counts(results, max_count=50)
        assert v["qc"]["pass"] is False
        assert "TOO MANY" in v["qc"]["message"]

    def test_empty_result(self):
        results = {"qc": pd.DataFrame()}
        v = validate_preset_counts(results, min_count=1)
        assert v["qc"]["pass"] is False
        assert "TOO FEW" in v["qc"]["message"]


# ==================================================================
# 10. Module-level constants
# ==================================================================


class TestConstants:
    """Verify module exports are correct."""

    def test_all_presets_has_six(self):
        assert len(ALL_PRESETS) == 6

    def test_all_preset_names(self):
        expected = [
            "quality_compounder", "value_pick", "growth_accelerator",
            "dividend_champion", "debt_free_blue_chip", "turnaround_watch",
        ]
        assert ALL_PRESETS == expected

    def test_preset_functions_has_six(self):
        assert len(PRESET_FUNCTIONS) == 6

    def test_preset_functions_match_all_presets(self):
        assert set(PRESET_FUNCTIONS.keys()) == set(ALL_PRESETS)