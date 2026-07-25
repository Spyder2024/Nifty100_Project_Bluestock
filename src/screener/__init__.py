"""Screener module — Filter Engine, Presets, Composite Score."""

from src.screener.engine import FilterEngine, apply_filters, load_preset
from src.screener.presets import (
    ALL_PRESETS,
    run_all_presets,
    run_preset,
    screen_debt_free_blue_chip,
    screen_dividend_champion,
    screen_growth_accelerator,
    screen_quality_compounder,
    screen_turnaround_watch,
    screen_value_pick,
    validate_preset_counts,
)

__all__ = [
    "FilterEngine",
    "apply_filters",
    "load_preset",
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
]