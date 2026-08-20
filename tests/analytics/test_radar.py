"""Tests for radar chart generation (Day 19)."""

import sqlite3

import matplotlib

matplotlib.use("Agg")

import matplotlib.pyplot as plt
import pytest

from src.analytics.radar import (
    DEFAULT_METRIC_LABELS,
    RADAR_METRICS,
    create_radar_chart,
    create_peer_radar_from_db,
    export_radar_png,
    export_peer_group_radars,
)
from src.analytics.peer import create_peer_table

# ── Fixtures ──────────────────────────────────────────────────────────────────


@pytest.fixture
def company_pctls():
    """Strong company — high percentiles across the board."""
    return {
        "return_on_equity": 80.0,
        "return_on_capital_employed": 75.0,
        "net_profit_margin": 70.0,
        "operating_profit_margin": 65.0,
        "cfo_quality_score": 85.0,
        "operating_cash_flow_ratio": 72.0,
        "debt_to_equity": 90.0,
        "interest_coverage_ratio": 60.0,
        "revenue_cagr_5yr": 55.0,
        "net_profit_cagr_5yr": 50.0,
    }


@pytest.fixture
def peer_avg_pctls():
    """Flat peer-group average at 50th percentile."""
    return {m: 50.0 for m in RADAR_METRICS}


@pytest.fixture
def db_conn():
    """In-memory DB with peer_percentiles for 3 IT companies in 2024."""
    conn = sqlite3.connect(":memory:")
    create_peer_table(conn)

    rows = []
    tcs_pctls = {
        "return_on_equity": 83.33,
        "return_on_capital_employed": 83.33,
        "net_profit_margin": 83.33,
        "operating_profit_margin": 83.33,
        "cfo_quality_score": 83.33,
        "operating_cash_flow_ratio": 83.33,
        "debt_to_equity": 83.33,
        "interest_coverage_ratio": 83.33,
        "revenue_cagr_5yr": 83.33,
        "net_profit_cagr_5yr": 83.33,
    }
    infy_pctls = {m: 50.0 for m in RADAR_METRICS}
    wipro_pctls = {m: 16.67 for m in RADAR_METRICS}

    for name, pctls in [
        ("TCS", tcs_pctls),
        ("INFY", infy_pctls),
        ("WIPRO", wipro_pctls),
    ]:
        for metric, pr in pctls.items():
            rows.append((name, 2024, "IT", metric, pr, 3))

    conn.executemany(
        "INSERT INTO peer_percentiles "
        "(company_name, year, peer_group, metric_name, percentile_rank, peer_count) "
        "VALUES (?,?,?,?,?,?)",
        rows,
    )
    conn.commit()
    yield conn
    conn.close()


# ── Constants ────────────────────────────────────────────────────────────────


class TestConstants:
    def test_ten_radar_metrics(self):
        assert len(RADAR_METRICS) == 10

    def test_labels_cover_all_metrics(self):
        assert set(RADAR_METRICS) == set(DEFAULT_METRIC_LABELS.keys())

    def test_metrics_match_peer_metrics(self):
        from src.analytics.peer import PEER_METRICS

        assert RADAR_METRICS == PEER_METRICS


# ── create_radar_chart ───────────────────────────────────────────────────────


class TestCreateRadarChart:
    def test_returns_figure(self, company_pctls, peer_avg_pctls):
        fig = create_radar_chart("TCS", "IT", 2024, company_pctls, peer_avg_pctls)
        assert isinstance(fig, plt.Figure)
        plt.close(fig)

    def test_figure_has_polar_axes(self, company_pctls, peer_avg_pctls):
        fig = create_radar_chart("TCS", "IT", 2024, company_pctls, peer_avg_pctls)
        ax = fig.axes[0]
        assert type(ax).__name__ == "PolarAxes"
        plt.close(fig)

    def test_two_lines_when_peer_overlay(self, company_pctls, peer_avg_pctls):
        fig = create_radar_chart("TCS", "IT", 2024, company_pctls, peer_avg_pctls)
        ax = fig.axes[0]
        assert len(ax.lines) == 2  # company + peer avg
        plt.close(fig)

    def test_one_line_without_peer_overlay(self, company_pctls):
        fig = create_radar_chart("TCS", "IT", 2024, company_pctls)
        ax = fig.axes[0]
        assert len(ax.lines) == 1
        plt.close(fig)

    def test_custom_title(self, company_pctls):
        fig = create_radar_chart("TCS", "IT", 2024, company_pctls, title="Custom Title")
        ax = fig.axes[0]
        assert ax.get_title() == "Custom Title"
        plt.close(fig)

    def test_default_title_contains_company_name(self, company_pctls):
        fig = create_radar_chart("TCS", "IT", 2024, company_pctls)
        ax = fig.axes[0]
        assert "TCS" in ax.get_title()
        assert "2024" in ax.get_title()
        plt.close(fig)

    def test_custom_metrics_subset(self, company_pctls, peer_avg_pctls):
        subset = ["return_on_equity", "net_profit_margin", "debt_to_equity"]
        fig = create_radar_chart(
            "TCS",
            "IT",
            2024,
            company_pctls,
            peer_avg_pctls,
            metrics=subset,
        )
        ax = fig.axes[0]
        # 3 labels on the polar axes
        tick_labels = [t.get_text() for t in ax.get_xticklabels()]
        assert len(tick_labels) == 3
        plt.close(fig)

    def test_missing_metric_defaults_to_zero(self, company_pctls):
        """Metrics not in the dict should default to 0 on the chart."""
        partial = {"return_on_equity": 80.0, "debt_to_equity": 60.0}
        fig = create_radar_chart("X", "IT", 2024, partial, metrics=RADAR_METRICS[:3])
        ax = fig.axes[0]
        # Should not raise — defaults to 0.0
        assert len(ax.lines) == 1
        plt.close(fig)

    def test_too_few_metrics_raises(self):
        with pytest.raises(ValueError, match="at least 3"):
            create_radar_chart("X", "IT", 2024, {}, metrics=["roe"])


# ── export_radar_png ─────────────────────────────────────────────────────────


class TestExportRadarPng:
    def test_creates_file(self, company_pctls, peer_avg_pctls, tmp_path):
        fig = create_radar_chart("TCS", "IT", 2024, company_pctls, peer_avg_pctls)
        out = tmp_path / "radar.png"
        result = export_radar_png(fig, str(out))
        assert result.exists()
        assert result.stat().st_size > 0

    def test_creates_parent_directories(self, company_pctls, tmp_path):
        fig = create_radar_chart("TCS", "IT", 2024, company_pctls)
        nested = tmp_path / "a" / "b" / "radar.png"
        result = export_radar_png(fig, str(nested))
        assert result.exists()

    def test_returns_absolute_path(self, company_pctls, tmp_path):
        fig = create_radar_chart("TCS", "IT", 2024, company_pctls)
        result = export_radar_png(fig, str(tmp_path / "r.png"))
        assert result.is_absolute()

    def test_closes_figure(self, company_pctls, tmp_path):
        fig = create_radar_chart("TCS", "IT", 2024, company_pctls)
        fig_num = fig.number
        export_radar_png(fig, str(tmp_path / "r.png"))
        assert fig_num not in plt.get_fignums()


# ── DB-backed radar ──────────────────────────────────────────────────────────


class TestPeerRadarFromDb:
    def test_basic_db_radar(self, db_conn):
        fig = create_peer_radar_from_db(db_conn, "TCS", 2024)
        assert isinstance(fig, plt.Figure)
        ax = fig.axes[0]
        assert type(ax).__name__ == "PolarAxes"
        # Should have 2 lines: TCS + IT Avg overlay
        assert len(ax.lines) == 2
        plt.close(fig)

    def test_missing_company_raises(self, db_conn):
        with pytest.raises(ValueError, match="No peer data"):
            create_peer_radar_from_db(db_conn, "NONEXISTENT", 2024)

    def test_title_contains_company(self, db_conn):
        fig = create_peer_radar_from_db(db_conn, "TCS", 2024)
        ax = fig.axes[0]
        assert "TCS" in ax.get_title()
        plt.close(fig)


# ── Batch export ──────────────────────────────────────────────────────────────


class TestExportPeerGroupRadars:
    def test_exports_all_members(self, db_conn, tmp_path):
        paths = export_peer_group_radars(db_conn, "IT", 2024, str(tmp_path))
        assert len(paths) == 3  # TCS, INFY, WIPRO
        for p in paths:
            assert p.exists()

    def test_exports_png_files(self, db_conn, tmp_path):
        paths = export_peer_group_radars(db_conn, "IT", 2024, str(tmp_path))
        for p in paths:
            assert p.suffix == ".png"

    def test_empty_group_returns_empty_list(self, db_conn, tmp_path):
        paths = export_peer_group_radars(
            db_conn, "NONEXISTENT_GROUP", 2024, str(tmp_path)
        )
        assert paths == []

    def test_files_have_reasonable_size(self, db_conn, tmp_path):
        paths = export_peer_group_radars(db_conn, "IT", 2024, str(tmp_path))
        for p in paths:
            assert p.stat().st_size > 5000  # radar PNGs are > 5 KB typically


# ── Visual integrity ─────────────────────────────────────────────────────────


class TestVisualIntegrity:
    def test_strong_company_polygon_is_above_peer(self, company_pctls, peer_avg_pctls):
        """When company percentiles > peer avg, the polygon should be larger."""
        fig = create_radar_chart("StrongCo", "IT", 2024, company_pctls, peer_avg_pctls)
        ax = fig.axes[0]
        # Company line is the first (blue), peer avg is second (red)
        company_line = ax.lines[0]
        peer_line = ax.lines[1]
        # The company polygon has higher values → larger y-range on polar
        co_max = max(company_line.get_ydata())
        pa_max = max(peer_line.get_ydata())
        assert co_max > pa_max
        plt.close(fig)
