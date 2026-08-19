"""tests/analytics/test_tearsheet.py — Unit & Integration tests for Day 33 Tearsheet generator.

Sprint 5, Day 33
"""

import re
from pathlib import Path
import pytest

from src.reports.tearsheet import (
    get_company_tearsheet_data,
    render_revenue_profit_chart,
    render_profitability_trend_chart,
    render_balance_sheet_chart,
    render_cashflow_waterfall_chart,
    build_tearsheet_pdf,
    generate_tearsheet,
    generate_all_tearsheets,
)


def _get_pdf_page_count(pdf_path: Path) -> int:
    with open(pdf_path, "rb") as f:
        data = f.read()
    pages = re.findall(rb"/Type\s*/Page\b", data)
    return len(pages)


class TestTearsheetDataExtraction:

    def test_extracts_tcs_data(self):
        data = get_company_tearsheet_data("TCS")
        assert data["ticker"] == "TCS"
        assert "company_name" in data
        assert "latest_year" in data
        assert isinstance(data["pros"], list)
        assert isinstance(data["cons"], list)
        assert data["cap_pattern"] != ""

    def test_extracts_hdfcbank_data(self):
        data = get_company_tearsheet_data("HDFCBANK")
        assert data["ticker"] == "HDFCBANK"
        assert not data["df_is"].empty or not data["df_bs"].empty


class TestTearsheetCharts:

    def test_revenue_profit_chart_renders(self):
        data = get_company_tearsheet_data("TCS")
        buf = render_revenue_profit_chart(data["df_is"])
        assert buf is not None
        assert buf.getbuffer().nbytes > 1000

    def test_profitability_trend_chart_renders(self):
        data = get_company_tearsheet_data("TCS")
        buf = render_profitability_trend_chart(data["df_ratios"])
        assert buf is not None
        assert buf.getbuffer().nbytes > 1000

    def test_balance_sheet_chart_renders(self):
        data = get_company_tearsheet_data("TCS")
        buf = render_balance_sheet_chart(data["df_bs"])
        assert buf is not None
        assert buf.getbuffer().nbytes > 1000

    def test_cashflow_waterfall_chart_renders(self):
        data = get_company_tearsheet_data("TCS")
        buf = render_cashflow_waterfall_chart(data["latest_cf_row"])
        assert buf is not None
        assert buf.getbuffer().nbytes > 1000


class TestTearsheetPDFGeneration:

    @pytest.mark.parametrize("ticker", ["TCS", "HDFCBANK", "RELIANCE", "SUNPHARMA", "TATASTEEL"])
    def test_generates_exact_2_page_pdf(self, ticker, tmp_path):
        pdf_path = generate_tearsheet(ticker, output_dir=tmp_path)
        assert pdf_path.exists()
        assert pdf_path.stat().st_size > 50000  # Non-empty, rich PDF
        pages = _get_pdf_page_count(pdf_path)
        assert pages == 2, f"{ticker} PDF generated {pages} pages instead of 2"

    def test_generate_all_tearsheets_subset(self, tmp_path):
        generated, skipped = generate_all_tearsheets(tickers=["TCS", "RELIANCE"], output_dir=tmp_path)
        assert len(generated) == 2
        for r in generated:
            assert r.exists()
            assert _get_pdf_page_count(r) == 2

