"""src/analytics/cashflow_kpis.py — Cash flow KPIs and capital allocation classifier.

Sprint 2, Day 11

Functions:
    free_cash_flow            — FCF = CFO + CFI
    cfo_quality_score         — Average CFO/PAT over 5 years → quality label
    capex_intensity           — |CFI| / sales × 100 → intensity label
    fcf_conversion_rate       — FCF / operating_profit × 100
    capital_allocation_pattern — 8-pattern classifier from (CFO, CFI, CFF) signs
"""

from __future__ import annotations

from typing import Optional

import csv
import logging
from pathlib import Path

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Core cash-flow KPIs
# ---------------------------------------------------------------------------

def free_cash_flow(
    operating_cf: Optional[float],
    investing_cf: Optional[float],
) -> Optional[float]:
    """Free Cash Flow = operating_cf + investing_cf.

    Negative values are allowed (company spending more than it generates).
    Returns None if either input is missing.
    """
    if operating_cf is None or investing_cf is None:
        return None
    return round(operating_cf + investing_cf, 2)


def cfo_quality_score(
    cfo_values: list[Optional[float]],
    pat_values: list[Optional[float]],
) -> Optional[str]:
    """CFO Quality based on average CFO/PAT ratio over available years.

    Classification:
        > 1.0  →  ``"High Quality"``
        0.5-1.0 → ``"Moderate"``
        < 0.5  → ``"Accrual Risk"``

    Returns None if no valid (non-zero PAT) year-pairs exist.
    """
    ratios: list[float] = []
    for cfo, pat in zip(cfo_values, pat_values):
        if cfo is None or pat is None or pat == 0:
            continue
        ratios.append(cfo / pat)

    if not ratios:
        return None

    avg_ratio = sum(ratios) / len(ratios)

    if avg_ratio > 1.0:
        return "High Quality"
    if avg_ratio >= 0.5:
        return "Moderate"
    return "Accrual Risk"


def capex_intensity(
    investing_cf: Optional[float],
    sales: Optional[float],
) -> tuple[Optional[float], str]:
    """CapEx Intensity = |investing_cf| / sales × 100.

    Classification:
        < 3%   → ``"Asset Light"``
        3-8%   → ``"Moderate"``
        > 8%   → ``"Capital Intensive"``

    Returns ``(None, "")`` if sales is zero or any input is missing.
    """
    if investing_cf is None or sales is None or sales == 0:
        return None, ""

    intensity = round(abs(investing_cf) / sales * 100, 2)

    if intensity < 3.0:
        return intensity, "Asset Light"
    if intensity <= 8.0:
        return intensity, "Moderate"
    return intensity, "Capital Intensive"


def fcf_conversion_rate(
    fcf: Optional[float],
    operating_profit: Optional[float],
) -> Optional[float]:
    """FCF Conversion Rate = (FCF / operating_profit) × 100.

    Returns None if operating_profit is zero or any input is missing.
    """
    if fcf is None or operating_profit is None or operating_profit == 0:
        return None
    return round((fcf / operating_profit) * 100, 2)


# ---------------------------------------------------------------------------
# Capital allocation 8-pattern classifier
# ---------------------------------------------------------------------------

# Sign of (CFO, CFI, CFF) → default pattern label
_SIGN_PATTERN_MAP: dict[tuple[int, int, int], str] = {
    ( 1, -1, -1): "Reinvestor",                # (+,-,-)
    ( 1,  1, -1): "Liquidating Assets",         # (+,+,-)
    (-1,  1,  1): "Distress Signal",            # (-,+,+)
    (-1, -1,  1): "Growth Funded by Debt",     # (-,-,+)
    ( 1,  1,  1): "Cash Accumulator",           # (+,+,+)
    (-1, -1, -1): "Pre-Revenue",                # (-,-,-)
    ( 1, -1,  1): "Mixed",                      # (+,-,+)
    (-1,  1, -1): "Unusual",                    # (-,+,-)
}


def _sign(value: Optional[float]) -> int:
    """Return +1, -1, or 0 for a numeric value."""
    if value is None or value == 0:
        return 0
    return 1 if value > 0 else -1


def capital_allocation_pattern(
    cfo: Optional[float],
    cfi: Optional[float],
    cff: Optional[float],
    cfo_pat_ratio: Optional[float] = None,
    high_cfo_pat_threshold: float = 1.5,
) -> str:
    """Classify a company-year into one of 8 capital-allocation patterns.

    Parameters
    ----------
    cfo, cfi, cff   : Cash flow from operating / investing / financing.
    cfo_pat_ratio   : Pre-computed CFO ÷ PAT ratio (optional).
    high_cfo_pat_threshold : Ratio above which a Reinvestor is
                      reclassified as *Shareholder Returns* (default 1.5).

    Returns
    -------
    Pattern label string.
    """
    s_cfo = _sign(cfo)
    s_cfi = _sign(cfi)
    s_cff = _sign(cff)

    key = (s_cfo, s_cfi, s_cff)
    label = _SIGN_PATTERN_MAP.get(key, "Unclassified")

    # Override: (+,-,-) with high CFO/PAT → Shareholder Returns
    if (
        label == "Reinvestor"
        and cfo_pat_ratio is not None
        and cfo_pat_ratio > high_cfo_pat_threshold
    ):
        label = "Shareholder Returns"

    return label


def classify_capital_allocation(
    cfo: Optional[float],
    cfi: Optional[float],
    cff: Optional[float],
    cfo_pat_ratio: Optional[float] = None,
) -> dict:
    """Return a full classification dict for one company-year.

    Returns ``{cfo_sign, cfi_sign, cff_sign, pattern_label}``.
    """
    return dict(
        cfo_sign=_sign(cfo),
        cfi_sign=_sign(cfi),
        cff_sign=_sign(cff),
        pattern_label=capital_allocation_pattern(
            cfo, cfi, cff, cfo_pat_ratio
        ),
    )


# ---------------------------------------------------------------------------
# CSV generation (called by Day 12 runner)
# ---------------------------------------------------------------------------

ALLOCATION_CSV_COLUMNS = [
    "company_id", "year",
    "cfo_sign", "cfi_sign", "cff_sign",
    "pattern_label",
]


def generate_capital_allocation_csv(
    rows: list[dict],
    output_path: str = "output/capital_allocation.csv",
) -> None:
    """Write capital-allocation classifications to CSV.

    Parameters
    ----------
    rows : List of dicts, each containing at least
           ``company_id``, ``year``, ``cfo_sign``,
           ``cfi_sign``, ``cff_sign``, ``pattern_label``.
    """
    Path(output_path).parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=ALLOCATION_CSV_COLUMNS)
        writer.writeheader()
        for row in rows:
            writer.writerow({k: row.get(k, "") for k in ALLOCATION_CSV_COLUMNS})

    logger.info(
        "Capital allocation CSV written: %d rows → %s",
        len(rows), output_path,
    )