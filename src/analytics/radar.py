"""Radar (spider) chart generation for peer comparison (Day 19).

Creates polar plots showing a company's percentile ranks across 10
key metrics, with optional peer-group-average overlay.  Exports to
PNG via ``export_radar_png`` or batch via ``export_peer_group_radars``.
"""

from __future__ import annotations

from pathlib import Path
from typing import Optional

import matplotlib
matplotlib.use("Agg")  # non-interactive — safe for headless / CI

import matplotlib.pyplot as plt
import numpy as np
from matplotlib.figure import Figure


# ── Metric labels for radar axes ───────────────────────────────────────────────

DEFAULT_METRIC_LABELS: dict[str, str] = {
    "return_on_equity": "ROE",
    "return_on_capital_employed": "ROCE",
    "net_profit_margin": "NPM",
    "operating_profit_margin": "OPM",
    "cfo_quality_score": "CFO Quality",
    "operating_cash_flow_ratio": "OCF Ratio",
    "debt_to_equity": "D/E\n(inverted)",
    "interest_coverage_ratio": "ICR",
    "revenue_cagr_5yr": "Revenue\nCAGR 5Y",
    "net_profit_cagr_5yr": "PAT\nCAGR 5Y",
}

RADAR_METRICS: list[str] = list(DEFAULT_METRIC_LABELS.keys())
"""Default 10 metrics shown on the radar chart."""


# ── Core chart builder ────────────────────────────────────────────────────────

def create_radar_chart(
    company_name: str,
    peer_group: str,
    year: int,
    company_percentiles: dict[str, float],
    peer_avg_percentiles: Optional[dict[str, float]] = None,
    metrics: Optional[list[str]] = None,
    metric_labels: Optional[dict[str, str]] = None,
    title: Optional[str] = None,
    figsize: tuple[float, float] = (8, 8),
    company_color: str = "#1E88E5",
    peer_color: str = "#E53935",
    fill_alpha: float = 0.15,
) -> Figure:
    """Build a radar (polar) chart for a single company's peer percentiles.

    Parameters
    ----------
    company_name, peer_group, year
        Metadata shown in the title and legend.
    company_percentiles
        ``{metric_name: percentile_rank_0_to_100}`` for the target company.
    peer_avg_percentiles
        Same shape for the peer-group average.  If *None*, no overlay is drawn.
    metrics, metric_labels
        Override which metrics / labels to display.  Defaults to
        :data:`RADAR_METRICS` and :data:`DEFAULT_METRIC_LABELS`.
    title
        Custom chart title.  Defaults to
        ``"{company_name} — {peer_group} — {year}"``.
    figsize, company_color, peer_color, fill_alpha
        Visual tuning knobs.

    Returns
    -------
    matplotlib.figure.Figure
        The caller is responsible for closing it (e.g. via
        :func:`export_radar_png` or ``plt.close(fig)``).
    """
    if metrics is None:
        metrics = RADAR_METRICS
    if metric_labels is None:
        metric_labels = DEFAULT_METRIC_LABELS

    N = len(metrics)
    if N < 3:
        raise ValueError("Need at least 3 metrics for a radar chart")

    # ── angles (close the polygon by repeating the first angle) ───────────
    angles = np.linspace(0, 2 * np.pi, N, endpoint=False).tolist()
    angles_closed = angles + angles[:1]

    # ── values ────────────────────────────────────────────────────────────
    company_values = [company_percentiles.get(m, 0.0) for m in metrics]
    company_closed = company_values + company_values[:1]

    # ── figure + polar axes ───────────────────────────────────────────────
    fig, ax = plt.subplots(
        figsize=figsize,
        subplot_kw=dict(polar=True),
        constrained_layout=True,
    )

    # Company polygon
    ax.plot(angles_closed, company_closed, "o-", linewidth=2.2,
            color=company_color, label=company_name, markersize=5)
    ax.fill(angles_closed, company_closed, alpha=fill_alpha,
            color=company_color)

    # Peer-average overlay
    if peer_avg_percentiles is not None:
        peer_values = [peer_avg_percentiles.get(m, 0.0) for m in metrics]
        peer_closed = peer_values + peer_values[:1]
        ax.plot(angles_closed, peer_closed, "s--", linewidth=1.6,
                color=peer_color, label=f"{peer_group} Avg", markersize=4)
        ax.fill(angles_closed, peer_closed, alpha=fill_alpha * 0.5,
                color=peer_color)

    # ── styling ───────────────────────────────────────────────────────────
    labels = [metric_labels.get(m, m) for m in metrics]
    ax.set_thetagrids(np.degrees(angles), labels, fontsize=9)

    ax.set_ylim(0, 100)
    ax.set_yticks([20, 40, 60, 80, 100])
    ax.set_yticklabels(["20", "40", "60", "80", "100"],
                        fontsize=7, color="grey")

    ax.grid(True, alpha=0.3)
    ax.spines["polar"].set_visible(False)

    # Title
    if title is None:
        title = f"{company_name} — {peer_group} — {year}"
    ax.set_title(title, fontsize=13, fontweight="bold", pad=20)

    ax.legend(loc="upper right", bbox_to_anchor=(1.35, 1.15), fontsize=9)

    return fig


# ── PNG export ────────────────────────────────────────────────────────────────

def export_radar_png(
    fig: Figure,
    output_path: str,
    dpi: int = 150,
    bbox_inches: str = "tight",
) -> Path:
    """Save a matplotlib Figure to PNG and close it.

    Returns the resolved absolute path.
    """
    out = Path(output_path)
    out.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(str(out), dpi=dpi, bbox_inches=bbox_inches, facecolor="white")
    plt.close(fig)
    return out.resolve()


# ── DB-backed convenience ────────────────────────────────────────────────────

def create_peer_radar_from_db(
    conn,
    company_name: str,
    year: int,
    metrics: Optional[list[str]] = None,
    **kwargs,
) -> Figure:
    """Build a radar chart directly from the ``peer_percentiles`` table.

    Automatically fetches the company's percentiles and its peer-group
    average, then delegates to :func:`create_radar_chart`.
    """
    from .peer import load_peer_percentiles, PEER_METRICS as _RM

    if metrics is None:
        metrics = _RM

    company_data = load_peer_percentiles(conn, company_name=company_name, year=year)
    if company_data.empty:
        raise ValueError(f"No peer data found for {company_name} in {year}")

    company_pctls = dict(
        zip(company_data["metric_name"], company_data["percentile_rank"])
    )

    peer_group = company_data.iloc[0]["peer_group"]

    # Compute peer group mean percentiles
    peer_data = load_peer_percentiles(conn, peer_group=peer_group, year=year)
    peer_avg = (
        peer_data.groupby("metric_name")["percentile_rank"].mean().to_dict()
    )

    return create_radar_chart(
        company_name=company_name,
        peer_group=peer_group,
        year=year,
        company_percentiles=company_pctls,
        peer_avg_percentiles=peer_avg,
        metrics=metrics,
        **kwargs,
    )


def export_peer_group_radars(
    conn,
    peer_group: str,
    year: int,
    output_dir: str,
    metrics: Optional[list[str]] = None,
    dpi: int = 150,
) -> list[Path]:
    """Generate and save radar PNGs for every company in a peer group.

    Returns a list of resolved file paths.
    """
    from .peer import (
        load_peer_percentiles,
        get_peer_group_members,
        PEER_METRICS as _RM,
    )

    if metrics is None:
        metrics = _RM

    members = get_peer_group_members(conn, peer_group, year)
    if members.empty:
        return []

    # Peer-group average (computed once)
    peer_data = load_peer_percentiles(conn, peer_group=peer_group, year=year)
    peer_avg = (
        peer_data.groupby("metric_name")["percentile_rank"].mean().to_dict()
    )

    out_dir = Path(output_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    paths: list[Path] = []

    for _, row in members.iterrows():
        name = row["company_name"]
        company_data = load_peer_percentiles(conn, company_name=name, year=year)
        if company_data.empty:
            continue

        company_pctls = dict(
            zip(company_data["metric_name"], company_data["percentile_rank"])
        )

        fig = create_radar_chart(
            company_name=name,
            peer_group=peer_group,
            year=year,
            company_percentiles=company_pctls,
            peer_avg_percentiles=peer_avg,
            metrics=metrics,
        )

        safe_name = name.replace(" ", "_").replace("&", "and")
        filename = f"{safe_name}_{peer_group.replace(' ', '_')}_{year}_radar.png"
        path = export_radar_png(fig, str(out_dir / filename), dpi=dpi)
        paths.append(path)

    return paths