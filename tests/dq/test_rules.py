"""tests/dq/test_rules.py — 14+ Unit Tests for individual Data Quality Rules.

Sprint 7, Day 41

Each test crafts a minimal DataFrame violating exactly one DQ rule
and verifies the correct rule_id and severity are returned.
"""

import pandas as pd
from src.etl.validator import (
    check_dq01_company_pk_uniqueness,
    check_dq02_annual_pk_uniqueness,
    check_dq03_fk_integrity,
    check_dq04_bs_balance,
    check_dq05_opm_crosscheck,
    check_dq06_positive_sales,
    check_dq07_year_format,
    check_dq08_ticker_format,
    check_dq09_net_cash,
    check_dq10_non_negative_fixed_assets,
    check_dq11_tax_rate_range,
    check_dq12_dividend_payout_cap,
    check_dq14_eps_sign_consistency,
    check_dq15_bs_strict_balance,
    check_dq16_coverage,
)


def test_01_dq01_company_pk_uniqueness():
    """DQ-01: Duplicate company ticker raises CRITICAL violation."""
    df = pd.DataFrame({"id": ["INFY", "TCS", "INFY"]})
    violations = check_dq01_company_pk_uniqueness(df)
    assert len(violations) >= 1
    assert violations[0].rule_id == "DQ-01"
    assert violations[0].severity == "CRITICAL"
    assert violations[0].company_id == "INFY"


def test_02_dq02_annual_pk_uniqueness():
    """DQ-02: Duplicate (company_id, year) pair raises CRITICAL violation."""
    df = pd.DataFrame(
        {
            "company_id": ["INFY", "INFY"],
            "year": ["2024-03", "2024-03"],
            "sales": [1000, 1050],
        }
    )
    violations = check_dq02_annual_pk_uniqueness(df, "profitandloss")
    assert len(violations) >= 1
    assert violations[0].rule_id == "DQ-02"
    assert violations[0].severity == "CRITICAL"
    assert violations[0].company_id == "INFY"


def test_03_dq03_fk_integrity():
    """DQ-03: Orphan company_id not in parent table raises CRITICAL violation."""
    parent = pd.DataFrame({"id": ["INFY", "TCS"]})
    child = pd.DataFrame(
        {"company_id": ["INFY", "UNKNOWN_CO"], "year": ["2024-03", "2024-03"]}
    )
    violations = check_dq03_fk_integrity(parent, child, "balancesheet")
    assert len(violations) >= 1
    assert violations[0].rule_id == "DQ-03"
    assert violations[0].severity == "CRITICAL"
    assert violations[0].company_id == "UNKNOWN_CO"


def test_04_dq04_bs_balance():
    """DQ-04: Total assets vs total liabilities imbalance (>= 1%) raises WARNING."""
    df = pd.DataFrame(
        {
            "company_id": ["INFY"],
            "year": ["2024-03"],
            "total_assets": [10000.0],
            "total_liabilities": [8500.0],  # 15% imbalance
        }
    )
    violations = check_dq04_bs_balance(df)
    assert len(violations) >= 1
    assert violations[0].rule_id == "DQ-04"
    assert violations[0].severity == "WARNING"


def test_05_dq05_opm_crosscheck():
    """DQ-05: Divergence between computed and source OPM (>= 1pp) raises WARNING."""
    df = pd.DataFrame(
        {
            "company_id": ["INFY"],
            "year": ["2024-03"],
            "operating_profit": [250.0],
            "sales": [1000.0],  # computed = 25.0%
            "opm_percentage": [20.0],  # source = 20.0% -> diff = 5.0pp
        }
    )
    violations = check_dq05_opm_crosscheck(df)
    assert len(violations) >= 1
    assert violations[0].rule_id == "DQ-05"
    assert violations[0].severity == "WARNING"


def test_06_dq06_positive_sales():
    """DQ-06: Non-positive sales for non-financial companies raises WARNING."""
    df = pd.DataFrame(
        {
            "company_id": ["TITAN"],
            "year": ["2024-03"],
            "sales": [-50.0],
        }
    )
    sectors = pd.DataFrame(
        {
            "company_id": ["TITAN"],
            "broad_sector": ["Consumer Discretionary"],
        }
    )
    violations = check_dq06_positive_sales(df, sectors)
    assert len(violations) >= 1
    assert violations[0].rule_id == "DQ-06"
    assert violations[0].severity == "WARNING"
    assert violations[0].company_id == "TITAN"


def test_07_dq07_year_format():
    """DQ-07: Year format not matching YYYY-MM raises CRITICAL violation."""
    df = pd.DataFrame(
        {
            "company_id": ["INFY"],
            "year": ["Mar-24"],  # Un-normalised year format
        }
    )
    violations = check_dq07_year_format(df, "profitandloss")
    assert len(violations) >= 1
    assert violations[0].rule_id == "DQ-07"
    assert violations[0].severity == "CRITICAL"


def test_08_dq08_ticker_format():
    """DQ-08: Ticker length outside 2-12 characters raises CRITICAL violation."""
    df = pd.DataFrame(
        {
            "company_id": ["A", "VERY_LONG_INVALID_TICKER_NAME"],
            "year": ["2024-03", "2024-03"],
        }
    )
    violations = check_dq08_ticker_format(df, "profitandloss")
    assert len(violations) == 2
    assert all(v.rule_id == "DQ-08" and v.severity == "CRITICAL" for v in violations)


def test_09_dq09_net_cash():
    """DQ-09: Cash flow components sum mismatch (> 10 Cr) raises WARNING."""
    df = pd.DataFrame(
        {
            "company_id": ["INFY"],
            "year": ["2024-03"],
            "operating_activity": [1000.0],
            "investing_activity": [-300.0],
            "financing_activity": [-200.0],  # computed net = 500
            "net_cash_flow": [200.0],  # diff = 300 > 10
        }
    )
    violations = check_dq09_net_cash(df)
    assert len(violations) >= 1
    assert violations[0].rule_id == "DQ-09"
    assert violations[0].severity == "WARNING"


def test_10_dq10_non_negative_fixed_assets():
    """DQ-10: Negative fixed assets raises WARNING."""
    df = pd.DataFrame(
        {
            "company_id": ["INFY"],
            "year": ["2024-03"],
            "fixed_assets": [-120.0],
        }
    )
    violations = check_dq10_non_negative_fixed_assets(df)
    assert len(violations) >= 1
    assert violations[0].rule_id == "DQ-10"
    assert violations[0].severity == "WARNING"


def test_11_dq11_tax_rate_range():
    """DQ-11: Tax percentage outside 0-60 range raises WARNING."""
    df = pd.DataFrame(
        {
            "company_id": ["INFY", "TCS"],
            "year": ["2024-03", "2024-03"],
            "tax_percentage": [-5.0, 75.0],
        }
    )
    violations = check_dq11_tax_rate_range(df)
    assert len(violations) == 2
    assert all(v.rule_id == "DQ-11" and v.severity == "WARNING" for v in violations)


def test_12_dq12_dividend_payout_cap():
    """DQ-12: Dividend payout > 200% raises WARNING."""
    df = pd.DataFrame(
        {
            "company_id": ["INFY"],
            "year": ["2024-03"],
            "dividend_payout": [250.0],
        }
    )
    violations = check_dq12_dividend_payout_cap(df)
    assert len(violations) >= 1
    assert violations[0].rule_id == "DQ-12"
    assert violations[0].severity == "WARNING"


def test_13_dq14_eps_sign_consistency():
    """DQ-14: Positive net profit with non-positive EPS raises WARNING."""
    df = pd.DataFrame(
        {
            "company_id": ["INFY"],
            "year": ["2024-03"],
            "net_profit": [500.0],
            "eps": [-2.5],
        }
    )
    violations = check_dq14_eps_sign_consistency(df)
    assert len(violations) >= 1
    assert violations[0].rule_id == "DQ-14"
    assert violations[0].severity == "WARNING"


def test_14_dq15_bs_strict_balance():
    """DQ-15: Strict imbalance between total_assets and total_liabilities raises INFO."""
    df = pd.DataFrame(
        {
            "company_id": ["INFY"],
            "year": ["2024-03"],
            "total_assets": [1000.50],
            "total_liabilities": [1000.49],
        }
    )
    violations = check_dq15_bs_strict_balance(df)
    assert len(violations) >= 1
    assert violations[0].rule_id == "DQ-15"
    assert violations[0].severity == "INFO"


def test_15_dq16_coverage():
    """DQ-16: Low historical coverage (< 5 years) raises WARNING."""
    pl = pd.DataFrame(
        {
            "company_id": ["NEWCO", "NEWCO"],
            "year": ["2023-03", "2024-03"],
        }
    )
    bs = pd.DataFrame(
        {
            "company_id": ["NEWCO", "NEWCO"],
            "year": ["2023-03", "2024-03"],
        }
    )
    cf = pd.DataFrame(
        {
            "company_id": ["NEWCO", "NEWCO"],
            "year": ["2023-03", "2024-03"],
        }
    )
    violations = check_dq16_coverage(pl, bs, cf, min_years=5)
    assert len(violations) >= 1
    assert violations[0].rule_id == "DQ-16"
    assert violations[0].severity == "WARNING"
    assert violations[0].company_id == "NEWCO"
