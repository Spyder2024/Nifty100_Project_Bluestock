"""Home screen — KPI tiles, sector donut, top-5 quality table."""

from __future__ import annotations
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))
import streamlit as st
import pandas as pd
import plotly.express as px

from src.dashboard.utils.db import get_companies, get_sectors, get_all_ratios

# ---- year selector (lives in the sidebar, persists per page) --------
YEARS = [str(y) for y in range(2019, 2025)]
year: str = st.sidebar.selectbox("Fiscal Year", YEARS, index=len(YEARS) - 1)

st.header("Home — Nifty 100 Overview")

# ---- load data -------------------------------------------------------
companies = get_companies()
sectors_df = get_sectors()
ratios = get_all_ratios(year)

if ratios.empty:
    st.warning(f"No financial-ratio data found for year {year}.")
    st.stop()

# ======================================================================
# 1. Six KPI tiles  (2 rows x 3 cols)
# ======================================================================
avg_roe = ratios["roe"].mean()
med_pe = ratios["pe_ratio"].median()
med_de = ratios["debt_to_equity"].median()
total_cos = int(ratios["company_id"].nunique())
med_rev_cagr = ratios["revenue_cagr_5yr"].median()
debt_free = int(ratios["is_debt_free"].sum()) if "is_debt_free" in ratios.columns else 0

row1 = st.columns(3)
row2 = st.columns(3)

with row1[0]:
    st.metric("Average ROE", f"{avg_roe:.1f}%" if pd.notna(avg_roe) else "N/A")
with row1[1]:
    st.metric("Median P/E", f"{med_pe:.1f}x" if pd.notna(med_pe) else "N/A")
with row1[2]:
    st.metric("Median D/E", f"{med_de:.2f}x" if pd.notna(med_de) else "N/A")
with row2[0]:
    st.metric("Total Companies", total_cos)
with row2[1]:
    st.metric(
        "Median Revenue CAGR 5Y",
        f"{med_rev_cagr:.1f}%" if pd.notna(med_rev_cagr) else "N/A",
    )
with row2[2]:
    st.metric("Debt-Free Companies", debt_free)

# ======================================================================
# 2. Sector breakdown donut chart (Plotly)
# ======================================================================
st.subheader("Sector Breakdown")

if sectors_df.empty:
    st.info("No sector data available.")
else:
    fig = px.pie(
        sectors_df,
        values="company_count",
        names="broad_sector",
        hole=0.50,
    )
    fig.update_traces(textposition="inside", textinfo="label+percent")
    fig.update_layout(margin=dict(t=20, b=20, l=20, r=20))
    st.plotly_chart(fig, use_container_width=True)

# ======================================================================
# 3. Top-5 companies by composite quality score
# ======================================================================
st.subheader("Top 5 by Composite Quality Score")

scored = ratios.dropna(subset=["composite_quality_score"])
if scored.empty:
    st.info("No composite scores available for this year.")
else:
    top5 = scored.nlargest(5, "composite_quality_score")
    display = top5[["company_name", "broad_sector", "composite_quality_score"]].copy()
    display["composite_quality_score"] = display["composite_quality_score"].round(1)
    display.columns = ["Company", "Sector", "Score"]
    st.dataframe(
        display.reset_index(drop=True), hide_index=True, use_container_width=True
    )
