"""Screener screen — 10 metric sliders, 6 presets, CSV export."""

from __future__ import annotations

from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

import pandas as pd
import streamlit as st

from src.dashboard.utils.db import get_all_ratios

st.header("Stock Screener")
st.caption(
    "Filter Nifty 100 companies across 10 financial metrics.  "
    "Pick a preset or tune individual sliders."
)

# ── Year selector (sidebar, unique key to avoid widget collisions) ───────
YEARS = [str(y) for y in range(2019, 2025)]
year: str = st.sidebar.selectbox(
    "Fiscal Year", YEARS, index=len(YEARS) - 1, key="screener_year"
)

# ── Load data ────────────────────────────────────────────────────────────
ratios_df = get_all_ratios(year)

if ratios_df.empty:
    st.warning(f"No financial-ratio data found for year {year}.")
    st.stop()

working = ratios_df.copy()

# Guard: some ETL paths may omit company_name from financial_ratios
if "company_name" not in working.columns:
    working["company_name"] = working["company_id"]

# ── Metric definitions ──────────────────────────────────────────────────
# (db_column, display_label, filter_direction)
#   "min" → slider sets the lower bound  (company passes if value >= threshold)
#   "max" → slider sets the upper bound  (company passes if value <= threshold)
METRIC_DEFS: list[tuple[str, str, str]] = [
    ("roe",               "ROE (%)",               "min"),
    ("roce",              "ROCE (%)",              "min"),
    ("net_profit_margin", "Net Profit Margin (%)", "min"),
    ("debt_to_equity",    "Debt-to-Equity",        "max"),
    ("pe_ratio",          "P/E Ratio",             "max"),
    ("price_to_book",     "P/B Ratio",             "max"),
    ("current_ratio",     "Current Ratio",         "min"),
    ("revenue_cagr_5yr",  "Revenue CAGR 5Y (%)",   "min"),
    ("dividend_payout",   "Dividend Payout (%)",   "min"),
    ("earning_yield",     "Earning Yield (%)",     "min"),
]

# ── Presets ─────────────────────────────────────────────────────────────
# Keys are column names; values are the slider threshold for that metric.
# For "min" metrics the value is a floor; for "max" metrics it is a ceiling.
PRESETS: dict[str, dict[str, float]] = {
    "Custom": {},
    "Value Pick": {
        "pe_ratio": 25.0,
        "price_to_book": 3.0,
        "earning_yield": 3.0,
        "roe": 12.0,
    },
    "Quality Compounder": {
        "roe": 18.0,
        "roce": 18.0,
        "net_profit_margin": 10.0,
        "revenue_cagr_5yr": 10.0,
        "debt_to_equity": 0.5,
    },
    "Debt-Free Gems": {
        "debt_to_equity": 0.01,
        "current_ratio": 1.5,
        "roe": 10.0,
    },
    "High ROE": {
        "roe": 20.0,
        "roce": 15.0,
        "net_profit_margin": 10.0,
    },
    "Dividend Yield": {
        "dividend_payout": 20.0,
        "earning_yield": 3.0,
        "debt_to_equity": 1.0,
    },
}

# ── Data-driven slider ranges ──────────────────────────────────────────


def _slider_range(series: pd.Series, pad: float = 0.10) -> tuple[float, float]:
    """Return ``(floor, ceil)`` with 10 % padding for a slider."""
    valid = series.dropna()
    if valid.empty:
        return 0.0, 100.0
    lo, hi = float(valid.min()), float(valid.max())
    if lo == hi:                       # constant column edge-case
        return round(lo - 1.0, 2), round(hi + 1.0, 2)
    margin = (hi - lo) * pad
    return round(lo - margin, 2), round(hi + margin, 2)


ranges: dict[str, tuple[float, float]] = {}
for col, _, _ in METRIC_DEFS:
    if col in working.columns:
        ranges[col] = _slider_range(working[col])

# ── Preset selector ────────────────────────────────────────────────────
preset_name = st.selectbox("Preset Filter", list(PRESETS.keys()), index=0)

# ── Build sliders — 2 per row, 5 rows total ────────────────────────────
st.subheader("Filter Criteria")

# Each entry: (column, threshold_lo, threshold_hi, direction, range_lo, range_hi)
filters: list[tuple[str, float, float, str, float, float]] = []

for i in range(0, len(METRIC_DEFS), 2):
    c_left, c_right = st.columns(2)
    for j in range(2):
        idx = i + j
        if idx >= len(METRIC_DEFS):
            break
        col, label, direction = METRIC_DEFS[idx]
        if col not in ranges:
            continue

        s_lo, s_hi = ranges[col]

        # Determine the initial slider value
        if preset_name != "Custom" and col in PRESETS[preset_name]:
            init_val = PRESETS[preset_name][col]
        else:
            init_val = s_lo if direction == "min" else s_hi

        with c_left if j == 0 else c_right:
            val = st.slider(
                label,
                min_value=s_lo,
                max_value=s_hi,
                value=init_val,
                step=0.01,
                key=f"scr_{col}",
            )
            t_lo = val if direction == "min" else s_lo
            t_hi = s_hi if direction == "min" else val
            filters.append((col, t_lo, t_hi, direction, s_lo, s_hi))

# ── Apply filters ──────────────────────────────────────────────────────
filtered = working.copy()

for col, t_lo, t_hi, direction, s_lo, s_hi in filters:
    if col not in filtered.columns:
        continue
    # Skip this metric entirely when the slider sits at the default
    # extreme — no effective filtering is being requested.
    if direction == "min" and abs(t_lo - s_lo) < 0.02:
        continue
    if direction == "max" and abs(t_hi - s_hi) < 0.02:
        continue
    # Active filter: require non-null AND within bounds
    filtered = filtered[
        filtered[col].notna() & (filtered[col] >= t_lo) & (filtered[col] <= t_hi)
    ]

# ── Results summary KPIs ───────────────────────────────────────────────
st.divider()

k1, k2, k3 = st.columns(3)
k1.metric("Companies Matched", len(filtered))
k2.metric("Total Screened", len(working))
k3.metric("Pass Rate", f"{len(filtered) / max(len(working), 1) * 100:.1f}%")

if filtered.empty:
    st.info("No companies match the current filters. Try relaxing the criteria.")
    st.stop()

# ── Sortable results table ─────────────────────────────────────────────
DISPLAY_COLS = [
    "company_name",
    "broad_sector",
    "roe",
    "roce",
    "net_profit_margin",
    "debt_to_equity",
    "pe_ratio",
    "price_to_book",
    "current_ratio",
    "revenue_cagr_5yr",
    "dividend_payout",
    "earning_yield",
    "composite_quality_score",
]

available_cols = [c for c in DISPLAY_COLS if c in filtered.columns]

sort_col = st.selectbox(
    "Sort by", available_cols, index=0, key="scr_sort"
)
ascending = st.checkbox("Ascending", value=False, key="scr_asc")

result = filtered[available_cols].sort_values(
    sort_col, ascending=ascending, na_position="last"
)

# Round floats for a cleaner table
for c in result.columns:
    if result[c].dtype in ("float64", "float32"):
        result[c] = result[c].round(2)

st.dataframe(result.reset_index(drop=True), hide_index=True, use_container_width=True)

# ── CSV download ───────────────────────────────────────────────────────
csv_bytes = result.to_csv(index=False).encode("utf-8")
st.download_button(
    label="Download Results as CSV",
    data=csv_bytes,
    file_name=f"screener_{year}.csv",
    mime="text/csv",
)