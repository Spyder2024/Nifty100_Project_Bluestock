"""Sector Analysis — bubble chart & median KPIs by broad sector."""

from __future__ import annotations

from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

import pandas as pd
import streamlit as st
import plotly.express as px

from src.dashboard.utils.db import get_all_ratios, get_sectors

st.header("Sector Analysis")
st.caption("Compare Nifty 100 sectors using median KPIs and distribution charts.")

# ── Year selector ─────────────────────────────────────────────────────
YEARS = [str(y) for y in range(2019, 2025)]
year: str = st.sidebar.selectbox(
    "Fiscal Year", YEARS, index=len(YEARS) - 1, key="sectors_year"
)

# ── Load data ─────────────────────────────────────────────────────────
all_ratios = get_all_ratios(year)
sectors_df = get_sectors()

if all_ratios.empty:
    st.warning(f"No financial-ratio data for year {year}.")
    st.stop()

# Drop rows with missing sector so groupby doesn't create a NaN group
all_ratios = all_ratios[all_ratios["broad_sector"].notna()].copy()

# ── Define KPIs to analyse ────────────────────────────────────────────
KPI_DEFS: list[tuple[str, str]] = [
    ("roe",               "ROE"),
    ("roce",              "ROCE"),
    ("net_profit_margin", "NPM"),
    ("debt_to_equity",    "D/E"),
    ("pe_ratio",          "P/E"),
    ("current_ratio",     "Curr. Ratio"),
]

available_kpis = [(col, label) for col, label in KPI_DEFS if col in all_ratios.columns]

if not available_kpis:
    st.warning("No recognised KPI columns found in the data.")
    st.stop()

# ── Compute medians per sector ────────────────────────────────────────
kpi_cols = [col for col, _ in available_kpis]

sector_medians = (
    all_ratios.groupby("broad_sector")[kpi_cols]
    .median()
    .round(2)
    .reset_index()
)

sector_counts = (
    all_ratios.groupby("broad_sector")["company_id"]
    .nunique()
    .rename("Companies")
    .reset_index()
)

sector_df = sector_medians.merge(sector_counts, on="broad_sector")

# ── 1. Bubble chart: ROE vs P/E ──────────────────────────────────────
st.subheader("Sector Map — ROE vs P/E")

if "roe" in sector_df.columns and "pe_ratio" in sector_df.columns:
    bubble = sector_df.dropna(subset=["roe", "pe_ratio"]).copy()
    if not bubble.empty:
        fig = px.scatter(
            bubble,
            x="roe",
            y="pe_ratio",
            size="Companies",
            color="broad_sector",
            hover_name="broad_sector",
            size_max=50,
            text="broad_sector",
        )
        fig.update_traces(textposition="top center", textfont_size=9)
        fig.update_layout(
            xaxis_title="Median ROE (%)",
            yaxis_title="Median P/E",
            margin=dict(t=30, b=40, l=60, r=20),
            legend=dict(orientation="h", yanchor="bottom", y=-0.3),
        )
        st.plotly_chart(fig, use_container_width=True)
    else:
        st.info("ROE or P/E values are all NaN — cannot render bubble chart.")
else:
    st.info("ROE or P/E column not available for bubble chart.")

# ── 2. Companies per sector (horizontal bar) ─────────────────────────
st.subheader("Companies per Sector")

if not sectors_df.empty:
    bar_data = sectors_df.sort_values("company_count", ascending=True)
    fig2 = px.bar(
        bar_data,
        x="company_count",
        y="broad_sector",
        orientation="h",
        color_discrete_sequence=["#1E88E5"],
    )
    fig2.update_layout(
        xaxis_title="Number of Companies",
        yaxis_title="",
        margin=dict(t=10, b=20, l=140, r=20),
        showlegend=False,
    )
    st.plotly_chart(fig2, use_container_width=True)

# ── 3. Median KPI table ─────────────────────────────────────────────
st.subheader("Median KPIs by Sector")

rename = {col: label for col, label in available_kpis}
display = sector_df.rename(columns=rename)
st.dataframe(display.reset_index(drop=True), hide_index=True, use_container_width=True)