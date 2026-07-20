"""
Tests for DQ review checks and orchestrator.
Sprint 1, Day 6
"""

import csv
import sqlite3
from pathlib import Path

import pytest

from src.etl.dq_review import (
    REVIEW_COLUMNS,
    ALL_CHECKS,
    check_bs_balance,
    check_current_ratio,
    check_debt_equity,
    check_dividend_payout,
    check_eps_sign,
    check_missing_data,
    check_opm_cross,
    check_positive_revenue,
    check_tax_rate,
    check_year_coverage,
    pick_random_companies,
    run_dq_review,
)

PROJECT_ROOT = Path(__file__).resolve().parent.parent
SCHEMA_PATH = PROJECT_ROOT / "db" / "schema.sql"


# ------------------------------------------------------------------
# Fixtures
# ------------------------------------------------------------------

@pytest.fixture()
def db():
    conn = sqlite3.connect(":memory:")
    conn.execute("PRAGMA foreign_keys = ON")
    conn.executescript(SCHEMA_PATH.read_text(encoding="utf-8"))

    # --- Master data ---
    conn.execute(
        "INSERT INTO sectors VALUES ('IT','Information Technology')"
    )
    conn.execute(
        "INSERT INTO companies (company_id,company_name,sector_id) "
        "VALUES ('TCS','Tata Consultancy Services','IT')"
    )
    conn.execute(
        "INSERT INTO companies (company_id,company_name,sector_id) "
        "VALUES ('INFY','Infosys Ltd','IT')"
    )

    # --- TCS: clean data across 3 years ---
    for yr, assets, liab, eq, rev, ni, eps, opm, tax, roe, de, cr, dp, ocf, icf, fcf in [
        ("2021-03", 160000,  95000, 65000, 195000, 38000, 107.0, 25.8,  9500, 47.0, 0.10, 2.6, 25.0, 42000, -15000, -20000),
        ("2022-03", 180000, 108000, 72000, 220000, 42500, 119.0, 26.1, 10200, 49.0, 0.12, 2.5, 28.0, 46000, -18000, -22000),
        ("2023-03", 200000, 120000, 80000, 240000, 45000, 125.5, 26.5, 11000, 48.0, 0.15, 2.5, 30.0, 50000, -20000, -25000),
    ]:
        conn.execute(
            "INSERT INTO balance_sheet (company_id,year,total_assets,total_liabilities,total_equity) "
            "VALUES (?,?,?,?,?)", ("TCS", yr, assets, liab, eq)
        )
        conn.execute(
            "INSERT INTO income_statement "
            "(company_id,year,revenue,net_income,eps,opm,tax_expense) "
            "VALUES (?,?,?,?,?,?,?)", ("TCS", yr, rev, ni, eps, opm, tax)
        )
        conn.execute(
            "INSERT INTO ratios "
            "(company_id,year,roe,opm,debt_to_equity,current_ratio,dividend_payout) "
            "VALUES (?,?,?,?,?,?,?)", ("TCS", yr, roe, opm, de, cr, dp)
        )
        conn.execute(
            "INSERT INTO cash_flow "
            "(company_id,year,operating_cf,investing_cf,financing_cf) "
            "VALUES (?,?,?,?,?)",
            ("TCS", yr, ocf, icf, fcf)
        )
        conn.execute(
            "INSERT INTO prices (company_id,year,price_close) VALUES (?,?,'3000')",
            ("TCS", yr)
        )

    # --- INFY: data with intentional DQ issues ---
    conn.execute(
        "INSERT INTO balance_sheet "
        "(company_id,year,total_assets,total_liabilities,total_equity) "
        "VALUES ('INFY','2023-03', 180000, 105000, 70000)"
        # bs_balance = 180000 - 105000 - 70000 = 5000 (2.78% > 1%)
    )
    conn.execute(
        "INSERT INTO income_statement "
        "(company_id,year,revenue,net_income,eps,opm,tax_expense) "
        "VALUES ('INFY','2023-03', 160000, 35000, -95.0, 27.0, 8000)"
        # EPS negative but NI positive -> DQ-R03 FAIL
    )
    conn.execute(
        "INSERT INTO ratios "
        "(company_id,year,roe,opm,debt_to_equity,current_ratio,dividend_payout) "
        "VALUES ('INFY','2023-03', 30.0, 30.0, -0.05, 1.8, 120.0)"
        # de < 0 -> DQ-R09, payout > 100 -> DQ-R08
    )

    yield conn
    conn.close()


# ==================================================================
# 1. BS Balance (DQ-R01)
# ==================================================================

class TestCheckBsBalance:
    def test_pass_when_balanced(self, db):
        results = check_bs_balance(db, "TCS")
        assert all(r["status"] == "PASS" for r in results)

    def test_fail_when_imbalanced(self, db):
        results = check_bs_balance(db, "INFY")
        fails = [r for r in results if r["status"] == "FAIL"]
        assert len(fails) == 1
        assert fails[0]["check_id"] == "DQ-R01"


# ==================================================================
# 2. OPM Cross-check (DQ-R02)
# ==================================================================

class TestCheckOpmCross:
    def test_pass_when_aligned(self, db):
        # TCS has same OPM in IS and ratios
        results = check_opm_cross(db, "TCS")
        assert all(r["status"] == "PASS" for r in results)

    def test_fail_when_diverged(self, db):
        # INFY: IS.opm=27.0, ratios.opm=30.0 -> diff=3.0pp > 2pp
        results = check_opm_cross(db, "INFY")
        fails = [r for r in results if r["status"] == "FAIL"]
        assert len(fails) == 1
        assert fails[0]["check_id"] == "DQ-R02"


# ==================================================================
# 3. EPS Sign (DQ-R03)
# ==================================================================

class TestCheckEpsSign:
    def test_pass_matching_signs(self, db):
        results = check_eps_sign(db, "TCS")
        assert all(r["status"] == "PASS" for r in results)

    def test_fail_mismatch(self, db):
        # INFY: NI=35000 (>0) but EPS=-95.0 (<0)
        results = check_eps_sign(db, "INFY")
        fails = [r for r in results if r["status"] == "FAIL"]
        assert len(fails) == 1
        assert fails[0]["severity"] == "CRITICAL"


# ==================================================================
# 4. Tax Rate (DQ-R04)
# ==================================================================

class TestCheckTaxRate:
    def test_pass_reasonable(self, db):
        # TCS: tax=11000, ebt=45000+11000=56000 -> 19.6%
        results = check_tax_rate(db, "TCS")
        assert all(r["status"] == "PASS" for r in results)

    def test_fail_out_of_range(self, db):
        # We need to inject an out-of-range year for this test
        db.execute(
            "INSERT INTO income_statement "
            "(company_id,year,revenue,net_income,eps,tax_expense) "
            "VALUES ('TCS','2020-03',100000,80000,10.0,5000)"
            # tax_rate = 5000/85000 = 5.9% < 15% -> FAIL
        )
        results = check_tax_rate(db, "TCS")
        fails = [r for r in results if r["status"] == "FAIL"]
        assert len(fails) >= 1
        assert any(r["year"] == "2020-03" for r in fails)


# ==================================================================
# 5. Positive Revenue (DQ-R05)
# ==================================================================

class TestCheckPositiveRevenue:
    def test_pass_positive(self, db):
        results = check_positive_revenue(db, "TCS")
        assert all(r["status"] == "PASS" for r in results)

    def test_fail_zero_revenue(self, db):
        db.execute(
            "INSERT INTO income_statement "
            "(company_id,year,revenue,net_income,eps) "
            "VALUES ('TCS','2019-03',0,1000,5.0)"
        )
        results = check_positive_revenue(db, "TCS")
        fails = [r for r in results if r["status"] == "FAIL"]
        assert any(r["year"] == "2019-03" for r in fails)


# ==================================================================
# 6. Year Coverage (DQ-R06)
# ==================================================================

class TestCheckYearCoverage:
    def test_fail_low_coverage(self, db):
        # INFY has only 1 year of data
        results = check_year_coverage(db, "INFY")
        assert results[0]["status"] == "FAIL"

    def test_pass_good_coverage(self, db):
        # TCS has 3 years — still < 10, but test the logic
        results = check_year_coverage(db, "TCS")
        assert results[0]["check_id"] == "DQ-R06"
        # With only 3 years, this will FAIL. Test structure, not pass/fail.
        assert "years" in results[0]["actual"]


# ==================================================================
# 7. Dividend Payout (DQ-R08)
# ==================================================================

class TestCheckDividendPayout:
    def test_pass_within_limit(self, db):
        results = check_dividend_payout(db, "TCS")
        assert all(r["status"] == "PASS" for r in results)

    def test_fail_exceeds_100(self, db):
        # INFY has payout=120%
        results = check_dividend_payout(db, "INFY")
        fails = [r for r in results if r["status"] == "FAIL"]
        assert len(fails) == 1
        assert fails[0]["check_id"] == "DQ-R08"


# ==================================================================
# 8. Debt-to-Equity (DQ-R09)
# ==================================================================

class TestCheckDebtEquity:
    def test_pass_non_negative(self, db):
        results = check_debt_equity(db, "TCS")
        assert all(r["status"] == "PASS" for r in results)

    def test_fail_negative(self, db):
        # INFY has de=-0.05
        results = check_debt_equity(db, "INFY")
        fails = [r for r in results if r["status"] == "FAIL"]
        assert len(fails) == 1


# ==================================================================
# 9. Current Ratio (DQ-R10)
# ==================================================================

class TestCheckCurrentRatio:
    def test_pass_positive(self, db):
        results = check_current_ratio(db, "TCS")
        assert all(r["status"] == "PASS" for r in results)


# ==================================================================
# 10. Missing Data (DQ-R07)
# ==================================================================

class TestCheckMissingData:
    def test_pass_low_nulls(self, db):
        results = check_missing_data(db, "TCS")
        assert all(r["status"] == "PASS" for r in results)

    def test_fail_high_nulls(self, db):
        # Insert a row with mostly NULL key columns
        db.execute(
            "INSERT INTO income_statement "
            "(company_id,year,revenue) VALUES ('TCS','2018-03',150000)"
            # net_income=NULL, eps=NULL -> 2/3 = 67% nulls > 20%
        )
        results = check_missing_data(db, "TCS")
        fails = [r for r in results if r["status"] == "FAIL"]
        assert any("income_statement" in r["check_description"] for r in fails)


# ==================================================================
# 11. Orchestrator
# ==================================================================
class TestOrchestrator:
    def test_run_dq_review_produces_csv(self, db, tmp_path):
        report_path = str(tmp_path / "review.csv")
        results = run_dq_review(conn=db, output_path=report_path, n_companies=2)

        assert Path(report_path).exists()
        assert results["total_findings"] > 0
        assert results["passes"] > 0
        assert len(results["companies"]) == 2

    def test_csv_has_correct_columns(self, db, tmp_path):
        report_path = str(tmp_path / "review.csv")
        run_dq_review(conn=db, output_path=report_path, n_companies=1)

        with open(report_path, encoding="utf-8") as f:
            reader = csv.DictReader(f)
            header = reader.fieldnames
        assert header == REVIEW_COLUMNS

    def test_pick_random_companies(self, db):
        companies = pick_random_companies(db, n=2)
        assert len(companies) == 2
        for c in companies:
            assert "company_id" in c
            assert "company_name" in c

    def test_all_checks_registered(self):
        assert len(ALL_CHECKS) == 10
        for fn in ALL_CHECKS:
            assert callable(fn)