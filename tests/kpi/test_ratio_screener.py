"""
Day 13 — Tests for ratio_screener.py
"""

import sqlite3

import pytest

from src.analytics.ratio_screener import (
    screen_debt_free,
    screen_high_roe,
    screen_low_leverage,
    screen_positive_fcf,
    top_n_by_kpi,
    get_company_ratios,
    get_sector_stats,
    ratio_summary,
)


# ------------------------------------------------------------------
# Fixture: in-memory DB with sample data
# ------------------------------------------------------------------

@pytest.fixture
def seeded_db():
    conn = sqlite3.connect(":memory:")
    conn.executescript("""
    CREATE TABLE financial_ratios (
        company_id   TEXT NOT NULL,
        year         TEXT NOT NULL,
        net_profit_margin_pct       REAL,
        return_on_equity_pct        REAL,
        debt_to_equity              REAL,
        interest_coverage           REAL,
        asset_turnover              REAL,
        free_cash_flow_cr           REAL,
        total_debt_cr               REAL,
        net_debt_cr                 REAL,
        composite_quality_score     REAL,
        PRIMARY KEY (company_id, year)
    );
    CREATE TABLE sectors (
        company_id   TEXT PRIMARY KEY,
        broad_sector TEXT,
        sub_sector   TEXT
    );
    """)
    rows = [
        ("TCS",      "2021-03", 19.8, 45.0, 0.0,  None, 0.65,  27000, 0,     -20000, 82),
        ("TCS",      "2022-03", 19.3, 47.0, 0.0,  None, 0.68,  30000, 0,     -22000, 85),
        ("TCS",      "2023-03", 15.5, 44.0, 0.0,  None, 0.70,  32000, 0,     -25000, 80),
        ("RELIANCE", "2023-03", 10.2,  8.5, 0.40, 5.2,  0.85,  15000, 150000, 125000, 55),
        ("HDFCBANK", "2023-03", 22.0, 16.0, 5.50, 2.1,  0.06,  25000, 500000, 480000, 60),
        ("INFOSYS",  "2023-03", 18.5, 32.0, 0.08, 12.5, 0.90,  12000, 2000,   -3000,  72),
        ("VODAIDEA", "2023-03", -5.0, -15.0, 2.50, 0.8,  0.45, -2000,  80000,  75000,  10),
    ]
    conn.executemany(
        """INSERT INTO financial_ratios
           (company_id, year, net_profit_margin_pct, return_on_equity_pct,
            debt_to_equity, interest_coverage, asset_turnover, free_cash_flow_cr,
            total_debt_cr, net_debt_cr, composite_quality_score)
           VALUES (?,?,?,?,?,?,?,?,?,?,?)""",
        rows,
    )
    conn.executemany(
        "INSERT OR REPLACE INTO sectors (company_id, broad_sector, sub_sector) "
        "VALUES (?,?,?)",
        [
            ("TCS",      "IT",                   "IT Services"),
            ("RELIANCE", "Energy",               "Oil & Gas"),
            ("HDFCBANK", "Financials",            "Private Banks"),
            ("INFOSYS",  "IT",                   "IT Services"),
            ("VODAIDEA", "Communication Services", "Telecom"),
        ],
    )
    conn.commit()
    yield conn
    conn.close()


# ------------------------------------------------------------------
# Test classes
# ------------------------------------------------------------------

class TestScreenDebtFree:
    def test_finds_debt_free(self, seeded_db):
        result = screen_debt_free(seeded_db)
        ids = [r["company_id"] for r in result]
        assert "TCS" in ids

    def test_excludes_companies_with_debt(self, seeded_db):
        result = screen_debt_free(seeded_db)
        for r in result:
            assert r["total_debt_cr"] == 0

    def test_filter_by_year(self, seeded_db):
        result = screen_debt_free(seeded_db, year="2023-03")
        for r in result:
            assert r["year"] == "2023-03"


class TestScreenHighRoe:
    def test_above_threshold(self, seeded_db):
        result = screen_high_roe(seeded_db, threshold=30)
        for r in result:
            assert r["return_on_equity_pct"] > 30

    def test_descending_order(self, seeded_db):
        result = screen_high_roe(seeded_db, threshold=0)
        if len(result) >= 2:
            assert (
                result[0]["return_on_equity_pct"]
                >= result[1]["return_on_equity_pct"]
            )

    def test_respects_limit(self, seeded_db):
        result = screen_high_roe(seeded_db, threshold=0, limit=2)
        assert len(result) <= 2


class TestScreenLowLeverage:
    def test_finds_low_de(self, seeded_db):
        result = screen_low_leverage(seeded_db, max_de=0.5)
        for r in result:
            assert r["debt_to_equity"] <= 0.5

    def test_excludes_high_de(self, seeded_db):
        result = screen_low_leverage(seeded_db, max_de=0.1)
        ids = [r["company_id"] for r in result]
        assert "HDFCBANK" not in ids  # D/E = 5.5


class TestScreenPositiveFcf:
    def test_finds_consistent_fcf(self, seeded_db):
        result = screen_positive_fcf(seeded_db, min_years=2)
        ids = [r["company_id"] for r in result]
        assert "TCS" in ids  # 3 positive-FCF years

    def test_excludes_negative_fcf(self, seeded_db):
        result = screen_positive_fcf(seeded_db, min_years=3)
        ids = [r["company_id"] for r in result]
        assert "VODAIDEA" not in ids  # only 1 year, negative


class TestTopNByKpi:
    def test_top_roe(self, seeded_db):
        result = top_n_by_kpi(seeded_db, "return_on_equity_pct", n=3)
        assert len(result) <= 3

    def test_descending_order(self, seeded_db):
        result = top_n_by_kpi(seeded_db, "return_on_equity_pct", n=5)
        if len(result) >= 2:
            assert (
                result[0]["return_on_equity_pct"]
                >= result[1]["return_on_equity_pct"]
            )

    def test_ascending_order(self, seeded_db):
        result = top_n_by_kpi(seeded_db, "debt_to_equity", n=3, ascending=True)
        if len(result) >= 2:
            assert result[0]["debt_to_equity"] <= result[1]["debt_to_equity"]

    def test_invalid_kpi_raises(self, seeded_db):
        with pytest.raises(ValueError, match="Invalid KPI column"):
            top_n_by_kpi(seeded_db, "not_a_real_kpi")

    def test_filter_by_year(self, seeded_db):
        result = top_n_by_kpi(
            seeded_db, "net_profit_margin_pct", n=5, year="2023-03"
        )
        for r in result:
            assert r["year"] == "2023-03"


class TestGetCompanyRatios:
    def test_single_company_all_years(self, seeded_db):
        result = get_company_ratios(seeded_db, "TCS")
        assert len(result) == 3
        for r in result:
            assert r["company_id"] == "TCS"

    def test_year_range(self, seeded_db):
        result = get_company_ratios(
            seeded_db, "TCS", start_year="2022-03", end_year="2023-03"
        )
        assert len(result) == 2

    def test_nonexistent_company(self, seeded_db):
        result = get_company_ratios(seeded_db, "NOTEXIST")
        assert result == []


class TestRatioSummary:
    def test_correct_counts(self, seeded_db):
        s = ratio_summary(seeded_db)
        assert s["total_rows"] == 7
        assert s["distinct_companies"] == 5
        assert s["distinct_years"] == 3

    def test_includes_top_quality(self, seeded_db):
        s = ratio_summary(seeded_db)
        assert len(s["top_5_quality"]) <= 5
        scores = [
            r["composite_quality_score"]
            for r in s["top_5_quality"]
            if r["composite_quality_score"] is not None
        ]
        if len(scores) >= 2:
            assert scores[0] >= scores[1]


class TestGetSectorStats:
    def test_returns_sectors(self, seeded_db):
        result = get_sector_stats(seeded_db, "2023-03")
        sectors = [r["sector"] for r in result]
        assert "IT" in sectors

    def test_has_aggregate_columns(self, seeded_db):
        result = get_sector_stats(seeded_db, "2023-03")
        for r in result:
            assert "avg_roe" in r
            assert "avg_npm" in r
            assert "company_count" in r