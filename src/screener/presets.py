"""Preset Screener Runners — Sprint 3 Day 16.

Wraps the FilterEngine with preset-specific logic. Five of six presets
map directly to config-defined thresholds. Turnaround Watch has
custom logic requiring multi-year D/E comparison.

Usage::
    from src.screener.presets import run_preset, run_all_presets

    # Run a single preset on multi-year data (auto-selects latest year)
    result = run_preset("quality_compounder", df)

    # Run all 6 presets, returns {name: DataFrame}
    all_results = run_all_presets(df)
"""

from __future__ import annotations

from pathlib import Path
from typing import Optional

import pandas as pd

from src.screener.engine import FilterEngine

# Presets that use standard config-driven thresholds
STANDARD_PRESETS = [
    "quality_compounder",
    "value_pick",
    "growth_accelerator",
    "dividend_champion",
    "debt_free_blue_chip",
]

# Presets with custom filter logic
CUSTOM_PRESETS = [
    "turnaround_watch",
]

ALL_PRESETS = STANDARD_PRESETS + CUSTOM_PRESETS


# ==================================================================
# Helpers
# ==================================================================


def get_latest_year(df: pd.DataFrame) -> pd.DataFrame:
    """Extract the latest year row for each company.

    Expects a 'company_id' and 'year' column. Years are compared as
    strings — works with '2024', 'FY24', '2023-24', etc.
    """
    if df.empty:
        return df.copy()

    # Sort by year descending (string sort works for '2024' format)
    sorted_df = df.sort_values(
        ["company_id", "year"], ascending=[True, False]
    )
    latest = sorted_df.drop_duplicates(subset="company_id", keep="first")
    return latest.reset_index(drop=True)


def get_previous_year(df: pd.DataFrame) -> pd.DataFrame:
    """Extract the second-most-recent year row for each company.

    Returns empty DataFrame for companies with only one year of data.
    """
    if df.empty:
        return df.copy()

    sorted_df = df.sort_values(
        ["company_id", "year"], ascending=[True, False]
    )
    # Keep the 2nd row per company (index 1 after groupby)
    previous = sorted_df.groupby("company_id").nth(1).reset_index(drop=True)
    return previous


def _get_de_declining_company_ids(df: pd.DataFrame) -> set:
    """Find companies where D/E is declining year-over-year.

    Compares latest year D/E to previous year D/E. A company qualifies
    if its latest D/E is strictly less than its previous year D/E.
    Also qualifies if D/E went from positive/NaN to exactly 0.

    Args:
        df: Multi-year financial_ratios DataFrame.

    Returns:
        Set of company_id strings with declining D/E.
    """
    if df.empty or "debt_to_equity" not in df.columns:
        return set()

    sorted_df = df.sort_values(
        ["company_id", "year"], ascending=[True, False]
    )

    declining = set()

    for cid, group in sorted_df.groupby("company_id"):
        if len(group) < 2:
            continue  # Need at least 2 years

        de_values = group["debt_to_equity"].tolist()
        de_latest = de_values[0]  # sorted desc, so index 0 is latest
        de_prev = de_values[1]    # index 1 is previous

        # Skip if either is NaN
        if pd.isna(de_latest) and pd.isna(de_prev):
            continue
        if pd.isna(de_latest):
            continue
        if pd.isna(de_prev):
            continue

        # D/E declining: latest < previous
        # Also counts as declining: went from positive to zero (debt paid off)
        if de_latest < de_prev:
            declining.add(cid)

    return declining


# ==================================================================
# Individual Preset Functions
# ==================================================================


def screen_quality_compounder(
    df: pd.DataFrame,
    config_path: Optional[Path] = None,
) -> pd.DataFrame:
    """Quality Compounder: ROE > 15%, D/E < 1.0, FCF > 0, Revenue CAGR 5yr > 10%."""
    engine = FilterEngine(config_path=config_path)
    latest = get_latest_year(df)
    return engine.apply_preset(latest, "quality_compounder")


def screen_value_pick(
    df: pd.DataFrame,
    config_path: Optional[Path] = None,
) -> pd.DataFrame:
    """Value Pick: P/E < 20, P/B < 3.0, D/E < 2.0, Dividend Yield > 1%."""
    engine = FilterEngine(config_path=config_path)
    latest = get_latest_year(df)
    return engine.apply_preset(latest, "value_pick")


def screen_growth_accelerator(
    df: pd.DataFrame,
    config_path: Optional[Path] = None,
) -> pd.DataFrame:
    """Growth Accelerator: PAT CAGR 5yr > 20%, Revenue CAGR 5yr > 15%, D/E < 2.0."""
    engine = FilterEngine(config_path=config_path)
    latest = get_latest_year(df)
    return engine.apply_preset(latest, "growth_accelerator")


def screen_dividend_champion(
    df: pd.DataFrame,
    config_path: Optional[Path] = None,
) -> pd.DataFrame:
    """Dividend Champion: Dividend Yield > 2%, Payout < 80%, FCF > 0."""
    engine = FilterEngine(config_path=config_path)
    latest = get_latest_year(df)
    return engine.apply_preset(latest, "dividend_champion")


def screen_debt_free_blue_chip(
    df: pd.DataFrame,
    config_path: Optional[Path] = None,
) -> pd.DataFrame:
    """Debt-Free Blue Chip: D/E = 0, ROE > 12%, Revenue > 5000 Cr."""
    engine = FilterEngine(config_path=config_path)
    latest = get_latest_year(df)
    return engine.apply_preset(latest, "debt_free_blue_chip")


def screen_turnaround_watch(
    df: pd.DataFrame,
    config_path: Optional[Path] = None,
) -> pd.DataFrame:
    """Turnaround Watch: Revenue CAGR 5yr > 10%, FCF > 0, D/E declining YoY.

    This preset has custom logic that cannot be expressed as simple
    threshold filters because "D/E declining YoY" requires comparing
    two years of data.

    Steps:
      1. Get latest-year rows for each company.
      2. Apply standard filters: Revenue CAGR 5yr > 10%, FCF > 0.
      3. Find companies where D/E is declining year-over-year.
      4. Intersect the two result sets.
      5. Sort by composite_quality_score descending.
    """
    engine = FilterEngine(config_path=config_path)
    latest = get_latest_year(df)

    # Step 2: Apply standard turnaround_watch config filters
    filtered = engine.apply_preset(latest, "turnaround_watch")

    if filtered.empty:
        return filtered

    # Step 3: Find D/E declining companies
    declining_ids = _get_de_declining_company_ids(df)

    # Step 4: Intersect
    result = filtered[filtered["company_id"].isin(declining_ids)].copy()

    return result.reset_index(drop=True)


# ==================================================================
# Dispatcher & Batch Runner
# ==================================================================


PRESET_FUNCTIONS = {
    "quality_compounder": screen_quality_compounder,
    "value_pick": screen_value_pick,
    "growth_accelerator": screen_growth_accelerator,
    "dividend_champion": screen_dividend_champion,
    "debt_free_blue_chip": screen_debt_free_blue_chip,
    "turnaround_watch": screen_turnaround_watch,
}


def run_preset(
    preset_name: str,
    df: pd.DataFrame,
    config_path: Optional[Path] = None,
) -> pd.DataFrame:
    """Run a named preset screener on the DataFrame.

    Automatically selects latest year for standard presets.
    Turnaround Watch uses multi-year data for D/E trend.

    Args:
        preset_name: One of the 6 preset names.
        df: financial_ratios DataFrame (may be multi-year).
        config_path: Optional path to screener_config.yaml.

    Returns:
        Filtered, sorted DataFrame.

    Raises:
        KeyError: if preset_name is not recognised.
    """
    if preset_name not in PRESET_FUNCTIONS:
        raise KeyError(
            f"Unknown preset '{preset_name}'. "
            f"Available: {list(PRESET_FUNCTIONS.keys())}"
        )
    return PRESET_FUNCTIONS[preset_name](df, config_path=config_path)


def run_all_presets(
    df: pd.DataFrame,
    config_path: Optional[Path] = None,
) -> dict:
    """Run all 6 preset screeners on the DataFrame.

    Args:
        df: Multi-year financial_ratios DataFrame.
        config_path: Optional path to screener_config.yaml.

    Returns:
        Dict mapping preset_name -> filtered DataFrame.
    """
    results = {}
    for name in ALL_PRESETS:
        results[name] = run_preset(name, df, config_path=config_path)
    return results


def validate_preset_counts(
    results: dict,
    min_count: int = 5,
    max_count: int = 50,
) -> dict:
    """Validate that each preset returns a reasonable number of companies.

    Args:
        results: {preset_name: DataFrame} from run_all_presets().
        min_count: Minimum acceptable results (default 5).
        max_count: Maximum acceptable results (default 50).

    Returns:
        {preset_name: {"count": int, "pass": bool, "message": str}}
    """
    validation = {}
    for name, df in results.items():
        count = len(df)
        passed = min_count <= count <= max_count
        if passed:
            msg = f"OK ({count} companies)"
        elif count < min_count:
            msg = f"TOO FEW: {count} < {min_count} minimum"
        else:
            msg = f"TOO MANY: {count} > {max_count} maximum"
        validation[name] = {
            "count": count,
            "pass": passed,
            "message": msg,
        }
    return validation