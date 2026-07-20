"""
Load Auditor — Runs full data load, generates audit CSV, checks FK integrity.
Sprint 1, Day 5

Usage:
    python -m src.etl.load_audit

Outputs:
    output/load_audit.csv   — per-table load status
    output/nifty100.db      — populated SQLite database
"""

import csv
import logging
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from src.etl.db_loader import (
    FINANCIAL_TABLES,
    create_schema,
    get_connection,
    load_companies,
    load_financial_table,
    load_sectors,
)
from src.etl.loader import (
    load_core_file,
    load_support_file,
    normalise_company_id,
    normalise_year_column,
)

logger = logging.getLogger(__name__)

# ------------------------------------------------------------------
# Audit CSV column specification
# ------------------------------------------------------------------

AUDIT_COLUMNS = [
    "table_name",
    "source_file",
    "source_type",
    "rows_loaded",
    "rows_skipped",
    "total_rows_in_source",
    "load_status",
    "error_message",
    "load_timestamp",
]


# ------------------------------------------------------------------
# Helpers
# ------------------------------------------------------------------

def _audit_status(rows_loaded: int, total_rows: int, error_msg: str) -> str:
    if error_msg:
        return "FAILED"
    if rows_loaded == 0:
        return "FAILED"
    if rows_loaded < total_rows:
        return "PARTIAL"
    return "SUCCESS"


def _write_audit_csv(records: list[dict], output_path: str) -> None:
    Path(output_path).parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=AUDIT_COLUMNS)
        writer.writeheader()
        writer.writerows(records)
    logger.info("Audit CSV written to %s (%d records)", output_path, len(records))


# ------------------------------------------------------------------
# FK Integrity
# ------------------------------------------------------------------

def check_fk_integrity(conn: sqlite3.Connection) -> list[dict]:
    results: list[dict] = []

    orphans = conn.execute("""
        SELECT COUNT(*) FROM companies c
        LEFT JOIN sectors s ON c.sector_id = s.sector_id
        WHERE c.sector_id IS NOT NULL AND s.sector_id IS NULL
    """).fetchone()[0]
    results.append(dict(
        fk_table="companies", fk_column="sector_id",
        ref_table="sectors", ref_column="sector_id",
        orphan_count=orphans,
    ))

    for tbl in [
        "balance_sheet", "income_statement", "cash_flow",
        "ratios", "prices", "market_cap", "shareholding", "dividends",
    ]:
        orphans = conn.execute(f"""
            SELECT COUNT(*) FROM {tbl} t
            LEFT JOIN companies c ON t.company_id = c.company_id
            WHERE c.company_id IS NULL
        """).fetchone()[0]
        results.append(dict(
            fk_table=tbl, fk_column="company_id",
            ref_table="companies", ref_column="company_id",
            orphan_count=orphans,
        ))

    return results


# ------------------------------------------------------------------
# Row counts
# ------------------------------------------------------------------

def get_table_row_counts(conn: sqlite3.Connection) -> dict[str, int]:
    rows = conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name"
    ).fetchall()
    return {t[0]: conn.execute(f"SELECT COUNT(*) FROM {t[0]}").fetchone()[0]
            for t in rows}


# ------------------------------------------------------------------
# Single-table load wrapper (captures audit metadata)
# ------------------------------------------------------------------

def _load_one_table(
    conn: sqlite3.Connection,
    file_name: str,
    table_name: str,
    source_type: str,
    load_fn,
    col_map: dict | None = None,
) -> dict:
    ts = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")
    try:
        if source_type == "supporting":
            df = load_support_file(file_name)
        else:
            df = load_core_file(file_name)

        total = len(df)

        if "company_id" in (c.lower() for c in df.columns):
            df = normalise_company_id(df)
        if "year" in (c.lower() for c in df.columns):
            df = normalise_year_column(df)

        if col_map is not None:
            loaded = load_financial_table(conn, df, table_name, col_map)
        else:
            loaded = load_fn(conn, df)

        return dict(
            table_name=table_name,
            source_file=f"{file_name}.xlsx",
            source_type=source_type,
            rows_loaded=loaded,
            rows_skipped=max(0, total - loaded),
            total_rows_in_source=total,
            load_status=_audit_status(loaded, total, ""),
            error_message="",
            load_timestamp=ts,
        )
    except Exception as exc:
        logger.error("Load failed for %s: %s", table_name, exc, exc_info=True)
        return dict(
            table_name=table_name,
            source_file=f"{file_name}.xlsx",
            source_type=source_type,
            rows_loaded=0,
            rows_skipped=0,
            total_rows_in_source=0,
            load_status="FAILED",
            error_message=str(exc)[:200],
            load_timestamp=ts,
        )


# ------------------------------------------------------------------
# Orchestrator
# ------------------------------------------------------------------

def run_load_with_audit(
    db_path: str,
    audit_path: str,
    schema_path: Optional[str] = None,
) -> dict:
    project_root = Path(__file__).resolve().parent.parent.parent
    schema_path = schema_path or str(project_root / "db" / "schema.sql")

    conn = get_connection(db_path)
    create_schema(conn, schema_path)

    audit_records: list[dict] = []
    ts = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")

    # ===========================================================
    # FILE → TABLE MAPPING  (matches actual dataset names)
    #
    # Core files (header=1):
    #   companies, balancesheet, profitandloss, cashflow,
    #   analysis, documents, prosandcons
    #
    # Supporting files (header=0):
    #   sectors, stock_prices, market_cap, financial_ratios,
    #   peer_groups
    # ===========================================================

    # ---- 1. sectors (supporting) ----
    audit_records.append(
        _load_one_table(conn, "sectors", "sectors", "supporting", load_sectors)
    )

    # ---- 2. companies (core) ----
    audit_records.append(
        _load_one_table(conn, "companies", "companies", "core", load_companies)
    )

    # ---- 3. Core financial tables ----
    for file_name, table_name in [
        ("balancesheet",   "balance_sheet"),
        ("profitandloss",  "income_statement"),
        ("cashflow",       "cash_flow"),
    ]:
        audit_records.append(
            _load_one_table(
                conn, file_name, table_name, "core",
                None, FINANCIAL_TABLES[table_name],
            )
        )

    # ---- 4. Supporting data tables ----
    for file_name, table_name in [
        ("financial_ratios", "ratios"),
        ("stock_prices",    "prices"),
        ("market_cap",      "market_cap"),
    ]:
        audit_records.append(
            _load_one_table(
                conn, file_name, table_name, "supporting",
                None, FINANCIAL_TABLES[table_name],
            )
        )

    # ---- 5. Tables with NO source file (SKIPPED) ----
    for table_name in ["shareholding", "dividends"]:
        audit_records.append(dict(
            table_name=table_name,
            source_file="N/A",
            source_type="none",
            rows_loaded=0,
            rows_skipped=0,
            total_rows_in_source=0,
            load_status="SKIPPED",
            error_message="No matching source file in data/",
            load_timestamp=ts,
        ))

    # ---- 6. FK integrity check ----
    fk_results = check_fk_integrity(conn)

    # ---- 7. Final row counts ----
    table_counts = get_table_row_counts(conn)

    # ---- 8. Write audit CSV ----
    _write_audit_csv(audit_records, audit_path)

    conn.close()
    logger.info(
        "Load audit complete. Tables: %d, FK issues: %d",
        len(audit_records),
        sum(1 for r in fk_results if r["orphan_count"] > 0),
    )

    return dict(
        audit_records=audit_records,
        fk_results=fk_results,
        table_counts=table_counts,
    )


# ------------------------------------------------------------------
# CLI
# ------------------------------------------------------------------

if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )
    project_root = Path(__file__).resolve().parent.parent.parent
    db_path = str(project_root / "output" / "nifty100.db")
    audit_path = str(project_root / "output" / "load_audit.csv")
    schema_path = str(project_root / "db" / "schema.sql")

    print("=" * 60)
    print("  Nifty 100 — Full Data Load with Audit")
    print("=" * 60)

    results = run_load_with_audit(
        db_path=db_path,
        audit_path=audit_path,
        schema_path=schema_path,
    )

    # ---- Print audit table ----
    print(f"\n{'Table':<22s} {'Status':<10s} {'Loaded':>7s} {'Source Rows':>12s}")
    print("-" * 55)
    for rec in results["audit_records"]:
        print(
            f"{rec['table_name']:<22s} {rec['load_status']:<10s} "
            f"{rec['rows_loaded']:>7d} {rec['total_rows_in_source']:>12d}"
        )

    # ---- Print FK check ----
    print(f"\n{'FK Check'}")
    print("-" * 45)
    all_ok = True
    for fk in results["fk_results"]:
        if fk["orphan_count"] == 0:
            status = "OK"
        else:
            status = f"FAIL ({fk['orphan_count']} orphans)"
            all_ok = False
        print(f"  {fk['fk_table']:<22s} .{fk['fk_column']:<16s} -> {status}")

    # ---- Print DB counts ----
    print(f"\n{'Final DB Row Counts'}")
    print("-" * 35)
    for table, count in results["table_counts"].items():
        print(f"  {table:<22s} {count:>7d}")

    print(f"\nAudit CSV  -> {audit_path}")
    print(f"Database   -> {db_path}")
    print(f"\nFK integrity: {'ALL GOOD' if all_ok else 'ISSUES FOUND — review above'}")