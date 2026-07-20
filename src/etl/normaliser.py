"""Normalisation utilities for Nifty 100 ETL pipeline."""

import logging
import re
from typing import Optional

logger = logging.getLogger(__name__)

# Month name mapping (full and abbreviated)
_MONTH_MAP: dict[str, int] = {
    "jan": 1,
    "january": 1,
    "feb": 2,
    "february": 2,
    "mar": 3,
    "march": 3,
    "apr": 4,
    "april": 4,
    "may": 5,
    "jun": 6,
    "june": 6,
    "jul": 7,
    "july": 7,
    "aug": 8,
    "august": 8,
    "sep": 9,
    "sept": 9,
    "september": 9,
    "oct": 10,
    "october": 10,
    "nov": 11,
    "november": 11,
    "dec": 12,
    "december": 12,
}

# Regex patterns for year parsing
# Pattern 1: "Mar-23" or "Dec-22" or "Jun-23"
_RE_MONTH_SHORT_YEAR = re.compile(r"^([A-Za-z]{3,9})[\s\-/]+(\d{2,4})$", re.IGNORECASE)
# Pattern 2: "FY23" or "FY24"
_RE_FY_PREFIX = re.compile(r"^FY\s*(\d{2,4})$", re.IGNORECASE)
# Pattern 3: "2023-03" (already normalised)
_RE_NORMALISED = re.compile(r"^(\d{4})-(\d{2})$")
# Pattern 4: Plain year "2023"
_RE_PLAIN_YEAR = re.compile(r"^(\d{4})$")


def normalize_year(raw: str) -> Optional[str]:
    """Convert any year label to 'YYYY-MM' format.

    Handles: 'Mar-23', 'Mar 23', 'March-2023', '2023', 'FY23',
    'Dec-22', 'Jun-23', '2023-03', '2023-03'.

    Returns:
        Normalised string like '2023-03', or None (PARSE_ERROR)
        if input cannot be parsed.
    """
    if not isinstance(raw, str):
        return None

    value = raw.strip()
    if not value:
        return None

    # Already normalised: "2023-03"
    match = _RE_NORMALISED.match(value)
    if match:
        year_str, month_str = match.group(1), match.group(2)
        month_int = int(month_str)
        if 1 <= month_int <= 12:
            return f"{year_str}-{month_int:02d}"
        return None

    # Plain 4-digit year: "2023" → assume March FY close
    match = _RE_PLAIN_YEAR.match(value)
    if match:
        year = int(match.group(1))
        if 1990 <= year <= 2100:
            return f"{year}-03"
        return None

    # "Mar-23", "Dec-22", "Mar 23", "March-2023", "June 2023"
    match = _RE_MONTH_SHORT_YEAR.match(value)
    if match:
        month_name = match.group(1).lower()
        year_part = match.group(2)

        month_num = _MONTH_MAP.get(month_name)
        if month_num is None:
            logger.debug("Unknown month name: %s", month_name)
            return None

        # Handle 2-digit year: "23" → "2023"
        year_int = int(year_part)
        if year_int < 100:
            year_int += 2000

        if 1990 <= year_int <= 2100:
            return f"{year_int}-{month_num:02d}"
        return None

    # "FY23", "FY24"
    match = _RE_FY_PREFIX.match(value)
    if match:
        year_part = match.group(1)
        year_int = int(year_part)
        if year_int < 100:
            year_int += 2000
        # FY23 = financial year ending March 2023
        return f"{year_int}-03"

    # Nothing matched — unparseable
    logger.warning("normalize_year: PARSE_ERROR for raw value '%s'", raw)
    return None


def normalize_ticker(raw: str) -> Optional[str]:
    """Normalise an NSE ticker: strip whitespace, uppercase, validate length.

    Valid tickers are 2-12 characters after normalisation.
    Preserves hyphens (BAJAJ-AUTO) and ampersands (M&M).

    Returns:
        Uppercase stripped ticker, or None if invalid.
    """
    if not isinstance(raw, str):
        return None

    value = raw.strip().upper()
    if not value:
        return None

    length = len(value)
    if length < 2 or length > 12:
        logger.warning(
            "normalize_ticker: rejected '%s' — length %d " "outside valid range 2-12",
            raw,
            length,
        )
        return None

    return value
