"""Data-quality rules for the Nifty 100 pipeline."""

from __future__ import annotations

from datetime import date
from typing import Protocol

import pandas as pd


# ---------------------------------------------------------------------------
# Protocol
# ---------------------------------------------------------------------------

class DQRule(Protocol):
    """A callable that returns a list of bad-row integer indices."""

    def __call__(self, df: pd.DataFrame, sector_col: str = "sector") -> list[int]:
        ...


# ---------------------------------------------------------------------------
# Individual rules
# ---------------------------------------------------------------------------

def check_no_negative_market_cap(
    df: pd.DataFrame, sector_col: str = "sector"
) -> list[int]:
    """Rows where market_cap is negative or zero."""
    col = "market_cap"
    if col not in df.columns:
        return []
    return df[df[col].le(0)].index.tolist()


def check_no_negative_revenue(
    df: pd.DataFrame, sector_col: str = "sector"
) -> list[int]:
    """Rows where revenue_from_operations is negative or zero."""
    col = "revenue_from_operations"
    if col not in df.columns:
        return []
    mask = df[col].notna() & (df[col] <= 0)
    return df[mask].index.tolist()


def check_roe_range(
    df: pd.DataFrame, sector_col: str = "sector"
) -> list[int]:
    """Rows where return_on_equity is outside [-100, 500]."""
    col = "return_on_equity"
    if col not in df.columns:
        return []
    mask = df[col].notna() & ((df[col] < -100) | (df[col] > 500))
    return df[mask].index.tolist()


def check_roce_range(
    df: pd.DataFrame, sector_col: str = "sector"
) -> list[int]:
    """Rows where return_on_capital_employed is outside [-100, 500]."""
    col = "return_on_capital_employed"
    if col not in df.columns:
        return []
    mask = df[col].notna() & ((df[col] < -100) | (df[col] > 500))
    return df[mask].index.tolist()


def check_de_non_negative(
    df: pd.DataFrame, sector_col: str = "sector"
) -> list[int]:
    """Rows where debt_to_equity is negative."""
    col = "debt_to_equity"
    if col not in df.columns:
        return []
    mask = df[col].notna() & (df[col] < 0)
    return df[mask].index.tolist()


def check_icr_non_negative(
    df: pd.DataFrame, sector_col: str = "sector"
) -> list[int]:
    """Rows where interest_coverage_ratio is negative."""
    col = "interest_coverage_ratio"
    if col not in df.columns:
        return []
    mask = df[col].notna() & (df[col] < 0)
    return df[mask].index.tolist()


def check_cfo_quality_range(
    df: pd.DataFrame, sector_col: str = "sector"
) -> list[int]:
    """Rows where cfo_quality_score is outside [0, 2]."""
    col = "cfo_quality_score"
    if col not in df.columns:
        return []
    mask = df[col].notna() & ((df[col] < 0) | (df[col] > 2))
    return df[mask].index.tolist()


def check_ocf_ratio_range(
    df: pd.DataFrame, sector_col: str = "sector"
) -> list[int]:
    """Rows where operating_cash_flow_ratio is outside [0, 5]."""
    col = "operating_cash_flow_ratio"
    if col not in df.columns:
        return []
    mask = df[col].notna() & ((df[col] < 0) | (df[col] > 5))
    return df[mask].index.tolist()


def check_cagr_range(
    df: pd.DataFrame, sector_col: str = "sector"
) -> list[int]:
    """Rows where any CAGR column is outside [-80, 300]."""
    cagr_columns = [col for col in df.columns if col.endswith("_cagr_5yr")]
    if not cagr_columns:
        return []

    mask = pd.Series(False, index=df.index)
    for col in cagr_columns:
        series = df[col]
        mask |= series.notna() & ((series < -80) | (series > 300))
    return df[mask].index.tolist()


def check_npm_range(
    df: pd.DataFrame, sector_col: str = "sector"
) -> list[int]:
    """Rows where net_profit_margin is outside [-100, 100]."""
    col = "net_profit_margin"
    if col not in df.columns:
        return []
    mask = df[col].notna() & ((df[col] < -100) | (df[col] > 100))
    return df[mask].index.tolist()


def check_no_duplicate_company_year(
    df: pd.DataFrame, sector_col: str = "sector"
) -> list[int]:
    """Rows that duplicate the same company_name/year pair."""
    required = {"company_name", "year"}
    if not required.issubset(df.columns):
        return []
    duplicated = df.duplicated(subset=["company_name", "year"], keep=False)
    return df[duplicated].index.tolist()


def check_sector_not_null(
    df: pd.DataFrame, sector_col: str = "sector"
) -> list[int]:
    """Rows where sector is null, empty string, or whitespace-only."""
    if sector_col not in df.columns:
        return []
    series = df[sector_col]
    mask = (
        series.isna()
        | series.astype(str).str.strip().eq("")
        | series.astype(str).str.strip().eq("nan")
    )
    return df[mask].index.tolist()


def check_year_range(
    df: pd.DataFrame, sector_col: str = "sector"
) -> list[int]:
    """Rows where year is outside the supported reporting window."""
    col = "year"
    if col not in df.columns:
        return []
    current_year = date.today().year
    mask = df[col].notna() & ((df[col] < 2007) | (df[col] > current_year))
    return df[mask].index.tolist()


FINANCIAL_METRICS: list[str] = [
    "return_on_equity",
    "return_on_capital_employed",
    "net_profit_margin",
    "debt_to_equity",
    "interest_coverage_ratio",
    "cfo_quality_score",
    "operating_cash_flow_ratio",
    "revenue_cagr_5yr",
    "net_profit_cagr_5yr",
    "ebitda_cagr_5yr",
]


def check_not_all_null_metrics(
    df: pd.DataFrame, sector_col: str = "sector"
) -> list[int]:
    """Rows where all tracked financial metrics are null."""
    metric_cols = [col for col in FINANCIAL_METRICS if col in df.columns]
    if not metric_cols:
        return []
    mask = df[metric_cols].isna().all(axis=1)
    return df[mask].index.tolist()


# ---------------------------------------------------------------------------
# Rule registry
# ---------------------------------------------------------------------------

ALL_DQ_RULES: list[DQRule] = [
    check_no_negative_market_cap,
    check_no_negative_revenue,
    check_roe_range,
    check_roce_range,
    check_de_non_negative,
    check_icr_non_negative,
    check_cfo_quality_range,
    check_ocf_ratio_range,
    check_cagr_range,
    check_npm_range,
    check_no_duplicate_company_year,
    check_sector_not_null,
    check_year_range,
    check_not_all_null_metrics,
]

# Public constant — list of rule function names (used by tests)
DQ_RULE_NAMES: list[str] = [r.__name__ for r in ALL_DQ_RULES]


# Backwards-compatible aliases for the newer internal names.
check_market_cap_positive = check_no_negative_market_cap
check_return_on_equity_range = check_roe_range
check_debt_equity_non_negative = check_de_non_negative
check_revenue_positive = check_no_negative_revenue
check_net_profit_margin_range = check_npm_range
check_operating_cash_flow_ratio_range = check_ocf_ratio_range


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def run_dq_checks(
    df: pd.DataFrame,
    sector_col: str = "sector",
) -> dict[str, list[int]]:
    """Run all registered DQ rules. Returns {rule_name: [bad_row_indices]}."""
    results: dict[str, list[int]] = {}
    for rule in ALL_DQ_RULES:
        results[rule.__name__] = rule(df, sector_col=sector_col)
    return results


def dq_summary(
    results: dict[str, list[int]],
) -> dict[str, int | list[str]]:
    """Return summary counts plus the failed rule names."""
    failed = [name for name, rows in results.items() if rows]
    total = sum(len(rows) for rows in results.values())
    return {
        "rules_failed": len(failed),
        "rules_passed": len(results) - len(failed),
        "total_violations": total,
        "failed_rules": failed,
    }