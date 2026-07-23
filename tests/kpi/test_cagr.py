"""tests/kpi/test_cagr.py — Unit tests for the CAGR engine.

Sprint 2, Day 10 — 10 tests covering:
  1.  Normal CAGR computation
  2.  Decline-to-loss flag (positive → negative)
  3.  Turnaround flag (negative → positive)
  4.  Both-negative flag
  5.  Zero-base flag
  6.  Insufficient-data flag (n_years < window)
  7.  3-year window from yearly data
  8.  5-year window exact match
  9.  10-year window with insufficient years
  10. None values filtered out gracefully
"""

import pytest

from src.analytics.cagr import cagr, compute_all_cagrs, compute_cagr_window


# ── Core formula + edge-case flags ─────────────────────────────────────

class TestCagrFormula:

    def test_normal_positive_values(self):
        """100 → 150 over 5 yr: CAGR ≈ 8.45%."""
        val, flag = cagr(100.0, 150.0, 5)
        assert flag == ""
        assert val == pytest.approx(8.45, abs=0.01)

    def test_decline_to_loss_flag(self):
        """Positive start, negative end → DECLINE_TO_LOSS."""
        val, flag = cagr(100.0, -20.0, 3)
        assert val is None
        assert flag == "DECLINE_TO_LOSS"

    def test_turnaround_flag(self):
        """Negative start, positive end → TURNAROUND."""
        val, flag = cagr(-50.0, 30.0, 3)
        assert val is None
        assert flag == "TURNAROUND"

    def test_both_negative_flag(self):
        """Both negative → BOTH_NEGATIVE."""
        val, flag = cagr(-50.0, -20.0, 3)
        assert val is None
        assert flag == "BOTH_NEGATIVE"

    def test_zero_base_flag(self):
        """Start = 0 → ZERO_BASE."""
        val, flag = cagr(0.0, 150.0, 5)
        assert val is None
        assert flag == "ZERO_BASE"

    def test_insufficient_n_years(self):
        """n_years = 0 → INSUFFICIENT."""
        val, flag = cagr(100.0, 150.0, 0)
        assert val is None
        assert flag == "INSUFFICIENT"


# ── Window-based computation ───────────────────────────────────────────

class TestCagrWindow:

    def test_3yr_window(self):
        """10 years of data, 3-yr window → uses 2020 and 2023."""
        data = [
            ("2014-03", 60.0), ("2015-03", 65.0), ("2016-03", 72.0),
            ("2017-03", 80.0), ("2018-03", 88.0), ("2019-03", 95.0),
            ("2020-03", 100.0), ("2021-03", 115.0), ("2022-03", 132.0),
            ("2023-03", 150.0),
        ]
        val, flag = compute_cagr_window(data, 3)
        assert flag == ""
        # 100 → 150 over 3 years
        assert val == pytest.approx(14.47, abs=0.01)

    def test_5yr_window_exact_match(self):
        """Start year exactly 5 years before end."""
        data = [
            ("2018-03", 100.0), ("2019-03", 110.0), ("2020-03", 120.0),
            ("2021-03", 135.0), ("2022-03", 142.0), ("2023-03", 150.0),
        ]
        val, flag = compute_cagr_window(data, 5)
        assert flag == ""
        assert val == pytest.approx(8.45, abs=0.01)

    def test_10yr_window_insufficient(self):
        """Only 5 years of data but requesting 10-yr window."""
        data = [
            ("2019-03", 80.0), ("2020-03", 90.0), ("2021-03", 105.0),
            ("2022-03", 120.0), ("2023-03", 150.0),
        ]
        val, flag = compute_cagr_window(data, 10)
        assert val is None
        assert flag == "INSUFFICIENT"

    def test_none_values_filtered(self):
        """None entries are skipped; valid entries still produce CAGR."""
        data = [
            ("2018-03", 100.0), ("2019-03", None), ("2020-03", None),
            ("2021-03", 115.0), ("2022-03", 132.0), ("2023-03", 150.0),
        ]
        val, flag = compute_cagr_window(data, 3)
        # 2020 missing → falls back to 2018 (5 yr span)
        assert flag == ""
        assert val is not None


# ── compute_all_cagrs convenience ──────────────────────────────────────

class TestComputeAllCagrs:

    def test_returns_three_windows(self):
        data = [
            ("2015-03", 70.0), ("2018-03", 100.0), ("2020-03", 100.0),
            ("2023-03", 150.0),
        ]
        result = compute_all_cagrs(data)
        assert "cagr_3yr" in result
        assert "cagr_5yr" in result
        assert "cagr_10yr" in result
        # 3-yr and 5-yr should succeed; 10-yr insufficient (no data ≤ 2013)
        assert result["cagr_3yr"][1] == ""
        assert result["cagr_5yr"][1] == ""
        assert result["cagr_10yr"][1] == "INSUFFICIENT"