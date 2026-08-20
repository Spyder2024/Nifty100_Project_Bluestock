"""tests/kpi/test_ratios.py — 20 Unit Tests for KPI and Ratio Engines.

Sprint 7, Day 41

Tests covering:
1. ROE with positive equity
2. ROE with negative equity (returns None)
3. D/E for debt-free company (returns 0)
4. ICR when interest=0 (returns None)
5. D/E > 5 flag for non-financial company
6. CAGR turnaround flag
7. CAGR decline-to-loss
8. Normal CAGR calculation
9. OPM cross-check divergence flag
10. CFO quality score calculation
11. ROCE standard calculation
12. ROCE for Financials sector (bank carve-out)
13. Net Profit Margin standard calculation
14. Net Profit Margin with zero sales (returns None)
15. Return on Assets calculation
16. Return on Assets with zero assets (returns None)
17. Net Debt calculation (borrowings - investments)
18. Asset Turnover calculation
19. Low ICR warning threshold (< 1.5) & ICR label
20. CAGR edge cases (ZERO_BASE, INSUFFICIENT, BOTH_NEGATIVE)
"""

import logging
import pytest
from src.analytics.cagr import cagr
from src.analytics.cashflow_kpis import cfo_quality_score, free_cash_flow
from src.analytics.ratios import (
    asset_turnover,
    debt_to_equity,
    get_icr_label,
    interest_coverage_ratio,
    is_high_leverage,
    is_low_icr_warning,
    net_debt,
    net_profit_margin,
    operating_profit_margin,
    return_on_assets,
    return_on_capital_employed,
    return_on_equity,
)


def test_01_roe_positive_equity():
    """1. ROE with positive equity: net_profit=500, equity_capital=100, reserves=1900 -> 25.0%."""
    roe = return_on_equity(net_profit=500.0, equity_capital=100.0, reserves_and_surplus=1900.0)
    assert roe == 25.0


def test_02_roe_negative_equity_returns_none():
    """2. ROE with negative equity (accumulated losses) returns None."""
    roe_neg = return_on_equity(net_profit=50.0, equity_capital=100.0, reserves_and_surplus=-300.0)
    assert roe_neg is None

    roe_zero = return_on_equity(net_profit=50.0, equity_capital=100.0, reserves_and_surplus=-100.0)
    assert roe_zero is None


def test_03_de_debt_free_returns_zero():
    """3. D/E for debt-free company (borrowings=0) returns 0.0 (not None)."""
    de = debt_to_equity(borrowings=0.0, equity_capital=100.0, reserves_and_surplus=900.0)
    assert de == 0.0


def test_04_icr_zero_interest_returns_none():
    """4. ICR when interest=0 returns None (division by zero / debt-free)."""
    icr = interest_coverage_ratio(operating_profit=1000.0, other_income=50.0, interest=0.0)
    assert icr is None


def test_05_high_leverage_flag_non_financial():
    """5. D/E > 5 flag is raised for non-financial companies and suppressed for Financials."""
    assert is_high_leverage(de_ratio=5.5, broad_sector="Capital Goods") is True
    assert is_high_leverage(de_ratio=5.5, broad_sector="Consumer Staples") is True
    assert is_high_leverage(de_ratio=3.0, broad_sector="Capital Goods") is False
    # Bank carve-out
    assert is_high_leverage(de_ratio=7.2, broad_sector="Financials") is False


def test_06_cagr_turnaround_flag():
    """6. CAGR turnaround flag: start < 0, end > 0 returns (None, 'TURNAROUND')."""
    val, flag = cagr(start_value=-50.0, end_value=120.0, n_years=3)
    assert val is None
    assert flag == "TURNAROUND"


def test_07_cagr_decline_to_loss_flag():
    """7. CAGR decline-to-loss: start > 0, end < 0 returns (None, 'DECLINE_TO_LOSS')."""
    val, flag = cagr(start_value=100.0, end_value=-20.0, n_years=5)
    assert val is None
    assert flag == "DECLINE_TO_LOSS"


def test_08_normal_cagr_calculation():
    """8. Normal CAGR calculation: 100 to 200 in 3 years -> ~25.99%."""
    val, flag = cagr(start_value=100.0, end_value=200.0, n_years=3)
    assert flag == ""
    assert round(val, 2) == 25.99


def test_09_opm_crosscheck_divergence(caplog):
    """9. OPM cross-check divergence flag: logs WARNING if diff > 1.0pp."""
    with caplog.at_level(logging.WARNING):
        opm = operating_profit_margin(operating_profit=200.0, sales=1000.0, source_opm=15.0)
        assert opm == 20.0
        assert any("OPM cross-check mismatch" in record.message for record in caplog.records)


def test_10_cfo_quality_score():
    """10. CFO quality score: >1.0 High Quality, 0.5-1.0 Moderate, <0.5 Accrual Risk."""
    # High Quality
    assert cfo_quality_score(cfo_values=[120.0, 150.0], pat_values=[100.0, 100.0]) == "High Quality"
    # Moderate
    assert cfo_quality_score(cfo_values=[70.0, 80.0], pat_values=[100.0, 100.0]) == "Moderate"
    # Accrual Risk
    assert cfo_quality_score(cfo_values=[30.0, 40.0], pat_values=[100.0, 100.0]) == "Accrual Risk"


def test_11_roce_standard_calculation():
    """11. ROCE = EBIT / Capital Employed: 300 / (100 + 400 + 500) = 30%."""
    roce = return_on_capital_employed(
        ebit=300.0,
        equity_capital=100.0,
        reserves_and_surplus=400.0,
        borrowings=500.0,
    )
    assert roce == 30.0


def test_12_roce_financials_sector_note(caplog):
    """12. ROCE for Financials sector logs info note regarding relative benchmark."""
    with caplog.at_level(logging.INFO):
        roce = return_on_capital_employed(
            ebit=500.0,
            equity_capital=200.0,
            reserves_and_surplus=1800.0,
            borrowings=3000.0,
            broad_sector="Financials",
        )
        assert roce == 10.0
        assert any("Financials sector company" in record.message for record in caplog.records)


def test_13_net_profit_margin():
    """13. Net Profit Margin = (net_profit / sales) * 100."""
    npm = net_profit_margin(net_profit=150.0, sales=1000.0)
    assert npm == 15.0


def test_14_net_profit_margin_zero_sales():
    """14. Net Profit Margin with zero or None sales returns None."""
    assert net_profit_margin(net_profit=150.0, sales=0.0) is None
    assert net_profit_margin(net_profit=150.0, sales=None) is None


def test_15_return_on_assets():
    """15. Return on Assets = (net_profit / total_assets) * 100."""
    roa = return_on_assets(net_profit=120.0, total_assets=1000.0)
    assert roa == 12.0


def test_16_return_on_assets_zero_assets():
    """16. Return on Assets with zero or None total_assets returns None."""
    assert return_on_assets(net_profit=120.0, total_assets=0.0) is None
    assert return_on_assets(net_profit=120.0, total_assets=None) is None


def test_17_net_debt_calculation():
    """17. Net Debt = borrowings - investments."""
    nd = net_debt(borrowings=1500.0, investments=500.0)
    assert nd == 1000.0
    assert net_debt(borrowings=None, investments=500.0) is None


def test_18_asset_turnover():
    """18. Asset Turnover = sales / total_assets."""
    at = asset_turnover(sales=2500.0, total_assets=1000.0)
    assert at == 2.5
    assert asset_turnover(sales=2500.0, total_assets=0.0) is None


def test_19_icr_threshold_and_label():
    """19. Low ICR warning (< 1.5) and display label generation."""
    assert is_low_icr_warning(1.2) is True
    assert is_low_icr_warning(3.5) is False
    assert is_low_icr_warning(None) is False

    assert get_icr_label(None) == "Debt Free"
    assert get_icr_label(1.1) == "At Risk"
    assert get_icr_label(4.0) == ""


def test_20_cagr_zero_base_and_insufficient():
    """20. CAGR edge cases: ZERO_BASE, INSUFFICIENT, BOTH_NEGATIVE."""
    val_zb, flag_zb = cagr(start_value=0.0, end_value=100.0, n_years=3)
    assert val_zb is None
    assert flag_zb == "ZERO_BASE"

    val_ins, flag_ins = cagr(start_value=100.0, end_value=200.0, n_years=0)
    assert val_ins is None
    assert flag_ins == "INSUFFICIENT"

    val_bn, flag_bn = cagr(start_value=-100.0, end_value=-50.0, n_years=3)
    assert val_bn is None
    assert flag_bn == "BOTH_NEGATIVE"
