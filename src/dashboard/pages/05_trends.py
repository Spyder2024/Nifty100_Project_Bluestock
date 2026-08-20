"""Trend Analysis — multi-metric 10-year trend lines."""

from __future__ import annotations

from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

import streamlit as st
import plotly.graph_objects as go

from src.dashboard.utils.db import get_companies, get_ratios

st.header("Trend Analysis")
st.caption("Plot 10-year trends for key financial metrics of any Nifty 100 company.")

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
    key="trends_company",
)

if not isinstance(choice, str) or not choice.strip():
    st.info("Select a company to view trend analysis.")
    st.stop()

ticker = choice.split("  —  ")[0].strip()

# ── Load all-year ratios ──────────────────────────────────────────────
ratios = get_ratios(ticker)

if ratios.empty:
    st.warning(f"No financial-ratio data available for {ticker}.")
    st.stop()

# ── Metric catalogue (only those actually present in the DataFrame) ───
METRIC_CATALOG: dict[str, str] = {
    "roe": "ROE (%)",
    "roce": "ROCE (%)",
    "net_profit_margin": "Net Profit Margin (%)",
    "opm": "OPM (%)",
    "debt_to_equity": "Debt-to-Equity",
    "current_ratio": "Current Ratio",
    "pe_ratio": "P/E Ratio",
    "price_to_book": "P/B Ratio",
    "revenue_cagr_5yr": "Revenue CAGR 5Y (%)",
    "net_profit_cagr_5yr": "PAT CAGR 5Y (%)",
    "earning_yield": "Earning Yield (%)",
    "dividend_payout": "Dividend Payout (%)",
}

present = {k: v for k, v in METRIC_CATALOG.items() if k in ratios.columns}

if not present:
    st.warning("No recognised financial metrics found in the ratio data.")
    st.stop()

selected_labels = st.multiselect(
    "Choose metrics to plot",
    list(present.values()),
    default=list(present.values())[:4],
    key="trends_metrics",
)

# Map display labels back to column names
label_to_col = {v: k for k, v in present.items()}
chosen_cols = [label_to_col[lbl] for lbl in selected_labels if lbl in label_to_col]

if not chosen_cols:
    st.info("Select at least one metric above to render the chart.")
    st.stop()

# ── Plotly multi-line chart ───────────────────────────────────────────
PALETTE = [
    "#1E88E5",
    "#E53935",
    "#43A047",
    "#FB8C00",
    "#8E24AA",
    "#00ACC1",
    "#6D4C41",
    "#546E7A",
    "#D81B60",
    "#3949AB",
    "#7CB342",
]

fig = go.Figure()

for i, col in enumerate(chosen_cols):
    fig.add_trace(
        go.Scatter(
            x=ratios["year"],
            y=ratios[col],
            name=present[col],
            mode="lines+markers",
            line=dict(color=PALETTE[i % len(PALETTE)], width=2),
            marker=dict(size=5),
            connectgaps=True,
        )
    )

fig.update_layout(
    xaxis_title="Year",
    yaxis_title="Value",
    margin=dict(t=30, b=40, l=60, r=20),
    legend=dict(orientation="h", yanchor="bottom", y=1.02),
    hovermode="x unified",
)

st.plotly_chart(fig, use_container_width=True)

# ── Raw data expander ─────────────────────────────────────────────────
with st.expander("View Raw Data"):
    show = ratios[["year"] + chosen_cols].copy()
    for c in chosen_cols:
        if show[c].dtype in ("float64", "float32"):
            show[c] = show[c].round(2)
    st.dataframe(show.reset_index(drop=True), hide_index=True, use_container_width=True)
