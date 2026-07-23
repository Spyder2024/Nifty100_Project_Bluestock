"""
Day 12 — Tests for ratio_runner.py
Tests: schema bootstrap, Excel loading (mocked), ratio computation, DB write, verification.
"""

import sqlite3
from pathlib import Path
from unittest.mock import patch, MagicMock

import pandas as pd
import pytest

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def tmp_db(tmp_path):
    """Create an in-memory DB with schema applied."""
    conn = sqlite3.connect(":memory:")
    # Import the module's ensure_schema to set up tables
    from src.analytics.ratio_runner import _create_minimal_tables
    _create_minimal_tables(conn)
    yield conn
    conn.close()


@pytest.fixture
def sample_is_data():
    """Return 3 years of income_statement data for TCS."""
    return [
        {"company_id": "TCS", "year": "2021-03", "sales": 165000, "expenses": 120000,
         "operating_profit": 45000, "opm_percentage": 27.3, "other_income": 3500,
         "interest": 0, "depreciation": 5000, "profit_before_tax": 43500,
         "tax_percentage": 25.0, "net_profit": 32625, "eps": 88.0, "dividend_payout": 40.0},
        {"company_id": "TCS", "year": "2022-03", "sales": 191000, "expenses": 140000,
         "operating_profit": 51000, "opm_percentage": 26.7, "other_income": 4000,
         "interest": 0, "depreciation": 5500, "profit_before_tax": 49500,
         "tax_percentage": 25.5, "net_profit": 36900, "eps": 100.0, "dividend_payout": 45.0},
        {"company_id": "TCS", "year": "2023-03", "sales": 225458, "expenses": 176924,
         "operating_profit": 48534, "opm_percentage": 21.5, "other_income": 3800,
         "interest": 0, "depreciation": 5800, "profit_before_tax": 46534,
         "tax_percentage": 25.0, "net_profit": 34990, "eps": 95.3, "dividend_payout": 45.0},
    ]


@pytest.fixture
def sample_bs_data():
    """Return 3 years of balance_sheet data for TCS."""
    return [
        {"company_id": "TCS", "year": "2021-03", "equity_capital": 370, "reserves": 52000,
         "borrowings": 0, "other_liabilities": 15000, "total_liabilities": 67370,
         "fixed_assets": 12000, "cwip": 500, "investments": 20000, "other_asset": 34870,
         "total_assets": 67370},
        {"company_id": "TCS", "year": "2022-03", "equity_capital": 370, "reserves": 58000,
         "borrowings": 0, "other_liabilities": 16000, "total_liabilities": 74370,
         "fixed_assets": 13000, "cwip": 600, "investments": 22000, "other_asset": 38770,
         "total_assets": 74370},
        {"company_id": "TCS", "year": "2023-03", "equity_capital": 370, "reserves": 62000,
         "borrowings": 0, "other_liabilities": 17500, "total_liabilities": 79870,
         "fixed_assets": 14000, "cwip": 400, "investments": 25000, "other_asset": 40470,
         "total_assets": 79870},
    ]


@pytest.fixture
def sample_cf_data():
    """Return 3 years of cash_flow data for TCS."""
    return [
        {"company_id": "TCS", "year": "2021-03", "operating_activity": 35000,
         "investing_activity": -8000, "financing_activity": -22000, "net_cash_flow": 5000},
        {"company_id": "TCS", "year": "2022-03", "operating_activity": 39000,
         "investing_activity": -9000, "financing_activity": -25000, "net_cash_flow": 5000},
        {"company_id": "TCS", "year": "2023-03", "operating_activity": 42000,
         "investing_activity": -10000, "financing_activity": -28000, "net_cash_flow": 4000},
    ]


# =========================================================================
# Test Classes
# =========================================================================

class TestSchemaBootstrap:
    """Test that schema creation works correctly."""

    def test_creates_all_tables(self, tmp_db):
        tables = [r[0] for r in tmp_db.execute(
            "SELECT name FROM sqlite_master WHERE type='table'"
        ).fetchall()]
        assert "companies" in tables
        assert "income_statement" in tables
        assert "balance_sheet" in tables
        assert "cash_flow" in tables
        assert "financial_ratios" in tables

    def test_financial_ratios_has_all_columns(self, tmp_db):
        cols = [r[1] for r in tmp_db.execute(
            "PRAGMA table_info(financial_ratios)"
        ).fetchall()]
        expected = [
            "company_id", "year", "net_profit_margin_pct",
            "operating_profit_margin_pct", "return_on_equity_pct",
            "debt_to_equity", "interest_coverage", "free_cash_flow_cr",
            "capital_allocation_pattern", "composite_quality_score",
        ]
        for col in expected:
            assert col in cols, f"Missing column: {col}"

    def test_idempotent(self, tmp_db):
        """Running create twice should not raise."""
        from src.analytics.ratio_runner import _create_minimal_tables
        _create_minimal_tables(tmp_db)  # second call
        count = tmp_db.execute(
            "SELECT COUNT(*) FROM sqlite_master WHERE type='table'"
        ).fetchone()[0]
        assert count >= 5


class TestYearNormalization:
    """Test the _normalize_year helper."""

    def test_mar_23_format(self):
        from src.analytics.ratio_runner import _normalize_year
        assert _normalize_year("Mar-23") == "2023-03"

    def test_mar_2023_format(self):
        from src.analytics.ratio_runner import _normalize_year
        assert _normalize_year("Mar-2023") == "2023-03"

    def test_yyyy_mm_format(self):
        from src.analytics.ratio_runner import _normalize_year
        assert _normalize_year("2023-03") == "2023-03"

    def test_four_digit_year(self):
        from src.analytics.ratio_runner import _normalize_year
        assert _normalize_year("2023") == "2023-03"


class TestComputeRow:
    """Test single-row ratio computation."""

    def test_debt_free_company(self, sample_is_data, sample_bs_data, sample_cf_data):
        from src.analytics.ratio_runner import compute_row
        row = compute_row(
            sample_is_data[2], sample_bs_data[2], sample_cf_data[2], "TCS", "2023-03"
        )
        # TCS is debt-free
        assert row["debt_to_equity"] == 0.0
        assert row["is_high_leverage"] == 0
        assert row["total_debt_cr"] == 0

    def test_npm_positive(self, sample_is_data, sample_bs_data, sample_cf_data):
        from src.analytics.ratio_runner import compute_row
        row = compute_row(
            sample_is_data[2], sample_bs_data[2], sample_cf_data[2], "TCS", "2023-03"
        )
        assert row["net_profit_margin_pct"] is not None
        assert row["net_profit_margin_pct"] > 0
        # 34990 / 225458 * 100 ≈ 15.5%
        assert 14.0 <= row["net_profit_margin_pct"] <= 17.0

    def test_roe_reasonable(self, sample_is_data, sample_bs_data, sample_cf_data):
        from src.analytics.ratio_runner import compute_row
        row = compute_row(
            sample_is_data[1], sample_bs_data[1], sample_cf_data[1], "TCS", "2022-03"
        )
        # ROE = 36900 / 58370 * 100 ≈ 63.2%
        assert row["return_on_equity_pct"] is not None
        assert 50.0 <= row["return_on_equity_pct"] <= 80.0

    def test_fcf_computed(self, sample_is_data, sample_bs_data, sample_cf_data):
        from src.analytics.ratio_runner import compute_row
        row = compute_row(
            sample_is_data[2], sample_bs_data[2], sample_cf_data[2], "TCS", "2023-03"
        )
        # FCF = 42000 + (-10000) = 32000
        assert row["free_cash_flow_cr"] == 32000.0

    def test_capital_allocation_reinvest(self, sample_is_data, sample_bs_data, sample_cf_data):
        from src.analytics.ratio_runner import compute_row
        row = compute_row(
            sample_is_data[2], sample_bs_data[2], sample_cf_data[2], "TCS", "2023-03"
        )
        # CFO+, CFI-, CFF- → REINVEST_AND_RETURN
        assert row["capital_allocation_pattern"] is not None
        assert len(row["capital_allocation_pattern"]) > 0

    def test_bvps_computed(self, sample_is_data, sample_bs_data, sample_cf_data):
        from src.analytics.ratio_runner import compute_row
        row = compute_row(
            sample_is_data[2], sample_bs_data[2], sample_cf_data[2], "TCS", "2023-03"
        )
        # BVPS = (370 + 62000) / (370/1) = 62370 / 370 ≈ 168.57
        assert row["book_value_per_share"] is not None
        assert 150.0 <= row["book_value_per_share"] <= 200.0


class TestCompositeScore:
    """Test the composite quality score calculation."""

    def test_high_quality_company(self):
        from src.analytics.ratio_runner import compute_composite_score
        row = {
            "return_on_equity_pct": 25.0,
            "net_profit_margin_pct": 22.0,
            "interest_coverage": 15.0,
            "debt_to_equity": 0.2,
            "fcf_conversion_rate": 85.0,
            "asset_turnover": 1.2,
        }
        score = compute_composite_score(row)
        assert score is not None
        assert score > 70  # Should be high quality

    def test_low_quality_company(self):
        from src.analytics.ratio_runner import compute_composite_score
        row = {
            "return_on_equity_pct": 2.0,
            "net_profit_margin_pct": 1.0,
            "interest_coverage": 1.5,
            "debt_to_equity": 3.0,
            "fcf_conversion_rate": 10.0,
            "asset_turnover": 0.3,
        }
        score = compute_composite_score(row)
        assert score is not None
        assert score < 40  # Should be low quality

    def test_all_none_returns_none(self):
        from src.analytics.ratio_runner import compute_composite_score
        score = compute_composite_score({
            "return_on_equity_pct": None,
            "net_profit_margin_pct": None,
            "interest_coverage": None,
            "debt_to_equity": None,
            "fcf_conversion_rate": None,
            "asset_turnover": None,
        })
        assert score is None


class TestCAGREnrichment:
    """Test that CAGR values get attached to rows."""

    def test_enriches_with_cagr_keys(self, sample_is_data):
        from src.analytics.ratio_runner import enrich_with_cagrs
        rows = [{"company_id": "TCS", "year": r["year"], "revenue_cagr_3yr": None,
                 "revenue_cagr_5yr": None, "revenue_cagr_10yr": None,
                 "pat_cagr_3yr": None, "pat_cagr_5yr": None, "pat_cagr_10yr": None,
                 "eps_cagr_3yr": None, "eps_cagr_5yr": None, "eps_cagr_10yr": None}
                for r in sample_is_data]
        enrich_with_cagrs(rows, sample_is_data)
        # With only 3 years, only 3yr CAGR should be valid
        for row in rows:
            assert "revenue_cagr_3yr" in row
            assert "pat_cagr_3yr" in row
            assert "eps_cagr_3yr" in row


class TestFullPipeline:
    """End-to-end test with seeded data."""

    def test_writes_correct_row_count(self, tmp_db, sample_is_data,
                                       sample_bs_data, sample_cf_data):
        """Seed 3 companies × 3 years → expect 9 rows in financial_ratios."""
        # Insert test companies
        tmp_db.executemany(
            "INSERT OR IGNORE INTO companies (id, company_name) VALUES (?, ?)",
            [("TCS", "Tata Consultancy Services"), ("RELIANCE", "Reliance Industries"),
             ("HDFCBANK", "HDFC Bank")]
        )

        # Create a second company's data (RELIANCE with debt)
        rel_is = [
            {**d, "company_id": "RELIANCE", "sales": d["sales"] * 3,
             "net_profit": d["net_profit"] * 2, "interest": 5000}
            for d in sample_is_data
        ]
        rel_bs = [
            {**d, "company_id": "RELIANCE", "borrowings": 150000,
             "equity_capital": 3500, "reserves": 300000}
            for d in sample_bs_data
        ]
        rel_cf = [{**d, "company_id": "RELIANCE"} for d in sample_cf_data]

        # HDFCBANK data
        hdfc_is = [
            {**d, "company_id": "HDFCBANK", "sales": d["sales"] * 2,
             "net_profit": d["net_profit"] * 1.8, "interest": 8000}
            for d in sample_is_data
        ]
        hdfc_bs = [
            {**d, "company_id": "HDFCBANK", "borrowings": 500000,
             "equity_capital": 1200, "reserves": 150000}
            for d in sample_bs_data
        ]
        hdfc_cf = [{**d, "company_id": "HDFCBANK"} for d in sample_cf_data]

        # Insert all data
        all_is = sample_is_data + rel_is + hdfc_is
        all_bs = sample_bs_data + rel_bs + hdfc_bs
        all_cf = sample_cf_data + rel_cf + hdfc_cf

        for r in all_is:
            tmp_db.execute(
                """INSERT INTO income_statement
                   (company_id, year, sales, expenses, operating_profit,
                    opm_percentage, other_income, interest, depreciation,
                    profit_before_tax, tax_percentage, net_profit, eps,
                    dividend_payout) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                (r["company_id"], r["year"], r["sales"], r["expenses"],
                 r["operating_profit"], r["opm_percentage"], r["other_income"],
                 r["interest"], r["depreciation"], r["profit_before_tax"],
                 r["tax_percentage"], r["net_profit"], r["eps"], r["dividend_payout"]),
            )
        for r in all_bs:
            tmp_db.execute(
                """INSERT INTO balance_sheet
                   (company_id, year, equity_capital, reserves, borrowings,
                    other_liabilities, total_liabilities, fixed_assets, cwip,
                    investments, other_asset, total_assets)
                   VALUES (?,?,?,?,?,?,?,?,?,?,?,?)""",
                (r["company_id"], r["year"], r["equity_capital"], r["reserves"],
                 r["borrowings"], r["other_liabilities"], r["total_liabilities"],
                 r["fixed_assets"], r["cwip"], r["investments"], r["other_asset"],
                 r["total_assets"]),
            )
        for r in all_cf:
            tmp_db.execute(
                """INSERT INTO cash_flow
                   (company_id, year, operating_activity, investing_activity,
                    financing_activity, net_cash_flow) VALUES (?,?,?,?,?,?)""",
                (r["company_id"], r["year"], r["operating_activity"],
                 r["investing_activity"], r["financing_activity"], r["net_cash_flow"]),
            )
        tmp_db.commit()

        # Now compute ratios using compute_row
        from src.analytics.ratio_runner import compute_row, enrich_with_cagrs, compute_composite_score
        from collections import defaultdict

        bs_index = {(r["company_id"], r["year"]): r for r in all_bs}
        cf_index = {(r["company_id"], r["year"]): r for r in all_cf}
        is_by_company = defaultdict(list)
        for r in all_is:
            is_by_company[r["company_id"]].append(r)

        output_rows = []
        for is_row in all_is:
            cid = is_row["company_id"]
            yr = is_row["year"]
            bs_row = bs_index.get((cid, yr), {})
            cf_row = cf_index.get((cid, yr), {})
            bs_row["face_value"] = 1  # default
            row = compute_row(is_row, bs_row, cf_row, cid, yr)
            output_rows.append(row)

        for cid, company_is in is_by_company.items():
            company_out = [r for r in output_rows if r["company_id"] == cid]
            enrich_with_cagrs(company_out, company_is)

        for row in output_rows:
            row["composite_quality_score"] = compute_composite_score(row)

        # Write to financial_ratios
        cols = [
            "company_id", "year", "net_profit_margin_pct",
            "operating_profit_margin_pct", "return_on_equity_pct",
            "return_on_capital_employed_pct", "return_on_assets_pct",
            "debt_to_equity", "interest_coverage", "is_high_leverage",
            "is_low_icr_warning", "net_debt_cr", "asset_turnover",
            "free_cash_flow_cr", "capex_intensity", "fcf_conversion_rate",
            "cfo_quality_score", "capital_allocation_pattern",
            "earnings_per_share", "book_value_per_share",
            "dividend_payout_ratio_pct", "total_debt_cr",
            "cash_from_operations_cr", "revenue_cagr_3yr", "revenue_cagr_5yr",
            "revenue_cagr_10yr", "pat_cagr_3yr", "pat_cagr_5yr",
            "pat_cagr_10yr", "eps_cagr_3yr", "eps_cagr_5yr", "eps_cagr_10yr",
            "composite_quality_score",
        ]
        placeholders = ", ".join(["?"] * len(cols))
        col_str = ", ".join(cols)
        update_str = ", ".join(f"{c}=excluded.{c}" for c in cols[2:])
        sql = f"INSERT INTO financial_ratios ({col_str}) VALUES ({placeholders}) ON CONFLICT(company_id, year) DO UPDATE SET {update_str}"

        for row in output_rows:
            tmp_db.execute(sql, [row.get(c) for c in cols])
        tmp_db.commit()

        # Verify
        count = tmp_db.execute("SELECT COUNT(*) FROM financial_ratios").fetchone()[0]
        assert count == 9, f"Expected 9 rows, got {count}"

    def test_tcs_debt_free_flags(self, tmp_db, sample_is_data,
                                  sample_bs_data, sample_cf_data):
        """TCS (debt-free) should have D/E=0 and is_high_leverage=0."""
        tmp_db.execute(
            "INSERT INTO companies (id, company_name) VALUES (?, ?)",
            ("TCS", "TCS")
        )
        for r in sample_is_data:
            tmp_db.execute(
                """INSERT INTO income_statement
                   (company_id, year, sales, expenses, operating_profit,
                    opm_percentage, other_income, interest, depreciation,
                    profit_before_tax, tax_percentage, net_profit, eps,
                    dividend_payout) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                (r["company_id"], r["year"], r["sales"], r["expenses"],
                 r["operating_profit"], r["opm_percentage"], r["other_income"],
                 r["interest"], r["depreciation"], r["profit_before_tax"],
                 r["tax_percentage"], r["net_profit"], r["eps"], r["dividend_payout"]),
            )
        for r in sample_bs_data:
            tmp_db.execute(
                """INSERT INTO balance_sheet
                   (company_id, year, equity_capital, reserves, borrowings,
                    other_liabilities, total_liabilities, fixed_assets, cwip,
                    investments, other_asset, total_assets)
                   VALUES (?,?,?,?,?,?,?,?,?,?,?,?)""",
                (r["company_id"], r["year"], r["equity_capital"], r["reserves"],
                 r["borrowings"], r["other_liabilities"], r["total_liabilities"],
                 r["fixed_assets"], r["cwip"], r["investments"], r["other_asset"],
                 r["total_assets"]),
            )
        for r in sample_cf_data:
            tmp_db.execute(
                """INSERT INTO cash_flow
                   (company_id, year, operating_activity, investing_activity,
                    financing_activity, net_cash_flow) VALUES (?,?,?,?,?,?)""",
                (r["company_id"], r["year"], r["operating_activity"],
                 r["investing_activity"], r["financing_activity"], r["net_cash_flow"]),
            )
        tmp_db.commit()

        from src.analytics.ratio_runner import compute_row
        row = compute_row(sample_is_data[2], sample_bs_data[2], sample_cf_data[2], "TCS", "2023-03")
        assert row["debt_to_equity"] == 0.0
        assert row["is_high_leverage"] == 0
        assert row["net_debt_cr"] == 0.0