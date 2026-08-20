"""Tests for peer percentile ranking engine (Day 18)."""

import sqlite3

import numpy as np
import pandas as pd
import pytest

from src.analytics.peer import (
    PEER_GROUP_MAP,
    PEER_LOWER_IS_BETTER,
    PEER_METRICS,
    ALL_PEER_GROUPS,
    compute_peer_percentiles,
    resolve_peer_group,
    save_peer_percentiles,
    load_peer_percentiles,
    get_peer_summary,
    get_peer_group_members,
    get_top_performers,
    get_bottom_performers,
    create_peer_table,
)

# ── Fixture column layout ─────────────────────────────────────────────────────

_PEER_COLS = [
    "company_name",
    "broad_sector",
    "year",
    "return_on_equity",
    "return_on_capital_employed",
    "net_profit_margin",
    "operating_profit_margin",
    "cfo_quality_score",
    "operating_cash_flow_ratio",
    "debt_to_equity",
    "interest_coverage_ratio",
    "revenue_cagr_5yr",
    "net_profit_cagr_5yr",
]


def _row(*args):
    """Build a dict from positional args mapped to _PEER_COLS."""
    return dict(zip(_PEER_COLS, args))


@pytest.fixture
def peer_df():
    """8 companies × 2 years × 10 metrics across 3 peer groups."""
    rows = [
        # IT — 2023
        _row(
            "TCS", "IT", 2023, 15.0, 20.0, 18.0, 22.0, 0.85, 1.2, 0.1, 25.0, 8.0, 10.0
        ),
        _row(
            "INFY", "IT", 2023, 12.0, 16.0, 15.0, 19.0, 0.80, 1.0, 0.3, 20.0, 7.0, 8.0
        ),
        _row(
            "WIPRO", "IT", 2023, 8.0, 10.0, 10.0, 13.0, 0.65, 0.7, 0.2, 15.0, 4.0, 5.0
        ),
        # IT — 2024
        _row(
            "TCS", "IT", 2024, 16.0, 21.0, 19.0, 23.0, 0.87, 1.3, 0.1, 27.0, 9.0, 11.0
        ),
        _row(
            "INFY", "IT", 2024, 13.0, 17.0, 16.0, 20.0, 0.82, 1.1, 0.3, 21.0, 8.0, 9.0
        ),
        _row(
            "WIPRO", "IT", 2024, 9.0, 11.0, 11.0, 14.0, 0.67, 0.8, 0.2, 16.0, 5.0, 6.0
        ),
        # Financial Services — 2023
        _row(
            "HDFCBANK",
            "Banks",
            2023,
            14.0,
            0.0,
            20.0,
            25.0,
            0.70,
            0.0,
            5.8,
            2.5,
            10.0,
            12.0,
        ),
        _row(
            "SBIN", "Banks", 2023, 10.0, 0.0, 12.0, 16.0, 0.55, 0.0, 4.2, 1.8, 8.0, 9.0
        ),
        _row(
            "KOTAKBANK",
            "NBFC",
            2023,
            11.0,
            0.0,
            14.0,
            18.0,
            0.60,
            0.0,
            3.5,
            2.0,
            9.0,
            10.0,
        ),
        # Financial Services — 2024
        _row(
            "HDFCBANK",
            "Banks",
            2024,
            15.0,
            0.0,
            21.0,
            26.0,
            0.72,
            0.0,
            5.5,
            2.8,
            11.0,
            13.0,
        ),
        _row(
            "SBIN", "Banks", 2024, 11.0, 0.0, 13.0, 17.0, 0.58, 0.0, 4.0, 1.9, 9.0, 10.0
        ),
        _row(
            "KOTAKBANK",
            "NBFC",
            2024,
            12.0,
            0.0,
            15.0,
            19.0,
            0.63,
            0.0,
            3.2,
            2.2,
            10.0,
            11.0,
        ),
        # FMCG — 2023
        _row(
            "HINDUNILVR",
            "FMCG",
            2023,
            25.0,
            30.0,
            12.0,
            16.0,
            0.95,
            1.5,
            0.2,
            30.0,
            8.0,
            10.0,
        ),
        _row(
            "ITC",
            "Consumer Goods",
            2023,
            22.0,
            28.0,
            25.0,
            28.0,
            0.92,
            1.3,
            0.1,
            25.0,
            7.0,
            8.0,
        ),
        # FMCG — 2024
        _row(
            "HINDUNILVR",
            "FMCG",
            2024,
            26.0,
            31.0,
            13.0,
            17.0,
            0.96,
            1.6,
            0.2,
            32.0,
            9.0,
            11.0,
        ),
        _row(
            "ITC",
            "Consumer Goods",
            2024,
            23.0,
            29.0,
            26.0,
            29.0,
            0.93,
            1.4,
            0.1,
            27.0,
            8.0,
            9.0,
        ),
    ]
    return pd.DataFrame(rows, columns=_PEER_COLS)


@pytest.fixture
def db_conn():
    """In-memory SQLite connection for testing."""
    conn = sqlite3.connect(":memory:")
    yield conn
    conn.close()


# ── Constants ────────────────────────────────────────────────────────────────


class TestConstants:
    def test_eleven_peer_groups(self):
        assert len(ALL_PEER_GROUPS) == 11

    def test_ten_peer_metrics(self):
        assert len(PEER_METRICS) == 10

    def test_de_in_lower_is_better(self):
        assert "debt_to_equity" in PEER_LOWER_IS_BETTER

    def test_icr_not_in_lower_is_better(self):
        assert "interest_coverage_ratio" not in PEER_LOWER_IS_BETTER

    def test_all_peer_groups_covered(self):
        values = set(PEER_GROUP_MAP.values())
        assert values == set(ALL_PEER_GROUPS)

    def test_peer_metrics_match_scoring(self):
        """PEER_METRICS should be a subset of what scoring.py uses."""
        expected = {
            "return_on_equity",
            "return_on_capital_employed",
            "net_profit_margin",
            "operating_profit_margin",
            "cfo_quality_score",
            "operating_cash_flow_ratio",
            "debt_to_equity",
            "interest_coverage_ratio",
            "revenue_cagr_5yr",
            "net_profit_cagr_5yr",
        }
        assert set(PEER_METRICS) == expected


# ── resolve_peer_group ───────────────────────────────────────────────────────


class TestResolvePeerGroup:
    def test_maps_banks_to_financial_services(self):
        s = pd.Series(["Banks", "NBFC", "IT", "FMCG"])
        result = resolve_peer_group(s)
        assert result.iloc[0] == "Financial Services"
        assert result.iloc[1] == "Financial Services"
        assert result.iloc[2] == "IT"
        assert result.iloc[3] == "FMCG"

    def test_unknown_sector_passes_through(self):
        s = pd.Series(["Banks", "SomeNewSector"])
        result = resolve_peer_group(s)
        assert result.iloc[1] == "SomeNewSector"

    def test_preserves_length(self):
        s = pd.Series(["IT"] * 100)
        assert len(resolve_peer_group(s)) == 100


# ── compute_peer_percentiles ─────────────────────────────────────────────────


class TestComputePeerPercentiles:
    def test_returns_long_format_dataframe(self, peer_df):
        result = compute_peer_percentiles(peer_df)
        assert isinstance(result, pd.DataFrame)
        expected_cols = {
            "company_name",
            "year",
            "peer_group",
            "metric_name",
            "raw_value",
            "percentile_rank",
            "peer_count",
        }
        assert expected_cols.issubset(set(result.columns))

    def test_correct_row_count(self, peer_df):
        """8 companies × 2 years × 10 metrics = 160 rows."""
        result = compute_peer_percentiles(peer_df)
        assert len(result) == 160

    def test_percentiles_in_range(self, peer_df):
        result = compute_peer_percentiles(peer_df)
        assert (result["percentile_rank"] >= 0).all()
        assert (result["percentile_rank"] <= 100).all()

    def test_peer_group_mapped_correctly(self, peer_df):
        result = compute_peer_percentiles(peer_df)
        # "Banks" → "Financial Services"
        hdfs = result[(result["company_name"] == "HDFCBANK") & (result["year"] == 2023)]
        assert (hdfs["peer_group"] == "Financial Services").all()

    def test_consumer_goods_maps_to_fmcg(self, peer_df):
        result = compute_peer_percentiles(peer_df)
        itc = result[(result["company_name"] == "ITC") & (result["year"] == 2023)]
        assert (itc["peer_group"] == "FMCG").all()

    def test_peer_count_reflects_group_size(self, peer_df):
        """IT has 3 companies, FMCG has 2."""
        result = compute_peer_percentiles(peer_df)
        it_row = result[
            (result["company_name"] == "TCS")
            & (result["year"] == 2023)
            & (result["metric_name"] == "return_on_equity")
        ]
        assert it_row["peer_count"].iloc[0] == 3

        fmcg_row = result[
            (result["company_name"] == "ITC")
            & (result["year"] == 2023)
            & (result["metric_name"] == "return_on_equity")
        ]
        assert fmcg_row["peer_count"].iloc[0] == 2


# ── D/E Inversion ────────────────────────────────────────────────────────────


class TestPeerInversion:
    def test_low_de_high_percentile(self, peer_df):
        """Company with lowest D/E should get highest percentile (inverted)."""
        result = compute_peer_percentiles(peer_df)
        # IT 2023: TCS D/E=0.1, INFY=0.3, WIPRO=0.2 → TCS should rank highest
        it_de = result[
            (result["peer_group"] == "IT")
            & (result["year"] == 2023)
            & (result["metric_name"] == "debt_to_equity")
        ].set_index("company_name")

        assert (
            it_de.loc["TCS", "percentile_rank"] > it_de.loc["INFY", "percentile_rank"]
        )
        assert (
            it_de.loc["TCS", "percentile_rank"] > it_de.loc["WIPRO", "percentile_rank"]
        )

    def test_high_de_low_percentile(self, peer_df):
        """Company with highest D/E should get lowest percentile (inverted)."""
        result = compute_peer_percentiles(peer_df)
        # FinSvc 2023: HDFCBANK D/E=5.8, SBIN=4.2, KOTAKBANK=3.5
        fin_de = result[
            (result["peer_group"] == "Financial Services")
            & (result["year"] == 2023)
            & (result["metric_name"] == "debt_to_equity")
        ].set_index("company_name")

        assert (
            fin_de.loc["HDFCBANK", "percentile_rank"]
            < fin_de.loc["KOTAKBANK", "percentile_rank"]
        )

    def test_non_inverted_metric_higher_is_better(self, peer_df):
        """ROE should NOT be inverted — higher ROE = higher percentile."""
        result = compute_peer_percentiles(peer_df)
        it_roe = result[
            (result["peer_group"] == "IT")
            & (result["year"] == 2023)
            & (result["metric_name"] == "return_on_equity")
        ].set_index("company_name")

        assert (
            it_roe.loc["TCS", "percentile_rank"]
            > it_roe.loc["WIPRO", "percentile_rank"]
        )


# ── Edge Cases ────────────────────────────────────────────────────────────────


class TestPeerEdgeCases:
    def test_missing_sector_col_raises(self, peer_df):
        df = peer_df.drop(columns=["broad_sector"])
        with pytest.raises(KeyError, match="sector_col"):
            compute_peer_percentiles(df)

    def test_empty_df_returns_empty(self):
        df = pd.DataFrame(columns=_PEER_COLS)
        result = compute_peer_percentiles(df)
        assert len(result) == 0

    def test_nan_metric_skipped(self):
        """Rows with NaN for a metric should not appear in output for that metric."""
        df = pd.DataFrame(
            [
                _row(
                    "A",
                    "IT",
                    2024,
                    15.0,
                    np.nan,
                    10.0,
                    12.0,
                    0.8,
                    1.0,
                    0.5,
                    20.0,
                    5.0,
                    6.0,
                ),
                _row(
                    "B",
                    "IT",
                    2024,
                    12.0,
                    10.0,
                    8.0,
                    10.0,
                    0.7,
                    0.9,
                    0.3,
                    15.0,
                    4.0,
                    5.0,
                ),
            ],
            columns=_PEER_COLS,
        )
        result = compute_peer_percentiles(df)
        roce_rows = result[result["metric_name"] == "return_on_capital_employed"]
        # Only B has ROCE data
        assert len(roce_rows) == 1
        assert roce_rows.iloc[0]["company_name"] == "B"

    def test_tied_values_get_same_rank(self):
        """Identical metric values should produce the same percentile."""
        df = pd.DataFrame(
            [
                _row(
                    "A",
                    "IT",
                    2024,
                    15.0,
                    15.0,
                    10.0,
                    12.0,
                    0.8,
                    1.0,
                    0.5,
                    20.0,
                    5.0,
                    6.0,
                ),
                _row(
                    "B",
                    "IT",
                    2024,
                    15.0,
                    12.0,
                    8.0,
                    10.0,
                    0.7,
                    0.9,
                    0.3,
                    15.0,
                    4.0,
                    5.0,
                ),
            ],
            columns=_PEER_COLS,
        )
        result = compute_peer_percentiles(df)
        roe_rows = result[(result["metric_name"] == "return_on_equity")].set_index(
            "company_name"
        )
        assert (
            abs(
                roe_rows.loc["A", "percentile_rank"]
                - roe_rows.loc["B", "percentile_rank"]
            )
            < 0.01
        )

    def test_single_company_group_gets_50(self):
        """One company in a peer group → percentile = 50.0."""
        df = pd.DataFrame(
            [
                _row(
                    "Solo",
                    "IT",
                    2024,
                    15.0,
                    20.0,
                    10.0,
                    12.0,
                    0.8,
                    1.0,
                    0.5,
                    20.0,
                    5.0,
                    6.0,
                ),
            ],
            columns=_PEER_COLS,
        )
        result = compute_peer_percentiles(df)
        roe = result[(result["metric_name"] == "return_on_equity")]
        assert roe.iloc[0]["percentile_rank"] == 50.0

    def test_custom_metrics_parameter(self, peer_df):
        """Should only compute for the specified metrics."""
        result = compute_peer_percentiles(
            peer_df, metrics=["return_on_equity", "debt_to_equity"]
        )
        assert set(result["metric_name"].unique()) == {
            "return_on_equity",
            "debt_to_equity",
        }
        # 8 companies × 2 years × 2 metrics = 32
        assert len(result) == 32


# ── SQLite Round-Trip ────────────────────────────────────────────────────────


class TestPeerSQLite:
    def test_save_and_load_round_trip(self, peer_df, db_conn):
        computed = compute_peer_percentiles(peer_df)
        count = save_peer_percentiles(db_conn, computed)
        assert count == len(computed)

        loaded = load_peer_percentiles(db_conn)
        assert len(loaded) == len(computed)
        assert set(loaded.columns) >= {
            "company_name",
            "year",
            "peer_group",
            "metric_name",
            "raw_value",
            "percentile_rank",
            "peer_count",
        }

    def test_filter_by_company_and_year(self, peer_df, db_conn):
        computed = compute_peer_percentiles(peer_df)
        save_peer_percentiles(db_conn, computed)

        loaded = load_peer_percentiles(db_conn, company_name="TCS", year=2023)
        assert len(loaded) == 10  # one row per metric
        assert (loaded["company_name"] == "TCS").all()
        assert (loaded["year"] == 2023).all()

    def test_filter_by_peer_group(self, peer_df, db_conn):
        computed = compute_peer_percentiles(peer_df)
        save_peer_percentiles(db_conn, computed)

        loaded = load_peer_percentiles(
            db_conn, peer_group="Financial Services", year=2023
        )
        assert (loaded["peer_group"] == "Financial Services").all()
        # 3 companies × 10 metrics = 30
        assert len(loaded) == 30

    def test_filter_by_metric(self, peer_df, db_conn):
        computed = compute_peer_percentiles(peer_df)
        save_peer_percentiles(db_conn, computed)

        loaded = load_peer_percentiles(db_conn, metric_name="return_on_equity")
        assert (loaded["metric_name"] == "return_on_equity").all()
        # 8 companies × 2 years = 16
        assert len(loaded) == 16

    def test_empty_result_on_no_match(self, peer_df, db_conn):
        computed = compute_peer_percentiles(peer_df)
        save_peer_percentiles(db_conn, computed)

        loaded = load_peer_percentiles(db_conn, company_name="NONEXISTENT")
        assert len(loaded) == 0


# ── Query Helpers ────────────────────────────────────────────────────────────


class TestQueryHelpers:
    def test_get_peer_summary(self, peer_df, db_conn):
        computed = compute_peer_percentiles(peer_df)
        save_peer_percentiles(db_conn, computed)

        summary = get_peer_summary(db_conn, "TCS", 2023)
        assert len(summary) == 10
        assert list(summary["metric_name"]) == sorted(PEER_METRICS)

    def test_get_peer_group_members(self, peer_df, db_conn):
        computed = compute_peer_percentiles(peer_df)
        save_peer_percentiles(db_conn, computed)

        members = get_peer_group_members(db_conn, "IT", 2024)
        names = sorted(members["company_name"].tolist())
        assert names == ["INFY", "TCS", "WIPRO"]

    def test_get_top_performers(self, peer_df, db_conn):
        computed = compute_peer_percentiles(peer_df)
        save_peer_percentiles(db_conn, computed)

        top = get_top_performers(db_conn, "IT", "return_on_equity", 2024, top_n=2)
        assert len(top) == 2
        # TCS has highest ROE in IT
        assert top.iloc[0]["company_name"] == "TCS"
        # Sorted by percentile descending
        assert top.iloc[0]["percentile_rank"] >= top.iloc[1]["percentile_rank"]

    def test_get_bottom_performers(self, peer_df, db_conn):
        computed = compute_peer_percentiles(peer_df)
        save_peer_percentiles(db_conn, computed)

        bottom = get_bottom_performers(
            db_conn, "Financial Services", "debt_to_equity", 2023, bottom_n=1
        )
        assert len(bottom) == 1
        # After inversion, HDFCBANK (highest D/E) has lowest percentile
        assert bottom.iloc[0]["company_name"] == "HDFCBANK"

    def test_get_top_performers_respects_limit(self, peer_df, db_conn):
        computed = compute_peer_percentiles(peer_df)
        save_peer_percentiles(db_conn, computed)

        top = get_top_performers(db_conn, "IT", "return_on_equity", 2024, top_n=1)
        assert len(top) == 1

    def test_create_peer_table_idempotent(self, db_conn):
        create_peer_table(db_conn)
        create_peer_table(db_conn)  # should not raise
        tables = pd.read_sql_query(
            "SELECT name FROM sqlite_master WHERE type='table'", db_conn
        )
        assert "peer_percentiles" in tables["name"].values
