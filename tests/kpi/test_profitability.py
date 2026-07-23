"""tests/kpi/test_profitability.py — Unit tests for profitability ratios.

Sprint 2, Day 08 — 8 tests covering:
  1. NPM normal computation
  2. NPM zero denominator → None
  3. OPM normal computation
  4. OPM cross-check mismatch → warning logged
  5. ROE normal computation
  6. ROE negative equity → None
  7. ROCE with Financials sector benchmark log
  8. ROA zero total_assets → None
"""

import logging

import pytest

from src.analytics.ratios import (
    net_profit_margin,
    operating_profit_margin,
    return_on_assets,
    return_on_capital_employed,
    return_on_equity,
)


# ── Net Profit Margin ────────────────────────────────────────────────

class TestNetProfitMargin:

    def test_normal_computation(self):
        """150 / 1000 × 100 = 15.0%."""
        assert net_profit_margin(150.0, 1000.0) == 15.0

    def test_zero_sales_returns_none(self):
        """Denominator is zero → must return None, not raise."""
        assert net_profit_margin(150.0, 0) is None
        assert net_profit_margin(150.0, None) is None
        assert net_profit_margin(None, 1000.0) is None


# ── Operating Profit Margin ──────────────────────────────────────────

class TestOperatingProfitMargin:

    def test_normal_computation(self):
        """200 / 1000 × 100 = 20.0%."""
        assert operating_profit_margin(200.0, 1000.0) == 20.0

    def test_cross_check_mismatch_logs_warning(self, caplog):
        """Computed 20% vs source 25% (diff=5pp > 1%) → WARNING logged."""
        with caplog.at_level(logging.WARNING, logger="src.analytics.ratios"):
            result = operating_profit_margin(
                200.0, 1000.0, source_opm=25.0
            )
        assert result == 20.0
        assert "OPM cross-check mismatch" in caplog.text


# ── Return on Equity ─────────────────────────────────────────────────

class TestReturnOnEquity:

    def test_normal_computation(self):
        """150 / (100 + 50) × 100 = 100.0%."""
        assert return_on_equity(150.0, 100.0, 50.0) == 100.0

    def test_negative_equity_returns_none(self):
        """Negative or zero shareholders' equity → None."""
        assert return_on_equity(150.0, 100.0, -150.0) is None
        assert return_on_equity(150.0, 0.0, 0.0) is None


# ── Return on Capital Employed ───────────────────────────────────────

class TestReturnOnCapitalEmployed:

    def test_normal_computation(self):
        """EBIT=200, CE=100+50+50=200 → 100.0%."""
        result = return_on_capital_employed(200.0, 100.0, 50.0, 50.0)
        assert result == 100.0

    def test_financials_sector_logs_benchmark_note(self, caplog):
        """Financials sector → INFO about sector-relative benchmark."""
        with caplog.at_level(logging.INFO, logger="src.analytics.ratios"):
            result = return_on_capital_employed(
                200.0, 100.0, 50.0, 50.0, broad_sector="Financials"
            )
        assert result == 100.0
        assert "sector-relative benchmark" in caplog.text


# ── Return on Assets ─────────────────────────────────────────────────

class TestReturnOnAssets:

    def test_zero_total_assets_returns_none(self):
        """total_assets = 0 → None, not ZeroDivisionError."""
        assert return_on_assets(150.0, 0) is None
        assert return_on_assets(150.0, None) is None