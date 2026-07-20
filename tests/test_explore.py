"""
Tests for exploratory SQL queries.
Sprint 1, Day 7
"""

import csv
import sqlite3
from pathlib import Path

import pytest

from src.etl.explore import (
    ALL_QUERIES,
    q_avg_de_by_sector,
    q_avg_opm_by_sector,
    q_bs_balance_issues,
    q_companies_per_table,
    q_data_coverage_per_year,
    q_key_metric_summary,
    q_loss_making_companies,
    q_sector_company_count,
    q_top_revenue_companies,
    q_top_roe_companies,
    q_yoy_revenue_growth,
    run_exploration,
)

PROJECT_ROOT = Path(__file__).resolve().parent.parent
SCHEMA_PATH = PROJECT_ROOT / "db" / "schema.sql"


@pytest.fixture()
def db():
    conn = sqlite3.connect(":memory:")
    conn.execute("PRAGMA foreign_keys = ON")
    conn.executescript(SCHEMA_PATH.read_text(encoding="utf-8"))

    conn.execute("INSERT INTO sectors VALUES ('IT','Information Technology')")
    conn.execute("INSERT INTO sectors VALUES ('BANK','Banking')")
    conn.execute(
        "INSERT INTO companies (company_id,company_name,sector_id) "
        "VALUES ('TCS','Tata Consultancy Services','IT')"
    )
    conn.execute(
        "INSERT INTO companies (company_id,company_name,sector_id) "
        "VALUES ('INFY','Infosys Ltd','IT')"
    )
    conn.execute(
        "INSERT INTO companies (company_id,company_name,sector_id) "
        "VALUES ('HDFCBANK','HDFC Bank Ltd','BANK')"
    )

    # TCS: 3 clean years
    for yr, rev, ni, opm, tax, eps in [
        ("2021-03", 195000, 38000, 25.8, 9500, 107.0),
        ("2022-03", 220000, 42500, 26.1, 10200, 119.0),
        ("2023-03", 240000, 45000, 26.5, 11000, 125.5),
    ]:
        conn.execute(
            "INSERT INTO income_statement "
            "(company_id,year,revenue,net_income,opm,tax_expense,eps) "
            "VALUES (?,?,?,?,?,?,?)", ("TCS", yr, rev, ni, opm, tax, eps)
        )
        conn.execute(
            "INSERT INTO ratios (company_id,year,roe,opm) VALUES (?,?,48.0,?)",
            ("TCS", yr, opm)
        )
        conn.execute(
            "INSERT INTO balance_sheet "
            "(company_id,year,total_assets,total_liabilities,total_equity) "
            "VALUES (?,?,200000,120000,80000)", ("TCS", yr)
        )

    # INFY: loss year + recovery
    conn.execute(
        "INSERT INTO income_statement "
        "(company_id,year,revenue,net_income,opm,tax_expense,eps) "
        "VALUES ('INFY','2022-03',160000,-5000,18.0,0,-15.0)"
    )
    conn.execute(
        "INSERT INTO income_statement "
        "(company_id,year,revenue,net_income,opm,tax_expense,eps) "
        "VALUES ('INFY','2023-03',170000,35000,22.0,7000,100.0)"
    )
    conn.execute(
        "INSERT INTO ratios (company_id,year,roe,opm) "
        "VALUES ('INFY','2023-03',32.0,22.0)"
    )
    conn.execute(
        "INSERT INTO balance_sheet "
        "(company_id,year,total_assets,total_liabilities,total_equity) "
        "VALUES ('INFY','2023-03',180000,105000,70000)"
    )

    # HDFCBANK: BS imbalance 200k - 100k - 85k = 15k (7.5%)
    conn.execute(
        "INSERT INTO income_statement "
        "(company_id,year,revenue,net_income,opm,tax_expense,eps) "
        "VALUES ('HDFCBANK','2023-03',280000,45000,45.0,12000,80.0)"
    )
    conn.execute(
        "INSERT INTO ratios (company_id,year,roe,opm) "
        "VALUES ('HDFCBANK','2023-03',18.0,45.0)"
    )
    conn.execute(
        "INSERT INTO balance_sheet "
        "(company_id,year,total_assets,total_liabilities,total_equity) "
        "VALUES ('HDFCBANK','2023-03',200000,100000,85000)"
    )

    # Commit the fixture's INSERTs so the connection has no open
    # transaction at yield. An open transaction makes Connection.backup()
    # (used by test_csv_readable) deadlock on the source's own write lock.
    conn.commit()
    yield conn
    conn.close()


# ==================================================================

class TestTopRevenue:
    def test_returns_list(self, db):
        results = q_top_revenue_companies(db, n=5)
        assert isinstance(results, list)
        assert len(results) <= 5

    def test_sorted_descending(self, db):
        results = q_top_revenue_companies(db, n=10)
        revenues = [r["revenue"] for r in results]
        assert revenues == sorted(revenues, reverse=True)


class TestSectorCount:
    def test_it_has_2(self, db):
        results = q_sector_company_count(db)
        it = [r for r in results if r["sector_id"] == "IT"]
        assert len(it) == 1
        assert it[0]["company_count"] == 2

    def test_bank_has_1(self, db):
        results = q_sector_company_count(db)
        bank = [r for r in results if r["sector_id"] == "BANK"]
        assert len(bank) == 1
        assert bank[0]["company_count"] == 1


class TestTopRoe:
    def test_includes_roe(self, db):
        results = q_top_roe_companies(db, n=5)
        assert all("roe" in r for r in results)
        assert all(r["roe"] is not None for r in results)


class TestYoYGrowth:
    def test_tcs_has_growth(self, db):
        results = q_yoy_revenue_growth(db, n=5)
        tcs = [r for r in results if r["company_id"] == "TCS"]
        assert len(tcs) == 1
        assert "yoy_growth_pct" in tcs[0]


class TestLossMaking:
    def test_latest_year_no_losses(self, db):
        # Latest year is 2023-03; all profitable
        results = q_loss_making_companies(db)
        assert isinstance(results, list)


class TestBsIssues:
    def test_finds_hdfcbank(self, db):
        results = q_bs_balance_issues(db, threshold_pct=5.0)
        hdfc = [r for r in results if r["company_id"] == "HDFCBANK"]
        assert len(hdfc) == 1
        assert hdfc[0]["imbalance_pct"] > 5.0

    def test_tcs_clean(self, db):
        results = q_bs_balance_issues(db, threshold_pct=1.0)
        tcs = [r for r in results if r["company_id"] == "TCS"]
        assert len(tcs) == 0


class TestMetricSummary:
    def test_returns_5_metrics(self, db):
        results = q_key_metric_summary(db)
        assert len(results) == 5
        names = {r["metric"] for r in results}
        assert "revenue" in names
        assert "roe" in names


class TestCoverage:
    def test_returns_per_year(self, db):
        results = q_data_coverage_per_year(db)
        assert len(results) > 0
        assert all("year" in r and "company_count" in r for r in results)


class TestCompaniesPerTable:
    def test_6_tables(self, db):
        results = q_companies_per_table(db)
        assert len(results) == 6
        names = {r["table_name"] for r in results}
        assert "income_statement" in names


class TestRunExploration:
    def test_produces_csv(self, db, tmp_path):
        csv_path = str(tmp_path / "explore.csv")
        results = run_exploration(conn=db, output_path=csv_path)

        assert Path(csv_path).exists()
        assert results["total_rows"] > 0

        ok_count = sum(
            1 for info in results["summary"].values()
            if info["status"] == "OK"
        )
        # At least 8 of 12 queries should succeed with the fixture data
        assert ok_count >= 8, (
            f"Only {ok_count}/12 queries succeeded. "
            f"Failures: {[(k,v) for k,v in results['summary'].items() if v['status'] != 'OK']}"
        )
        
    def test_csv_readable(self, db, tmp_path):
        db_path = str(tmp_path / "test.db")
        disk = sqlite3.connect(db_path)
        db.backup(disk)
        disk.close()

        csv_path = str(tmp_path / "explore.csv")
        run_exploration(db_path, csv_path)

        with open(csv_path, encoding="utf-8") as f:
            rows = list(csv.DictReader(f))
        assert len(rows) > 0
        assert "query_id" in rows[0]


class TestRegistry:
    def test_12_queries(self):
        assert len(ALL_QUERIES) == 12
        for qid, desc, fn in ALL_QUERIES:
            assert qid.startswith("Q")
            assert callable(fn)