"""Dashboard settings — cache management, data audit, session state reset.

This is the final screen in the 9-page dashboard.  It provides operational
controls that tie together every other screen.
"""

from __future__ import annotations

import sqlite3
import sys
from pathlib import Path

import pandas as pd
import plotly.express as px
import streamlit as st

# ── Multi-page path fix ────────────────────────────────────────────────────
sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

from src.dashboard.utils.db import (  # noqa: E402
    get_sectors,
)
from src.dashboard.utils.error_handler import (  # noqa: E402
    null_audit,
    safe_execute,
    validate_dataframe,
)

DB_PATH = Path(__file__).resolve().parents[3] / "output" / "nifty100.db"

st.set_page_config(page_title="Settings & QA", page_icon="⚙️", layout="wide")


# ── Helpers ────────────────────────────────────────────────────────────────


@st.cache_data(ttl=600)
def _table_row_counts() -> dict[str, int]:
    """Row counts for every user-facing table."""
    if not DB_PATH.exists():
        return {}
    conn = sqlite3.connect(str(DB_PATH))
    # ── Discover which tables actually exist ──────────────────────────
    existing = {
        r[0]
        for r in conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table'"
        ).fetchall()
    }
    wanted = [
        "companies",
        "balance_sheet",
        "cash_flow",
        "financial_ratios",
        "pros_cons",
    ]
    counts: dict[str, int] = {}
    for t in wanted:
        if t not in existing:
            counts[t] = -1
            continue
        try:
            counts[t] = int(
                pd.read_sql(f"SELECT COUNT(*) AS c FROM {t}", conn).iloc[0, 0]
            )
        except Exception:
            counts[t] = -1
    conn.close()
    return counts


@st.cache_data(ttl=600)
def _db_size_mb() -> float:
    """Return DB file size in MB."""
    if not DB_PATH.exists():
        return 0.0
    return round(DB_PATH.stat().st_size / (1024 * 1024), 2)


def _get_db_schema() -> pd.DataFrame:
    """Read full DB schema via PRAGMA."""
    if not DB_PATH.exists():
        return pd.DataFrame()
    conn = sqlite3.connect(str(DB_PATH))
    schema = pd.read_sql(
        "SELECT name AS table_name, sql FROM sqlite_master "
        "WHERE type='table' ORDER BY name",
        conn,
    )
    conn.close()
    return schema


# ── Page content ───────────────────────────────────────────────────────────

st.title("⚙️ Settings & Data Audit")
st.caption("Cache management, data health checks, and session controls.")

# ── Row 1: Quick Stats ─────────────────────────────────────────────────────
st.subheader("Database Health")

col_db, col_cache, col_session = st.columns(3)

with col_db:
    st.metric("DB Size", f"{_db_size_mb()} MB")
    counts = _table_row_counts()
    for tbl, cnt in counts.items():
        if cnt >= 0:
            st.write(f"**{tbl}**: {cnt:,} rows")
        else:
            st.write(f"**{tbl}**: ❌ not found")

with col_cache:
    st.markdown("**Cache Controls**")
    st.caption("Cached data refreshes every 10 min (TTL=600s).")
    if st.button("🗑️ Clear All Caches", use_container_width=True):
        st.cache_data.clear()
        st.success("All cached data cleared.  Refresh pages to reload.")
    st.divider()
    st.markdown("You can also press **`C`** on any page to clear caches globally.")

with col_session:
    st.markdown("**Session State**")
    st.caption("Reset picks the currently selected company across pages.")
    if st.button("🔄 Reset Session State", use_container_width=True):
        for key in list(st.session_state.keys()):
            del st.session_state[key]
        st.success("Session state cleared.")

# ── Row 2: Null Audit per table ───────────────────────────────────────────
st.subheader("Data Coverage Audit")
st.caption("Null percentages per column — expand each table to inspect.")

if DB_PATH.exists():
    conn = sqlite3.connect(str(DB_PATH))
    # ── Discover actual table names, skip missing ones ────────────────
    _db_tables = [
        r[0]
        for r in conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table'"
        ).fetchall()
    ]

    _wanted = ["financial_ratios", "balance_sheet", "cash_flow", "companies"]
    # If financial_ratios is missing, try a ratio-like alias
    if "financial_ratios" not in _db_tables:
        _alias = next((t for t in _db_tables if "ratio" in t.lower()), None)
        if _alias:
            _wanted[_wanted.index("financial_ratios")] = _alias

    for table in _wanted:
        if table not in _db_tables:
            with st.expander(f"📊 {table}"):
                st.warning(f"Table `{table}` not found in database.")
            continue
        _is_ratios = "ratio" in table.lower()
        with st.expander(f"📊 {table}", expanded=_is_ratios):
            try:
                df = pd.read_sql(f"SELECT * FROM {table}", conn)
            except Exception as e:
                st.error(f"Failed to read `{table}`: {e}")
                continue
            audit = null_audit(df, component=table)
            if audit.empty:
                st.info("No data.")
            else:
                st.dataframe(
                    audit,
                    use_container_width=True,
                    hide_index=True,
                    column_config={
                        "null_pct": st.column_config.ProgressColumn(
                            "Null %", format="%.1f%%", min_value=0, max_value=100
                        )
                    },
                )
    conn.close()
else:
    st.error("Database file not found.")

# ── Row 3: Sector distribution quick check ────────────────────────────────
st.subheader("Sector Distribution Check")
sectors = safe_execute(get_sectors, component="get_sectors")
if validate_dataframe(sectors, component="Sector distribution"):
    fig = px.pie(
        sectors,
        values="company_count",
        names="broad_sector",
        hole=0.45,
        title="Companies per Broad Sector",
    )
    fig.update_layout(
        margin=dict(t=40, b=10, l=10, r=10),
        height=420,
        showlegend=True,
        legend=dict(font=dict(size=11)),
    )
    st.plotly_chart(fig, use_container_width=True)

# ── Row 4: Year coverage ──────────────────────────────────────────────────
st.subheader("Year Coverage")

if DB_PATH.exists():
    conn = sqlite3.connect(str(DB_PATH))
    year_data = []
    for table in ["balance_sheet", "cash_flow"]:
        years = pd.read_sql(f"SELECT DISTINCT year FROM {table} ORDER BY year", conn)[
            "year"
        ].tolist()
        year_data.append(
            {
                "table": table,
                "min_year": min(years),
                "max_year": max(years),
                "count": len(years),
            }
        )
    conn.close()

    st.dataframe(
        pd.DataFrame(year_data),
        use_container_width=True,
        hide_index=True,
        column_config={
            "min_year": st.column_config.NumberColumn("Earliest Year", format="%d"),
            "max_year": st.column_config.NumberColumn("Latest Year", format="%d"),
            "count": st.column_config.NumberColumn("Years Available", format="%d"),
        },
    )
else:
    st.warning("Cannot check year coverage — DB not found.")

# ── Row 5: DB Schema reference ────────────────────────────────────────────
st.subheader("DB Schema Reference")

schema_df = safe_execute(_get_db_schema, component="Schema reader")
if validate_dataframe(
    schema_df, required_cols=["table_name", "sql"], component="Schema"
):
    for _, row in schema_df.iterrows():
        with st.expander(f"📋 {row['table_name']}"):
            st.code(row["sql"], language="sql")

# ── Row 6: Known gotchas reference ────────────────────────────────────────
st.subheader("Known Gotchas (Dev Reference)")
with st.expander("Click to expand"):
    st.markdown("""
1. **PyArrow `None` ≠ NaN** — `.abs()` throws `TypeError` on `None`.
   Always chain `.fillna(0)` before `.abs()` or arithmetic ops.

2. **`na_position="bottom"` is invalid** — pandas only accepts
   `"first"` or `"last"`. Use `na_position="last"`.

3. **`broad_sector` lives ONLY in `financial_ratios`** — not in the
   `companies` table. Join on `company_id` when needed.

4. **Cache TTL = 600s** — all `@st.cache_data` functions auto-expire.
   Press `C` or use Settings page to force-clear.

5. **Percentile method** — use average-rank:
   `(below + 0.5 * equal) / n * 100`.  Invert for D/E:
   `100 - percentile`.
        """)
