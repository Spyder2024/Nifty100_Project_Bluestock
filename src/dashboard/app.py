"""Nifty 100 Financial Intelligence Platform — Streamlit entry point.

Run with:
    streamlit run src/dashboard/app.py
"""

import streamlit as st

st.set_page_config(
    page_title="Nifty 100 Analytics",
    layout="wide",
    initial_sidebar_state="expanded",
)

st.title("Nifty 100 Financial Intelligence Platform")
st.markdown(
    """
    Welcome! Use the **sidebar navigation** to explore the 8 screens.

    | Screen | Description |
    |--------|-------------|
    | Home | KPI overview, sector breakdown, top-5 quality companies |
    | Company Profile | Deep-dive into any Nifty-100 company |
    | Screener | Filter 92 companies by 10 financial metrics |
    | Peer Comparison | Radar chart + table vs peer group |
    | Trend Analysis | 10-year multi-metric trend lines |
    | Sector Analysis | Bubble chart & median KPIs by sector |
    | Capital Allocation | Treemap of 8 capital-allocation patterns |
    | Annual Reports | BSE annual-report PDF links |
    """
)