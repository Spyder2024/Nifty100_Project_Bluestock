"""tests/etl/test_loader.py — 10 Unit Tests for raw and supporting file loaders.

Sprint 7, Day 41

Verifies loader reads correct row counts and column names for core & supporting files.
"""

import pytest
from src.etl.loader import (
    load_all_core,
    load_all_supporting,
    load_core_file,
    load_support_file,
)


def test_01_load_companies():
    """Verify companies master file row count (92) and primary columns."""
    df = load_core_file("companies")
    assert len(df) == 92
    expected_cols = ["id", "company_name", "face_value", "book_value"]
    for col in expected_cols:
        assert col in df.columns, f"Column '{col}' missing from companies dataset"


def test_02_load_profitandloss():
    """Verify profitandloss table row count and key columns."""
    df = load_core_file("profitandloss")
    assert len(df) >= 1200
    expected_cols = ["company_id", "year", "sales", "operating_profit", "net_profit"]
    for col in expected_cols:
        assert col in df.columns, f"Column '{col}' missing from profitandloss dataset"


def test_03_load_balancesheet():
    """Verify balancesheet table row count and essential balance sheet columns."""
    df = load_core_file("balancesheet")
    assert len(df) >= 1200
    expected_cols = ["company_id", "year", "equity_capital", "reserves", "borrowings", "total_assets"]
    for col in expected_cols:
        assert col in df.columns, f"Column '{col}' missing from balancesheet dataset"


def test_04_load_cashflow():
    """Verify cashflow table row count and CFO/Capex columns."""
    df = load_core_file("cashflow")
    assert len(df) >= 1000
    expected_cols = ["company_id", "year", "operating_activity", "investing_activity", "financing_activity"]
    for col in expected_cols:
        assert col in df.columns, f"Column '{col}' missing from cashflow dataset"


def test_05_load_sectors():
    """Verify sectors supporting file row count (92) and sector columns."""
    df = load_support_file("sectors")
    assert len(df) == 92
    assert "company_id" in df.columns
    assert "broad_sector" in df.columns
    assert "sub_sector" in df.columns


def test_06_load_market_cap():
    """Verify market_cap historical records (552 rows across 6 years for 92 cos)."""
    df = load_support_file("market_cap")
    assert len(df) == 552
    assert "company_id" in df.columns
    assert "year" in df.columns
    assert "market_cap_crore" in df.columns


def test_07_load_financial_ratios():
    """Verify financial_ratios table row count and ratio fields."""
    df = load_support_file("financial_ratios")
    assert len(df) >= 1000
    assert "company_id" in df.columns
    assert "year" in df.columns
    assert "net_profit_margin_pct" in df.columns


def test_08_load_documents_and_analysis():
    """Verify documents and analysis table loading."""
    docs = load_core_file("documents")
    analysis = load_core_file("analysis")
    assert len(docs) >= 1500
    assert "Annual_Report" in docs.columns or "annual_report" in [c.lower() for c in docs.columns]
    assert len(analysis) >= 10


def test_09_load_all_core_dict():
    """Verify load_all_core() loads all 7 core datasets into a single dict."""
    datasets = load_all_core()
    assert isinstance(datasets, dict)
    assert len(datasets) == 7
    expected_keys = ["companies", "profitandloss", "balancesheet", "cashflow", "analysis", "documents", "prosandcons"]
    for key in expected_keys:
        assert key in datasets
        assert len(datasets[key]) > 0


def test_10_load_invalid_dataset_raises_error():
    """Verify attempting to load non-existent dataset raises ValueError."""
    with pytest.raises(ValueError) as excinfo:
        load_core_file("non_existent_dataset_name")
    assert "Unknown core dataset" in str(excinfo.value)
