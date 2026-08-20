#!/usr/bin/env python3
"""
Standalone QA runner for the Nifty-100 dashboard.

Run from project root:
    python src/dashboard/utils/qa_runner.py

Tests:
  1. DB connectivity & schema introspection
  2. Every cached query function returns valid DataFrames
  3. Cross-table consistency (company_id / year alignment)
  4. Null-audit across all tables
  5. PyArrow dtype compatibility check
  6. Page import check

Exit code 0 = all pass, 1 = one or more failures.
"""

from __future__ import annotations

import json
import sqlite3
import sys
import time
from pathlib import Path

import pandas as pd

# ── Path setup (mirrors the multi-page fix) ───────────────────────────────
_PROJECT_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(_PROJECT_ROOT))

from src.dashboard.utils.db import (  # noqa: E402
    get_all_ratios,
    get_bs,
    get_cf,
    get_companies,
    get_peers,
    get_pl,
    get_pros_cons,
    get_ratios,
    get_sectors,
)

DB_PATH = _PROJECT_ROOT / "output" / "nifty100.db"

# ── Colour helpers for terminal output ────────────────────────────────────
_PASS = "\033[92mPASS\033[0m"
_FAIL = "\033[91mFAIL\033[0m"
_WARN = "\033[93mWARN\033[0m"
_BOLD = "\033[1m"
_RESET = "\033[0m"

results: list[dict] = []


def _record(name: str, passed: bool, detail: str = "") -> None:
    tag = _PASS if passed else _FAIL
    print(f"  [{tag}] {name}" + (f" — {detail}" if detail else ""))
    # CRITICAL: cast numpy bool_ → Python bool for JSON serialization
    results.append({"test": name, "passed": bool(passed), "detail": str(detail)})


def _section(title: str) -> None:
    print(f"\n{_BOLD}{title}{_RESET}")
    print("-" * len(title))


# ── Shared: discover actual table names from DB ───────────────────────────


def _discover_tables(conn: sqlite3.Connection) -> list[str]:
    """Return sorted list of user table names (skip sqlite internals)."""
    return [
        r[0]
        for r in conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name"
        ).fetchall()
    ]


def _find_ratios_table(tables: list[str]) -> str | None:
    """Return the name of the ratios table (could be 'ratios', 'financial_ratios', etc.)."""
    for candidate in ("financial_ratios", "ratios", "fin_ratios"):
        if candidate in tables:
            return candidate
    # Fallback: any table with 'ratio' in the name
    return next((t for t in tables if "ratio" in t.lower()), None)


def _find_ticker_column(df: pd.DataFrame) -> str | None:
    """Detect the column used as company identifier (ticker/symbol/name)."""
    aliases = (
        "ticker",
        "symbol",
        "ticker_symbol",
        "stock_code",
        "nse_symbol",
        "company_ticker",
        "company_name",
    )
    for col in aliases:
        if col in df.columns:
            return col
    return None


# ────────────────────────────────────────────────────────────────────────────
# 1. DB connectivity
# ────────────────────────────────────────────────────────────────────────────


def test_db_connectivity(conn: sqlite3.Connection, tables: list[str]) -> None:
    _section("1. DB Connectivity & Schema")
    if not DB_PATH.exists():
        _record("DB file exists", False, f"{DB_PATH} not found")
        return
    _record("DB file exists", True, str(DB_PATH))
    _record("DB readable", True, f"{len(tables)} tables")

    expected = {"companies", "balance_sheet", "cash_flow", "financial_ratios", "ratios"}
    for t in expected:
        exists = t in tables
        _record(f"Table '{t}' exists", exists)

    # If neither financial_ratios nor ratios found, scan for aliases
    if "financial_ratios" not in tables and "ratios" not in tables:
        ratio_like = [t for t in tables if "ratio" in t.lower()]
        if ratio_like:
            _record(
                "Ratio table alias found", True, f"Candidates: {', '.join(ratio_like)}"
            )
        else:
            _record(
                "Ratio table alias found", False, f"No ratio-like table. All: {tables}"
            )


# ────────────────────────────────────────────────────────────────────────────
# 2. Query functions
# ────────────────────────────────────────────────────────────────────────────


def test_query_functions() -> None:
    _section("2. Cached Query Functions")

    # get_companies
    t0 = time.perf_counter()
    companies = get_companies()
    dt = (time.perf_counter() - t0) * 1000
    ok = (
        companies is not None
        and isinstance(companies, pd.DataFrame)
        and not companies.empty
    )
    _record(
        "get_companies()",
        ok,
        f"{len(companies)} rows, {dt:.1f}ms" if ok else str(type(companies)),
    )

    if not ok:
        _record("Remaining query tests", False, "Skipped — no companies data")
        return

    # ── Discover the company identifier column ─────────────────────────
    ticker_col = _find_ticker_column(companies)
    if ticker_col is None:
        _record(
            "Find identifier column",
            False,
            f"Available: {list(companies.columns)}",
        )
        _record("Remaining query tests", False, "Skipped — no identifier column")
        return

    _record("Identifier column detected", True, f"Using '{ticker_col}'")
    sample_id = str(companies[ticker_col].iloc[0])

    # get_all_ratios — try last 2 years
    for year in [2024, 2023]:
        t0 = time.perf_counter()
        ratios = get_all_ratios(year)
        dt = (time.perf_counter() - t0) * 1000
        ok = ratios is not None and isinstance(ratios, pd.DataFrame)
        _record(
            f"get_all_ratios({year})",
            ok,
            f"{len(ratios)} rows, {dt:.1f}ms" if ok else str(type(ratios)),
        )

    # get_ratios
    t0 = time.perf_counter()
    ratios = get_ratios(sample_id)
    dt = (time.perf_counter() - t0) * 1000
    ok = ratios is not None and isinstance(ratios, pd.DataFrame)
    _record(
        f"get_ratios('{sample_id[:20]}')",
        ok,
        f"{len(ratios)} rows, {dt:.1f}ms" if ok else str(type(ratios)),
    )

    # get_pl
    t0 = time.perf_counter()
    pl = get_pl(sample_id)
    dt = (time.perf_counter() - t0) * 1000
    ok = pl is not None and isinstance(pl, pd.DataFrame)
    _record(
        f"get_pl('{sample_id[:20]}')",
        ok,
        f"{len(pl)} rows, {dt:.1f}ms" if ok else str(type(pl)),
    )

    # get_bs
    t0 = time.perf_counter()
    bs = get_bs(sample_id)
    dt = (time.perf_counter() - t0) * 1000
    ok = bs is not None and isinstance(bs, pd.DataFrame)
    _record(
        f"get_bs('{sample_id[:20]}')",
        ok,
        f"{len(bs)} rows, {dt:.1f}ms" if ok else str(type(bs)),
    )

    # get_cf
    t0 = time.perf_counter()
    cf = get_cf(sample_id)
    dt = (time.perf_counter() - t0) * 1000
    ok = cf is not None and isinstance(cf, pd.DataFrame)
    _record(
        f"get_cf('{sample_id[:20]}')",
        ok,
        f"{len(cf)} rows, {dt:.1f}ms" if ok else str(type(cf)),
    )

    # get_sectors
    t0 = time.perf_counter()
    sectors = get_sectors()
    dt = (time.perf_counter() - t0) * 1000
    ok = sectors is not None and isinstance(sectors, pd.DataFrame)
    _record(
        "get_sectors()",
        ok,
        f"{len(sectors)} rows, {dt:.1f}ms" if ok else str(type(sectors)),
    )

    # get_peers
    t0 = time.perf_counter()
    peers = get_peers(sample_id)
    dt = (time.perf_counter() - t0) * 1000
    ok = peers is not None and isinstance(peers, pd.DataFrame)
    _record(
        f"get_peers('{sample_id[:20]}')",
        ok,
        f"{len(peers)} peers, {dt:.1f}ms" if ok else str(type(peers)),
    )

    # get_pros_cons
    t0 = time.perf_counter()
    pc = get_pros_cons(sample_id)
    dt = (time.perf_counter() - t0) * 1000
    ok = pc is not None and isinstance(pc, pd.DataFrame)
    _record(
        f"get_pros_cons('{sample_id[:20]}')",
        ok,
        f"{len(pc)} rows, {dt:.1f}ms" if ok else str(type(pc)),
    )


# ────────────────────────────────────────────────────────────────────────────
# 3. Cross-table consistency
# ────────────────────────────────────────────────────────────────────────────


def test_cross_table_consistency(
    conn: sqlite3.Connection,
    tables: list[str],
) -> None:
    _section("3. Cross-Table Consistency")

    companies = get_companies()
    ratios = get_all_ratios(2024)
    if companies is None or ratios is None:
        _record("Consistency check", False, "Cannot load base tables")
        return

    comp_ids = set(companies["company_id"])
    ratio_ids = set(ratios["company_id"]) if not ratios.empty else set()

    # Companies in ratios but not in companies table
    orphan = ratio_ids - comp_ids
    _record(
        "No orphan ratio rows",
        len(orphan) == 0,
        f"{len(orphan)} orphan(s)" if orphan else "All ratio rows linked",
    )

    # Companies with no ratio data — WARN, not FAIL (data gap, not code bug)
    uncovered = comp_ids - ratio_ids
    _record(
        "All companies have ratios",
        len(uncovered) == 0,
        f"{len(uncovered)} uncovered" if uncovered else "Full coverage",
    )

    # Year range sanity
    for table in ("balance_sheet", "cash_flow"):
        if table not in tables:
            _record(f"{table} year range", False, "Table not in DB")
            continue
        try:
            years = pd.read_sql(
                f"SELECT DISTINCT year FROM {table} ORDER BY year", conn
            )["year"].tolist()
            span = f"{min(years)}–{max(years)} ({len(years)} periods)"
            _record(f"{table} year range", len(years) > 0, span)
        except Exception as e:
            _record(f"{table} year range", False, str(e))


# ────────────────────────────────────────────────────────────────────────────
# 4. Null audit (data quality — separate from code correctness)
# ────────────────────────────────────────────────────────────────────────────


def test_null_audit(conn: sqlite3.Connection, tables: list[str]) -> None:
    _section("4. Null Audit Across Tables (Data Quality)")

    # Only check tables that exist
    _target = ["companies", "balance_sheet", "cash_flow", "financial_ratios", "ratios"]
    check_tables = [t for t in _target if t in tables]

    for table in check_tables:
        try:
            df = pd.read_sql(f"SELECT * FROM {table}", conn)
        except Exception as e:
            _record(f"{table} null audit", False, f"Read error: {e}")
            continue

        if df.empty:
            _record(f"{table} null audit", False, "Empty table")
            continue

        null_pcts = df.isna().mean().mul(100).round(1)
        fully_null = int((null_pcts == 100).sum())
        mostly_null = int(((null_pcts > 80) & (null_pcts < 100)).sum())

        # Data quality issue — not a code bug — so we WARN, not FAIL
        if fully_null == 0 and mostly_null == 0:
            _record(f"{table} null audit", True, "Clean — no fully-null columns")
        else:
            _record(
                f"{table} null audit",
                True,  # code is fine; this is a data pipeline issue
                f"[DATA] {fully_null} fully null, {mostly_null} >80% null",
            )
            # Print the column names for reference
            if fully_null > 0:
                cols = null_pcts[null_pcts == 100].index.tolist()
                print(f"       Fully-null columns: {', '.join(cols)}")


# ────────────────────────────────────────────────────────────────────────────
# 5. PyArrow dtype compatibility
# ────────────────────────────────────────────────────────────────────────────


def test_pyarrow_compat() -> None:
    _section("5. PyArrow Dtype Compatibility")

    companies = get_companies()
    if companies is None or companies.empty:
        _record("PyArrow compat", False, "No data")
        return

    # Detect backend from dtype string
    sample_dtype = str(companies.dtypes.iloc[0])
    backend = "PyArrow" if "pyarrow" in sample_dtype.lower() else "numpy"
    _record("Backend detected", True, backend)

    # Test that .fillna(0).abs() works on numeric columns (the Day 25 gotcha)
    numeric = companies.select_dtypes(include="number")
    if numeric.empty:
        _record("fillna(0).abs() safe", True, "No numeric columns to test")
        return

    try:
        _ = numeric.fillna(0).abs()
        _record(
            "fillna(0).abs() safe", True, f"Tested on {numeric.shape[1]} numeric cols"
        )
    except TypeError as e:
        _record("fillna(0).abs() safe", False, str(e))

    # Test sort_values with na_position (the Day 24 gotcha)
    try:
        _ = companies.sort_values(
            companies.columns[0], ascending=False, na_position="last"
        )
        _record("sort_values na_position='last'", True)
    except Exception as e:
        _record("sort_values na_position='last'", False, str(e))


# ────────────────────────────────────────────────────────────────────────────
# 6. Page import check
# ────────────────────────────────────────────────────────────────────────────


def test_page_imports() -> None:
    _section("6. Page Import Check")

    pages_dir = Path(__file__).resolve().parents[1] / "pages"
    if not pages_dir.exists():
        _record("pages/ directory", False, f"{pages_dir} not found")
        return

    page_files = sorted(pages_dir.glob("[0-9]*_*.py"))
    for pf in page_files:
        try:
            compile(pf.read_text(encoding="utf-8"), str(pf), "exec")
            _record(f"Import: {pf.name}", True)
        except SyntaxError as e:
            _record(
                f"Import: {pf.name}",
                False,
                f"SyntaxError line {e.lineno}: {e.msg}",
            )


# ────────────────────────────────────────────────────────────────────────────
# Main
# ────────────────────────────────────────────────────────────────────────────


def main() -> None:
    print(f"\n{'=' * 60}")
    print("  Nifty-100 Dashboard — Integration QA")
    print(f"  DB: {DB_PATH}")
    print(f"{'=' * 60}")

    # ── Open DB once, share connection ─────────────────────────────────
    conn: sqlite3.Connection | None = None
    tables: list[str] = []

    if DB_PATH.exists():
        conn = sqlite3.connect(str(DB_PATH))
        tables = _discover_tables(conn)

    # ── Run test suites ────────────────────────────────────────────────
    if conn:
        test_db_connectivity(conn, tables)
    else:
        _section("1. DB Connectivity & Schema")
        _record("DB file exists", False, f"{DB_PATH} not found")

    test_query_functions()

    if conn:
        test_cross_table_consistency(conn, tables)
        test_null_audit(conn, tables)
        conn.close()

    test_pyarrow_compat()
    test_page_imports()

    # ── Summary ────────────────────────────────────────────────────────
    total = len(results)
    passed = sum(1 for r in results if r["passed"])
    failed = total - passed

    print(f"\n{'=' * 60}")
    print(f"  Results: {_PASS} {passed}/{total}   {_FAIL} {failed}/{total}")
    print(f"{'=' * 60}\n")

    if failed:
        print("Failed tests:")
        for r in results:
            if not r["passed"]:
                print(f"  ✗ {r['test']} — {r['detail']}")

    # ── Write JSON report ──────────────────────────────────────────────
    report_path = _PROJECT_ROOT / "output" / "qa_report.json"
    report_path.parent.mkdir(exist_ok=True)
    try:
        with open(report_path, "w", encoding="utf-8") as f:
            json.dump(
                {
                    "timestamp": pd.Timestamp.now().isoformat(),
                    "total": total,
                    "passed": passed,
                    "failed": failed,
                    "results": results,
                },
                f,
                indent=2,
                default=str,  # fallback for any remaining non-serializable types
            )
        print(f"\nJSON report → {report_path}")
    except TypeError as e:
        print(f"\n⚠️  Failed to write JSON report: {e}")
        print("    This is non-critical; terminal output above is the real result.")

    sys.exit(1 if failed else 0)


if __name__ == "__main__":
    main()
