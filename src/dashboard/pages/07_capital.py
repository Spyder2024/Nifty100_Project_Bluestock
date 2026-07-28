"""Capital Allocation — cash flow breakdown, capital structure & ratios."""

from __future__ import annotations

from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

import pandas as pd
import streamlit as st
import plotly.graph_objects as go
import plotly.express as px

from src.dashboard.utils.db import get_companies, get_cf, get_bs

st.header("Capital Allocation")
st.caption(
    "Analyse how a company allocates capital — "
    "cash flow components, balance-sheet structure, and key ratios."
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
    key="capital_company",
)

if not isinstance(choice, str) or not choice.strip():
    st.info("Select a company to view capital allocation analysis.")
    st.stop()

ticker = choice.split("  —  ")[0].strip()

# ── Load data ─────────────────────────────────────────────────────────
cf = get_cf(ticker)
bs = get_bs(ticker)

if cf.empty and bs.empty:
    st.warning(f"No cash-flow or balance-sheet data for {ticker}.")
    st.stop()

# ── 1. Cash Flow Breakdown (grouped bar) ─────────────────────────────
st.subheader("Cash Flow Breakdown")

CF_PLOT = [
    ("operating_cf",  "Operating CF",  "#43A047"),
    ("investing_cf",  "Investing CF",  "#E53935"),
    ("financing_cf",  "Financing CF",  "#1E88E5"),
    ("net_cash_flow", "Net Cash Flow", "#FB8C00"),
]

cf_found = [(col, label, color) for col, label, color in CF_PLOT
            if not cf.empty and col in cf.columns]

if cf_found:
    fig = go.Figure()
    for col, label, color in cf_found:
        fig.add_trace(go.Bar(
            name=label, x=cf["year"], y=cf[col],
            marker_color=color,
        ))
    fig.update_layout(
        barmode="group",
        xaxis_title="Year",
        yaxis_title="INR Crore",
        margin=dict(t=30, b=40, l=60, r=20),
        legend=dict(orientation="h", yanchor="bottom", y=1.02),
    )
    st.plotly_chart(fig, use_container_width=True)
else:
    st.info("No cash-flow data available for this company.")

# ── 2. FCF & CapEx trend ─────────────────────────────────────────────
if "fcf" in cf.columns and "capex" in cf.columns and not cf.empty:
    st.subheader("Free Cash Flow & CapEx")
    fig_fc = go.Figure()
    fig_fc.add_trace(go.Bar(
        name="CapEx", x=cf["year"], y=cf["capex"].fillna(0).abs(),
        marker_color="#E53935",
    ))
    fig_fc.add_trace(go.Scatter(
        name="FCF", x=cf["year"], y=cf["fcf"],
        mode="lines+markers", line=dict(color="#43A047", width=2),
        marker=dict(size=6),
    ))
    fig_fc.update_layout(
        xaxis_title="Year", yaxis_title="INR Crore",
        margin=dict(t=30, b=40, l=60, r=20),
        legend=dict(orientation="h", yanchor="bottom", y=1.02),
        barmode="group",
    )
    st.plotly_chart(fig_fc, use_container_width=True)

# ── 3. Capital Structure Trend (BS) ───────────────────────────────────
st.subheader("Capital Structure Trend")

BS_PLOT = [
    ("total_equity", "Total Equity",     "#1E88E5"),
    ("borrowings",   "Borrowings (Debt)", "#E53935"),
    ("reserves",     "Reserves",          "#43A047"),
]

bs_found = [(col, label, color) for col, label, color in BS_PLOT
            if not bs.empty and col in bs.columns]

if bs_found:
    fig2 = go.Figure()
    for col, label, color in bs_found:
        fig2.add_trace(go.Scatter(
            x=bs["year"], y=bs[col],
            name=label, mode="lines+markers",
            line=dict(color=color, width=2), marker=dict(size=6),
        ))
    fig2.update_layout(
        xaxis_title="Year", yaxis_title="INR Crore",
        margin=dict(t=30, b=40, l=60, r=20),
        legend=dict(orientation="h", yanchor="bottom", y=1.02),
    )
    st.plotly_chart(fig2, use_container_width=True)
else:
    st.info("No balance-sheet data available for this company.")

# ── 4. Capital Allocation Treemap (latest year) ───────────────────────
if not cf.empty and "operating_cf" in cf.columns:
    st.subheader("Cash Allocation Treemap (Latest Year)")
    latest_cf = cf.iloc[-1]
    ocf = latest_cf.get("operating_cf", 0)
    capex_val = abs(latest_cf.get("capex", 0) or 0)
    div_val = abs(latest_cf.get("dividend_paid", 0) or 0)
    buyback_val = abs(latest_cf.get("buyback_paid", 0) or 0)
    fcf_val = latest_cf.get("fcf", 0) or 0

    # Build treemap data — only include items with meaningful values
    tree_items = []
    if capex_val > 0:
        tree_items.append(("CapEx", capex_val, "#E53935"))
    if div_val > 0:
        tree_items.append(("Dividends", div_val, "#FB8C00"))
    if buyback_val > 0:
        tree_items.append(("Buybacks", buyback_val, "#8E24AA"))
    if fcf_val != 0:
        tree_items.append(("Retained FCF", abs(fcf_val),
                           "#43A047" if fcf_val > 0 else "#E53935"))

    if tree_items:
        tree_df = pd.DataFrame(tree_items, columns=["Category", "Amount", "Color"])
        fig_tree = px.treemap(
            tree_df,
            path=["Category"],
            values="Amount",
            color="Category",
            color_discrete_map={item[0]: item[2] for item in tree_items},
        )
        fig_tree.update_layout(margin=dict(t=20, b=20, l=20, r=20))
        fig_tree.update_traces(
            textinfo="label+value",
            texttemplate="%{label}<br>₹%{value:,.0f} Cr",
        )
        st.plotly_chart(fig_tree, use_container_width=True)
    else:
        st.info("No allocation breakdown available for the latest year.")

# ── 5. Key Capital Ratios (latest year) ──────────────────────────────
st.subheader("Key Capital Ratios (Latest Year)")

rows: list[dict[str, str | float]] = []

if not bs.empty:
    lb = bs.iloc[-1]
    # Debt / Equity
    d = lb.get("borrowings")
    e = lb.get("total_equity")
    if pd.notna(d) and pd.notna(e) and e != 0:
        rows.append({"Ratio": "Debt / Equity", "Value": round(d / e, 2)})
    # Reserves / Equity
    r = lb.get("reserves")
    if pd.notna(r) and pd.notna(e) and e != 0:
        rows.append({"Ratio": "Reserves / Equity", "Value": round(r / e, 2)})
    # Cash / Total Assets
    a = lb.get("total_assets")
    cash = lb.get("cash_and_equiv")
    if pd.notna(a) and pd.notna(cash) and a != 0:
        rows.append({"Ratio": "Cash / Total Assets",
                      "Value": f"{cash / a * 100:.1f}%"})

if not cf.empty:
    lcf = cf.iloc[-1]
    # FCF margin
    ocf_val = lcf.get("operating_cf")
    fcf_v = lcf.get("fcf")
    if pd.notna(ocf_val) and pd.notna(fcf_v) and ocf_val != 0:
        rows.append({"Ratio": "FCF / OCF",
                      "Value": f"{fcf_v / ocf_val * 100:.1f}%"})
    # Dividend payout from cash flow
    div_v = lcf.get("dividend_paid")
    if pd.notna(ocf_val) and pd.notna(div_v) and ocf_val != 0:
        rows.append({"Ratio": "Dividend / OCF",
                      "Value": f"{abs(div_v) / abs(ocf_val) * 100:.1f}%"})

if rows:
    st.dataframe(pd.DataFrame(rows), hide_index=True, use_container_width=True)
else:
    st.info("Insufficient data to compute capital-allocation ratios.")