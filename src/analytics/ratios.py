"""src/analytics/ratios.py — Financial ratio computation engine.

Sprint 2, Day 08 — Profitability Ratios

All functions accept raw numeric inputs and return computed ratios.
Returns None for invalid / undefined cases.

Column mapping (used by Day 12 runner):
    income_statement  → revenue, net_income, opm, operating_profit
    balance_sheet     → equity_capital, reserves_and_surplus,
                        borrowings, total_assets
    companies         → broad_sector
"""

from __future__ import annotations

import logging
from typing import Optional

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _safe_add(a: Optional[float], b: Optional[float]) -> Optional[float]:
    """Return a + b, or None if either operand is None."""
    if a is None or b is None:
        return None
    return a + b


# ---------------------------------------------------------------------------
# Profitability ratios
# ---------------------------------------------------------------------------

def net_profit_margin(
    net_profit: Optional[float],
    sales: Optional[float],
) -> Optional[float]:
    """Net Profit Margin = (net_profit / sales) × 100.

    Returns None if sales is None or zero, or net_profit is None.
    """
    if sales is None or net_profit is None or sales == 0:
        return None
    return round((net_profit / sales) * 100, 2)


def operating_profit_margin(
    operating_profit: Optional[float],
    sales: Optional[float],
    source_opm: Optional[float] = None,
) -> Optional[float]:
    """Operating Profit Margin = (operating_profit / sales) × 100.

    If *source_opm* is provided, cross-checks the computed value
    against it and logs a WARNING when the absolute difference
    exceeds 1 percentage point.

    Returns None if sales is None or zero, or operating_profit is None.
    """
    if sales is None or operating_profit is None or sales == 0:
        return None

    computed = round((operating_profit / sales) * 100, 2)

    if source_opm is not None:
        diff = abs(computed - source_opm)
        if diff > 1.0:
            logger.warning(
                "OPM cross-check mismatch: computed=%.2f%%, "
                "source=%.2f%%, diff=%.2fpp",
                computed, source_opm, diff,
            )

    return computed


def return_on_equity(
    net_profit: Optional[float],
    equity_capital: Optional[float],
    reserves_and_surplus: Optional[float],
) -> Optional[float]:
    """Return on Equity = (net_profit / shareholders_equity) × 100.

    shareholders_equity = equity_capital + reserves_and_surplus.

    Returns None if:
      • any input is None
      • shareholders_equity <= 0
    """
    shareholders_equity = _safe_add(equity_capital, reserves_and_surplus)
    if shareholders_equity is None or shareholders_equity <= 0:
        return None
    if net_profit is None:
        return None
    return round((net_profit / shareholders_equity) * 100, 2)


def return_on_capital_employed(
    ebit: Optional[float],
    equity_capital: Optional[float],
    reserves_and_surplus: Optional[float],
    borrowings: Optional[float],
    broad_sector: Optional[str] = None,
) -> Optional[float]:
    """Return on Capital Employed = (EBIT / capital_employed) × 100.

    capital_employed = equity_capital + reserves_and_surplus + borrowings.

    For companies in the **Financials** broad_sector the function logs
    an INFO note reminding the caller to use a sector-relative benchmark
    instead of an absolute threshold (bank carve-out — full logic in
    Day 13).

    Returns None if:
      • any input is None
      • capital_employed <= 0
    """
    capital_employed = _safe_add(
        _safe_add(equity_capital, reserves_and_surplus),
        borrowings,
    )
    if capital_employed is None or capital_employed <= 0:
        return None
    if ebit is None:
        return None

    roce = round((ebit / capital_employed) * 100, 2)

    if broad_sector and broad_sector.strip().upper() == "FINANCIALS":
        logger.info(
            "ROCE=%.2f%% for Financials sector company — "
            "use sector-relative benchmark for threshold comparison",
            roce,
        )

    return roce


def return_on_assets(
    net_profit: Optional[float],
    total_assets: Optional[float],
) -> Optional[float]:
    """Return on Assets = (net_profit / total_assets) × 100.

    Returns None if total_assets is None or zero, or net_profit is None.
    """
    if total_assets is None or net_profit is None or total_assets == 0:
        return None
    return round((net_profit / total_assets) * 100, 2)

# ---------------------------------------------------------------------------
# Leverage ratios
# ---------------------------------------------------------------------------

def debt_to_equity(
    borrowings: Optional[float],
    equity_capital: Optional[float],
    reserves_and_surplus: Optional[float],
) -> Optional[float]:
    """Debt-to-Equity = borrowings / (equity_capital + reserves_and_surplus).

    Returns **0** (not None) when borrowings is zero — a debt-free company
    still has a valid D/E ratio of 0.

    Returns None if:
      • any input is None (except borrowings=0 which is valid)
      • shareholders_equity <= 0
    """
    shareholders_equity = _safe_add(equity_capital, reserves_and_surplus)
    if shareholders_equity is None or shareholders_equity <= 0:
        return None
    if borrowings is None:
        return None
    if borrowings == 0:
        return 0
    return round(borrowings / shareholders_equity, 2)


def is_high_leverage(
    de_ratio: Optional[float],
    broad_sector: Optional[str] = None,
) -> bool:
    """Flag companies with D/E > 5 outside the Financials sector.

    High leverage is structurally normal for banks / NBFCs / insurance,
    so the flag is suppressed when *broad_sector* is ``Financials``.
    """
    if de_ratio is None:
        return False
    if broad_sector and broad_sector.strip().upper() == "FINANCIALS":
        return False
    return de_ratio > 5.0


# ---------------------------------------------------------------------------
# Coverage / solvency ratios
# ---------------------------------------------------------------------------

def interest_coverage_ratio(
    operating_profit: Optional[float],
    other_income: Optional[float],
    interest: Optional[float],
) -> Optional[float]:
    """Interest Coverage Ratio = (operating_profit + other_income) / interest.

    Returns None if:
      • any input is None
      • interest == 0  (debt-free company — use ``get_icr_label`` for label)
    """
    if operating_profit is None or other_income is None or interest is None:
        return None
    if interest == 0:
        return None
    return round((operating_profit + other_income) / interest, 2)


def get_icr_label(icr: Optional[float]) -> str:
    """Return a display label for ICR.

    ``"Debt Free"`` when ICR is None (no interest obligation).
    ``"At Risk"``   when ICR < 1.5.
    Empty string     otherwise.
    """
    if icr is None:
        return "Debt Free"
    if icr < 1.5:
        return "At Risk"
    return ""


def is_low_icr_warning(icr: Optional[float]) -> bool:
    """Return True if ICR is defined but below the 1.5× safety threshold."""
    if icr is None:
        return False
    return icr < 1.5


# ---------------------------------------------------------------------------
# Efficiency ratios
# ---------------------------------------------------------------------------

def net_debt(
    borrowings: Optional[float],
    investments: Optional[float],
) -> Optional[float]:
    """Net Debt = borrowings − investments.

    *investments* is used as a liquid-asset proxy.

    Returns None if either input is missing.
    """
    if borrowings is None or investments is None:
        return None
    return round(borrowings - investments, 2)


def asset_turnover(
    sales: Optional[float],
    total_assets: Optional[float],
) -> Optional[float]:
    """Asset Turnover = sales / total_assets.

    Returns None if total_assets is None or zero, or sales is None.
    """
    if total_assets is None or sales is None or total_assets == 0:
        return None
    return round(sales / total_assets, 2)