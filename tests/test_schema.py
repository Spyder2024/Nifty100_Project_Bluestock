"""
Tests for SQLite schema — tables, PKs, FKs, virtual column.
Sprint 1, Day 4
"""

import sqlite3
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parent.parent
SCHEMA_PATH = PROJECT_ROOT / "db" / "schema.sql"

# ------------------------------------------------------------------
# Expected catalogue
# ------------------------------------------------------------------

EXPECTED_TABLES = [
    "sectors",
    "companies",
    "balance_sheet",
    "income_statement",
    "cash_flow",
    "ratios",
    "prices",
    "market_cap",
    "shareholding",
    "dividends",
]

EXPECTED_COLUMNS = {
    "sectors": [
        "sector_id", "sector_name",
    ],
    "companies": [
        "company_id", "company_name", "sector_id", "nse_symbol",
        "bse_code", "isin", "series", "listed_date", "face_value",
    ],
    "balance_sheet": [
        "company_id", "year", "total_assets", "total_liabilities",
        "total_equity", "current_assets", "current_liabilities",
        "non_current_assets", "non_current_liab", "inventories",
        "cash_and_equiv", "borrowings", "other_current_liab",
        "trade_payables", "trade_receivables", "fixed_assets",
        "investments", "reserves", "share_capital", "bs_balance",
    ],
    "income_statement": [
        "company_id", "year", "revenue", "operating_income",
        "other_income", "total_expenses", "interest_expense",
        "depreciation", "tax_expense", "net_income", "eps",
        "opm", "npm", "ebitda", "ebit",
    ],
    "cash_flow": [
        "company_id", "year", "operating_cf", "investing_cf",
        "financing_cf", "net_cash_flow", "capex", "fcf",
        "dividend_paid", "buyback_paid", "opening_cash", "closing_cash",
    ],
    "ratios": [
        "company_id", "year", "roe", "roa", "roce",
        "debt_to_equity", "current_ratio", "quick_ratio",
        "interest_coverage", "asset_turnover", "net_profit_margin",
        "opm", "dividend_payout", "earning_yield",
        "book_value_per_share", "price_to_book", "price_to_earnings",
    ],
    "prices": [
        "company_id", "year", "price_open", "price_high",
        "price_low", "price_close", "volume",
    ],
    "market_cap": [
        "company_id", "year", "market_cap", "market_cap_cr",
        "free_float_mcap", "weight_pct",
    ],
    "shareholding": [
        "company_id", "year", "promoter_pct", "fii_pct",
        "dii_pct", "public_pct", "govt_pct", "custodian_pct",
    ],
    "dividends": [
        "company_id", "year", "dividend_per_share",
        "dividend_yield_pct", "dividend_payout_pct",
        "total_dividend", "ex_date", "record_date",
    ],
}


# ------------------------------------------------------------------
# Fixture
# ------------------------------------------------------------------

@pytest.fixture()
def db_conn():
    """In-memory SQLite DB with full schema applied."""
    conn = sqlite3.connect(":memory:")
    conn.execute("PRAGMA foreign_keys = ON")
    sql = SCHEMA_PATH.read_text(encoding="utf-8")
    conn.executescript(sql)
    yield conn
    conn.close()


# ==================================================================
# Class 1: Schema Creation
# ==================================================================

class TestSchemaCreation:
    """Verify all 10 tables are created with correct columns."""

    def test_all_tables_exist(self, db_conn):
        rows = db_conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name"
        ).fetchall()
        names = {r[0] for r in rows}
        for t in EXPECTED_TABLES:
            assert t in names, f"Missing table: {t}"

    def test_exactly_ten_tables(self, db_conn):
        n = db_conn.execute(
            "SELECT COUNT(*) FROM sqlite_master WHERE type='table'"
        ).fetchone()[0]
        assert n == 10

    @pytest.mark.parametrize("table", EXPECTED_TABLES)
    def test_table_has_expected_columns(self, db_conn, table):
        info = db_conn.execute(f"PRAGMA table_xinfo({table})").fetchall()
        actual = {c[1] for c in info}
        expected = set(EXPECTED_COLUMNS[table])
        missing = expected - actual
        assert not missing, f"{table} missing columns: {missing}"

    def test_no_extra_tables(self, db_conn):
        """Schema should not create internal SQLite tables as user tables."""
        rows = db_conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table'"
        ).fetchall()
        for r in rows:
            assert r[0] in EXPECTED_TABLES, f"Unexpected table: {r[0]}"


# ==================================================================
# Class 2: Primary-Key Constraints
# ==================================================================

class TestPrimaryKeys:
    """Verify PK definitions and uniqueness enforcement."""

    def test_companies_pk_is_company_id(self, db_conn):
        info = db_conn.execute("PRAGMA table_info(companies)").fetchall()
        pk_cols = [c[1] for c in info if c[5] == 1]
        assert pk_cols == ["company_id"]

    @pytest.mark.parametrize("table", EXPECTED_TABLES[2:])
    def test_financial_tables_composite_pk(self, db_conn, table):
        info = db_conn.execute(f"PRAGMA table_info({table})").fetchall()
        pk_cols = sorted([c[1] for c in info if c[5] > 0])
        assert pk_cols == ["company_id", "year"], (
            f"{table} PK cols = {pk_cols}"
        )

    def test_duplicate_company_rejected(self, db_conn):
        db_conn.execute(
            "INSERT INTO companies (company_id, company_name) VALUES ('TEST','Test Co')"
        )
        with pytest.raises(sqlite3.IntegrityError):
            db_conn.execute(
                "INSERT INTO companies (company_id, company_name) VALUES ('TEST','Dup')"
            )

    def test_duplicate_composite_key_rejected(self, db_conn):
        db_conn.execute(
            "INSERT INTO companies (company_id, company_name) VALUES ('X','X Co')"
        )
        db_conn.execute(
            "INSERT INTO income_statement (company_id, year, revenue) "
            "VALUES ('X','2023-03',1000)"
        )
        with pytest.raises(sqlite3.IntegrityError):
            db_conn.execute(
                "INSERT INTO income_statement (company_id, year, revenue) "
                "VALUES ('X','2023-03',2000)"
            )

    def test_different_years_allowed(self, db_conn):
        db_conn.execute(
            "INSERT INTO companies (company_id, company_name) VALUES ('Y','Y Co')"
        )
        db_conn.execute(
            "INSERT INTO ratios (company_id, year, roe) VALUES ('Y','2022-03',15.0)"
        )
        db_conn.execute(
            "INSERT INTO ratios (company_id, year, roe) VALUES ('Y','2023-03',18.0)"
        )
        cnt = db_conn.execute(
            "SELECT COUNT(*) FROM ratios WHERE company_id='Y'"
        ).fetchone()[0]
        assert cnt == 2


# ==================================================================
# Class 3: Foreign-Key Constraints
# ==================================================================

class TestForeignKeys:
    """Verify FK enforcement between tables."""

    def test_company_valid_sector_fk(self, db_conn):
        db_conn.execute(
            "INSERT INTO sectors (sector_id, sector_name) VALUES ('IT','Info Tech')"
        )
        db_conn.execute(
            "INSERT INTO companies (company_id, company_name, sector_id) "
            "VALUES ('TCS','TCS Ltd','IT')"
        )
        row = db_conn.execute(
            "SELECT sector_id FROM companies WHERE company_id='TCS'"
        ).fetchone()
        assert row[0] == "IT"

    def test_company_invalid_sector_fk_rejected(self, db_conn):
        with pytest.raises(sqlite3.IntegrityError):
            db_conn.execute(
                "INSERT INTO companies (company_id, company_name, sector_id) "
                "VALUES ('X','X Co','FAKE_SECTOR')"
            )

    def test_null_sector_allowed(self, db_conn):
        db_conn.execute(
            "INSERT INTO companies (company_id, company_name, sector_id) "
            "VALUES ('Z','Z Co',NULL)"
        )
        row = db_conn.execute(
            "SELECT sector_id FROM companies WHERE company_id='Z'"
        ).fetchone()
        assert row[0] is None

    def test_financial_table_valid_company_fk(self, db_conn):
        db_conn.execute(
            "INSERT INTO companies (company_id, company_name) VALUES ('A','A Co')"
        )
        db_conn.execute(
            "INSERT INTO balance_sheet (company_id, year, total_assets) "
            "VALUES ('A','2023-03',5000)"
        )
        cnt = db_conn.execute(
            "SELECT COUNT(*) FROM balance_sheet"
        ).fetchone()[0]
        assert cnt == 1

    def test_financial_table_invalid_company_fk_rejected(self, db_conn):
        with pytest.raises(sqlite3.IntegrityError):
            db_conn.execute(
                "INSERT INTO cash_flow (company_id, year, operating_cf) "
                "VALUES ('GHOST','2023-03',100)"
            )

    def test_cascade_delete_not_configured(self, db_conn):
        """Deleting a company should NOT cascade (default RESTRICT)."""
        db_conn.execute(
            "INSERT INTO companies (company_id, company_name) VALUES ('D','D Co')"
        )
        db_conn.execute(
            "INSERT INTO prices (company_id, year, price_close) "
            "VALUES ('D','2023-03',2500)"
        )
        with pytest.raises(sqlite3.IntegrityError):
            db_conn.execute("DELETE FROM companies WHERE company_id='D'")


# ==================================================================
# Class 4: Virtual / Generated Columns
# ==================================================================

class TestVirtualColumns:
    """Verify the bs_balance GENERATED ALWAYS AS virtual column."""

    def _insert_company(self, conn, cid="V"):
        conn.execute(
            f"INSERT INTO companies (company_id, company_name) VALUES ('{cid}','{cid} Co')"
        )

    def test_bs_balance_zero_when_balanced(self, db_conn):
        self._insert_company(db_conn)
        db_conn.execute(
            """INSERT INTO balance_sheet
               (company_id, year, total_assets, total_liabilities, total_equity)
               VALUES ('V','2023-03', 10000, 6000, 4000)"""
        )
        bal = db_conn.execute(
            "SELECT bs_balance FROM balance_sheet WHERE company_id='V'"
        ).fetchone()[0]
        assert bal == 0.0

    def test_bs_balance_detects_imbalance(self, db_conn):
        self._insert_company(db_conn)
        db_conn.execute(
            """INSERT INTO balance_sheet
               (company_id, year, total_assets, total_liabilities, total_equity)
               VALUES ('V','2023-03', 10000, 6000, 3500)"""
        )
        bal = db_conn.execute(
            "SELECT bs_balance FROM balance_sheet WHERE company_id='V'"
        ).fetchone()[0]
        assert bal == 500.0

    def test_bs_balance_handles_nulls_as_zero(self, db_conn):
        self._insert_company(db_conn)
        db_conn.execute(
            """INSERT INTO balance_sheet
               (company_id, year, total_assets)
               VALUES ('V','2022-03', 5000)"""
        )
        bal = db_conn.execute(
            "SELECT bs_balance FROM balance_sheet "
            "WHERE company_id='V' AND year='2022-03'"
        ).fetchone()[0]
        # 5000 - 0 - 0 = 5000
        assert bal == 5000.0

    def test_bs_balance_not_insertable(self, db_conn):
        """Virtual column should reject explicit INSERT values."""
        self._insert_company(db_conn)
        with pytest.raises(sqlite3.OperationalError):
            db_conn.execute(
                """INSERT INTO balance_sheet
                   (company_id, year, bs_balance)
                   VALUES ('V','2023-03', 0)"""
            )


# ==================================================================
# Class 5: PRAGMA & Defaults
# ==================================================================

class TestPragmaAndDefaults:
    """Verify database settings and column defaults."""

    def test_foreign_keys_pragma_on(self, db_conn):
        assert db_conn.execute("PRAGMA foreign_keys").fetchone()[0] == 1

    def test_companies_default_series(self, db_conn):
        db_conn.execute(
            "INSERT INTO companies (company_id, company_name) "
            "VALUES ('DEF','Default Co')"
        )
        row = db_conn.execute(
            "SELECT series FROM companies WHERE company_id='DEF'"
        ).fetchone()
        assert row[0] == "EQ"

    def test_companies_default_face_value(self, db_conn):
        db_conn.execute(
            "INSERT INTO companies (company_id, company_name) "
            "VALUES ('DEF2','Default Co 2')"
        )
        row = db_conn.execute(
            "SELECT face_value FROM companies WHERE company_id='DEF2'"
        ).fetchone()
        assert row[0] == 1.0

    def test_shareholding_defaults_zero(self, db_conn):
        db_conn.execute(
            "INSERT INTO companies (company_id, company_name) VALUES ('SH','SH Co')"
        )
        db_conn.execute(
            "INSERT INTO shareholding (company_id, year, promoter_pct) "
            "VALUES ('SH','2023-03', 55.0)"
        )
        row = db_conn.execute(
            "SELECT govt_pct, custodian_pct FROM shareholding "
            "WHERE company_id='SH'"
        ).fetchone()
        assert row[0] == 0
        assert row[1] == 0

    def test_sector_name_unique(self, db_conn):
        db_conn.execute(
            "INSERT INTO sectors (sector_id, sector_name) VALUES ('BANK','Banking')"
        )
        with pytest.raises(sqlite3.IntegrityError):
            db_conn.execute(
                "INSERT INTO sectors (sector_id, sector_name) VALUES ('BANK2','Banking')"
            )