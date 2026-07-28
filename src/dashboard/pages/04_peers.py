"""Peer Comparison screen — radar chart + side-by-side KPI table."""

import streamlit as st
from pathlib import Path; import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[3]))
st.header("Peer Comparison")

st.info("Peer Comparison screen will be built on Day 24.")