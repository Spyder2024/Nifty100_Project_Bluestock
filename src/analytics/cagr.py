"""src/analytics/cagr.py — CAGR engine with all edge case handlers.

Sprint 2, Day 10 — All Growth Metrics

CAGR formula: ((end_value / start_value) ** (1 / n_years) - 1) × 100

Edge case flags stored alongside the CAGR value:
    INSUFFICIENT     — fewer than *window* years of valid data
    ZERO_BASE        — start_value is zero (division impossible)
    DECLINE_TO_LOSS  — start > 0, end < 0 (sign change)
    TURNAROUND       — start < 0, end > 0 (sign change)
    BOTH_NEGATIVE    — both start and end are negative
    ""               — normal computation, value is valid
"""

from __future__ import annotations

from typing import Optional


# ---------------------------------------------------------------------------
# Core CAGR formula with edge-case detection
# ---------------------------------------------------------------------------

def cagr(
    start_value: Optional[float],
    end_value: Optional[float],
    n_years: Optional[int],
) -> tuple[Optional[float], str]:
    """Compute CAGR and return (value, flag).

    Parameters
    ----------
    start_value : Base-period metric value.
    end_value   : End-period metric value.
    n_years     : Number of years between the two periods.

    Returns
    -------
    (cagr_value, flag)
        cagr_value is ``None`` when a flag is raised;
        flag is ``""`` for a successful computation.
    """
    # --- missing data ---
    if start_value is None or end_value is None or n_years is None:
        return None, "INSUFFICIENT"
    if n_years < 1:
        return None, "INSUFFICIENT"

    # --- zero base ---
    if start_value == 0:
        return None, "ZERO_BASE"

    # --- sign-change edge cases ---
    if start_value > 0 and end_value < 0:
        return None, "DECLINE_TO_LOSS"
    if start_value < 0 and end_value > 0:
        return None, "TURNAROUND"
    if start_value < 0 and end_value < 0:
        return None, "BOTH_NEGATIVE"

    # --- normal computation (both ≥ 0, start > 0) ---
    # end_value == 0 is valid: CAGR = -100 %
    value = ((end_value / start_value) ** (1.0 / n_years) - 1.0) * 100.0
    return round(value, 2), ""


# ---------------------------------------------------------------------------
# Window-based CAGR from yearly time-series data
# ---------------------------------------------------------------------------

def compute_cagr_window(
    yearly_data: list[tuple[str, Optional[float]]],
    window: int,
) -> tuple[Optional[float], str]:
    """Compute CAGR over a *window*-year period from yearly data.

    Parameters
    ----------
    yearly_data : List of ``(year_str, value)`` tuples.
                  ``year_str`` format is ``"YYYY-MM"`` (e.g. ``"2023-03"``).
                  List does **not** need to be sorted; None values are skipped.
    window      : Requested window in years (3, 5, or 10).

    Logic
    -----
    1.  Filter out entries with ``None`` values and sort by year.
    2.  The **latest** valid entry is the end-point.
    3.  The start-point is the latest valid entry whose year is
        **≤ (end_year − window)**.
    4.  Delegate to :func:`cagr` for formula + edge-case handling.
    """
    # Filter and sort
    valid: list[tuple[str, float]] = [
        (y, v) for y, v in yearly_data if v is not None
    ]
    valid.sort(key=lambda pair: pair[0])

    if len(valid) < 2:
        return None, "INSUFFICIENT"

    end_year, end_value = valid[-1]
    end_y = int(end_year.split("-")[0])
    target_y = end_y - window

    # Walk backwards to find the latest year <= target
    best_start: Optional[tuple[str, float, int]] = None
    for y, v in valid:
        y_num = int(y.split("-")[0])
        if y_num <= target_y:
            best_start = (y, v, y_num)

    if best_start is None:
        return None, "INSUFFICIENT"

    _start_year, start_value, start_y = best_start
    n_years = end_y - start_y

    if n_years < 1:
        return None, "INSUFFICIENT"

    return cagr(start_value, end_value, n_years)


# ---------------------------------------------------------------------------
# Convenience: compute all three windows for one metric
# ---------------------------------------------------------------------------

def compute_all_cagrs(
    yearly_data: list[tuple[str, Optional[float]]],
) -> dict[str, tuple[Optional[float], str]]:
    """Return 3-year, 5-year, and 10-year CAGRs for one metric.

    Returns
    -------
    ``{"cagr_3yr": (val, flag), "cagr_5yr": (val, flag), "cagr_10yr": (val, flag)}``
    """
    return {
        "cagr_3yr": compute_cagr_window(yearly_data, 3),
        "cagr_5yr": compute_cagr_window(yearly_data, 5),
        "cagr_10yr": compute_cagr_window(yearly_data, 10),
    }