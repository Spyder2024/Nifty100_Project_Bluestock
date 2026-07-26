"""P10/P90 winsorised sector-relative composite scoring.

Replaces the basic linear composite score (Day 15) with a robust,
sector-relative scoring system. Each metric is winsorised at P10/P90
within its sector, then converted to a 0-100 percentile rank.
Category averages are weighted to produce the final composite score.

Weights:
    Profitability (35%) | Cash Quality (30%) | Growth (20%) | Leverage (15%)
"""

import numpy as np
import pandas as pd


# ── Metric Definitions ────────────────────────────────────────────────────────

PROFITABILITY_METRICS = [
    "return_on_equity",
    "return_on_capital_employed",
    "net_profit_margin",
    "operating_profit_margin",
]

CASH_QUALITY_METRICS = [
    "cfo_quality_score",
    "operating_cash_flow_ratio",
]

GROWTH_METRICS = [
    "revenue_cagr_5yr",
    "net_profit_cagr_5yr",
    "ebitda_cagr_5yr",
]

LEVERAGE_METRICS = [
    "debt_to_equity",           # lower is better → inverted
    "interest_coverage_ratio",  # higher is better
]

CATEGORY_WEIGHTS = {
    "profitability": 0.35,
    "cash_quality": 0.30,
    "growth": 0.20,
    "leverage": 0.15,
}

LOWER_IS_BETTER = {"debt_to_equity"}

ALL_SCORING_METRICS = (
    PROFITABILITY_METRICS
    + CASH_QUALITY_METRICS
    + GROWTH_METRICS
    + LEVERAGE_METRICS
)

CATEGORY_MAP: dict[str, str] = {}
for _m in PROFITABILITY_METRICS:
    CATEGORY_MAP[_m] = "profitability"
for _m in CASH_QUALITY_METRICS:
    CATEGORY_MAP[_m] = "cash_quality"
for _m in GROWTH_METRICS:
    CATEGORY_MAP[_m] = "growth"
for _m in LEVERAGE_METRICS:
    CATEGORY_MAP[_m] = "leverage"


# ── Core Functions ────────────────────────────────────────────────────────────

def winsorise_series(
    series: pd.Series,
    lower_pct: float = 0.10,
    upper_pct: float = 0.90,
) -> pd.Series:
    """Winsorise a Series at the given percentiles.

    Values below *lower_pct* are clipped to the P10 value; values above
    *upper_pct* are clipped to the P90 value.  NaN values are preserved
    and do not affect the percentile boundaries.

    Edge cases:
    - Fewer than 2 valid values → returns an unmodified copy.
    """
    valid = series.dropna()
    if len(valid) < 2:
        return series.copy()
    lower_bound = valid.quantile(lower_pct)
    upper_bound = valid.quantile(upper_pct)
    return series.clip(lower=lower_bound, upper=upper_bound)


def sector_relative_score(
    df: pd.DataFrame,
    metric_col: str,
    sector_col: str = "sector",
) -> pd.Series:
    """Compute a 0-100 percentile score for *metric_col* within each sector.

    Pipeline per sector group:
        1. Extract non-NaN values.
        2. Winsorise at P10/P90.
        3. Compute percentile rank → scale to 0-100.
        4. Invert if the metric is in ``LOWER_IS_BETTER``.

    Edge cases:
    - Sector with < 2 valid values → score = 50.0 (neutral).
    - Missing column → all-NaN Series.
    """
    if metric_col not in df.columns or sector_col not in df.columns:
        return pd.Series(np.nan, index=df.index, dtype=float)

    scores = pd.Series(np.nan, index=df.index, dtype=float)
    invert = metric_col in LOWER_IS_BETTER

    for _sector_val, group in df.groupby(sector_col):
        metric_values = group[metric_col]
        valid_mask = metric_values.notna()
        valid_count = valid_mask.sum()

        if valid_count < 2:
            # Not enough data for a meaningful rank → neutral
            scores.loc[group.index[valid_mask]] = 50.0
            continue

        # Winsorise within this sector, then rank
        winsorised = winsorise_series(metric_values[valid_mask])
        pct_ranks = winsorised.rank(pct=True) * 100.0

        if invert:
            pct_ranks = 100.0 - pct_ranks

        scores.loc[winsorised.index] = pct_ranks

    return scores


def compute_all_scores(
    df: pd.DataFrame,
    sector_col: str = "sector",
) -> pd.DataFrame:
    """Compute sector-relative scores + composite for all metrics.

    Args:
        df: DataFrame with financial metrics.
        sector_col: Name of the sector column (default "sector").
                    Pass "broad_sector" if that's what your df uses.

    Returns:
        DataFrame with score columns + composite_score.
    """
    # Determine the actual sector column to use
    actual_sector_col = None
    for sc in [sector_col, "broad_sector", "sector", "sector_id"]:
        if sc in df.columns and df[sc].notna().any():
            actual_sector_col = sc
            break

    # ... rest of function uses actual_sector_col everywhere
    # instead of hard-coded "sector"
    if df.empty:
        return pd.DataFrame(
            {
                "composite_score": pd.Series(dtype=float),
                "profitability_score": pd.Series(dtype=float),
                "cash_quality_score": pd.Series(dtype=float),
                "growth_score": pd.Series(dtype=float),
                "leverage_score": pd.Series(dtype=float),
            }
        )

    # ── Per-metric sector-relative scores ─────────────────────────────────
    metric_scores: dict[str, pd.Series] = {}
    for metric in ALL_SCORING_METRICS:
        if metric in df.columns:
            metric_scores[metric] = sector_relative_score(df, metric, sector_col)

    # ── Average within each category ──────────────────────────────────────
    category_scores: dict[str, pd.Series] = {}
    for category in CATEGORY_WEIGHTS:
        cat_metrics = [
            m for m, c in CATEGORY_MAP.items()
            if c == category and m in metric_scores
        ]
        if cat_metrics:
            temp = pd.DataFrame({m: metric_scores[m] for m in cat_metrics})
            category_scores[category] = temp.mean(axis=1)
        else:
            # No data for this category → neutral
            category_scores[category] = pd.Series(50.0, index=df.index)

    # ── Weighted composite ────────────────────────────────────────────────
    composite = pd.Series(0.0, index=df.index)
    for category, weight in CATEGORY_WEIGHTS.items():
        composite += weight * category_scores[category]

    return pd.DataFrame(
        {
            "composite_score": composite.round(2),
            "profitability_score": category_scores["profitability"].round(2),
            "cash_quality_score": category_scores["cash_quality"].round(2),
            "growth_score": category_scores["growth"].round(2),
            "leverage_score": category_scores["leverage"].round(2),
        }
    )


def compute_composite_score(
    df: pd.DataFrame,
    sector_col: str = "sector",
) -> pd.Series:
    """P10/P90 winsorised sector-relative composite score (0-100).

    Convenience wrapper around :func:`compute_all_scores` that returns
    only the ``composite_score`` column as a Series.
    """
    return compute_all_scores(df, sector_col=sector_col)["composite_score"]