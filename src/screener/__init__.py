"""Screener package — filter engine, scoring, presets, and Excel export."""

from .engine import FilterEngine
from .engine import apply_filters, load_preset
from .scoring import (
    compute_composite_score,
    compute_all_scores,
    sector_relative_score,
    winsorise_series,
    CATEGORY_WEIGHTS,
    ALL_SCORING_METRICS,
    PROFITABILITY_METRICS,
    CASH_QUALITY_METRICS,
    GROWTH_METRICS,
    LEVERAGE_METRICS,
    LOWER_IS_BETTER,
    CATEGORY_MAP,
)
from .presets import (
    run_preset,
    run_all_presets,
    validate_preset_counts,
    ALL_PRESETS,
    screen_quality_compounder,
    screen_value_pick,
    screen_growth_accelerator,
    screen_dividend_champion,
    screen_debt_free_blue_chip,
    screen_turnaround_watch,
)
from .export import export_to_excel

__all__ = [
    # Engine
    "FilterEngine",
    "apply_filters",
    "load_preset",
    # Scoring
    "compute_composite_score",
    "compute_all_scores",
    "sector_relative_score",
    "winsorise_series",
    "CATEGORY_WEIGHTS",
    "ALL_SCORING_METRICS",
    "PROFITABILITY_METRICS",
    "CASH_QUALITY_METRICS",
    "GROWTH_METRICS",
    "LEVERAGE_METRICS",
    "LOWER_IS_BETTER",
    "CATEGORY_MAP",
    # Presets
    "run_preset",
    "run_all_presets",
    "validate_preset_counts",
    "ALL_PRESETS",
    "screen_quality_compounder",
    "screen_value_pick",
    "screen_growth_accelerator",
    "screen_dividend_champion",
    "screen_debt_free_blue_chip",
    "screen_turnaround_watch",
    # Export
    "export_to_excel",
]
