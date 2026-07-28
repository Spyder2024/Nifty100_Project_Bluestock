"""Screener screen — 10 metric sliders, 6 presets, CSV export."""

import streamlit as st
from pathlib import Path; import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[3]))
st.header("Screener")

st.info("Screener screen will be built on Day 24.")