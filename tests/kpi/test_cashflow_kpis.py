"""tests/kpi/test_cashflow_kpis.py — Unit tests for cash flow KPIs.

Sprint 2, Day 11 — 10 tests covering:
  1.  FCF normal (positive)
  2.  FCF negative (company spending > generation)
  3.  CFO Quality — High Quality
  4.  CFO Quality — Accrual Risk
  5.  CapEx Intensity — Asset Light
  6.  CapEx Intensity — Capital Intensive
  7.  FCF Conversion Rate — normal
  8.  Capital Allocation — Reinvestor (+,-,-)
  9.  Capital Allocation — Shareholder Returns (high CFO/PAT)
  10. Capital Allocation — Distress Signal (-,+,+)
"""

import pytest

from src.analytics.cashflow_kpis import (
    capex_intensity,
    cfo_quality_score,
    classify_capital_allocation,
    fcf_conversion_rate,
    free_cash_flow,
    generate_capital_allocation_csv,
)


# ── Free Cash Flow ─────────────────────────────────────────────────────

class TestFreeCashFlow:

    def test_normal_positive(self):
        """CFO=500, CFI=-200 → FCF=300."""
        assert free_cash_flow(500.0, -200.0) == 300.0

    def test_negative_allowed(self):
        """FCF can be negative (heavy investing)."""
        assert free_cash_flow(100.0, -300.0) == -200.0


# ── CFO Quality Score ──────────────────────────────────────────────────

class TestCfoQualityScore:

    def test_high_quality(self):
        """CFO/PAT ratios: [1.2, 1.3, 1.1] → avg 1.2 > 1.0."""
        cfo = [120.0, 130.0, 110.0]
        pat = [100.0, 100.0, 100.0]
        assert cfo_quality_score(cfo, pat) == "High Quality"

    def test_accrual_risk(self):
        """CFO/PAT ratios: [0.3, 0.4] → avg 0.35 < 0.5."""
        cfo = [30.0, 40.0]
        pat = [100.0, 100.0]
        assert cfo_quality_score(cfo, pat) == "Accrual Risk"

    def test_returns_none_when_pat_zero(self):
        """All PAT values are 0 → no valid ratios → None."""
        assert cfo_quality_score([100.0, 200.0], [0.0, 0.0]) is None


# ── CapEx Intensity ────────────────────────────────────────────────────

class TestCapExIntensity:

    def test_asset_light(self):
        """|CFI|=20, sales=1000 → 2% < 3% → Asset Light."""
        pct, label = capex_intensity(-20.0, 1000.0)
        assert label == "Asset Light"
        assert pct == 2.0

    def test_capital_intensive(self):
        """|CFI|=100, sales=1000 → 10% > 8% → Capital Intensive."""
        pct, label = capex_intensity(-100.0, 1000.0)
        assert label == "Capital Intensive"
        assert pct == 10.0


# ── FCF Conversion Rate ───────────────────────────────────────────────

class TestFcfConversionRate:

    def test_normal(self):
        """FCF=300, OP=500 → 60%."""
        assert fcf_conversion_rate(300.0, 500.0) == 60.0

    def test_operating_profit_zero_returns_none(self):
        assert fcf_conversion_rate(300.0, 0.0) is None


# ── Capital Allocation Pattern ─────────────────────────────────────────

class TestCapitalAllocationPattern:

    def test_reinvestor(self):
        """(+,-,-) without high CFO/PAT → Reinvestor."""
        result = classify_capital_allocation(500.0, -200.0, -100.0)
        assert result["pattern_label"] == "Reinvestor"

    def test_shareholder_returns(self):
        """(+,-,-) with CFO/PAT=2.0 > 1.5 → Shareholder Returns."""
        result = classify_capital_allocation(
            500.0, -200.0, -100.0, cfo_pat_ratio=2.0
        )
        assert result["pattern_label"] == "Shareholder Returns"

    def test_distress_signal(self):
        """(-,+,+) → Distress Signal."""
        result = classify_capital_allocation(-100.0, 50.0, 200.0)
        assert result["pattern_label"] == "Distress Signal"

    def test_growth_funded_by_debt(self):
        """(-,-,+) → Growth Funded by Debt."""
        result = classify_capital_allocation(-50.0, -300.0, 400.0)
        assert result["pattern_label"] == "Growth Funded by Debt"


# ── CSV generation ─────────────────────────────────────────────────────

class TestGenerateCsv:

    def test_writes_csv(self, tmp_path):
        import csv as csv_mod

        csv_path = str(tmp_path / "allocation.csv")
        rows = [
            dict(
                company_id="TCS", year="2023-03",
                cfo_sign=1, cfi_sign=-1, cff_sign=-1,
                pattern_label="Shareholder Returns",
            ),
        ]
        generate_capital_allocation_csv(rows, csv_path)

        with open(csv_path, encoding="utf-8") as f:
            reader = csv_mod.DictReader(f)
            header = reader.fieldnames
            data = list(reader)

        assert "company_id" in header
        assert "pattern_label" in header
        assert len(data) == 1
        assert data[0]["pattern_label"] == "Shareholder Returns"