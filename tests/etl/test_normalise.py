"""Unit tests for normalize_year() and normalize_ticker()."""

from src.etl.normaliser import normalize_ticker, normalize_year

# ============================================================
# normalize_year() — 20+ test cases
# ============================================================


class TestNormalizeYearStandardFormats:
    """Standard year label formats from project document Section 23."""

    def test_year_mar23(self) -> None:
        assert normalize_year("Mar-23") == "2023-03"

    def test_year_mar_23_space(self) -> None:
        assert normalize_year("Mar 23") == "2023-03"

    def test_year_march_2023_full(self) -> None:
        assert normalize_year("March-2023") == "2023-03"

    def test_year_dec22(self) -> None:
        assert normalize_year("Dec-22") == "2022-12"

    def test_year_jun23(self) -> None:
        assert normalize_year("Jun-23") == "2023-06"

    def test_year_sept24(self) -> None:
        assert normalize_year("Sep-24") == "2024-09"

    def test_year_jan25(self) -> None:
        assert normalize_year("Jan-25") == "2025-01"


class TestNormalizeYearFYFormat:
    """FY prefix formats — Indian financial year convention."""

    def test_fy24(self) -> None:
        assert normalize_year("FY24") == "2024-03"

    def test_fy23_lowercase(self) -> None:
        assert normalize_year("fy23") == "2023-03"

    def test_fy22_with_space(self) -> None:
        assert normalize_year("FY 22") == "2022-03"

    def test_fy20_four_digit(self) -> None:
        assert normalize_year("FY2020") == "2020-03"


class TestNormalizeYearAlreadyNormalised:
    """Already in YYYY-MM format — pass through."""

    def test_normalised_2023_03(self) -> None:
        assert normalize_year("2023-03") == "2023-03"

    def test_normalised_2022_12(self) -> None:
        assert normalize_year("2022-12") == "2022-12"

    def test_normalised_2024_06(self) -> None:
        assert normalize_year("2024-06") == "2024-06"


class TestNormalizeYearPlainYear:
    """Plain 4-digit year — assume March FY close."""

    def test_plain_2023(self) -> None:
        assert normalize_year("2023") == "2023-03"

    def test_plain_2020(self) -> None:
        assert normalize_year("2020") == "2020-03"


class TestNormalizeYearEdgeCases:
    """Edge cases: garbage, empty, None, non-string."""

    def test_garbage_returns_none(self) -> None:
        assert normalize_year("xyz") is None

    def test_empty_string_returns_none(self) -> None:
        assert normalize_year("") is None

    def test_none_input_returns_none(self) -> None:
        assert normalize_year(None) is None  # type: ignore[arg-type]

    def test_integer_input_returns_none(self) -> None:
        assert normalize_year(2023) is None  # type: ignore[arg-type]

    def test_whitespace_only_returns_none(self) -> None:
        assert normalize_year("   ") is None

    def test_unknown_month_returns_none(self) -> None:
        assert normalize_year("ABC-23") is None

    def test_slash_separator(self) -> None:
        assert normalize_year("Mar/23") == "2023-03"

    def test_february_leap_year(self) -> None:
        assert normalize_year("Feb-24") == "2024-02"

    def test_full_month_december(self) -> None:
        assert normalize_year("December-2024") == "2024-12"


# ============================================================
# normalize_ticker() — 15+ test cases
# ============================================================


class TestNormalizeTickerStandard:
    """Standard NSE ticker normalisation."""

    def test_tcs(self) -> None:
        assert normalize_ticker("TCS") == "TCS"

    def test_reliance(self) -> None:
        assert normalize_ticker("RELIANCE") == "RELIANCE"


class TestNormalizeTickerWhitespace:
    """Whitespace handling — strip both sides."""

    def test_strip_spaces(self) -> None:
        assert normalize_ticker("  TCS  ") == "TCS"

    def test_strip_tab(self) -> None:
        assert normalize_ticker("\tHDFCBANK\t") == "HDFCBANK"

    def test_strip_newline(self) -> None:
        assert normalize_ticker("\nINFY\n") == "INFY"


class TestNormalizeTickerCase:
    """Lowercase → uppercase."""

    def test_lowercase_to_upper(self) -> None:
        assert normalize_ticker("tcs") == "TCS"

    def test_mixed_case(self) -> None:
        assert normalize_ticker("HdfcBank") == "HDFCBANK"


class TestNormalizeTickerSpecialChars:
    """Preserve valid special characters in NSE tickers."""

    def test_hyphen_preserved(self) -> None:
        assert normalize_ticker("BAJAJ-AUTO") == "BAJAJ-AUTO"

    def test_ampersand_preserved(self) -> None:
        assert normalize_ticker("M&M") == "M&M"

    def test_hyphen_lowercase(self) -> None:
        assert normalize_ticker("bajaj-auto") == "BAJAJ-AUTO"


class TestNormalizeTickerEdgeCases:
    """Invalid inputs — should return None."""

    def test_too_short_returns_none(self) -> None:
        assert normalize_ticker("A") is None

    def test_too_long_returns_none(self) -> None:
        assert normalize_ticker("THISISWAYTOOLONG") is None

    def test_empty_string_returns_none(self) -> None:
        assert normalize_ticker("") is None

    def test_none_input_returns_none(self) -> None:
        assert normalize_ticker(None) is None  # type: ignore[arg-type]

    def test_integer_input_returns_none(self) -> None:
        assert normalize_ticker(123) is None  # type: ignore[arg-type]

    def test_whitespace_only_returns_none(self) -> None:
        assert normalize_ticker("   ") is None

    def test_single_char_returns_none(self) -> None:
        assert normalize_ticker("Z") is None

    def test_exactly_12_chars_valid(self) -> None:
        """Boundary: 12 chars is the max allowed length."""
        ticker = "A" * 12  # exactly 12 characters — the upper boundary
        result = normalize_ticker(ticker)
        assert result is not None
        assert len(result) == 12

    def test_13_chars_returns_none(self) -> None:
        ticker = "A" * 13  # one over the 12-char limit
        assert normalize_ticker(ticker) is None
