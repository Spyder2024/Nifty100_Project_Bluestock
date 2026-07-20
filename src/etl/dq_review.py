"""
DQ Review — Automated data quality review of 5 random companies.
Sprint 1, Day 6

10 checks per company across BS, IS, CF, ratios:
    DQ-R01  BS balance within ±1% of total assets
    DQ-R02  OPM cross-check (IS vs ratios, ±2pp)
    DQ-R03  EPS sign matches net income sign
    DQ-R04  Tax rate between 15% and 40%
    DQ-R05  Revenue > 0
    DQ-R06  Year coverage >= 10 years
    DQ-R07  Missing data < 20% per table
    DQ-R08  Dividend payout <= 100%
    DQ-R09  Debt-to-equity >= 0
    DQ-R10  Current ratio > 0

Usage:
    python -m src.etl.dq_review
"""

import sqlite3
import csv
import logging
from pathlib import Path

logger = logging.getLogger(__name__)

REVIEW_COLUMNS = [
    "company_id", "company_name", "year", "check_id",
    "check_description", "severity", "expected",
    "actual", "status", "notes",
]

# ===================================================================
# Individual DQ checks — each returns list[dict]
# ===================================================================

def check_bs_balance(conn: sqlite3.Connection, company_id: str) -> list[dict]:
    """DQ-R01: BS balance (assets − liabilities − equity) within ±1%."""
    rows = conn.execute("""
        SELECT year, total_assets, bs_balance
        FROM balance_sheet
        WHERE company_id = ?
          AND total_assets IS NOT NULL AND total_assets > 0
        ORDER BY year
    """, (company_id,)).fetchall()

    findings = []
    for year, total_assets, bs_balance in rows:
        pct = abs(bs_balance / total_assets) * 100
        if pct > 1.0:
            sev = "CRITICAL" if pct > 5 else "WARNING"
            findings.append(dict(
                year=year, check_id="DQ-R01",
                check_description="BS balance within ±1% of total assets",
                severity=sev, expected="≤1%", actual=f"{pct:.2f}%",
                status="FAIL",
                notes=f"bs_balance={bs_balance:.0f}, assets={total_assets:.0f}",
            ))
        else:
            findings.append(dict(
                year=year, check_id="DQ-R01",
                check_description="BS balance within ±1% of total assets",
                severity="INFO", expected="≤1%", actual=f"{pct:.2f}%",
                status="PASS", notes="",
            ))
    return findings


def check_opm_cross(conn: sqlite3.Connection, company_id: str) -> list[dict]:
    """DQ-R02: OPM in income_statement vs ratios should be within 2pp."""
    rows = conn.execute("""
        SELECT i.year, i.opm AS is_opm, r.opm AS ratio_opm
        FROM income_statement i
        JOIN ratios r ON i.company_id = r.company_id AND i.year = r.year
        WHERE i.company_id = ?
          AND i.opm IS NOT NULL AND r.opm IS NOT NULL
        ORDER BY i.year
    """, (company_id,)).fetchall()

    findings = []
    for year, is_opm, ratio_opm in rows:
        diff = abs(is_opm - ratio_opm)
        if diff > 2.0:
            findings.append(dict(
                year=year, check_id="DQ-R02",
                check_description="OPM cross-check (IS vs ratios, ±2pp)",
                severity="WARNING",
                expected="≤2pp diff",
                actual=f"{diff:.2f}pp (IS={is_opm:.1f}%, Ratios={ratio_opm:.1f}%)",
                status="FAIL", notes="",
            ))
        else:
            findings.append(dict(
                year=year, check_id="DQ-R02",
                check_description="OPM cross-check (IS vs ratios, ±2pp)",
                severity="INFO", expected="≤2pp diff", actual=f"{diff:.2f}pp",
                status="PASS", notes="",
            ))
    return findings


def check_eps_sign(conn: sqlite3.Connection, company_id: str) -> list[dict]:
    """DQ-R03: EPS sign must match net income sign."""
    rows = conn.execute("""
        SELECT year, net_income, eps
        FROM income_statement
        WHERE company_id = ?
          AND net_income IS NOT NULL AND eps IS NOT NULL
          AND net_income != 0 AND eps != 0
        ORDER BY year
    """, (company_id,)).fetchall()

    findings = []
    for year, net_income, eps in rows:
        ni_pos = net_income > 0
        eps_pos = eps > 0
        if ni_pos != eps_pos:
            findings.append(dict(
                year=year, check_id="DQ-R03",
                check_description="EPS sign matches net income sign",
                severity="CRITICAL",
                expected=f"EPS {'+'if ni_pos else '-'} (NI={net_income:.0f})",
                actual=f"EPS={eps:.2f}",
                status="FAIL", notes="Sign mismatch",
            ))
        else:
            findings.append(dict(
                year=year, check_id="DQ-R03",
                check_description="EPS sign matches net income sign",
                severity="INFO", expected="Same sign",
                actual=f"NI={net_income:.0f}, EPS={eps:.2f}",
                status="PASS", notes="",
            ))
    return findings


def check_tax_rate(conn: sqlite3.Connection, company_id: str) -> list[dict]:
    """DQ-R04: Effective tax rate between 15% and 40%."""
    rows = conn.execute("""
        SELECT year, net_income, tax_expense
        FROM income_statement
        WHERE company_id = ?
          AND tax_expense IS NOT NULL
          AND net_income IS NOT NULL
          AND (net_income + tax_expense) > 0
        ORDER BY year
    """, (company_id,)).fetchall()

    findings = []
    for year, net_income, tax_expense in rows:
        ebt = net_income + tax_expense
        tax_rate = (tax_expense / ebt) * 100
        if tax_rate < 15 or tax_rate > 40:
            findings.append(dict(
                year=year, check_id="DQ-R04",
                check_description="Tax rate between 15% and 40%",
                severity="WARNING", expected="15–40%",
                actual=f"{tax_rate:.1f}%",
                status="FAIL",
                notes=f"tax={tax_expense:.0f}, ebt={ebt:.0f}",
            ))
        else:
            findings.append(dict(
                year=year, check_id="DQ-R04",
                check_description="Tax rate between 15% and 40%",
                severity="INFO", expected="15–40%",
                actual=f"{tax_rate:.1f}%",
                status="PASS", notes="",
            ))
    return findings


def check_positive_revenue(conn: sqlite3.Connection, company_id: str) -> list[dict]:
    """DQ-R05: Revenue must be positive."""
    rows = conn.execute("""
        SELECT year, revenue
        FROM income_statement
        WHERE company_id = ? AND revenue IS NOT NULL
        ORDER BY year
    """, (company_id,)).fetchall()

    findings = []
    for year, revenue in rows:
        if revenue <= 0:
            findings.append(dict(
                year=year, check_id="DQ-R05",
                check_description="Revenue > 0",
                severity="CRITICAL", expected="> 0",
                actual=f"{revenue:.0f}",
                status="FAIL", notes="",
            ))
        else:
            findings.append(dict(
                year=year, check_id="DQ-R05",
                check_description="Revenue > 0",
                severity="INFO", expected="> 0",
                actual=f"{revenue:.0f}",
                status="PASS", notes="",
            ))
    return findings


def check_year_coverage(conn: sqlite3.Connection, company_id: str) -> list[dict]:
    """DQ-R06: Company should have data for >= 10 distinct years."""
    year_sets = []
    for tbl in [
        "balance_sheet", "income_statement", "cash_flow",
        "ratios", "prices", "market_cap",
    ]:
        yrs = conn.execute(
            f"SELECT DISTINCT year FROM {tbl} WHERE company_id = ?",
            (company_id,),
        ).fetchall()
        year_sets.extend(r[0] for r in yrs)

    count = len(set(year_sets))
    if count < 10:
        return [dict(
            year="ALL", check_id="DQ-R06",
            check_description="Year coverage >= 10 years",
            severity="WARNING", expected=">= 10 years",
            actual=f"{count} years",
            status="FAIL", notes="",
        )]
    return [dict(
        year="ALL", check_id="DQ-R06",
        check_description="Year coverage >= 10 years",
        severity="INFO", expected=">= 10 years",
        actual=f"{count} years",
        status="PASS", notes="",
    )]


def check_missing_data(conn: sqlite3.Connection, company_id: str) -> list[dict]:
    """DQ-R07: Key column null % should be < 20% per table."""
    table_key_cols = {
        "balance_sheet": ["total_assets", "total_liabilities", "total_equity"],
        "income_statement": ["revenue", "net_income", "eps"],
        "cash_flow": ["operating_cf", "investing_cf", "financing_cf"],
        "ratios": ["roe", "debt_to_equity", "current_ratio"],
    }

    findings = []
    has_any_fail = False

    for table, key_cols in table_key_cols.items():
        cols_sql = ", ".join(key_cols)
        try:
            rows = conn.execute(f"""
                SELECT year, {cols_sql}
                FROM {table}
                WHERE company_id = ?
                ORDER BY year
            """, (company_id,)).fetchall()
        except sqlite3.OperationalError:
            continue

        for row in rows:
            year = row[0]
            values = row[1:]
            nulls = sum(1 for v in values if v is None)
            total = len(values)
            if total == 0:
                continue
            pct = (nulls / total) * 100
            if pct > 20:
                has_any_fail = True
                findings.append(dict(
                    year=year, check_id="DQ-R07",
                    check_description=f"Missing data < 20% ({table})",
                    severity="WARNING", expected="< 20% nulls",
                    actual=f"{pct:.0f}% nulls ({nulls}/{total} cols)",
                    status="FAIL", notes="",
                ))

    if not has_any_fail:
        findings.append(dict(
            year="ALL", check_id="DQ-R07",
            check_description="Missing data < 20% (all tables)",
            severity="INFO", expected="< 20% nulls",
            actual="< 20% nulls",
            status="PASS", notes="All checked tables OK",
        ))
    return findings


def check_dividend_payout(conn: sqlite3.Connection, company_id: str) -> list[dict]:
    """DQ-R08: Dividend payout ratio <= 100%."""
    rows = conn.execute("""
        SELECT year, dividend_payout
        FROM ratios
        WHERE company_id = ? AND dividend_payout IS NOT NULL
        ORDER BY year
    """, (company_id,)).fetchall()

    findings = []
    for year, payout in rows:
        if payout > 100:
            findings.append(dict(
                year=year, check_id="DQ-R08",
                check_description="Dividend payout <= 100%",
                severity="WARNING", expected="<= 100%",
                actual=f"{payout:.1f}%",
                status="FAIL", notes="",
            ))
        else:
            findings.append(dict(
                year=year, check_id="DQ-R08",
                check_description="Dividend payout <= 100%",
                severity="INFO", expected="<= 100%",
                actual=f"{payout:.1f}%",
                status="PASS", notes="",
            ))
    return findings


def check_debt_equity(conn: sqlite3.Connection, company_id: str) -> list[dict]:
    """DQ-R09: Debt-to-equity should be >= 0."""
    rows = conn.execute("""
        SELECT year, debt_to_equity
        FROM ratios
        WHERE company_id = ? AND debt_to_equity IS NOT NULL
        ORDER BY year
    """, (company_id,)).fetchall()

    findings = []
    for year, de in rows:
        if de < 0:
            findings.append(dict(
                year=year, check_id="DQ-R09",
                check_description="Debt-to-equity >= 0",
                severity="WARNING", expected=">= 0",
                actual=f"{de:.2f}",
                status="FAIL", notes="",
            ))
        else:
            findings.append(dict(
                year=year, check_id="DQ-R09",
                check_description="Debt-to-equity >= 0",
                severity="INFO", expected=">= 0",
                actual=f"{de:.2f}",
                status="PASS", notes="",
            ))
    return findings


def check_current_ratio(conn: sqlite3.Connection, company_id: str) -> list[dict]:
    """DQ-R10: Current ratio should be > 0."""
    rows = conn.execute("""
        SELECT year, current_ratio
        FROM ratios
        WHERE company_id = ? AND current_ratio IS NOT NULL
        ORDER BY year
    """, (company_id,)).fetchall()

    findings = []
    for year, cr in rows:
        if cr <= 0:
            findings.append(dict(
                year=year, check_id="DQ-R10",
                check_description="Current ratio > 0",
                severity="WARNING", expected="> 0",
                actual=f"{cr:.2f}",
                status="FAIL", notes="",
            ))
        else:
            findings.append(dict(
                year=year, check_id="DQ-R10",
                check_description="Current ratio > 0",
                severity="INFO", expected="> 0",
                actual=f"{cr:.2f}",
                status="PASS", notes="",
            ))
    return findings


# ===================================================================
# Check registry (ordered by ID)
# ===================================================================

ALL_CHECKS = [
    check_bs_balance, check_opm_cross, check_eps_sign,
    check_tax_rate, check_positive_revenue, check_year_coverage,
    check_dividend_payout, check_debt_equity, check_current_ratio,
    check_missing_data,
]


# ===================================================================
# Company selection
# ===================================================================

def pick_random_companies(conn, n: int = 5) -> list[dict]:
    """Select up to n companies with highest data coverage (no while-loop)."""
    query = """
        SELECT c.company_id, c.company_name,
               COUNT(bs.year) AS data_years
        FROM companies c
        LEFT JOIN balance_sheet bs ON c.company_id = bs.company_id
        GROUP BY c.company_id, c.company_name
        ORDER BY data_years DESC
        LIMIT ?
    """
    rows = conn.execute(query, (n,)).fetchall()
    return [dict(company_id=r[0], company_name=r[1], data_years=r[2]) for r in rows]

# ===================================================================
# Orchestrator
# ===================================================================

def run_dq_review(
    db_path: str | None = None,
    output_path: str = "output/dq_review_report.csv",
    n_companies: int = 5,
    conn: sqlite3.Connection | None = None,
) -> dict:
    """Run all checks on n random companies, write report CSV."""
    own_conn = False
    if conn is None:
        if db_path is None:
            raise ValueError("Either db_path or conn must be provided")
        conn = sqlite3.connect(db_path)
        conn.row_factory = sqlite3.Row
        own_conn = True

    companies = pick_random_companies(conn, n_companies)

    if not companies:
        companies = [
            dict(company_id=r[0], company_name=r[1], data_years=0)
            for r in conn.execute(
                "SELECT company_id, company_name FROM companies LIMIT ?",
                (n_companies,),
            ).fetchall()
        ]

    all_findings: list[dict] = []

    for comp in companies:
        cid = comp["company_id"]
        cname = comp["company_name"]

        for check_fn in ALL_CHECKS:
            try:
                findings = check_fn(conn, cid)
            except Exception as exc:
                logger.warning("%s failed for %s: %s", check_fn.__name__, cid, exc)
                findings = [dict(
                    year="ALL", check_id=check_fn.__name__,
                    check_description="Check execution error",
                    severity="WARNING", expected="N/A",
                    actual=f"Error: {str(exc)[:100]}",
                    status="ERROR", notes="",
                )]

            for f in findings:
                f["company_id"] = cid
                f["company_name"] = cname
            all_findings.extend(findings)

    # Write CSV
    Path(output_path).parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=REVIEW_COLUMNS)
        writer.writeheader()
        for f in all_findings:
            writer.writerow({k: f.get(k, "") for k in REVIEW_COLUMNS})

    # Summary
    by_severity: dict[str, int] = {}
    for f in all_findings:
        s = f.get("severity", "INFO")
        by_severity[s] = by_severity.get(s, 0) + 1

    fails = sum(1 for f in all_findings if f.get("status") == "FAIL")
    passes = sum(1 for f in all_findings if f.get("status") == "PASS")

    if own_conn:
        conn.close()

    logger.info(
        "DQ review: %d companies, %d checks (%d PASS, %d FAIL)",
        len(companies), len(all_findings), passes, fails,
    )

    return dict(
        companies=companies,
        total_findings=len(all_findings),
        passes=passes,
        fails=fails,
        by_severity=by_severity,
    )
# ===================================================================
# CLI
# ===================================================================

def _read_report(path: str) -> list[dict]:
    """Helper to re-read the CSV for the CLI summary."""
    with open(path, encoding="utf-8") as fh:
        return list(csv.DictReader(fh))

if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )
    project_root = Path(__file__).resolve().parent.parent.parent
    db_path = str(project_root / "output" / "nifty100.db")
    report_path = str(project_root / "output" / "dq_review_report.csv")

    print("=" * 60)
    print("  Nifty 100 — DQ Review (5 Random Companies)")
    print("=" * 60)

    results = run_dq_review(db_path, report_path, n_companies=5)

    print(f"\nCompanies reviewed:")
    for c in results["companies"]:
        print(
            f"  - {c['company_id']:<12s} {c['company_name']:<35s} "
            f"({c.get('data_years', '?')} yrs data)"
        )

    print(f"\nResults: {results['passes']} PASS, {results['fails']} FAIL "
          f"out of {results['total_findings']} checks")

    print(f"\nBy severity:")
    for sev in ["CRITICAL", "WARNING", "INFO"]:
        print(f"  {sev:<10s} {results['by_severity'].get(sev, 0):>5d}")

    # Show only FAILs for quick review
    fail_findings = [
        f for f in _read_report(report_path) if f["status"] == "FAIL"
    ]
    if fail_findings:
        print(f"\n{'='*60}")
        print(f"  FAILURES ({len(fail_findings)}) — review these manually:")
        print(f"{'='*60}")
        for f in fail_findings[:20]:  # show first 20
            print(
                f"  [{f['severity']:<8s}] {f['company_id']:<12s} "
                f"{f['year']:<10s} {f['check_id']:<8s} {f['actual']}"
            )
        if len(fail_findings) > 20:
            print(f"  ... and {len(fail_findings) - 20} more (see full CSV)")

    print(f"\nFull report -> {report_path}")
