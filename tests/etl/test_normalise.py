"""tests/etl/test_normalise.py — 20+ Unit Tests for normalize_year() and format normalisation.

Sprint 7, Day 41
"""

import pytest
from src.etl.normaliser import normalize_ticker, normalize_year


class TestNormalizeYearVariants:
    """20 Unit tests for normalize_year() covering all format variants and edge cases."""

    # 1. Standard Month-Year with hyphen (Mar-23)
    def test_01_mar_hyphen_2digit(self):
        assert normalize_year("Mar-23") == "2023-03"

    # 2. Standard Month-Year with space (Mar 23)
    def test_02_mar_space_2digit(self):
        assert normalize_year("Mar 23") == "2023-03"

    # 3. Full month name with hyphen and 4-digit year (March-2023)
    def test_03_march_full_4digit(self):
        assert normalize_year("March-2023") == "2023-03"

    # 4. Dec-22 month-end
    def test_04_dec_hyphen_2digit(self):
        assert normalize_year("Dec-22") == "2022-12"

    # 5. Jun-23 mid-year
    def test_05_jun_hyphen_2digit(self):
        assert normalize_year("Jun-23") == "2023-06"

    # 6. Sep-24 quarter
    def test_06_sep_hyphen_2digit(self):
        assert normalize_year("Sep-24") == "2024-09"

    # 7. Jan-25 beginning of calendar year
    def test_07_jan_hyphen_2digit(self):
        assert normalize_year("Jan-25") == "2025-01"

    # 8. FY prefix 2-digit uppercase (FY24 -> 2024-03)
    def test_08_fy_uppercase_2digit(self):
        assert normalize_year("FY24") == "2024-03"

    # 9. FY prefix lowercase (fy23 -> 2023-03)
    def test_09_fy_lowercase(self):
        assert normalize_year("fy23") == "2023-03"

    # 10. FY prefix with space (FY 22 -> 2022-03)
    def test_10_fy_with_space(self):
        assert normalize_year("FY 22") == "2022-03"

    # 11. FY prefix with 4-digit year (FY2020 -> 2020-03)
    def test_11_fy_4digit(self):
        assert normalize_year("FY2020") == "2020-03"

    # 12. Already normalised standard format (2023-03)
    def test_12_already_normalised_march(self):
        assert normalize_year("2023-03") == "2023-03"

    # 13. Already normalised calendar year-end (2022-12)
    def test_13_already_normalised_december(self):
        assert normalize_year("2022-12") == "2022-12"

    # 14. Plain 4-digit year (2023 -> 2023-03 default fiscal month)
    def test_14_plain_year_4digit(self):
        assert normalize_year("2023") == "2023-03"

    # 15. Plain 4-digit past year (2019 -> 2019-03)
    def test_15_plain_past_year(self):
        assert normalize_year("2019") == "2019-03"

    # 16. Edge case: Empty string
    def test_16_empty_string(self):
        assert normalize_year("") is None

    # 17. Edge case: Whitespace-only string
    def test_17_whitespace_only(self):
        assert normalize_year("   \t  ") is None

    # 18. Edge case: None input
    def test_18_none_input(self):
        assert normalize_year(None) is None

    # 19. Edge case: Invalid month text (Foo-23)
    def test_19_invalid_month_name(self):
        assert normalize_year("Foo-23") is None

    # 20. Edge case: Invalid format / random string ("N/A", "Unknown")
    def test_20_invalid_string_or_na(self):
        assert normalize_year("N/A") is None
        assert normalize_year("NotAYear") is None
        assert normalize_year("2023-99") is None


class TestNormalizeTicker:
    """Complementary ticker normalisation tests."""

    def test_ticker_clean_uppercase(self):
        assert normalize_ticker("infy") == "INFY"
        assert normalize_ticker("  TCS  ") == "TCS"
        assert normalize_ticker("BAJAJ-AUTO") == "BAJAJ-AUTO"
        assert normalize_ticker("M&M") == "M&M"

    def test_ticker_length_bounds(self):
        assert normalize_ticker("A") is None  # too short (<2)
        assert normalize_ticker("VERY_LONG_TICKER_NAME") is None  # too long (>12)
        assert normalize_ticker("") is None
        assert normalize_ticker(None) is None
