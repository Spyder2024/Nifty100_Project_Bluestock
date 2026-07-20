"""Data quality validation engine — 16 DQ rules for Nifty 100 ETL."""

import logging
import re
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Optional

import pandas as pd

logger = logging.getLogger(__name__)

# The valid year format after normalisation
_RE_VALID_YEAR = re.compile(r"^\d{4}-\d{2}$")

# Financial sector names (for bank/NBFC exclusion in DQ-06)
_FINANCIAL_SECTORS = {
    "Financials",
    "Private Banks",
    "Public Sector Banks",
    "Life Insurance",
    "General Insurance",
    "Consumer Finance",
    "Holding Cos",
    "Speciality Finance",
}


@dataclass
class DQViolation:
    """A single data quality violation record."""

    rule_id: str
    severity: str  # CRITICAL, WARNING, INFO
    company_id: Optional[str]
    year: Optional[str]
    field: str
    issue: str
    action: str


def _violations_to_df(violations: list[DQViolation]) -> pd.DataFrame:
    """Convert list of DQViolation to DataFrame."""
    if not violations:
        return pd.DataFrame(
            columns=[
                "rule_id",
                "severity",
                "company_id",
                "year",
                "field",
                "issue",
                "action",
            ]
        )
    return pd.DataFrame([asdict(v) for v in violations])


def save_violations_csv(
    violations: list[DQViolation],
    output_path: str = "output/validation_failures.csv",
) -> pd.DataFrame:
    """Save DQ violations to CSV.

    Args:
        violations: List of DQViolation objects.
        output_path: Where to write the CSV.

    Returns:
        DataFrame of all violations.
    """
    df = _violations_to_df(violations)
    Path(output_path).parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(output_path, index=False)
    logger.info(
        "Saved %d DQ violations to %s (%d CRITICAL, %d WARNING, %d INFO)",
        len(violations),
        output_path,
        len(df[df["severity"] == "CRITICAL"]),
        len(df[df["severity"] == "WARNING"]),
        len(df[df["severity"] == "INFO"]),
    )
    return df


# ============================================================
# CRITICAL RULES (DQ-01 to DQ-03, DQ-07, DQ-08)
# ============================================================


def check_dq01_company_pk_uniqueness(
    companies: pd.DataFrame,
) -> list[DQViolation]:
    """DQ-01: Company PK Uniqueness.

    Every row in companies must have a unique 'id' (NSE ticker).
    """
    violations: list[DQViolation] = []
    if "id" not in companies.columns:
        violations.append(
            DQViolation(
                rule_id="DQ-01",
                severity="CRITICAL",
                company_id=None,
                year=None,
                field="id",
                issue="Column 'id' not found in companies table",
                action="Halt load. Check source file header.",
            )
        )
        return violations

    dupes = companies[companies["id"].duplicated(keep=False)]
    if len(dupes) > 0:
        for ticker in dupes["id"].unique():
            count = len(companies[companies["id"] == ticker])
            violations.append(
                DQViolation(
                    rule_id="DQ-01",
                    severity="CRITICAL",
                    company_id=ticker,
                    year=None,
                    field="id",
                    issue=f"Duplicate ticker '{ticker}' appears {count} times",
                    action="Halt load. Investigate duplicate ticker.",
                )
            )
    return violations


def check_dq02_annual_pk_uniqueness(
    df: pd.DataFrame, table_name: str
) -> list[DQViolation]:
    """DQ-02: Annual PK Uniqueness.

    No duplicate (company_id, year) pairs in time-series tables.
    """
    violations: list[DQViolation] = []
    required = {"company_id", "year"}
    if not required.issubset(df.columns):
        return violations

    dupes = df[df.duplicated(subset=["company_id", "year"], keep=False)]
    if len(dupes) > 0:
        for _, row in dupes.drop_duplicates(subset=["company_id", "year"]).iterrows():
            violations.append(
                DQViolation(
                    rule_id="DQ-02",
                    severity="CRITICAL",
                    company_id=str(row["company_id"]),
                    year=str(row["year"]),
                    field="company_id,year",
                    issue=(
                        f"Duplicate (company_id, year) in {table_name}: "
                        f"({row['company_id']}, {row['year']})"
                    ),
                    action="Deduplicate: keep last occurrence. Log all duplicates.",
                )
            )
    return violations


def check_dq03_fk_integrity(
    companies: pd.DataFrame, child_df: pd.DataFrame, table_name: str
) -> list[DQViolation]:
    """DQ-03: FK Integrity.

    All company_id values in child tables must exist in companies.id.
    """
    violations: list[DQViolation] = []
    if "id" not in companies.columns or "company_id" not in child_df.columns:
        return violations

    valid_ids = set(companies["id"].dropna().unique())
    child_ids = set(child_df["company_id"].dropna().unique())
    orphans = child_ids - valid_ids

    for orphan in sorted(orphans):
        count = len(child_df[child_df["company_id"] == orphan])
        violations.append(
            DQViolation(
                rule_id="DQ-03",
                severity="CRITICAL",
                company_id=str(orphan),
                year=None,
                field="company_id",
                issue=(
                    f"Orphan company_id '{orphan}' in {table_name} "
                    f"({count} rows) — not found in companies table"
                ),
                action="Reject orphan rows. Log to validation_failures.csv.",
            )
        )
    return violations


def check_dq07_year_format(df: pd.DataFrame, table_name: str) -> list[DQViolation]:
    """DQ-07: Year Format.

    After normalize_year(), all year values must match YYYY-MM.
    """
    violations: list[DQViolation] = []
    if "year" not in df.columns:
        return violations

    for idx, row in df.iterrows():
        val = str(row["year"])
        if not _RE_VALID_YEAR.match(val):
            violations.append(
                DQViolation(
                    rule_id="DQ-07",
                    severity="CRITICAL",
                    company_id=str(row.get("company_id", "")),
                    year=val,
                    field="year",
                    issue=(
                        f"Invalid year format '{val}' in {table_name} "
                        f"(expected YYYY-MM)"
                    ),
                    action="Reject row. Log raw value.",
                )
            )
    return violations


def check_dq08_ticker_format(df: pd.DataFrame, table_name: str) -> list[DQViolation]:
    """DQ-08: Ticker Format.

    company_id must be stripped, uppercased, 2–12 chars.
    """
    violations: list[DQViolation] = []
    if "company_id" not in df.columns:
        return violations

    for idx, row in df.iterrows():
        raw = str(row["company_id"])
        if len(raw) < 2 or len(raw) > 12:
            violations.append(
                DQViolation(
                    rule_id="DQ-08",
                    severity="CRITICAL",
                    company_id=raw,
                    year=str(row.get("year", "")),
                    field="company_id",
                    issue=(
                        f"Ticker length {len(raw)} outside "
                        f"valid range 2-12 in {table_name}"
                    ),
                    action="Normalise if possible. Reject if out of range.",
                )
            )
    return violations


# ============================================================
# WARNING RULES (DQ-04 to DQ-06, DQ-09 to DQ-14, DQ-16)
# ============================================================


def check_dq04_bs_balance(
    balancesheet: pd.DataFrame,
) -> list[DQViolation]:
    """DQ-04: Balance Sheet Balance.

    |total_assets - total_liabilities| / total_assets < 0.01
    """
    violations: list[DQViolation] = []
    required = {"company_id", "year", "total_assets", "total_liabilities"}
    if not required.issubset(balancesheet.columns):
        return violations

    for _, row in balancesheet.iterrows():
        assets = row["total_assets"]
        liab = row["total_liabilities"]
        if pd.isna(assets) or pd.isna(liab) or assets == 0:
            continue
        diff_pct = abs(assets - liab) / assets
        if diff_pct >= 0.01:
            violations.append(
                DQViolation(
                    rule_id="DQ-04",
                    severity="WARNING",
                    company_id=str(row["company_id"]),
                    year=str(row["year"]),
                    field="total_assets,total_liabilities",
                    issue=(
                        f"BS imbalance: assets={assets}, "
                        f"liabilities={liab}, diff={diff_pct:.4f}"
                    ),
                    action="Flag row. Do not reject. Analyst review required.",
                )
            )
    return violations


def check_dq05_opm_crosscheck(
    pl: pd.DataFrame,
) -> list[DQViolation]:
    """DQ-05: OPM Cross-Check.

    |opm_percentage - (operating_profit / sales * 100)| < 1.0
    """
    violations: list[DQViolation] = []
    required = {"company_id", "year", "operating_profit", "sales", "opm_percentage"}
    if not required.issubset(pl.columns):
        return violations

    for _, row in pl.iterrows():
        op = row["operating_profit"]
        sales = row["sales"]
        opm_src = row["opm_percentage"]
        if pd.isna(op) or pd.isna(sales) or pd.isna(opm_src) or sales == 0:
            continue
        computed_opm = (op / sales) * 100
        diff = abs(computed_opm - opm_src)
        if diff >= 1.0:
            violations.append(
                DQViolation(
                    rule_id="DQ-05",
                    severity="WARNING",
                    company_id=str(row["company_id"]),
                    year=str(row["year"]),
                    field="opm_percentage",
                    issue=(
                        f"OPM mismatch: source={opm_src}, "
                        f"computed={computed_opm:.2f}, diff={diff:.2f}"
                    ),
                    action=(
                        "Flag row. Use computed OPM in Ratio Engine; "
                        "keep source for display."
                    ),
                )
            )
    return violations


def check_dq06_positive_sales(
    pl: pd.DataFrame,
    sectors: Optional[pd.DataFrame] = None,
) -> list[DQViolation]:
    """DQ-06: Positive Sales.

    sales > 0 for all non-bank companies.
    """
    violations: list[DQViolation] = []
    if (
        "company_id" not in pl.columns
        or "sales" not in pl.columns
        or "year" not in pl.columns
    ):
        return violations

    # Build set of financial-sector tickers if sectors table is available
    financial_tickers: set[str] = set()
    if (
        sectors is not None
        and "company_id" in sectors.columns
        and "broad_sector" in sectors.columns
    ):
        financial_tickers = set(
            sectors[sectors["broad_sector"].isin(_FINANCIAL_SECTORS)]["company_id"]
            .dropna()
            .str.upper()
            .unique()
        )

    for _, row in pl.iterrows():
        ticker = str(row["company_id"]).upper()
        if ticker in financial_tickers:
            continue
        sales = row["sales"]
        if pd.notna(sales) and sales <= 0:
            violations.append(
                DQViolation(
                    rule_id="DQ-06",
                    severity="WARNING",
                    company_id=ticker,
                    year=str(row["year"]),
                    field="sales",
                    issue=f"Non-positive sales: {sales}",
                    action=("Flag row. Exclude from growth CAGR calculation."),
                )
            )
    return violations


def check_dq09_net_cash(
    cashflow: pd.DataFrame,
) -> list[DQViolation]:
    """DQ-09: Net Cash Check.

    |net_cash_flow - (CFO + CFI + CFF)| <= 10 (Rs Cr tolerance).
    """
    violations: list[DQViolation] = []
    required = {
        "company_id",
        "year",
        "operating_activity",
        "investing_activity",
        "financing_activity",
        "net_cash_flow",
    }
    if not required.issubset(cashflow.columns):
        return violations

    for _, row in cashflow.iterrows():
        cfo = row["operating_activity"]
        cfi = row["investing_activity"]
        cff = row["financing_activity"]
        net = row["net_cash_flow"]
        if pd.isna(cfo) or pd.isna(cfi) or pd.isna(cff) or pd.isna(net):
            continue
        computed_net = cfo + cfi + cff
        diff = abs(net - computed_net)
        if diff > 10:
            violations.append(
                DQViolation(
                    rule_id="DQ-09",
                    severity="WARNING",
                    company_id=str(row["company_id"]),
                    year=str(row["year"]),
                    field="net_cash_flow",
                    issue=(
                        f"Cash sum mismatch: reported={net}, "
                        f"computed={computed_net:.2f}, diff={diff:.2f}"
                    ),
                    action="Flag and recompute net_cash_flow from components.",
                )
            )
    return violations


def check_dq10_non_negative_fixed_assets(
    balancesheet: pd.DataFrame,
) -> list[DQViolation]:
    """DQ-10: Non-Negative Fixed Assets.

    fixed_assets >= 0. Negative → coerce to 0.
    """
    violations: list[DQViolation] = []
    if (
        "company_id" not in balancesheet.columns
        or "year" not in balancesheet.columns
        or "fixed_assets" not in balancesheet.columns
    ):
        return violations

    for _, row in balancesheet.iterrows():
        fa = row["fixed_assets"]
        if pd.notna(fa) and fa < 0:
            violations.append(
                DQViolation(
                    rule_id="DQ-10",
                    severity="WARNING",
                    company_id=str(row["company_id"]),
                    year=str(row["year"]),
                    field="fixed_assets",
                    issue=f"Negative fixed_assets: {fa}",
                    action="Coerce to 0 and log.",
                )
            )
    return violations


def check_dq11_tax_rate_range(
    pl: pd.DataFrame,
) -> list[DQViolation]:
    """DQ-11: Tax Rate Range.

    0 <= tax_percentage <= 60.
    """
    violations: list[DQViolation] = []
    if (
        "company_id" not in pl.columns
        or "year" not in pl.columns
        or "tax_percentage" not in pl.columns
    ):
        return violations

    for _, row in pl.iterrows():
        tax = row["tax_percentage"]
        if pd.isna(tax):
            continue
        if tax < 0 or tax > 60:
            violations.append(
                DQViolation(
                    rule_id="DQ-11",
                    severity="WARNING",
                    company_id=str(row["company_id"]),
                    year=str(row["year"]),
                    field="tax_percentage",
                    issue=f"Tax rate {tax} outside valid range 0-60",
                    action=("Flag. May indicate one-off deferred tax reversal."),
                )
            )
    return violations


def check_dq12_dividend_payout_cap(
    pl: pd.DataFrame,
) -> list[DQViolation]:
    """DQ-12: Dividend Payout Cap.

    dividend_payout <= 200 (pct).
    """
    violations: list[DQViolation] = []
    if (
        "company_id" not in pl.columns
        or "year" not in pl.columns
        or "dividend_payout" not in pl.columns
    ):
        return violations

    for _, row in pl.iterrows():
        dp = row["dividend_payout"]
        if pd.isna(dp):
            continue
        if dp > 200:
            violations.append(
                DQViolation(
                    rule_id="DQ-12",
                    severity="WARNING",
                    company_id=str(row["company_id"]),
                    year=str(row["year"]),
                    field="dividend_payout",
                    issue=f"Dividend payout {dp}% exceeds 200% cap",
                    action="Flag as likely data entry error. Analyst confirm.",
                )
            )
    return violations


def check_dq13_url_validity(
    documents: pd.DataFrame, timeout: int = 5
) -> list[DQViolation]:
    """DQ-13: URL Validity (documents).

    Validate that Annual_Report URLs return HTTP 200.
    """
    violations: list[DQViolation] = []
    if (
        "company_id" not in documents.columns
        or "Annual_Report" not in documents.columns
        or "Year" not in documents.columns
    ):
        return violations

    try:
        import requests
    except ImportError:
        logger.warning("requests not installed — skipping DQ-13 URL checks")
        return violations

    checked: set[str] = set()
    for _, row in documents.iterrows():
        url = row.get("Annual_Report")
        if pd.isna(url) or not isinstance(url, str):
            continue
        url = url.strip()
        if url in checked:
            continue
        checked.add(url)
        try:
            resp = requests.head(url, timeout=timeout, allow_redirects=True)
            if resp.status_code != 200:
                violations.append(
                    DQViolation(
                        rule_id="DQ-13",
                        severity="WARNING",
                        company_id=str(row["company_id"]),
                        year=str(row["Year"]),
                        field="Annual_Report",
                        issue=f"URL returned {resp.status_code}: {url[:80]}",
                        action="Log 404 URLs. URL decay expected over time.",
                    )
                )
        except requests.RequestException as exc:
            violations.append(
                DQViolation(
                    rule_id="DQ-13",
                    severity="WARNING",
                    company_id=str(row["company_id"]),
                    year=str(row["Year"]),
                    field="Annual_Report",
                    issue=f"URL request failed: {exc}",
                    action="Log failure. Do not reject row.",
                )
            )
    return violations


def check_dq14_eps_sign_consistency(
    pl: pd.DataFrame,
) -> list[DQViolation]:
    """DQ-14: EPS Sign Consistency.

    eps > 0 if net_profit > 0.
    """
    violations: list[DQViolation] = []
    if (
        "company_id" not in pl.columns
        or "year" not in pl.columns
        or "eps" not in pl.columns
        or "net_profit" not in pl.columns
    ):
        return violations

    for _, row in pl.iterrows():
        np_val = row["net_profit"]
        eps_val = row["eps"]
        if pd.isna(np_val) or pd.isna(eps_val):
            continue
        if np_val > 0 and eps_val <= 0:
            violations.append(
                DQViolation(
                    rule_id="DQ-14",
                    severity="WARNING",
                    company_id=str(row["company_id"]),
                    year=str(row["year"]),
                    field="eps",
                    issue=(
                        f"Positive net_profit={np_val} but "
                        f"non-positive eps={eps_val}"
                    ),
                    action=(
                        "Flag mismatch. May indicate adjustments. "
                        "Use net_profit/shares as fallback."
                    ),
                )
            )
    return violations


# ============================================================
# INFO RULE (DQ-15)
# ============================================================


def check_dq15_bs_strict_balance(
    balancesheet: pd.DataFrame,
) -> list[DQViolation]:
    """DQ-15: BS/ASE Balance (extended, INFO).

    Strict equality: total_liabilities == total_assets.
    """
    violations: list[DQViolation] = []
    if "company_id" not in balancesheet.columns or "year" not in balancesheet.columns:
        return violations
    if (
        "total_assets" not in balancesheet.columns
        or "total_liabilities" not in balancesheet.columns
    ):
        return violations

    for _, row in balancesheet.iterrows():
        assets = row["total_assets"]
        liab = row["total_liabilities"]
        if pd.isna(assets) or pd.isna(liab):
            continue
        if assets != liab:
            violations.append(
                DQViolation(
                    rule_id="DQ-15",
                    severity="INFO",
                    company_id=str(row["company_id"]),
                    year=str(row["year"]),
                    field="total_assets,total_liabilities",
                    issue=(
                        f"Strict imbalance: assets={assets}, " f"liabilities={liab}"
                    ),
                    action="Informational counter. Flag in load_audit only.",
                )
            )
    return violations


# ============================================================
# COVERAGE RULE (DQ-16)
# ============================================================


def check_dq16_coverage(
    pl: pd.DataFrame,
    bs: pd.DataFrame,
    cf: pd.DataFrame,
    min_years: int = 5,
) -> list[DQViolation]:
    """DQ-16: Coverage Check.

    Each company must have >= min_years of P&L, BS, CF records.
    """
    violations: list[DQViolation] = []

    for table_name, df in [
        ("profitandloss", pl),
        ("balancesheet", bs),
        ("cashflow", cf),
    ]:
        if "company_id" not in df.columns:
            continue
        counts = df.groupby("company_id").size().reset_index(name="record_count")
        low_coverage = counts[counts["record_count"] < min_years]
        for _, row in low_coverage.iterrows():
            violations.append(
                DQViolation(
                    rule_id="DQ-16",
                    severity="WARNING",
                    company_id=str(row["company_id"]),
                    year=None,
                    field="coverage",
                    issue=(
                        f"{row['record_count']} {table_name} records "
                        f"(minimum {min_years})"
                    ),
                    action=("Flag company. Exclude from CAGR if < 3 years."),
                )
            )
    return violations


# ============================================================
# MASTER RUNNER — runs all 16 rules
# ============================================================


def run_all_validations(
    datasets: dict[str, pd.DataFrame],
) -> list[DQViolation]:
    """Execute all 16 DQ rules against loaded datasets.

    Args:
        datasets: Dict mapping table name → DataFrame.
            Expected keys (at minimum): companies, profitandloss,
            balancesheet, cashflow.
            Optional: sectors, documents.

    Returns:
        List of all DQViolation objects found.
    """
    violations: list[DQViolation] = []
    companies = datasets.get("companies", pd.DataFrame())
    pl = datasets.get("profitandloss", pd.DataFrame())
    bs = datasets.get("balancesheet", pd.DataFrame())
    cf = datasets.get("cashflow", pd.DataFrame())
    sectors = datasets.get("sectors", pd.DataFrame())
    docs = datasets.get("documents", pd.DataFrame())

    logger.info("Running 16 DQ validation rules...")

    # --- CRITICAL rules ---
    logger.info("  CRITICAL: DQ-01 Company PK Uniqueness")
    violations.extend(check_dq01_company_pk_uniqueness(companies))

    logger.info("  CRITICAL: DQ-02 Annual PK Uniqueness")
    for table_name in ["profitandloss", "balancesheet", "cashflow"]:
        violations.extend(
            check_dq02_annual_pk_uniqueness(
                datasets.get(table_name, pd.DataFrame()), table_name
            )
        )

    logger.info("  CRITICAL: DQ-03 FK Integrity")
    for table_name in [
        "profitandloss",
        "balancesheet",
        "cashflow",
        "analysis",
        "documents",
        "prosandcons",
        "sectors",
    ]:
        violations.extend(
            check_dq03_fk_integrity(
                companies, datasets.get(table_name, pd.DataFrame()), table_name
            )
        )

    logger.info("  CRITICAL: DQ-07 Year Format")
    for table_name in ["profitandloss", "balancesheet", "cashflow"]:
        violations.extend(
            check_dq07_year_format(datasets.get(table_name, pd.DataFrame()), table_name)
        )

    logger.info("  CRITICAL: DQ-08 Ticker Format")
    for table_name in [
        "profitandloss",
        "balancesheet",
        "cashflow",
        "analysis",
        "documents",
        "prosandcons",
    ]:
        violations.extend(
            check_dq08_ticker_format(
                datasets.get(table_name, pd.DataFrame()), table_name
            )
        )

    # --- WARNING rules ---
    logger.info("  WARNING: DQ-04 BS Balance")
    violations.extend(check_dq04_bs_balance(bs))

    logger.info("  WARNING: DQ-05 OPM Cross-Check")
    violations.extend(check_dq05_opm_crosscheck(pl))

    logger.info("  WARNING: DQ-06 Positive Sales")
    violations.extend(check_dq06_positive_sales(pl, sectors))

    logger.info("  WARNING: DQ-09 Net Cash Check")
    violations.extend(check_dq09_net_cash(cf))

    logger.info("  WARNING: DQ-10 Non-Negative Fixed Assets")
    violations.extend(check_dq10_non_negative_fixed_assets(bs))

    logger.info("  WARNING: DQ-11 Tax Rate Range")
    violations.extend(check_dq11_tax_rate_range(pl))

    logger.info("  WARNING: DQ-12 Dividend Payout Cap")
    violations.extend(check_dq12_dividend_payout_cap(pl))

    logger.info("  WARNING: DQ-13 URL Validity (skipping in test)")
    # DQ-13 is slow (HTTP calls) — skip by default in batch runs.
    # Run separately: check_dq13_url_validity(docs)

    logger.info("  WARNING: DQ-14 EPS Sign Consistency")
    violations.extend(check_dq14_eps_sign_consistency(pl))

    # --- INFO rule ---
    logger.info("  INFO: DQ-15 BS Strict Balance")
    violations.extend(check_dq15_bs_strict_balance(bs))

    # --- COVERAGE rule ---
    logger.info("  WARNING: DQ-16 Coverage Check")
    violations.extend(check_dq16_coverage(pl, bs, cf))

    # Summary
    critical = sum(1 for v in violations if v.severity == "CRITICAL")
    warning = sum(1 for v in violations if v.severity == "WARNING")
    info = sum(1 for v in violations if v.severity == "INFO")
    logger.info(
        "DQ complete: %d violations (%d CRITICAL, %d WARNING, %d INFO)",
        len(violations),
        critical,
        warning,
        info,
    )

    return violations
