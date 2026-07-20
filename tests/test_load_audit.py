"""
Tests for load audit CSV generation, FK integrity check, row counts.
Sprint 1, Day 5
"""

import csv
import sqlite3
from pathlib import Path

import pytest

from src.etl.load_audit import (
    AUDIT_COLUMNS,
    _audit_status,
    _write_audit_csv,
    check_fk_integrity,
    get_table_row_counts,
)

PROJECT_ROOT = Path(__file__).resolve().parent.parent
SCHEMA_PATH = PROJECT_ROOT / "db" / "schema.sql"


@pytest.fixture()
def db_conn():
    conn = sqlite3.connect(":memory:")
    conn.execute("PRAGMA foreign_keys = ON")
    conn.executescript(SCHEMA_PATH.read_text(encoding="utf-8"))
    yield conn
    conn.close()


@pytest.fixture()
def populated_db(db_conn):
    """DB with sample data covering multiple tables."""
    db_conn.execute(
        "INSERT INTO sectors (sector_id, sector_name) "
        "VALUES ('IT','Information Technology')"
    )
    db_conn.execute(
        "INSERT INTO companies (company_id, company_name, sector_id) "
        "VALUES ('TCS','Tata Consultancy Services','IT')"
    )
    db_conn.execute(
        "INSERT INTO companies (company_id, company_name, sector_id) "
        "VALUES ('INFY','Infosys Ltd','IT')"
    )
    db_conn.execute(
        "INSERT INTO balance_sheet (company_id, year, total_assets) "
        "VALUES ('TCS','2023-03', 200000)"
    )
    db_conn.execute(
        "INSERT INTO income_statement (company_id, year, revenue) "
        "VALUES ('TCS','2023-03', 240000)"
    )
    db_conn.execute(
        "INSERT INTO ratios (company_id, year, roe) "
        "VALUES ('INFY','2023-03', 32.5)"
    )
    db_conn.execute(
        "INSERT INTO ratios (company_id, year, roe) "
        "VALUES ('INFY','2022-03', 30.1)"
    )
    return db_conn


# ==================================================================
# 1. Audit status helper
# ==================================================================

class TestAuditStatus:
    """Test the _audit_status logic."""

    def test_success_when_all_loaded(self):
        assert _audit_status(100, 100, "") == "SUCCESS"

    def test_partial_when_some_skipped(self):
        assert _audit_status(80, 100, "") == "PARTIAL"

    def test_failed_when_zero_loaded(self):
        assert _audit_status(0, 100, "") == "FAILED"

    def test_failed_on_any_error(self):
        assert _audit_status(50, 50, "File not found") == "FAILED"

    def test_success_with_single_row(self):
        assert _audit_status(1, 1, "") == "SUCCESS"


# ==================================================================
# 2. Audit CSV output
# ==================================================================

class TestAuditCsv:
    """Test _write_audit_csv file output."""

    def test_writes_all_columns(self, tmp_path):
        records = [{
            "table_name": "companies",
            "source_file": "companies.xlsx",
            "source_type": "core",
            "rows_loaded": 92,
            "rows_skipped": 0,
            "total_rows_in_source": 92,
            "load_status": "SUCCESS",
            "error_message": "",
            "load_timestamp": "2026-07-20 10:00:00 UTC",
        }]
        out = str(tmp_path / "audit.csv")
        _write_audit_csv(records, out)

        with open(out, encoding="utf-8") as f:
            reader = csv.DictReader(f)
            rows = list(reader)

        assert len(rows) == 1
        assert rows[0]["table_name"] == "companies"
        assert rows[0]["load_status"] == "SUCCESS"
        assert rows[0]["rows_loaded"] == "92"

    def test_header_matches_audit_columns(self, tmp_path):
        out = str(tmp_path / "audit.csv")
        _write_audit_csv([], out)
        with open(out, encoding="utf-8") as f:
            header = f.readline().strip()
        assert header == ",".join(AUDIT_COLUMNS)

    def test_empty_records_header_only(self, tmp_path):
        out = str(tmp_path / "audit.csv")
        _write_audit_csv([], out)
        with open(out, encoding="utf-8") as f:
            lines = f.readlines()
        assert len(lines) == 1  # header only, no data rows

    def test_multiple_records(self, tmp_path):
        records = [
            dict(
                table_name="sectors", source_file="sectors.xlsx",
                source_type="supporting", rows_loaded=10, rows_skipped=0,
                total_rows_in_source=10, load_status="SUCCESS",
                error_message="", load_timestamp="2026-07-20 10:00:00 UTC",
            ),
            dict(
                table_name="companies", source_file="companies.xlsx",
                source_type="core", rows_loaded=90, rows_skipped=2,
                total_rows_in_source=92, load_status="PARTIAL",
                error_message="", load_timestamp="2026-07-20 10:00:00 UTC",
            ),
        ]
        out = str(tmp_path / "audit.csv")
        _write_audit_csv(records, out)
        with open(out, encoding="utf-8") as f:
            rows = list(csv.DictReader(f))
        assert len(rows) == 2
        assert rows[1]["load_status"] == "PARTIAL"


# ==================================================================
# 3. FK integrity check
# ==================================================================

class TestFkIntegrity:
    """Test the check_fk_integrity function."""

    def test_clean_data_zero_orphans(self, populated_db):
        results = check_fk_integrity(populated_db)
        for r in results:
            assert r["orphan_count"] == 0, (
                f"{r['fk_table']}.{r['fk_column']} has {r['orphan_count']} orphans"
            )

    def test_nine_fk_checks_total(self, db_conn):
        """1 (companies→sectors) + 8 (financial→companies) = 9."""
        results = check_fk_integrity(db_conn)
        assert len(results) == 9

    def test_result_dict_keys(self, populated_db):
        results = check_fk_integrity(populated_db)
        expected_keys = {"fk_table", "fk_column", "ref_table", "ref_column", "orphan_count"}
        for r in results:
            assert expected_keys.issubset(r.keys())

    def test_companies_sector_fk_first(self, populated_db):
        results = check_fk_integrity(populated_db)
        first = results[0]
        assert first["fk_table"] == "companies"
        assert first["fk_column"] == "sector_id"
        assert first["ref_table"] == "sectors"


# ==================================================================
# 4. Table row counts
# ==================================================================

class TestTableRowCounts:
    """Test get_table_row_counts function."""

    def test_empty_db_all_zero(self, db_conn):
        counts = get_table_row_counts(db_conn)
        assert len(counts) == 10
        for table, cnt in counts.items():
            assert cnt == 0, f"{table} should be empty but has {cnt} rows"

    def test_populated_db_correct_counts(self, populated_db):
        counts = get_table_row_counts(populated_db)
        assert counts["sectors"] == 1
        assert counts["companies"] == 2
        assert counts["balance_sheet"] == 1
        assert counts["income_statement"] == 1
        assert counts["ratios"] == 2
        assert counts["prices"] == 0
        assert counts["cash_flow"] == 0
        assert counts["market_cap"] == 0
        assert counts["shareholding"] == 0
        assert counts["dividends"] == 0

    def test_covers_all_ten_tables(self, db_conn):
        counts = get_table_row_counts(db_conn)
        expected = {
            "sectors", "companies", "balance_sheet", "income_statement",
            "cash_flow", "ratios", "prices", "market_cap",
            "shareholding", "dividends",
        }
        assert set(counts.keys()) == expected