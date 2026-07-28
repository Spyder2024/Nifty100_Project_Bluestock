"""Peer Comparison — radar chart, percentile table, top/bottom performers."""

from __future__ import annotations

from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

import pandas as pd
import streamlit as st
import plotly.graph_objects as go

from src.dashboard.utils.db import get_all_ratios, get_companies

st.header("Peer Comparison")
st.caption(
    "Compare a company against its sector peers with a radar chart "
    "and percentile rankings."
)

# ── Year selector ──────────────────────────────────────────────────────
YEARS = [str(y) for y in range(2019, 2025)]
year: str = st.sidebar.selectbox(
    "Fiscal Year", YEARS, index=len(YEARS) - 1, key="peers_year"
)

# ── Company selector ───────────────────────────────────────────────────
companies_df = get_companies()

if companies_df.empty:
    st.warning("No companies found in the database.")
    st.stop()

_options = [
    f"{row['company_id']}  —  {row['company_name']}"
    for _, row in companies_df.iterrows()
]
choice = st.selectbox(
    "Select Company",
    _options,
    index=None,
    placeholder="Type to search ...",
    key="peers_company",
)

if not isinstance(choice, str) or not choice.strip():
    st.info("Select a company to view peer comparison.")
    st.stop()

ticker = choice.split("  —  ")[0].strip()

# ── Load ratio data for the chosen year ────────────────────────────────
all_ratios = get_all_ratios(year)

if all_ratios.empty:
    st.warning(f"No financial-ratio data for year {year}.")
    st.stop()

company_rows = all_ratios[all_ratios["company_id"] == ticker]
if company_rows.empty:
    st.warning(f"No data for {ticker} in {year}.")
    st.stop()

company = company_rows.iloc[0]
company_name = company.get("company_name", ticker)

# ── Determine peer group via broad_sector ─────────────────────────────
peer_group = company.get("broad_sector")

if pd.isna(peer_group) or not str(peer_group).strip():
    st.warning("This company has no sector / peer group assigned.")
    st.stop()

peer_group = str(peer_group).strip()

st.subheader(f"{company_name}  vs  {peer_group} Peers")

# ── Slice the peer group ───────────────────────────────────────────────
peer_df = all_ratios[all_ratios["broad_sector"] == peer_group].copy()
peer_count = len(peer_df)

st.caption(f"Peer group size: **{peer_count}** companies")

if peer_count < 2:
    st.warning(
        f"Only {peer_count} company in this peer group.  "
        "Need at least 2 for a meaningful comparison."
    )
    st.stop()

# ── Radar metric definitions ──────────────────────────────────────────
# (db_column, display_label, invert)
#   invert=True  → lower raw value is better (D/E)
#                  percentile is flipped so high = good
RADAR_METRICS: list[tuple[str, str, bool]] = [
    ("roe",                "ROE",           False),
    ("roce",               "ROCE",          False),
    ("net_profit_margin",  "NPM",           False),
    ("opm",                "OPM",           False),
    ("current_ratio",      "Current Ratio", False),
    ("interest_coverage",  "ICR",           False),
    ("debt_to_equity",     "D/E (inv)",     True),
    ("revenue_cagr_5yr",   "Rev CAGR 5Y",   False),
    ("net_profit_cagr_5yr","PAT CAGR 5Y",   False),
    ("earning_yield",      "Earning Yield", False),
]


# ── Percentile helper ─────────────────────────────────────────────────

def _percentile_rank(value: float, series: pd.Series) -> float:
    """Return 0-100 percentile rank of *value* within *series*.

    Ties are split equally (average-rank method).
    Returns 50.0 when data is insufficient.
    """
    valid = series.dropna()
    n = len(valid)
    if n < 2 or pd.isna(value):
        return 50.0
    below = int((valid < value).sum())
    equal = int((valid == value).sum())
    return round((below + 0.5 * equal) / n * 100, 1)


# ── Compute percentiles for every radar metric ────────────────────────
company_pcts: list[float] = []
peer_avg_pcts: list[float] = []
metric_labels: list[str] = []
detail_rows: list[dict] = []

for col, label, invert in RADAR_METRICS:
    if col not in peer_df.columns:
        continue

    metric_labels.append(label)
    raw_val = company.get(col)
    peer_series = peer_df[col]
    peer_mean = float(peer_series.mean())

    pct = _percentile_rank(raw_val, peer_series)
    avg_pct = _percentile_rank(peer_mean, peer_series)

    if invert:
        pct = 100.0 - pct
        avg_pct = 100.0 - avg_pct

    company_pcts.append(pct)
    peer_avg_pcts.append(avg_pct)

    display_val = round(raw_val, 2) if pd.notna(raw_val) else "N/A"
    detail_rows.append({
        "Metric": label,
        "Company Value": display_val,
        "Peer Average": round(peer_mean, 2),
        "Percentile": pct,
    })

# ── Radar chart (Plotly Scatterpolar) ─────────────────────────────────
if len(metric_labels) >= 3:
    # Close the polygon by repeating the first point
    r_company = company_pcts + company_pcts[:1]
    r_peer = peer_avg_pcts + peer_avg_pcts[:1]
    theta = metric_labels + metric_labels[:1]

    fig = go.Figure()

    fig.add_trace(go.Scatterpolar(
        r=r_company,
        theta=theta,
        fill="toself",
        name=company_name,
        line=dict(color="#1E88E5", width=2.5),
        marker=dict(size=6),
    ))

    fig.add_trace(go.Scatterpolar(
        r=r_peer,
        theta=theta,
        fill="toself",
        name=f"{peer_group} Avg",
        line=dict(color="#E53935", width=1.8, dash="dot"),
        marker=dict(size=5),
    ))

    fig.update_layout(
        polar=dict(
            radialaxis=dict(
                visible=True,
                range=[0, 100],
                tickfont=dict(size=8),
            ),
            angularaxis=dict(tickfont=dict(size=10)),
        ),
        showlegend=True,
        legend=dict(orientation="h", yanchor="bottom", y=-0.05),
        margin=dict(t=40, b=60, l=40, r=40),
        height=520,
    )

    st.plotly_chart(fig, use_container_width=True)
else:
    st.warning(
        "Not enough metrics with data to render a radar chart (need ≥ 3)."
    )

# ── Percentile detail table ───────────────────────────────────────────
st.subheader("Percentile Breakdown")

if detail_rows:
    st.dataframe(
        pd.DataFrame(detail_rows), hide_index=True, use_container_width=True
    )

# ── Top & Bottom performers within the peer group ─────────────────────
st.subheader("Top & Bottom Performers in Peer Group")

if detail_rows:
    metric_options = [r["Metric"] for r in detail_rows]
    selected_label = st.selectbox(
        "Select Metric", metric_options, key="peers_rank_metric"
    )

    # Map display label back to DB column name
    col_map = {label: col for col, label, _ in RADAR_METRICS}
    db_col = col_map.get(selected_label)

    # Determine whether this metric is inverted
    _, _, invert = next(
        (c, l, inv) for c, l, inv in RADAR_METRICS if l == selected_label
    )

    if db_col and db_col in peer_df.columns:
        ranking = (
            peer_df[["company_name", db_col]]
            .dropna(subset=[db_col])
            .copy()
        )
        # For inverted metrics (D/E), lower raw value = better → sort ascending
        ranking = ranking.sort_values(db_col, ascending=invert)

        show_n = min(5, len(ranking))
        col_top, col_bot = st.columns(2)

        with col_top:
            qualifier = "(lowest value)" if invert else "(highest value)"
            st.markdown(f"**Top {show_n}** {qualifier}")
            top = ranking.head(show_n).reset_index(drop=True)
            top.index = top.index + 1
            st.dataframe(top, use_container_width=True)

        with col_bot:
            qualifier = "(highest value)" if invert else "(lowest value)"
            st.markdown(f"**Bottom {show_n}** {qualifier}")
            bot = ranking.tail(show_n).iloc[::-1].reset_index(drop=True)
            bot.index = bot.index + 1
            st.dataframe(bot, use_container_width=True)