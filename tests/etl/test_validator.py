"""Unit tests for all 16 DQ validation rules."""

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
    run_all_validations,
    DQViolation,
    save_violations_csv,
)


def _companies_basic() -> pd.DataFrame:
    """Helper: 3-company companies table."""
    return pd.DataFrame(
        {
            "id": ["TCS", "HDFCBANK", "ABB"],
            "company_name": [
                "Tata Consultancy Services Ltd",
                "HDFC Bank Ltd",
                "ABB India Ltd",
            ],
        }
    )


# ============================================================
# DQ-01: Company PK Uniqueness
# ============================================================


class TestDQ01:
    def test_no_duplicates(self) -> None:
        df = _companies_basic()
        assert check_dq01_company_pk_uniqueness(df) == []

    def test_duplicate_ticker(self) -> None:
        df = pd.DataFrame(
            {
                "id": ["TCS", "TCS", "ABB"],
                "company_name": ["TCS Ltd", "TCS Duplicate", "ABB Ltd"],
            }
        )
        violations = check_dq01_company_pk_uniqueness(df)
        assert len(violations) == 1
        assert violations[0].severity == "CRITICAL"
        assert "TCS" in violations[0].issue

    def test_missing_id_column(self) -> None:
        df = pd.DataFrame({"name": ["TCS"]})
        violations = check_dq01_company_pk_uniqueness(df)
        assert len(violations) == 1
        assert "not found" in violations[0].issue


# ============================================================
# DQ-02: Annual PK Uniqueness
# ============================================================


class TestDQ02:
    def test_no_duplicates(self) -> None:
        df = pd.DataFrame(
            {
                "company_id": ["TCS", "TCS"],
                "year": ["2022-03", "2023-03"],
                "sales": [100, 200],
            }
        )
        assert check_dq02_annual_pk_uniqueness(df, "test") == []

    def test_duplicate_row(self) -> None:
        df = pd.DataFrame(
            {
                "company_id": ["TCS", "TCS", "TCS"],
                "year": ["2022-03", "2022-03", "2023-03"],
                "sales": [100, 110, 200],
            }
        )
        violations = check_dq02_annual_pk_uniqueness(df, "pl")
        assert len(violations) == 1
        assert violations[0].severity == "CRITICAL"


# ============================================================
# DQ-03: FK Integrity
# ============================================================


class TestDQ03:
    def test_valid_fk(self) -> None:
        companies = _companies_basic()
        child = pd.DataFrame(
            {
                "company_id": ["TCS", "ABB"],
                "year": ["2022-03", "2022-03"],
            }
        )
        assert check_dq03_fk_integrity(companies, child, "pl") == []

    def test_orphan_ticker(self) -> None:
        companies = _companies_basic()
        child = pd.DataFrame(
            {
                "company_id": ["TCS", "FAKE"],
                "year": ["2022-03", "2022-03"],
            }
        )
        violations = check_dq03_fk_integrity(companies, child, "pl")
        assert len(violations) == 1
        assert "FAKE" in violations[0].issue
        assert violations[0].severity == "CRITICAL"


# ============================================================
# DQ-04: BS Balance
# ============================================================


class TestDQ04:
    def test_balanced_sheet(self) -> None:
        bs = pd.DataFrame(
            {
                "company_id": ["TCS"],
                "year": ["2023-03"],
                "total_assets": [1000],
                "total_liabilities": [1000],
            }
        )
        assert check_dq04_bs_balance(bs) == []

    def test_imbalanced_sheet(self) -> None:
        bs = pd.DataFrame(
            {
                "company_id": ["TCS"],
                "year": ["2023-03"],
                "total_assets": [1000],
                "total_liabilities": [1020],
            }
        )
        violations = check_dq04_bs_balance(bs)
        assert len(violations) == 1
        assert violations[0].rule_id == "DQ-04"
        assert violations[0].severity == "WARNING"


# ============================================================
# DQ-05: OPM Cross-Check
# ============================================================


class TestDQ05:
    def test_opm_matches(self) -> None:
        pl = pd.DataFrame(
            {
                "company_id": ["TCS"],
                "year": ["2023-03"],
                "operating_profit": [48534],
                "sales": [225458],
                "opm_percentage": [21.5],
            }
        )
        assert check_dq05_opm_crosscheck(pl) == []

    def test_opm_mismatch(self) -> None:
        pl = pd.DataFrame(
            {
                "company_id": ["TCS"],
                "year": ["2023-03"],
                "operating_profit": [48534],
                "sales": [225458],
                "opm_percentage": [30.0],
            }
        )
        violations = check_dq05_opm_crosscheck(pl)
        assert len(violations) == 1
        assert violations[0].rule_id == "DQ-05"


# ============================================================
# DQ-06: Positive Sales
# ============================================================


class TestDQ06:
    def test_positive_sales_ok(self) -> None:
        pl = pd.DataFrame(
            {
                "company_id": ["TCS"],
                "year": ["2023-03"],
                "sales": [1000],
            }
        )
        assert check_dq06_positive_sales(pl) == []

    def test_zero_sales_flagged(self) -> None:
        pl = pd.DataFrame(
            {
                "company_id": ["TCS"],
                "year": ["2023-03"],
                "sales": [0],
            }
        )
        violations = check_dq06_positive_sales(pl)
        assert len(violations) == 1
        assert violations[0].rule_id == "DQ-06"

    def test_bank_with_zero_sales_not_flagged(self) -> None:
        pl = pd.DataFrame(
            {
                "company_id": ["HDFCBANK"],
                "year": ["2023-03"],
                "sales": [0],
            }
        )
        sectors = pd.DataFrame(
            {
                "company_id": ["HDFCBANK"],
                "broad_sector": ["Financials"],
            }
        )
        violations = check_dq06_positive_sales(pl, sectors)
        assert violations == []


# ============================================================
# DQ-07: Year Format
# ============================================================


class TestDQ07:
    def test_valid_year(self) -> None:
        df = pd.DataFrame(
            {
                "company_id": ["TCS"],
                "year": ["2023-03"],
            }
        )
        assert check_dq07_year_format(df, "test") == []

    def test_invalid_year(self) -> None:
        df = pd.DataFrame(
            {
                "company_id": ["TCS"],
                "year": ["bad-year"],
            }
        )
        violations = check_dq07_year_format(df, "test")
        assert len(violations) == 1
        assert violations[0].severity == "CRITICAL"


# ============================================================
# DQ-08: Ticker Format
# ============================================================


class TestDQ08:
    def test_valid_ticker(self) -> None:
        df = pd.DataFrame(
            {
                "company_id": ["TCS"],
                "year": ["2023-03"],
            }
        )
        assert check_dq08_ticker_format(df, "test") == []

    def test_ticker_too_short(self) -> None:
        df = pd.DataFrame(
            {
                "company_id": ["A"],
                "year": ["2023-03"],
            }
        )
        violations = check_dq08_ticker_format(df, "test")
        assert len(violations) == 1
        assert violations[0].severity == "CRITICAL"


# ============================================================
# DQ-09: Net Cash Check
# ============================================================


class TestDQ09:
    def test_balanced_cash(self) -> None:
        cf = pd.DataFrame(
            {
                "company_id": ["TCS"],
                "year": ["2023-03"],
                "operating_activity": [100],
                "investing_activity": [-50],
                "financing_activity": [-20],
                "net_cash_flow": [30],
            }
        )
        assert check_dq09_net_cash(cf) == []

    def test_mismatched_cash(self) -> None:
        cf = pd.DataFrame(
            {
                "company_id": ["TCS"],
                "year": ["2023-03"],
                "operating_activity": [100],
                "investing_activity": [-50],
                "financing_activity": [-20],
                "net_cash_flow": [100],
            }
        )
        violations = check_dq09_net_cash(cf)
        assert len(violations) == 1
        assert violations[0].rule_id == "DQ-09"


# ============================================================
# DQ-10: Non-Negative Fixed Assets
# ============================================================


class TestDQ10:
    def test_positive_fixed_assets(self) -> None:
        bs = pd.DataFrame(
            {
                "company_id": ["TCS"],
                "year": ["2023-03"],
                "fixed_assets": [500],
            }
        )
        assert check_dq10_non_negative_fixed_assets(bs) == []

    def test_negative_fixed_assets(self) -> None:
        bs = pd.DataFrame(
            {
                "company_id": ["TCS"],
                "year": ["2023-03"],
                "fixed_assets": [-10],
            }
        )
        violations = check_dq10_non_negative_fixed_assets(bs)
        assert len(violations) == 1
        assert violations[0].rule_id == "DQ-10"


# ============================================================
# DQ-11: Tax Rate Range
# ============================================================


class TestDQ11:
    def test_normal_tax(self) -> None:
        pl = pd.DataFrame(
            {
                "company_id": ["TCS"],
                "year": ["2023-03"],
                "tax_percentage": [25.0],
            }
        )
        assert check_dq11_tax_rate_range(pl) == []

    def test_tax_too_high(self) -> None:
        pl = pd.DataFrame(
            {
                "company_id": ["TCS"],
                "year": ["2023-03"],
                "tax_percentage": [75.0],
            }
        )
        violations = check_dq11_tax_rate_range(pl)
        assert len(violations) == 1
        assert violations[0].rule_id == "DQ-11"


# ============================================================
# DQ-12: Dividend Payout Cap
# ============================================================


class TestDQ12:
    def test_normal_payout(self) -> None:
        pl = pd.DataFrame(
            {
                "company_id": ["TCS"],
                "year": ["2023-03"],
                "dividend_payout": [45.0],
            }
        )
        assert check_dq12_dividend_payout_cap(pl) == []

    def test_payout_exceeds_cap(self) -> None:
        pl = pd.DataFrame(
            {
                "company_id": ["TCS"],
                "year": ["2023-03"],
                "dividend_payout": [250.0],
            }
        )
        violations = check_dq12_dividend_payout_cap(pl)
        assert len(violations) == 1
        assert violations[0].rule_id == "DQ-12"


# ============================================================
# DQ-14: EPS Sign Consistency
# ============================================================


class TestDQ14:
    def test_consistent_signs(self) -> None:
        pl = pd.DataFrame(
            {
                "company_id": ["TCS"],
                "year": ["2023-03"],
                "net_profit": [34990],
                "eps": [95.30],
            }
        )
        assert check_dq14_eps_sign_consistency(pl) == []

    def test_inconsistent_eps(self) -> None:
        pl = pd.DataFrame(
            {
                "company_id": ["TCS"],
                "year": ["2023-03"],
                "net_profit": [34990],
                "eps": [-5.0],
            }
        )
        violations = check_dq14_eps_sign_consistency(pl)
        assert len(violations) == 1
        assert violations[0].rule_id == "DQ-14"


# ============================================================
# DQ-15: BS Strict Balance (INFO)
# ============================================================


class TestDQ15:
    def test_strict_balance(self) -> None:
        bs = pd.DataFrame(
            {
                "company_id": ["TCS"],
                "year": ["2023-03"],
                "total_assets": [1000],
                "total_liabilities": [1000],
            }
        )
        assert check_dq15_bs_strict_balance(bs) == []

    def test_strict_imbalance(self) -> None:
        bs = pd.DataFrame(
            {
                "company_id": ["TCS"],
                "year": ["2023-03"],
                "total_assets": [1000],
                "total_liabilities": [999],
            }
        )
        violations = check_dq15_bs_strict_balance(bs)
        assert len(violations) == 1
        assert violations[0].severity == "INFO"


# ============================================================
# DQ-16: Coverage Check
# ============================================================


class TestDQ16:
    def test_sufficient_coverage(self) -> None:
        pl = pd.DataFrame(
            {
                "company_id": ["TCS"] * 10,
                "year": [f"{y}-03" for y in range(2015, 2025)],
            }
        )
        bs = pl.copy()
        cf = pl.copy()
        assert check_dq16_coverage(pl, bs, cf, min_years=5) == []

    def test_insufficient_coverage(self) -> None:
        pl = pd.DataFrame(
            {
                "company_id": ["NEWCO"] * 3,
                "year": ["2022-03", "2023-03", "2024-03"],
            }
        )
        bs = pl.copy()
        cf = pl.copy()
        violations = check_dq16_coverage(pl, bs, cf, min_years=5)
        # 3 tables × 1 company = 3 violations
        assert len(violations) == 3
        assert all(v.rule_id == "DQ-16" for v in violations)


# ============================================================
# Integration: run_all_validations
# ============================================================


class TestRunAll:
    def test_clean_datasets_no_critical(self) -> None:
        datasets = {
            "companies": pd.DataFrame(
                {
                    "id": ["TCS", "ABB"],
                    "company_name": ["TCS Ltd", "ABB Ltd"],
                }
            ),
            "profitandloss": pd.DataFrame(
                {
                    "company_id": ["TCS", "TCS"],
                    "year": ["2022-03", "2023-03"],
                    "sales": [100, 200],
                    "operating_profit": [21, 42],
                    "opm_percentage": [21.0, 21.0],
                    "tax_percentage": [25.0, 25.0],
                    "dividend_payout": [30.0, 30.0],
                    "net_profit": [50, 100],
                    "eps": [10.0, 20.0],
                }
            ),
            "balancesheet": pd.DataFrame(
                {
                    "company_id": ["TCS", "TCS"],
                    "year": ["2022-03", "2023-03"],
                    "total_assets": [500, 600],
                    "total_liabilities": [500, 600],
                    "fixed_assets": [200, 220],
                }
            ),
            "cashflow": pd.DataFrame(
                {
                    "company_id": ["TCS", "TCS"],
                    "year": ["2022-03", "2023-03"],
                    "operating_activity": [50, 60],
                    "investing_activity": [-20, -25],
                    "financing_activity": [-10, -15],
                    "net_cash_flow": [20, 20],
                }
            ),
        }
        violations = run_all_validations(datasets)
        critical = [v for v in violations if v.severity == "CRITICAL"]
        assert len(critical) == 0


# ============================================================
# CSV output
# ============================================================


class TestSaveCSV:
    def test_save_empty(self, tmp_path) -> None:
        out = str(tmp_path / "test_violations.csv")
        df = save_violations_csv([], out)
        assert len(df) == 0

    def test_save_with_violations(self, tmp_path) -> None:
        out = str(tmp_path / "test_violations.csv")
        violations = [
            DQViolation(
                rule_id="DQ-04",
                severity="WARNING",
                company_id="TCS",
                year="2023-03",
                field="total_assets",
                issue="test issue",
                action="test action",
            ),
        ]
        df = save_violations_csv(violations, out)
        assert len(df) == 1
        assert df.iloc[0]["rule_id"] == "DQ-04"
