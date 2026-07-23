"""
Day 14 — Sprint 2 Integration Tests
End-to-end tests verifying all Sprint 2 modules work together:
  ratios.py + cagr.py + cashflow_kpis.py
  → ratio_runner.py (compute_row, enrich_with_cagrs, composite_score)
  → ratio_screener.py (query helpers)
  → edge_case_logger.py (structured logging)
"""

import sqlite3
from collections import defaultdict

import pytest

from src.analytics.ratio_runner import (
    compute_row,
    enrich_with_cagrs,
    compute_composite_score,
    _create_minimal_tables,
)
from src.analytics.edge_case_logger import EdgeCaseLogger, EdgeCaseType
from src.analytics.ratio_screener import (
    screen_debt_free,
    screen_high_roe,
    screen_low_leverage,
    top_n_by_kpi,
    get_company_ratios,
    ratio_summary,
)


# ==================================================================
# Test data — 3 companies × 5 years, each with a distinct profile
# ==================================================================

COMPANIES = [
    ("TCS", "Tata Consultancy Services", 1),
    ("RELIANCE", "Reliance Industries", 10),
    ("VODAIDEA", "Vodafone Idea", 10),
]

TCS_IS = [
    {"company_id": "TCS", "year": "2019-03", "sales": 142000,
     "net_profit": 31000, "operating_profit": 39000,
     "other_income": 2800, "interest": 0, "depreciation": 4200,
     "eps": 83.0, "dividend_payout": 35.0},
    {"company_id": "TCS", "year": "2020-03", "sales": 153000,
     "net_profit": 33000, "operating_profit": 42000,
     "other_income": 3000, "interest": 0, "depreciation": 4500,
     "eps": 89.0, "dividend_payout": 38.0},
    {"company_id": "TCS", "year": "2021-03", "sales": 165000,
     "net_profit": 32625, "operating_profit": 45000,
     "other_income": 3500, "interest": 0, "depreciation": 5000,
     "eps": 88.0, "dividend_payout": 40.0},
    {"company_id": "TCS", "year": "2022-03", "sales": 191000,
     "net_profit": 36900, "operating_profit": 51000,
     "other_income": 4000, "interest": 0, "depreciation": 5500,
     "eps": 100.0, "dividend_payout": 45.0},
    {"company_id": "TCS", "year": "2023-03", "sales": 225458,
     "net_profit": 34990, "operating_profit": 48534,
     "other_income": 3800, "interest": 0, "depreciation": 5800,
     "eps": 95.3, "dividend_payout": 45.0},
]

TCS_BS = [
    {"company_id": "TCS", "year": "2019-03", "equity_capital": 370,
     "reserves": 44000, "borrowings": 0, "total_assets": 57370},
    {"company_id": "TCS", "year": "2020-03", "equity_capital": 370,
     "reserves": 48000, "borrowings": 0, "total_assets": 62370},
    {"company_id": "TCS", "year": "2021-03", "equity_capital": 370,
     "reserves": 52000, "borrowings": 0, "total_assets": 67370},
    {"company_id": "TCS", "year": "2022-03", "equity_capital": 370,
     "reserves": 58000, "borrowings": 0, "total_assets": 74370},
    {"company_id": "TCS", "year": "2023-03", "equity_capital": 370,
     "reserves": 62000, "borrowings": 0, "total_assets": 79870},
]

TCS_CF = [
    {"company_id": "TCS", "year": "2019-03", "operating_activity": 30000,
     "investing_activity": -7000, "financing_activity": -20000},
    {"company_id": "TCS", "year": "2020-03", "operating_activity": 32000,
     "investing_activity": -7500, "financing_activity": -22000},
    {"company_id": "TCS", "year": "2021-03", "operating_activity": 35000,
     "investing_activity": -8000, "financing_activity": -22000},
    {"company_id": "TCS", "year": "2022-03", "operating_activity": 39000,
     "investing_activity": -9000, "financing_activity": -25000},
    {"company_id": "TCS", "year": "2023-03", "operating_activity": 42000,
     "investing_activity": -10000, "financing_activity": -28000},
]

# RELIANCE — high debt, moderate ROE, positive profit
REL_IS = [
    {"company_id": "RELIANCE", "year": "2019-03", "sales": 450000,
     "net_profit": 35000, "operating_profit": 60000,
     "other_income": 5000, "interest": 12000, "depreciation": 15000,
     "eps": 53.0, "dividend_payout": 20.0},
    {"company_id": "RELIANCE", "year": "2020-03", "sales": 350000,
     "net_profit": 20000, "operating_profit": 45000,
     "other_income": 4000, "interest": 12000, "depreciation": 16000,
     "eps": 30.0, "dividend_payout": 10.0},
    {"company_id": "RELIANCE", "year": "2021-03", "sales": 530000,
     "net_profit": 53000, "operating_profit": 75000,
     "other_income": 6000, "interest": 10000, "depreciation": 17000,
     "eps": 80.0, "dividend_payout": 15.0},
    {"company_id": "RELIANCE", "year": "2022-03", "sales": 580000,
     "net_profit": 60000, "operating_profit": 82000,
     "other_income": 7000, "interest": 9000, "depreciation": 18000,
     "eps": 90.0, "dividend_payout": 18.0},
    {"company_id": "RELIANCE", "year": "2023-03", "sales": 600000,
     "net_profit": 55000, "operating_profit": 80000,
     "other_income": 6500, "interest": 8500, "depreciation": 19000,
     "eps": 83.0, "dividend_payout": 16.0},
]

REL_BS = [
    {"company_id": "RELIANCE", "year": "2019-03", "equity_capital": 3500,
     "reserves": 250000, "borrowings": 200000, "total_assets": 541500},
    {"company_id": "RELIANCE", "year": "2020-03", "equity_capital": 3500,
     "reserves": 270000, "borrowings": 220000, "total_assets": 578500},
    {"company_id": "RELIANCE", "year": "2021-03", "equity_capital": 3500,
     "reserves": 310000, "borrowings": 180000, "total_assets": 583500},
    {"company_id": "RELIANCE", "year": "2022-03", "equity_capital": 3500,
     "reserves": 350000, "borrowings": 160000, "total_assets": 608500},
    {"company_id": "RELIANCE", "year": "2023-03", "equity_capital": 3500,
     "reserves": 380000, "borrowings": 150000, "total_assets": 633500},
]

REL_CF = [
    {"company_id": "RELIANCE", "year": "2019-03", "operating_activity": 50000,
     "investing_activity": -40000, "financing_activity": -10000},
    {"company_id": "RELIANCE", "year": "2020-03", "operating_activity": 40000,
     "investing_activity": -30000, "financing_activity": -5000},
    {"company_id": "RELIANCE", "year": "2021-03", "operating_activity": 65000,
     "investing_activity": -50000, "financing_activity": -15000},
    {"company_id": "RELIANCE", "year": "2022-03", "operating_activity": 70000,
     "investing_activity": -55000, "financing_activity": -18000},
    {"company_id": "RELIANCE", "year": "2023-03", "operating_activity": 68000,
     "investing_activity": -48000, "financing_activity": -20000},
]

# VODAIDEA — loss-making, negative equity, high debt
VOD_IS = [
    {"company_id": "VODAIDEA", "year": "2019-03", "sales": 25000,
     "net_profit": -5000, "operating_profit": -2000,
     "other_income": 500, "interest": 3000, "depreciation": 5000,
     "eps": -8.0, "dividend_payout": 0},
    {"company_id": "VODAIDEA", "year": "2020-03", "sales": 22000,
     "net_profit": -7000, "operating_profit": -3500,
     "other_income": 400, "interest": 3200, "depreciation": 5200,
     "eps": -12.0, "dividend_payout": 0},
    {"company_id": "VODAIDEA", "year": "2021-03", "sales": 20000,
     "net_profit": -8000, "operating_profit": -4000,
     "other_income": 300, "interest": 3500, "depreciation": 5400,
     "eps": -14.0, "dividend_payout": 0},
    {"company_id": "VODAIDEA", "year": "2022-03", "sales": 23000,
     "net_profit": -6000, "operating_profit": -2500,
     "other_income": 600, "interest": 3300, "depreciation": 5500,
     "eps": -10.0, "dividend_payout": 0},
    {"company_id": "VODAIDEA", "year": "2023-03", "sales": 26000,
     "net_profit": -3000, "operating_profit": -1000,
     "other_income": 800, "interest": 3000, "depreciation": 5600,
     "eps": -5.0, "dividend_payout": 0},
]

VOD_BS = [
    {"company_id": "VODAIDEA", "year": "2019-03", "equity_capital": 700,
     "reserves": -20000, "borrowings": 80000, "total_assets": 75700},
    {"company_id": "VODAIDEA", "year": "2020-03", "equity_capital": 700,
     "reserves": -27000, "borrowings": 85000, "total_assets": 72700},
    {"company_id": "VODAIDEA", "year": "2021-03", "equity_capital": 700,
     "reserves": -35000, "borrowings": 90000, "total_assets": 68700},
    {"company_id": "VODAIDEA", "year": "2022-03", "equity_capital": 700,
     "reserves": -41000, "borrowings": 88000, "total_assets": 51200},
    {"company_id": "VODAIDEA", "year": "2023-03", "equity_capital": 700,
     "reserves": -44000, "borrowings": 85000, "total_assets": 55700},
]

VOD_CF = [
    {"company_id": "VODAIDEA", "year": "2019-03", "operating_activity": 2000,
     "investing_activity": -3000, "financing_activity": 1000},
    {"company_id": "VODAIDEA", "year": "2020-03", "operating_activity": 1000,
     "investing_activity": -2500, "financing_activity": 2000},
    {"company_id": "VODAIDEA", "year": "2021-03", "operating_activity": -500,
     "investing_activity": -2000, "financing_activity": 3000},
    {"company_id": "VODAIDEA", "year": "2022-03", "operating_activity": 500,
     "investing_activity": -2000, "financing_activity": 2000},
    {"company_id": "VODAIDEA", "year": "2023-03", "operating_activity": 1500,
     "investing_activity": -2500, "financing_activity": 1000},
]

# Aggregate
ALL_IS = TCS_IS + REL_IS + VOD_IS
ALL_BS = TCS_BS + REL_BS + VOD_BS
ALL_CF = TCS_CF + REL_CF + VOD_CF


# ==================================================================
# Fixture — full pipeline in an in-memory DB
# ==================================================================

@pytest.fixture
def integrated_db():
    """Schema → seed data → compute_row → enrich CAGR → composite score → write."""
    conn = sqlite3.connect(":memory:")
    _create_minimal_tables(conn)

    # Companies
    conn.executemany(
        "INSERT INTO companies (id, company_name, face_value) VALUES (?,?,?)",
        COMPANIES,
    )

    # Income statements
    for r in ALL_IS:
        conn.execute(
            """INSERT INTO income_statement
               (company_id, year, sales, expenses, operating_profit,
                opm_percentage, other_income, interest, depreciation,
                profit_before_tax, tax_percentage, net_profit, eps,
                dividend_payout)
               VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            (r["company_id"], r["year"], r.get("sales"), None,
             r.get("operating_profit"), None, r.get("other_income"),
             r.get("interest"), r.get("depreciation"), None,
             None, r.get("net_profit"), r.get("eps"),
             r.get("dividend_payout")),
        )

    # Balance sheets
    for r in ALL_BS:
        conn.execute(
            """INSERT INTO balance_sheet
               (company_id, year, equity_capital, reserves, borrowings,
                other_liabilities, total_liabilities, fixed_assets, cwip,
                investments, other_asset, total_assets)
               VALUES (?,?,?,?,?,?,?,?,?,?,?,?)""",
            (r["company_id"], r["year"], r.get("equity_capital"),
             r.get("reserves"), r.get("borrowings"), None, None,
             None, None, None, None, r.get("total_assets")),
        )

    # Cash flows
    for r in ALL_CF:
        conn.execute(
            """INSERT INTO cash_flow
               (company_id, year, operating_activity, investing_activity,
                financing_activity, net_cash_flow)
               VALUES (?,?,?,?,?,?)""",
            (r["company_id"], r["year"], r.get("operating_activity"),
             r.get("investing_activity"), r.get("financing_activity"), None),
        )

    conn.commit()

    # Build lookup indexes
    bs_idx = {(r["company_id"], r["year"]): r for r in ALL_BS}
    cf_idx = {(r["company_id"], r["year"]): r for r in ALL_CF}
    is_by_co = defaultdict(list)
    for r in ALL_IS:
        is_by_co[r["company_id"]].append(r)

    fv_map = {c[0]: c[2] for c in COMPANIES}

    # Compute ratios for every company-year
    output_rows: list[dict] = []
    logger = EdgeCaseLogger(log_dir=None)  # no file I/O in tests

    for is_row in ALL_IS:
        cid, yr = is_row["company_id"], is_row["year"]
        bs_row = bs_idx.get((cid, yr), {})
        cf_row = cf_idx.get((cid, yr), {})
        bs_row["face_value"] = fv_map.get(cid, 1)

        row = compute_row(is_row, bs_row, cf_row, cid, yr)
        output_rows.append(row)

        # Edge-case logging
        eq_cap = bs_row.get("equity_capital") or 0
        res = bs_row.get("reserves") or 0
        total_eq = eq_cap + res
        if total_eq < 0:
            logger.log_negative_equity(cid, yr, eq_cap, res)
        if (bs_row.get("borrowings") or 0) == 0:
            logger.log_debt_free(cid, yr, "D/E")

    # Enrich with CAGRs (per company)
    for cid, co_is in is_by_co.items():
        co_out = [r for r in output_rows if r["company_id"] == cid]
        if co_out:
            enrich_with_cagrs(co_out, co_is)

    # Composite quality score
    for row in output_rows:
        row["composite_quality_score"] = compute_composite_score(row)

    # Write to financial_ratios
    cols = [
        "company_id", "year", "net_profit_margin_pct",
        "operating_profit_margin_pct", "return_on_equity_pct",
        "return_on_capital_employed_pct", "return_on_assets_pct",
        "debt_to_equity", "interest_coverage", "is_high_leverage",
        "is_low_icr_warning", "net_debt_cr", "asset_turnover",
        "free_cash_flow_cr", "capex_intensity", "fcf_conversion_rate",
        "cfo_quality_score", "capital_allocation_pattern",
        "earnings_per_share", "book_value_per_share",
        "dividend_payout_ratio_pct", "total_debt_cr",
        "cash_from_operations_cr", "revenue_cagr_3yr", "revenue_cagr_5yr",
        "revenue_cagr_10yr", "pat_cagr_3yr", "pat_cagr_5yr",
        "pat_cagr_10yr", "eps_cagr_3yr", "eps_cagr_5yr", "eps_cagr_10yr",
        "composite_quality_score",
    ]
    ph = ", ".join(["?"] * len(cols))
    cs = ", ".join(cols)
    us = ", ".join(f"{c}=excluded.{c}" for c in cols[2:])
    sql = (
        f"INSERT INTO financial_ratios ({cs}) VALUES ({ph}) "
        f"ON CONFLICT(company_id, year) DO UPDATE SET {us}"
    )
    for row in output_rows:
        conn.execute(sql, [row.get(c) for c in cols])
    conn.commit()

    yield conn, logger, output_rows
    conn.close()


# ==================================================================
# Test classes
# ==================================================================

class TestPipelineRowCounts:
    """Verify the pipeline writes the correct number of rows."""

    def test_fifteen_rows_total(self, integrated_db):
        conn, _, _ = integrated_db
        s = ratio_summary(conn)
        assert s["total_rows"] == 15  # 3 × 5

    def test_three_companies(self, integrated_db):
        conn, _, _ = integrated_db
        s = ratio_summary(conn)
        assert s["distinct_companies"] == 3

    def test_five_years(self, integrated_db):
        conn, _, _ = integrated_db
        s = ratio_summary(conn)
        assert s["distinct_years"] == 5


class TestTCSProfile:
    """TCS: debt-free, high ROE, positive NPM, positive FCF."""

    def test_zero_debt_all_years(self, integrated_db):
        _, _, rows = integrated_db
        for r in [r for r in rows if r["company_id"] == "TCS"]:
            assert r["debt_to_equity"] == 0.0
            assert r["total_debt_cr"] == 0

    def test_not_high_leverage(self, integrated_db):
        _, _, rows = integrated_db
        for r in [r for r in rows if r["company_id"] == "TCS"]:
            assert r["is_high_leverage"] == 0

    def test_positive_npm(self, integrated_db):
        _, _, rows = integrated_db
        for r in [r for r in rows if r["company_id"] == "TCS"]:
            assert r["net_profit_margin_pct"] is not None
            assert r["net_profit_margin_pct"] > 10

    def test_high_roe(self, integrated_db):
        _, _, rows = integrated_db
        for r in [r for r in rows if r["company_id"] == "TCS"]:
            if r["return_on_equity_pct"] is not None:
                assert r["return_on_equity_pct"] > 40

    def test_positive_fcf_all_years(self, integrated_db):
        _, _, rows = integrated_db
        for r in [r for r in rows if r["company_id"] == "TCS"]:
            assert r["free_cash_flow_cr"] is not None
            assert r["free_cash_flow_cr"] > 0


class TestRelianceProfile:
    """RELIANCE: leveraged, positive ICR, has capex."""

    def test_positive_debt(self, integrated_db):
        _, _, rows = integrated_db
        for r in [r for r in rows if r["company_id"] == "RELIANCE"]:
            assert r["debt_to_equity"] > 0
            assert r["total_debt_cr"] > 0

    def test_icr_above_one(self, integrated_db):
        _, _, rows = integrated_db
        for r in [r for r in rows if r["company_id"] == "RELIANCE"]:
            if r["interest_coverage"] is not None:
                assert r["interest_coverage"] > 1

    def test_capital_allocation_not_empty(self, integrated_db):
        _, _, rows = integrated_db
        for r in [r for r in rows if r["company_id"] == "RELIANCE"]:
            assert r["capital_allocation_pattern"] is not None
            assert len(r["capital_allocation_pattern"]) > 0


class TestVodafoneProfile:
    """VODAIDEA: loss-making, negative equity → ROE is None."""

    def test_negative_npm(self, integrated_db):
        _, _, rows = integrated_db
        for r in [r for r in rows if r["company_id"] == "VODAIDEA"]:
            assert r["net_profit_margin_pct"] is not None
            assert r["net_profit_margin_pct"] < 0

    def test_roe_none_due_to_negative_equity(self, integrated_db):
        _, _, rows = integrated_db
        for r in [r for r in rows if r["company_id"] == "VODAIDEA"]:
            assert r["return_on_equity_pct"] is None


class TestScreenerOnPipelineOutput:
    """Screener queries should return correct results from pipeline output."""

    def test_debt_free_finds_only_tcs(self, integrated_db):
        conn, _, _ = integrated_db
        result = screen_debt_free(conn)
        ids = [r["company_id"] for r in result]
        assert "TCS" in ids
        assert "RELIANCE" not in ids
        assert "VODAIDEA" not in ids

    def test_high_roe_includes_tcs(self, integrated_db):
        conn, _, _ = integrated_db
        result = screen_high_roe(conn, threshold=30, year="2023-03")
        ids = [r["company_id"] for r in result]
        assert "TCS" in ids

    def test_low_leverage_excludes_reliance(self, integrated_db):
        conn, _, _ = integrated_db
        result = screen_low_leverage(conn, max_de=0.1, year="2023-03")
        ids = [r["company_id"] for r in result]
        assert "RELIANCE" not in ids

    def test_top_npm_tcs_is_number_one(self, integrated_db):
        conn, _, _ = integrated_db
        result = top_n_by_kpi(
            conn, "net_profit_margin_pct", n=3, year="2023-03"
        )
        assert len(result) <= 3
        assert result[0]["company_id"] == "TCS"

    def test_company_ratios_returns_five_years(self, integrated_db):
        conn, _, _ = integrated_db
        result = get_company_ratios(conn, "RELIANCE")
        assert len(result) == 5
        years = [r["year"] for r in result]
        assert years == sorted(years)


class TestEdgeCaseLoggerCapturesIssues:
    """Logger should record negative equity and debt-free events."""

    def test_vodafone_negative_equity_logged(self, integrated_db):
        _, logger, _ = integrated_db
        neg_eq = [r for r in logger.records
                  if r.edge_type == "NEGATIVE_EQUITY"]
        ids = {r.company_id for r in neg_eq}
        assert "VODAIDEA" in ids

    def test_tcs_debt_free_logged(self, integrated_db):
        _, logger, _ = integrated_db
        df = [r for r in logger.records
              if r.edge_type == "DEBT_FREE_SUBSTITUTION"]
        ids = {r.company_id for r in df}
        assert "TCS" in ids

    def test_summary_has_both_types(self, integrated_db):
        _, logger, _ = integrated_db
        s = logger.summary()
        assert "NEGATIVE_EQUITY" in s
        assert "DEBT_FREE_SUBSTITUTION" in s


class TestCompositeScoreSanity:
    """Quality score should be in [0, 100] and TCS > VODAIDEA."""

    def test_all_scores_in_range(self, integrated_db):
        _, _, rows = integrated_db
        for r in rows:
            if r["composite_quality_score"] is not None:
                assert 0 <= r["composite_quality_score"] <= 100

    def test_tcs_higher_than_vodafone(self, integrated_db):
        _, _, rows = integrated_db
        tcs = [r["composite_quality_score"] for r in rows
               if r["company_id"] == "TCS"
               and r["composite_quality_score"] is not None]
        vod = [r["composite_quality_score"] for r in rows
               if r["company_id"] == "VODAIDEA"
               and r["composite_quality_score"] is not None]
        if tcs and vod:
            assert max(tcs) > max(vod)