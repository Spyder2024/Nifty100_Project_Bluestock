"""src/analytics/optimize_db.py — SQLite Database Performance & Indexing Optimizer (Day 43).

Sprint 7, Day 43

Creates optimal indexes on company_id, year, and composite fields across all tables,
runs SQLite ANALYZE for query planner statistics, and measures performance boost.
"""

from __future__ import annotations

import logging
import sqlite3
import time
from pathlib import Path
from typing import Dict, List

logging.basicConfig(
    level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s"
)
logger = logging.getLogger(__name__)

PROJECT_ROOT = Path(__file__).resolve().parents[2]
DB_PATH = PROJECT_ROOT / "output" / "nifty100.db"

INDEX_DEFINITIONS = [
    # 1. Ratios Table
    (
        "idx_ratios_company_id",
        "CREATE INDEX IF NOT EXISTS idx_ratios_company_id ON ratios(company_id)",
    ),
    ("idx_ratios_year", "CREATE INDEX IF NOT EXISTS idx_ratios_year ON ratios(year)"),
    (
        "idx_ratios_comp_year",
        "CREATE INDEX IF NOT EXISTS idx_ratios_comp_year ON ratios(company_id, year)",
    ),
    ("idx_ratios_roe", "CREATE INDEX IF NOT EXISTS idx_ratios_roe ON ratios(roe)"),
    # 2. Income Statement Table
    (
        "idx_is_company_id",
        "CREATE INDEX IF NOT EXISTS idx_is_company_id ON income_statement(company_id)",
    ),
    ("idx_is_year", "CREATE INDEX IF NOT EXISTS idx_is_year ON income_statement(year)"),
    (
        "idx_is_comp_year",
        "CREATE INDEX IF NOT EXISTS idx_is_comp_year ON income_statement(company_id, year)",
    ),
    # 3. Balance Sheet Table
    (
        "idx_bs_company_id",
        "CREATE INDEX IF NOT EXISTS idx_bs_company_id ON balance_sheet(company_id)",
    ),
    ("idx_bs_year", "CREATE INDEX IF NOT EXISTS idx_bs_year ON balance_sheet(year)"),
    (
        "idx_bs_comp_year",
        "CREATE INDEX IF NOT EXISTS idx_bs_comp_year ON balance_sheet(company_id, year)",
    ),
    # 4. Cash Flow Table
    (
        "idx_cf_company_id",
        "CREATE INDEX IF NOT EXISTS idx_cf_company_id ON cash_flow(company_id)",
    ),
    ("idx_cf_year", "CREATE INDEX IF NOT EXISTS idx_cf_year ON cash_flow(year)"),
    (
        "idx_cf_comp_year",
        "CREATE INDEX IF NOT EXISTS idx_cf_comp_year ON cash_flow(company_id, year)",
    ),
    # 5. Market Cap Table
    (
        "idx_mcap_company_id",
        "CREATE INDEX IF NOT EXISTS idx_mcap_company_id ON market_cap(company_id)",
    ),
    ("idx_mcap_year", "CREATE INDEX IF NOT EXISTS idx_mcap_year ON market_cap(year)"),
    (
        "idx_mcap_comp_year",
        "CREATE INDEX IF NOT EXISTS idx_mcap_comp_year ON market_cap(company_id, year)",
    ),
    # 6. Prices Table
    (
        "idx_prices_company_id",
        "CREATE INDEX IF NOT EXISTS idx_prices_company_id ON prices(company_id)",
    ),
    ("idx_prices_year", "CREATE INDEX IF NOT EXISTS idx_prices_year ON prices(year)"),
    (
        "idx_prices_comp_year",
        "CREATE INDEX IF NOT EXISTS idx_prices_comp_year ON prices(company_id, year)",
    ),
    # 7. Companies Table
    (
        "idx_companies_sector_id",
        "CREATE INDEX IF NOT EXISTS idx_companies_sector_id ON companies(sector_id)",
    ),
]


def apply_database_indexes(db_path: Path = DB_PATH) -> List[str]:
    """Create all performance indexes on SQLite database."""
    if not db_path.exists():
        raise FileNotFoundError(f"Database not found at {db_path}")

    applied = []
    conn = sqlite3.connect(str(db_path))
    try:
        cursor = conn.cursor()
        for idx_name, sql_stmt in INDEX_DEFINITIONS:
            cursor.execute(sql_stmt)
            applied.append(idx_name)
            logger.info("Ensured index: %s", idx_name)

        # Update SQLite Query Planner Statistics
        cursor.execute("ANALYZE")
        conn.commit()
        logger.info("Successfully executed SQLite ANALYZE on %s", db_path.name)
    finally:
        conn.close()

    return applied


def verify_database_indexes(db_path: Path = DB_PATH) -> Dict[str, str]:
    """Return dictionary of all active user indexes."""
    if not db_path.exists():
        return {}

    conn = sqlite3.connect(str(db_path))
    try:
        cursor = conn.cursor()
        cursor.execute(
            "SELECT name, tbl_name FROM sqlite_master WHERE type='index' AND name NOT LIKE 'sqlite_%'"
        )
        return {r[0]: r[1] for r in cursor.fetchall()}
    finally:
        conn.close()


if __name__ == "__main__":
    t0 = time.perf_counter()
    applied = apply_database_indexes()
    t1 = time.perf_counter()
    print("=" * 60)
    print(f"Applied {len(applied)} Performance Indexes in {(t1 - t0)*1000:.2f}ms")
    print("=" * 60)
    indexes = verify_database_indexes()
    for name, tbl in indexes.items():
        print(f"  * {name:30} on table: {tbl}")
