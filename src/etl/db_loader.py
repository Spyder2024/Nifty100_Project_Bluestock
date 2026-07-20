"""
DB Loader — Creates SQLite database and inserts data from Excel files.
Sprint 1, Day 4

Usage (standalone):
    python -m src.etl.db_loader

Tables created:
    sectors, companies, balance_sheet, income_statement,
    cash_flow, ratios, prices, market_cap, shareholding, dividends
"""

import sqlite3
import logging
from pathlib import Path
from typing import Optional

import pandas as pd

from src.etl.loader import (
    load_core_file,
    load_support_file,
    normalise_company_id,
    normalise_year_column,
)

logger = logging.getLogger(__name__)

# ===================================================================
# Column Mapping:  lowercase Excel header → DB column name
# Add / adjust aliases here if your Excel headers differ.
# ===================================================================

COMPANY_COL_MAP = {
    "company_name": "company_name",
    "company": "company_name",
    "name": "company_name",
    "sector": "sector_id",
    "industry": "industry",
    "nse_symbol": "nse_symbol",
    "nse": "nse_symbol",
    "bse_code": "bse_code",
    "bse": "bse_code",
    "isin": "isin",
    "face_value": "face_value",
    "series": "series",
    "listed_date": "listed_date",
    "listing_date": "listed_date",
}

SECTOR_COL_MAP = {
    "sector": "sector_name",
    "sector_name": "sector_name",
    "name": "sector_name",
}

BS_COL_MAP = {
    "total_assets": "total_assets",
    "total_liabilities": "total_liabilities",
    "total_equity": "total_equity",
    "shareholders_funds": "total_equity",
    "current_assets": "current_assets",
    "current_liabilities": "current_liabilities",
    "non_current_assets": "non_current_assets",
    "non_current_liabilities": "non_current_liab",
    "non_current_liab": "non_current_liab",
    "inventories": "inventories",
    "inventory": "inventories",
    "cash_and_cash_equivalents": "cash_and_equiv",
    "cash_and_equiv": "cash_and_equiv",
    "cash": "cash_and_equiv",
    "borrowings": "borrowings",
    "total_borrowings": "borrowings",
    "other_current_liabilities": "other_current_liab",
    "trade_payables": "trade_payables",
    "trade_receivables": "trade_receivables",
    "fixed_assets": "fixed_assets",
    "gross_block": "fixed_assets",
    "net_fixed_assets": "fixed_assets",
    "investments": "investments",
    "reserves": "reserves",
    "reserves_and_surplus": "reserves",
    "share_capital": "share_capital",
    "paid_up_capital": "share_capital",
    "equity_share_capital": "share_capital",
}

IS_COL_MAP = {
    "revenue": "revenue",
    "net_sales": "revenue",
    "sales": "revenue",
    "total_revenue": "revenue",
    "operating_income": "operating_income",
    "operating_profit": "operating_income",
    "other_income": "other_income",
    "total_expenses": "total_expenses",
    "interest_expense": "interest_expense",
    "interest": "interest_expense",
    "finance_costs": "interest_expense",
    "depreciation": "depreciation",
    "depreciation_and_amortization": "depreciation",
    "tax_expense": "tax_expense",
    "tax": "tax_expense",
    "net_income": "net_income",
    "net_profit": "net_income",
    "profit_after_tax": "net_income",
    "pat": "net_income",
    "eps": "eps",
    "opm": "opm",
    "npm": "npm",
    "ebitda": "ebitda",
    "ebit": "ebit",
}

CF_COL_MAP = {
    "operating_cash_flow": "operating_cf",
    "cash_from_operations": "operating_cf",
    "cash_flow_from_operating_activities": "operating_cf",
    "operating_cf": "operating_cf",
    "investing_cash_flow": "investing_cf",
    "cash_from_investing": "investing_cf",
    "cash_flow_from_investing_activities": "investing_cf",
    "investing_cf": "investing_cf",
    "financing_cash_flow": "financing_cf",
    "cash_from_financing": "financing_cf",
    "cash_flow_from_financing_activities": "financing_cf",
    "financing_cf": "financing_cf",
    "net_cash_flow": "net_cash_flow",
    "net_change_in_cash": "net_cash_flow",
    "capex": "capex",
    "capital_expenditure": "capex",
    "purchase_of_fixed_assets": "capex",
    "free_cash_flow": "fcf",
    "fcf": "fcf",
    "dividend_paid": "dividend_paid",
    "buyback_paid": "buyback_paid",
    "opening_cash": "opening_cash",
    "closing_cash": "closing_cash",
    "cash_and_cash_equivalents_opening": "opening_cash",
    "cash_and_cash_equivalents_closing": "closing_cash",
}

RATIOS_COL_MAP = {
    "roe": "roe",
    "return_on_equity": "roe",
    "roa": "roa",
    "return_on_assets": "roa",
    "roce": "roce",
    "return_on_capital_employed": "roce",
    "debt_to_equity": "debt_to_equity",
    "d_e_ratio": "debt_to_equity",
    "debt_equity_ratio": "debt_to_equity",
    "current_ratio": "current_ratio",
    "quick_ratio": "quick_ratio",
    "acid_test_ratio": "quick_ratio",
    "interest_coverage": "interest_coverage",
    "interest_coverage_ratio": "interest_coverage",
    "asset_turnover": "asset_turnover",
    "net_profit_margin": "net_profit_margin",
    "npm": "net_profit_margin",
    "opm": "opm",
    "operating_profit_margin": "opm",
    "dividend_payout": "dividend_payout",
    "dividend_payout_ratio": "dividend_payout",
    "earning_yield": "earning_yield",
    "book_value_per_share": "book_value_per_share",
    "bvps": "book_value_per_share",
    "price_to_book": "price_to_book",
    "pb_ratio": "price_to_book",
    "p_b_ratio": "price_to_book",
    "price_to_earnings": "price_to_earnings",
    "pe_ratio": "price_to_earnings",
    "p_e_ratio": "price_to_earnings",
}

PRICES_COL_MAP = {
    "open": "price_open",
    "price_open": "price_open",
    "high": "price_high",
    "price_high": "price_high",
    "low": "price_low",
    "price_low": "price_low",
    "close": "price_close",
    "price_close": "price_close",
    "volume": "volume",
}

MCAP_COL_MAP = {
    "market_cap": "market_cap",
    "market_cap_cr": "market_cap_cr",
    "market_capitalisation": "market_cap",
    "free_float_market_cap": "free_float_mcap",
    "free_float_mcap": "free_float_mcap",
    "weight": "weight_pct",
    "weight_pct": "weight_pct",
    "nifty_weight": "weight_pct",
}

SHAREHOLDING_COL_MAP = {
    "promoter": "promoter_pct",
    "promoter_holding": "promoter_pct",
    "promoter_pct": "promoter_pct",
    "fii": "fii_pct",
    "fii_holding": "fii_pct",
    "fii_pct": "fii_pct",
    "dii": "dii_pct",
    "dii_holding": "dii_pct",
    "dii_pct": "dii_pct",
    "public": "public_pct",
    "public_holding": "public_pct",
    "public_pct": "public_pct",
    "government": "govt_pct",
    "govt": "govt_pct",
    "custodian": "custodian_pct",
    "custodian_pct": "custodian_pct",
}

DIVIDEND_COL_MAP = {
    "dividend_per_share": "dividend_per_share",
    "dps": "dividend_per_share",
    "dividend_yield": "dividend_yield_pct",
    "dividend_yield_pct": "dividend_yield_pct",
    "dividend_payout": "dividend_payout_pct",
    "dividend_payout_ratio": "dividend_payout_pct",
    "total_dividend": "total_dividend",
    "ex_date": "ex_date",
    "record_date": "record_date",
}

# Aggregate: table_name → column-map
FINANCIAL_TABLES = {
    "balance_sheet": BS_COL_MAP,
    "income_statement": IS_COL_MAP,
    "cash_flow": CF_COL_MAP,
    "ratios": RATIOS_COL_MAP,
    "prices": PRICES_COL_MAP,
    "market_cap": MCAP_COL_MAP,
    "shareholding": SHAREHOLDING_COL_MAP,
    "dividends": DIVIDEND_COL_MAP,
}


# ===================================================================
# Core helpers
# ===================================================================

def get_connection(db_path: str) -> sqlite3.Connection:
    """Return a SQLite connection with FK enforcement and WAL mode."""
    Path(db_path).parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(db_path)
    conn.execute("PRAGMA foreign_keys = ON")
    conn.execute("PRAGMA journal_mode = WAL")
    conn.row_factory = sqlite3.Row
    logger.info("Connected to %s", db_path)
    return conn


def create_schema(conn: sqlite3.Connection, schema_path: str) -> None:
    """Execute schema.sql to create all 10 tables."""
    p = Path(schema_path)
    if not p.exists():
        raise FileNotFoundError(f"Schema file not found: {schema_path}")
    conn.executescript(p.read_text(encoding="utf-8"))
    conn.commit()
    logger.info("Schema created from %s", schema_path)


def _rename_columns(df: pd.DataFrame, col_map: dict) -> pd.DataFrame:
    """Rename columns that appear in *col_map* (key = lowercase header)."""
    rename = {}
    for col in df.columns:
        key = col.lower().strip().replace(" ", "_")
        if key in col_map:
            rename[col] = col_map[key]
    return df.rename(columns=rename)


# ===================================================================
# Table-specific loaders
# ===================================================================

def load_sectors(conn: sqlite3.Connection, df: pd.DataFrame) -> int:
    """Insert unique sectors.  Generates sector_id from sector_name."""
    count = 0
    for _, row in df.iterrows():
        raw = row.get("sector_name") or row.get("sector") or row.get("name")
        if not raw or pd.isna(raw):
            continue
        name = str(raw).strip()
        sector_id = name.upper().replace(" ", "_").replace("&", "AND")
        try:
            conn.execute(
                "INSERT OR IGNORE INTO sectors (sector_id, sector_name) VALUES (?, ?)",
                (sector_id, name),
            )
            count += 1
        except sqlite3.IntegrityError:
            logger.warning("Duplicate sector skipped: %s", name)
    conn.commit()
    logger.info("Loaded %d sectors", count)
    return count


def load_companies(conn: sqlite3.Connection, df: pd.DataFrame) -> int:
    """Insert companies; resolves sector_id from sector name."""
    count = 0
    for _, row in df.iterrows():
        cid = row.get("company_id")
        if not cid or pd.isna(cid):
            continue
        cid = str(cid).strip()
        name = str(row.get("company_name") or cid).strip()

        # Resolve sector_id
        raw_sector = row.get("sector_id")
        sector_id = None
        if raw_sector and not pd.isna(raw_sector):
            sector_id = (
                str(raw_sector).strip().upper().replace(" ", "_").replace("&", "AND")
            )

        try:
            conn.execute(
                """INSERT OR IGNORE INTO companies
                   (company_id, company_name, sector_id, nse_symbol,
                    bse_code, isin, series, listed_date, face_value)
                   VALUES (?,?,?,?,?,?,?,?,?)""",
                (
                    cid,
                    name,
                    sector_id,
                    row.get("nse_symbol"),
                    row.get("bse_code"),
                    row.get("isin"),
                    row.get("series", "EQ"),
                    row.get("listed_date"),
                    row.get("face_value", 1.0),
                ),
            )
            count += 1
        except sqlite3.IntegrityError as exc:
            logger.warning("Company insert failed %s: %s", cid, exc)
    conn.commit()
    logger.info("Loaded %d companies", count)
    return count


def load_financial_table(
    conn: sqlite3.Connection,
    df: pd.DataFrame,
    table_name: str,
    col_map: dict,
) -> int:
    """Generic loader for any (company_id, year) financial table."""
    df = _rename_columns(df, col_map)

    for req in ("company_id", "year"):
        if req not in df.columns:
            logger.error("%s missing required column '%s'", table_name, req)
            return 0

    # Determine insertable columns (must exist in both df and target)
    target_cols = {"company_id", "year"} | set(col_map.values())
    insert_cols = [c for c in df.columns if c in target_cols]

    if len(insert_cols) < 3:
        logger.warning(
            "%s: only %d cols resolved — %s", table_name, len(insert_cols), insert_cols
        )

    cols_str = ", ".join(insert_cols)
    placeholders = ", ".join(["?"] * len(insert_cols))
    sql = f"INSERT OR REPLACE INTO {table_name} ({cols_str}) VALUES ({placeholders})"

    count = 0
    errors = 0
    for _, row in df.iterrows():
        vals = [
            None if pd.isna(row.get(c)) else row.get(c) for c in insert_cols
        ]
        try:
            conn.execute(sql, vals)
            count += 1
        except sqlite3.IntegrityError as exc:
            errors += 1
            if errors <= 5:
                logger.warning(
                    "%s PK clash %s/%s: %s", table_name, row.get("company_id"),
                    row.get("year"), exc,
                )
        except sqlite3.OperationalError as exc:
            logger.error("%s SQL error: %s  SQL=%s", table_name, exc, sql)
            break
    conn.commit()
    logger.info("Loaded %d rows into %s (%d errors)", count, table_name, errors)
    return count


# ===================================================================
# Orchestrator
# ===================================================================

def run_full_load(
    db_path: str,
    data_dir: Optional[str] = None,
    schema_path: Optional[str] = None,
) -> dict[str, int]:
    """Create DB, run schema, load every Excel file.

    Returns dict  {table_name: row_count}.
    """
    project_root = Path(__file__).resolve().parent.parent.parent
    data_dir = data_dir or str(project_root / "data")
    schema_path = schema_path or str(project_root / "db" / "schema.sql")

    conn = get_connection(db_path)
    create_schema(conn, schema_path)

    results: dict[str, int] = {}

    # --- sectors (supporting file, header=0) ---
    try:
        s_df = load_support_file("sectors")
        results["sectors"] = load_sectors(conn, s_df)
    except Exception as exc:
        logger.error("sectors load failed: %s", exc)
        results["sectors"] = 0

    # --- companies (core file, header=1) ---
    try:
        c_df = load_core_file("companies")
        c_df = normalise_company_id(c_df)
        results["companies"] = load_companies(conn, c_df)
    except Exception as exc:
        logger.error("companies load failed: %s", exc)
        results["companies"] = 0

    # --- core financial tables (header=1) ---
    for file_name, table_name in [
        ("balance_sheet", "balance_sheet"),
        ("income_statement", "income_statement"),
        ("cash_flow", "cash_flow"),
        ("ratios", "ratios"),
        ("prices", "prices"),
        ("market_cap", "market_cap"),
    ]:
        try:
            df = load_core_file(file_name)
            df = normalise_company_id(df)
            df = normalise_year_column(df)
            results[table_name] = load_financial_table(
                conn, df, table_name, FINANCIAL_TABLES[table_name]
            )
        except Exception as exc:
            logger.error("%s load failed: %s", table_name, exc)
            results[table_name] = 0

    # --- supporting financial tables (header=0) ---
    for file_name, table_name in [
        ("shareholding", "shareholding"),
        ("dividends", "dividends"),
    ]:
        try:
            df = load_support_file(file_name)
            df = normalise_company_id(df)
            df = normalise_year_column(df)
            results[table_name] = load_financial_table(
                conn, df, table_name, FINANCIAL_TABLES[table_name]
            )
        except Exception as exc:
            logger.error("%s load failed: %s", table_name, exc)
            results[table_name] = 0

    conn.close()
    logger.info("Full load complete → %s", results)
    return results


# ===================================================================
# CLI entry-point  (python -m src.etl.db_loader)
# ===================================================================

if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )
    project_root = Path(__file__).resolve().parent.parent.parent
    db_path = str(project_root / "output" / "nifty100.db")
    schema_path = str(project_root / "db" / "schema.sql")

    print(f"Creating database at {db_path} ...")
    results = run_full_load(db_path, schema_path=schema_path)
    print("\n=== Load Summary ===")
    for tbl, cnt in results.items():
        print(f"  {tbl:20s} {cnt:>6d} rows")
    print(f"\nTotal tables written: {sum(1 for v in results.values() if v > 0)}")