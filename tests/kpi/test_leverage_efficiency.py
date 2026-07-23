"""tests/kpi/test_leverage_efficiency.py — Unit tests for leverage & efficiency ratios.

Sprint 2, Day 09 — 8 tests covering:
  1. D/E normal computation
  2. D/E debt-free returns 0 (not None)
  3. high_leverage_flag True for non-Financials D/E > 5
  4. high_leverage_flag False for Financials even with high D/E
  5. ICR normal computation
  6. ICR interest=0 returns None + label = "Debt Free"
  7. ICR label "At Risk" when ICR < 1.5
  8. Asset Turnover zero total_assets returns None
"""

import pytest

from src.analytics.ratios import (
    asset_turnover,
    debt_to_equity,
    get_icr_label,
    interest_coverage_ratio,
    is_high_leverage,
    is_low_icr_warning,
    net_debt,
)


# ── Debt-to-Equity ────────────────────────────────────────────────────

class TestDebtToEquity:

    def test_normal_computation(self):
        """500 / (100 + 50) = 3.33."""
        result = debt_to_equity(500.0, 100.0, 50.0)
        assert result == pytest.approx(3.33, abs=0.01)

    def test_debt_free_returns_zero_not_none(self):
        """borrowings = 0 → D/E must be exactly 0, not None."""
        assert debt_to_equity(0.0, 100.0, 50.0) == 0
        assert debt_to_equity(0.0, 100.0, 50.0) is not None


class TestHighLeverageFlag:

    def test_true_for_non_financials_high_de(self):
        """D/E = 6.0, sector = IT → flag = True."""
        assert is_high_leverage(6.0, broad_sector="IT") is True

    def test_false_for_financials_even_with_high_de(self):
        """D/E = 6.0, sector = Financials → flag = False (suppressed)."""
        assert is_high_leverage(6.0, broad_sector="Financials") is False


# ── Interest Coverage Ratio ───────────────────────────────────────────

class TestInterestCoverageRatio:

    def test_normal_computation(self):
        """(200 + 50) / 100 = 2.5."""
        assert interest_coverage_ratio(200.0, 50.0, 100.0) == 2.5

    def test_interest_zero_returns_none(self):
        """interest = 0 → None (debt-free company)."""
        assert interest_coverage_ratio(200.0, 50.0, 0) is None

    def test_debt_free_label(self):
        """ICR = None → label must be 'Debt Free'."""
        assert get_icr_label(None) == "Debt Free"
        assert is_low_icr_warning(None) is False

    def test_at_risk_label(self):
        """ICR = 1.2 (< 1.5) → label = 'At Risk'."""
        assert get_icr_label(1.2) == "At Risk"
        assert is_low_icr_warning(1.2) is True


# ── Asset Turnover ────────────────────────────────────────────────────

class TestAssetTurnover:

    def test_zero_total_assets_returns_none(self):
        """total_assets = 0 → None, not ZeroDivisionError."""
        assert asset_turnover(1000.0, 0) is None
        assert asset_turnover(1000.0, None) is None