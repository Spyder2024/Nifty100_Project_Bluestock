"""
Centralized error handling & data validation for the Nifty-100 dashboard.

Every page should import helpers from this module instead of scattering
raw try/except blocks.  All functions are pure or lightweight wrappers
with no side-effects beyond optional st.warning / st.error calls.
"""

from __future__ import annotations

import logging
import sys
from pathlib import Path
from typing import Any, Callable, TypeVar

import pandas as pd
import streamlit as st

# ── Logging setup ──────────────────────────────────────────────────────────
_LOG_DIR = Path(__file__).resolve().parents[3] / "logs"
_LOG_DIR.mkdir(exist_ok=True)

_file_handler = logging.FileHandler(_LOG_DIR / "dashboard_errors.log")
_file_handler.setFormatter(
    logging.Formatter("%(asctime)s [%(levelname)s] %(name)s: %(message)s")
)
logger = logging.getLogger("dashboard")
logger.setLevel(logging.ERROR)
if not logger.handlers:
    logger.addHandler(_file_handler)

# ── Type var for the safe_execute wrapper ──────────────────────────────────
F = TypeVar("F", bound=Callable[..., Any])


# ── Public API ─────────────────────────────────────────────────────────────

def safe_execute(
    func: F,
    *args: Any,
    fallback: Any = None,
    component: str = "unknown",
    reraise: bool = False,
    **kwargs: Any,
) -> Any:
    """Execute *func* inside a try/except; surface errors via Streamlit.

    Parameters
    ----------
    func        : Callable to run safely.
    *args/**kwargs: Forwarded to *func*.
    fallback    : Value returned on failure (default ``None``).
    component   : Human-readable label used in log & UI messages.
    reraise     : If True, re-raises after logging (useful for init code).

    Returns
    -------
    The return value of *func*, or *fallback* on exception.
    """
    try:
        return func(*args, **kwargs)
    except Exception as exc:
        msg = f"[{component}] {type(exc).__name__}: {exc}"
        logger.error(msg, exc_info=True)
        st.error(f"⚠️ **{component}**: {exc}")
        if reraise:
            raise
        return fallback


def validate_dataframe(
    df: pd.DataFrame | None,
    *,
    required_cols: list[str] | None = None,
    min_rows: int = 0,
    component: str = "unknown",
) -> bool:
    """Run sanity checks on a DataFrame before rendering.

    Checks (in order):
      1. *df* is not None and is a DataFrame.
      2. Row count ≥ *min_rows* (warns but does **not** fail).
      3. Every name in *required_cols* exists in ``df.columns``.
      4. Required columns that are ≥ 95 % null trigger an info banner.

    Returns ``True`` when the DataFrame is usable, ``False`` when the
    caller should skip rendering entirely.
    """
    if df is None or not isinstance(df, pd.DataFrame):
        st.warning(f"⚠️ [{component}] No data available.")
        return False

    if df.empty:
        st.warning(f"⚠️ [{component}] Empty dataset returned.")
        return False

    if len(df) < min_rows:
        st.warning(
            f"⚠️ [{component}] Only {len(df)} row(s) — expected ≥ {min_rows}."
        )

    if not required_cols:
        return True

    present = set(df.columns)
    missing = [c for c in required_cols if c not in present]
    if missing:
        st.warning(
            f"⚠️ [{component}] Columns not found: {', '.join(missing)}"
        )
        return False

    # Warn on near-empty required columns (handles both NaN and PyArrow None)
    for col in required_cols:
        null_pct = df[col].isna().mean()
        if null_pct > 0.95:
            st.info(
                f"ℹ️ [{component}] '{col}' is {null_pct:.0%} null — "
                "data may not be populated for the selected filters."
            )

    return True


def check_data_freshness(
    df: pd.DataFrame,
    year_col: str = "year",
    component: str = "unknown",
) -> int | None:
    """Return the most recent year available, or None if undetermined.

    Also shows a warning if the latest year is older than 2 years from
    the current calendar year.
    """
    if df is None or year_col not in df.columns:
        return None

    latest = int(df[year_col].max())
    current_year = pd.Timestamp.now().year
    if current_year - latest > 2:
        st.warning(
            f"⚠️ [{component}] Latest data year is {latest} — "
            f"more than 2 years behind ({current_year})."
        )
    return latest


def null_audit(df: pd.DataFrame, component: str = "unknown") -> pd.DataFrame:
    """Return a summary DataFrame of null percentages per column.

    Useful for embedding in an expander so users can see data coverage
    at a glance.
    """
    if df is None or df.empty:
        return pd.DataFrame()

    result = (
        df.isna()
        .mean()
        .mul(100)
        .round(1)
        .rename("null_pct")
        .reset_index()
        .rename(columns={"index": "column"})
        .sort_values("null_pct", ascending=False, na_position="last")
    )
    result["status"] = result["null_pct"].apply(
        lambda p: "✅" if p == 0 else ("⚠️" if p < 50 else "❌")
    )
    return result


def percentile_rank(
    value: float,
    series: pd.Series,
    *,
    higher_is_better: bool = True,
) -> float:
    """Average-rank percentile (handles ties correctly).

    ``higher_is_better=False`` inverts the score so that 100 always
    means "best" — used for metrics like D/E where lower is better.
    """
    s = series.dropna()
    if s.empty or pd.isna(value):
        return 0.0

    n = len(s)
    below = (s < value).sum()
    equal = (s == value).sum()
    raw = (below + 0.5 * equal) / n * 100

    return raw if higher_is_better else 100.0 - raw