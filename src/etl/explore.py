"""
Exploratory SQL Queries — Data profiling for the Nifty 100 dataset.
Sprint 1, Day 7

12 queries covering revenue rankings, sector aggregations,
data quality diagnostics, and coverage statistics.

Usage:
    python -m src.etl.explore
"""

import csv
import logging
import sqlite3
from datetime import datetime, timezone
from pathlib import Path

logger = logging.getLogger(__name__)


# ===================================================================
# Query functions — each takes conn, returns list[dict]
# ===================================================================

def q_top_revenue_companies(conn, n=10):
    """Q01: Top N companies by latest-year revenue."""
    return [
        dict(company_id=r[0], company_name=r[1], year=r[2],
             revenue=r[3], net_income=r[4], opm=r[5])
        for r in conn.execute(f"""
            SELECT i.company_id, c.company_name, i.year,
                   i.revenue, i.net_income, i.opm
            FROM income_statement i
            JOIN companies c ON i.company_id = c.company_id
            WHERE i.year = (SELECT MAX(year) FROM income_statement)
              AND i.revenue IS NOT NULL
            ORDER BY i.revenue DESC LIMIT {n}
        """).fetchall()
    ]


def q_sector_company_count(conn):
    """Q02: Number of companies per sector."""
    return [
        dict(sector_id=r[0], company_count=r[1])
        for r in conn.execute("""
            SELECT sector_id, COUNT(*) AS company_count
            FROM companies
            WHERE sector_id IS NOT NULL
            GROUP BY sector_id ORDER BY company_count DESC
        """).fetchall()
    ]


def q_avg_opm_by_sector(conn):
    """Q03: Average OPM by sector (latest year)."""
    max_yr = conn.execute("SELECT MAX(year) FROM income_statement").fetchone()[0]
    return [
        dict(sector_id=r[0], avg_opm=round(r[1], 2),
             n_companies=r[2], min_opm=r[3], max_opm=r[4])
        for r in conn.execute("""
            SELECT c.sector_id, AVG(i.opm), COUNT(*),
                   MIN(i.opm), MAX(i.opm)
            FROM income_statement i
            JOIN companies c ON i.company_id = c.company_id
            WHERE i.year = ? AND i.opm IS NOT NULL
            GROUP BY c.sector_id ORDER BY AVG(i.opm) DESC
        """, (max_yr,)).fetchall()
    ]


def q_top_roe_companies(conn, n=10):
    """Q04: Top N companies by ROE (latest year)."""
    max_yr = conn.execute("SELECT MAX(year) FROM ratios").fetchone()[0]
    return [
        dict(company_id=r[0], company_name=r[1], roe=r[2], roa=r[3], roce=r[4])
        for r in conn.execute(f"""
            SELECT r.company_id, c.company_name, r.roe, r.roa, r.roce
            FROM ratios r
            JOIN companies c ON r.company_id = c.company_id
            WHERE r.year = ? AND r.roe IS NOT NULL
            ORDER BY r.roe DESC LIMIT {n}
        """, (max_yr,)).fetchall()
    ]


def q_yoy_revenue_growth(conn, n=5):
    """Q05: Year-over-year revenue growth for top N (by latest revenue)."""
    return [
        dict(company_id=r[0], company_name=r[1],
             revenue_latest=r[2], revenue_prev=r[3], yoy_growth_pct=r[4])
        for r in conn.execute("""
            SELECT c.company_id, c.company_name,
                   cur.revenue, prev.revenue,
                   ROUND((cur.revenue - prev.revenue)
                         * 100.0 / prev.revenue, 2)
            FROM income_statement cur
            JOIN income_statement prev
              ON cur.company_id = prev.company_id
             AND prev.year = (
                SELECT MAX(year) FROM income_statement
                WHERE company_id = cur.company_id AND year < cur.year
             )
            JOIN companies c ON cur.company_id = c.company_id
            WHERE cur.year = (
                SELECT MAX(year) FROM income_statement
                WHERE company_id = cur.company_id
             )
              AND cur.revenue IS NOT NULL
              AND prev.revenue IS NOT NULL
              AND prev.revenue > 0
            ORDER BY cur.revenue DESC LIMIT ?
        """, (n,)).fetchall()
    ]

def q_loss_making_companies(conn):
    """Q06: Companies with negative net income in latest year."""
    max_yr = conn.execute("SELECT MAX(year) FROM income_statement").fetchone()[0]
    return [
        dict(company_id=r[0], company_name=r[1], year=r[2],
             revenue=r[3], net_income=r[4])
        for r in conn.execute("""
            SELECT i.company_id, c.company_name, i.year,
                   i.revenue, i.net_income
            FROM income_statement i
            JOIN companies c ON i.company_id = c.company_id
            WHERE i.year = ? AND i.net_income < 0
            ORDER BY i.net_income ASC
        """, (max_yr,)).fetchall()
    ]


def q_avg_de_by_sector(conn):
    """Q07: Average debt-to-equity by sector (latest year)."""
    max_yr = conn.execute("SELECT MAX(year) FROM ratios").fetchone()[0]
    return [
        dict(sector_id=r[0], avg_de=round(r[1], 2), n_companies=r[2])
        for r in conn.execute("""
            SELECT c.sector_id, AVG(r.debt_to_equity), COUNT(*)
            FROM ratios r
            JOIN companies c ON r.company_id = c.company_id
            WHERE r.year = ? AND r.debt_to_equity IS NOT NULL
            GROUP BY c.sector_id ORDER BY AVG(r.debt_to_equity) DESC
        """, (max_yr,)).fetchall()
    ]


def q_highest_dividend_payout(conn, n=10):
    """Q08: Companies with highest dividend payout (latest year)."""
    max_yr = conn.execute("SELECT MAX(year) FROM ratios").fetchone()[0]
    return [
        dict(company_id=r[0], company_name=r[1], dividend_payout=r[2])
        for r in conn.execute(f"""
            SELECT r.company_id, c.company_name, r.dividend_payout
            FROM ratios r
            JOIN companies c ON r.company_id = c.company_id
            WHERE r.year = ? AND r.dividend_payout IS NOT NULL
            ORDER BY r.dividend_payout DESC LIMIT {n}
        """, (max_yr,)).fetchall()
    ]


def q_data_coverage_per_year(conn):
    """Q09: Company count per year, per source table."""
    rows = []
    for tbl in ("balance_sheet", "income_statement", "cash_flow",
                "ratios", "prices", "market_cap"):
        for r in conn.execute(f"""
            SELECT year, COUNT(DISTINCT company_id)
            FROM {tbl} GROUP BY year ORDER BY year
        """).fetchall():
            rows.append(dict(year=r[0], company_count=r[1], source_table=tbl))
    return rows


def q_bs_balance_issues(conn, threshold_pct=5.0):
    """Q10: Companies where BS imbalance exceeds threshold."""
    return [
        dict(company_id=r[0], year=r[1], total_assets=r[2],
             bs_balance=r[3], imbalance_pct=r[4])
        for r in conn.execute("""
            SELECT company_id, year, total_assets, bs_balance,
                   ROUND(ABS(bs_balance) * 100.0 / total_assets, 2)
            FROM balance_sheet
            WHERE total_assets > 0
              AND ABS(bs_balance) * 100.0 / total_assets > ?
            ORDER BY 5 DESC
        """, (threshold_pct,)).fetchall()
    ]


def q_key_metric_summary(conn):
    """Q11: Min / Max / Avg for 5 key metrics across all data."""
    metrics = [
        ("revenue", "income_statement"),
        ("net_income", "income_statement"),
        ("roe", "ratios"),
        ("debt_to_equity", "ratios"),
        ("current_ratio", "ratios"),
    ]
    results = []
    for col, tbl in metrics:
        try:
            r = conn.execute(f"""
                SELECT MIN({col}), MAX({col}), AVG({col}), COUNT(*),
                       COUNT(*) - SUM(CASE WHEN {col} IS NULL THEN 1 ELSE 0 END)
                FROM {tbl}
            """).fetchone()
            results.append(dict(
                metric=col, table=tbl,
                min_val=round(r[0], 2) if r[0] is not None else None,
                max_val=round(r[1], 2) if r[1] is not None else None,
                avg_val=round(r[2], 2) if r[2] is not None else None,
                total_rows=r[3], non_null_rows=r[4],
            ))
        except sqlite3.OperationalError:
            results.append(dict(metric=col, table=tbl,
                                min_val=None, max_val=None,
                                avg_val=None, total_rows=0, non_null_rows=0))
    return results


def q_companies_per_table(conn):
    """Q12: Distinct company count per table."""
    results = []
    for tbl in ("balance_sheet", "income_statement", "cash_flow",
                "ratios", "prices", "market_cap"):
        cnt = conn.execute(
            f"SELECT COUNT(DISTINCT company_id) FROM {tbl}"
        ).fetchone()[0]
        results.append(dict(table_name=tbl, distinct_companies=cnt))
    return results


# ===================================================================
# Registry
# ===================================================================

ALL_QUERIES = [
    ("Q01_top_revenue",    "Top 10 by revenue (latest year)",      q_top_revenue_companies),
    ("Q02_sector_count",   "Companies per sector",                 q_sector_company_count),
    ("Q03_avg_opm_sector", "Avg OPM by sector",                   q_avg_opm_by_sector),
    ("Q04_top_roe",        "Top 10 by ROE",                       q_top_roe_companies),
    ("Q05_yoy_growth",     "YoY revenue growth (top 5)",           q_yoy_revenue_growth),
    ("Q06_losses",         "Loss-making companies (latest year)",  q_loss_making_companies),
    ("Q07_avg_de_sector",  "Avg debt-to-equity by sector",        q_avg_de_by_sector),
    ("Q08_div_payout",     "Highest dividend payout",              q_highest_dividend_payout),
    ("Q09_coverage",       "Data coverage per year & table",       q_data_coverage_per_year),
    ("Q10_bs_issues",      "BS balance issues (>5%)",              q_bs_balance_issues),
    ("Q11_metric_stats",   "Key metric min/max/avg",               q_key_metric_summary),
    ("Q12_companies_tbl",  "Distinct companies per table",         q_companies_per_table),
]


# ===================================================================
# Orchestrator
# ===================================================================

def run_exploration(
    db_path: str | None = None,
    output_path: str = "output/exploration.csv",
    conn: sqlite3.Connection | None = None,
) -> dict:
    """Run all 12 queries, write results to a single CSV."""
    own_conn = False
    if conn is None:
        if db_path is None:
            raise ValueError("Either db_path or conn must be provided")
        conn = sqlite3.connect(db_path)
        own_conn = True

    all_rows: list[dict] = []
    summary: dict[str, dict] = {}

    for qid, desc, fn in ALL_QUERIES:
        try:
            results = fn(conn)
            for r in results:
                r["query_id"] = qid
                r["query_description"] = desc
            all_rows.extend(results)
            summary[qid] = dict(status="OK", rows=len(results), error="")
            logger.info("%s: %d rows", qid, len(results))
        except Exception as exc:
            logger.error("%s failed: %s", qid, exc)
            summary[qid] = dict(status="ERROR", rows=0, error=str(exc)[:200])
            all_rows.append(dict(query_id=qid, query_description=desc,
                                 error=str(exc)[:200]))

    Path(output_path).parent.mkdir(parents=True, exist_ok=True)
    fieldnames = list(all_rows[0].keys()) if all_rows else ["query_id", "error"]
    with open(output_path, "w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(all_rows)

    if  own_conn:
        conn.close()
        
    return dict(summary=summary, total_rows=len(all_rows))


# ===================================================================
# Sprint 1 Retrospective
# ===================================================================

def generate_retro(project_root: str) -> str:
    """Build Sprint 1 retrospective from live DB stats."""
    db_path = str(Path(project_root) / "output" / "nifty100.db")
    conn = sqlite3.connect(db_path)

    n_companies = conn.execute("SELECT COUNT(*) FROM companies").fetchone()[0]
    n_sectors = conn.execute("SELECT COUNT(*) FROM sectors").fetchone()[0]

    tbl_rows = {}
    for tbl in ("balance_sheet", "income_statement", "cash_flow",
                "ratios", "prices", "market_cap"):
        tbl_rows[tbl] = conn.execute(
            f"SELECT COUNT(*) FROM {tbl}"
        ).fetchone()[0]
    conn.close()

    total = sum(tbl_rows.values())
    ts = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")

    lines = [
        "=" * 60,
        "  SPRINT 1 RETROSPECTIVE — DATA FOUNDATION (Days 1–7)",
        f"  Generated: {ts}",
        "=" * 60,
        "",
        "PLANNED vs DELIVERED",
        "-" * 40,
        "Day 1  Project scaffold, requirements, .gitignore, .env   DONE",
        "Day 2  ETL normaliser (year/ticker) + Excel loader (12 files)  DONE",
        "Day 3  Schema validator with 16 DQ rules                      DONE",
        "Day 4  SQLite schema (10 tables) + insert loader               DONE",
        "Day 5  Full data load, load_audit.csv, FK integrity check      DONE",
        "Day 6  DQ review of 5 random companies (10 checks)             DONE",
        "Day 7  Exploratory SQL queries + Sprint retro                  DONE",
        "",
        "KEY METRICS",
        "-" * 40,
        f"  Companies loaded:    {n_companies}",
        f"  Sectors:             {n_sectors}",
        f"  Total DB rows:       {total:,}",
        "",
        "  Table breakdown:",
    ]
    for tbl, cnt in sorted(tbl_rows.items()):
        lines.append(f"    {tbl:<22s} {cnt:>8,} rows")

    lines += [
        "",
        "FILES CREATED",
        "-" * 40,
        "src/etl/normaliser.py     Year & ticker normalisation (44 tests)",
        "src/etl/loader.py         Excel loading infrastructure",
        "src/etl/validator.py      16 DQ rules (CRITICAL / WARNING)",
        "src/etl/db_loader.py      SQLite insert loader with column mapping",
        "src/etl/load_audit.py     Full load orchestrator + audit CSV",
        "src/etl/dq_review.py      10-check DQ review for 5 companies",
        "src/etl/explore.py        12 exploratory SQL queries",
        "db/schema.sql             10-table DDL with PK/FK/virtual column",
        "",
        "tests/etl/test_normalise.py   44 tests",
        "tests/test_schema.py          ~27 tests",
        "tests/test_load_audit.py      ~13 tests",
        "tests/test_dq_review.py       ~18 tests",
        "tests/test_explore.py         ~15 tests",
        "",
        "output/",
        "  validation_failures.csv   DQ rule violations",
        "  load_audit.csv            Per-table load status",
        "  dq_review_report.csv      Per-company DQ findings",
        "  exploratory_queries.csv   SQL exploration results",
        "  nifty100.db               Populated SQLite database",
        "",
        "WHAT WENT WELL",
        "-" * 40,
        "  - Normaliser handles all Indian FY formats (Mar-YY, FY24, YYYY)",
        "  - Column alias mapping in db_loader is adaptable to Excel headers",
        "  - Virtual bs_balance column catches BS drift automatically",
        "  - 16 DQ rules with CRITICAL/WARNING classification",
        "  - FK integrity verified end-to-end across 9 relationships",
        "",
        "WHAT TO IMPROVE",
        "-" * 40,
        "  - shareholding & dividends tables have no source files yet",
        "  - Some Excel column names required manual alias additions",
        "  - Multi-sheet Excel files needed sheet_name=0 fix",
        "  - Year coverage threshold (10 yrs) may need adjustment",
        "",
        "NEXT SPRINT FOCUS",
        "-" * 40,
        "  Sprint 2: Ratio Engine (Days 8-14)",
        "  - Compute 50+ financial ratios from raw data",
        "  - Build ratio comparison & screening queries",
        "  - Add ratio trend analysis",
    ]
    return "\n".join(lines)


# ===================================================================
# CLI
# ===================================================================

if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )
    project_root = str(Path(__file__).resolve().parent.parent.parent)
    db_path = str(Path(project_root) / "output" / "nifty100.db")
    csv_path = str(Path(project_root) / "output" / "exploratory_queries.csv")
    retro_path = str(Path(project_root) / "output" / "sprint1_retro.txt")

    print("=" * 60)
    print("  Nifty 100 — Exploratory SQL Queries")
    print("=" * 60)

    results = run_exploration(db_path, csv_path)

    print(f"\n{'Query':<25s} {'Status':<8s} {'Rows':>6s}")
    print("-" * 42)
    for qid, info in results["summary"].items():
        print(f"  {qid:<25s} {info['status']:<8s} {info['rows']:>6d}")
    print(f"\n  Total rows written: {results['total_rows']}")

    # Sprint retro
    retro_text = generate_retro(project_root)
    Path(retro_path).write_text(retro_text, encoding="utf-8")

    print(f"\nExploration CSV  -> {csv_path}")
    print(f"Sprint Retro     -> {retro_path}")
    print(f"\n{retro_text}")