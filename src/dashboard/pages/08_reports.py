"""Annual Reports & Resources — external links and data availability."""

from __future__ import annotations

from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

import pandas as pd
import streamlit as st

from src.dashboard.utils.db import get_companies, get_ratios, get_pl, get_bs, get_cf

st.header("Annual Reports & Resources")
st.caption(
    "External links to exchange filings and a summary of data available in the database."
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
    key="reports_company",
)

if not isinstance(choice, str) or not choice.strip():
    st.info("Select a company to view reports and resources.")
    st.stop()

ticker = choice.split("  —  ")[0].strip()
co_row = companies_df[companies_df["company_id"] == ticker].iloc[0]
co_name = co_row["company_name"]

st.subheader(co_name)

# ── External resource links ───────────────────────────────────────────
st.subheader("External Resources")

c1, c2 = st.columns(2)

with c1:
    nse_url = f"https://www.nseindia.com/market-data/equities?symbol={ticker}"
    st.markdown(f"- [**NSE India — Quotes & Announcements**]({nse_url})")

    scr_url = f"https://www.screener.in/company/{ticker}/"
    st.markdown(f"- [**Screener.in — 10-Yr Financials**]({scr_url})")

    tv_url = f"https://www.tradingview.com/symbols/NSE-{ticker}/"
    st.markdown(f"- [**TradingView — Charts**]({tv_url})")

with c2:
    bse_url = f"https://www.bseindia.com/corporates/corporate.html?scripcode={ticker}"
    st.markdown(f"- [**BSE — Corporate Filings**]({bse_url})")

    bse_ann = f"https://www.bseindia.com/corporates/CompAnnResult.aspx?expand=3&scripcode={ticker}"
    st.markdown(f"- [**BSE — Annual Report PDFs**]({bse_ann})")

    tl_url = f"https://trendlyne.com/equity/{ticker}/"
    st.markdown(f"- [**Trendlyne — Consensus Estimates**]({tl_url})")

# ── Data availability summary ─────────────────────────────────────────
st.subheader("Data Availability in Database")

ratios = get_ratios(ticker)
pl = get_pl(ticker)
bs = get_bs(ticker)
cf = get_cf(ticker)

datasets = [
    ("Financial Ratios", ratios),
    ("Income Statement", pl),
    ("Balance Sheet", bs),
    ("Cash Flow Statement", cf),
]

for name, df in datasets:
    if df.empty:
        st.markdown(f"- **{name}**: No data")
        continue
    if "year" not in df.columns:
        st.markdown(f"- **{name}**: {len(df)} rows (no year column)")
        continue
    years = sorted(df["year"].dropna().unique())
    non_id = [c for c in df.columns if c != "company_id"]
    populated = sum(1 for c in non_id if df[c].notna().any())
    first = years[0] if years else "N/A"
    last = years[-1] if years else "N/A"
    st.markdown(
        f"- **{name}**: {len(years)} years ({first} – {last}) | "
        f"{populated}/{len(non_id)} columns with data"
    )

# ── Quick snapshot from latest available ratios ───────────────────────
if not ratios.empty:
    latest_year = ratios["year"].max()
    latest = ratios[ratios["year"] == latest_year].iloc[0]

    st.subheader(f"Quick Snapshot ({latest_year})")

    snapshot_defs = [
        ("ROE", latest.get("roe"), "%", 1),
        ("ROCE", latest.get("roce"), "%", 1),
        ("NPM", latest.get("net_profit_margin"), "%", 1),
        ("D/E", latest.get("debt_to_equity"), "x", 2),
        ("P/E", latest.get("pe_ratio"), "x", 1),
    ]

    metric_cols = st.columns(5)
    for i, (label, val, unit, dec) in enumerate(snapshot_defs):
        with metric_cols[i]:
            if pd.notna(val):
                st.metric(label, f"{val:.{dec}f}{unit}")
            else:
                st.metric(label, "N/A")
