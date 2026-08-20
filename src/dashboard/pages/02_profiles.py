"""Company Profile — search, KPIs, 10-yr charts, pros & cons."""

from __future__ import annotations
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))
import pandas as pd
import streamlit as st
import plotly.graph_objects as go

from src.dashboard.utils.db import (
    get_companies,
    get_ratios,
    get_pl,
    get_pros_cons,
)

st.header("Company Profile")

# ======================================================================
# Search box — autocomplete dropdown
# ======================================================================
companies_df = get_companies()
if companies_df.empty:
    st.warning("No companies were found in the database.")
    st.stop()
    raise SystemExit

_options = [
    f"{row['company_id']}  —  {row['company_name']}"
    for _, row in companies_df.iterrows()
]
choice = st.selectbox(
    "Search by ticker or name",
    _options,
    index=None,
    placeholder="Type to search …",
)

if not isinstance(choice, str) or not choice.strip():
    st.info("Select a company to view its profile.")
    st.stop()
    raise SystemExit

ticker = choice.split("  —  ")[0].strip()

# Fetch the matching company row
_rows = companies_df[companies_df["company_id"] == ticker]
if _rows.empty:
    st.warning("Ticker not found — please try another.")
    st.stop()

co = _rows.iloc[0]

# ======================================================================
# Company card
# ======================================================================
st.subheader(co["company_name"])
card_cols = st.columns(4)
card_cols[0].metric("NSE Ticker", co["company_id"])
card_cols[1].metric("Broad Sector", str(co.get("broad_sector", "N/A")))
card_cols[2].metric("Sub-Sector", str(co.get("sector_name", "N/A")))
card_cols[3].metric("Sector ID", str(co.get("sector_id", "N/A")))

# ======================================================================
# Load financial data
# ======================================================================
ratios = get_ratios(ticker)
pl = get_pl(ticker)

if ratios.empty:
    st.warning("No financial-ratio data available for this company.")
    st.stop()

latest_year = ratios["year"].max()
latest = ratios[ratios["year"] == latest_year].iloc[0]

# ======================================================================
# 6 KPI tiles (latest year)
# ======================================================================
st.subheader(f"Key Metrics  ({latest_year})")

_kpi_defs = [
    ("ROE", latest.get("roe"), "%", 1),
    ("ROCE", latest.get("roce"), "%", 1),
    ("NPM", latest.get("net_profit_margin"), "%", 1),
    ("D/E", latest.get("debt_to_equity"), "x", 2),
    ("Rev CAGR 5Y", latest.get("revenue_cagr_5yr"), "%", 1),
    ("FCF", latest.get("free_cash_flow"), " Cr", 0),
]

kpi_cols = st.columns(6)
for i, (label, val, unit, dec) in enumerate(_kpi_defs):
    if pd.notna(val):
        kpi_cols[i].metric(label, f"{val:.{dec}f}{unit}")
    else:
        kpi_cols[i].metric(label, "N/A")

# ======================================================================
# 10-year Revenue & Net Profit bar chart
# ======================================================================
st.subheader("Revenue & Net Profit  (10 Years)")

if pl.empty:
    st.info("No income-statement data available.")
else:
    fig = go.Figure()
    fig.add_trace(
        go.Bar(name="Revenue", x=pl["year"], y=pl["net_sales"], marker_color="#2196F3")
    )
    fig.add_trace(
        go.Bar(
            name="Net Profit", x=pl["year"], y=pl["net_profit"], marker_color="#4CAF50"
        )
    )
    fig.update_layout(
        barmode="group",
        xaxis_title="Year",
        yaxis_title="INR Crore",
        margin=dict(t=30, b=40, l=60, r=20),
        legend=dict(orientation="h", yanchor="bottom", y=1.02),
    )
    st.plotly_chart(fig, use_container_width=True)

# ======================================================================
# ROE & ROCE dual-axis line chart
# ======================================================================
st.subheader("ROE & ROCE Trend")

if len(ratios) < 2:
    st.info("Need at least 2 years of data for the trend chart.")
else:
    fig = go.Figure()
    fig.add_trace(
        go.Scatter(
            x=ratios["year"],
            y=ratios["roe"],
            name="ROE",
            mode="lines+markers",
            line=dict(color="#1565C0"),
        )
    )
    fig.add_trace(
        go.Scatter(
            x=ratios["year"],
            y=ratios["roce"],
            name="ROCE",
            mode="lines+markers",
            line=dict(color="#E65100"),
            yaxis="y2",
        )
    )
    fig.update_layout(
        yaxis=dict(title=dict(text="ROE (%)", font=dict(color="#1565C0"))),
        yaxis2=dict(
            title=dict(text="ROCE (%)", font=dict(color="#E65100")),
            overlaying="y",
            side="right",
        ),
        xaxis_title="Year",
        margin=dict(t=30, b=40, l=60, r=60),
        legend=dict(orientation="h", yanchor="bottom", y=1.02),
    )
    st.plotly_chart(fig, use_container_width=True)

# ======================================================================
# Pros & Cons
# ======================================================================
st.subheader("Strengths & Concerns")

pc = get_pros_cons(ticker)
if pc.empty:
    st.info("No pros/cons data available for this company.")
else:
    pos = pc[pc["sentiment"].str.strip().str.lower() == "positive"]
    neg = pc[pc["sentiment"].str.strip().str.lower() == "negative"]

    if not pos.empty:
        for _, row in pos.iterrows():
            st.markdown(
                f'<span style="color:green;font-size:18px">&#10004;</span> '
                f'{row["item"]}',
                unsafe_allow_html=True,
            )
    if not neg.empty:
        for _, row in neg.iterrows():
            st.markdown(
                f'<span style="color:red;font-size:18px">&#10008;</span> '
                f'{row["item"]}',
                unsafe_allow_html=True,
            )
