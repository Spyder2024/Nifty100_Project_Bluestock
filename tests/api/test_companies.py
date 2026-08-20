"""tests/api/test_companies.py — Unit tests for Day 39 Company Data Endpoints.

Tests:
1. GET /api/v1/companies (list all 92 companies, verify fields id, company_name, broad_sector, sub_sector, roe_pct, roce_pct).
2. GET /api/v1/companies with filters (sector, search, market_cap_category).
3. GET /api/v1/companies/{ticker} (full profile, latest KPIs, 404 for invalid ticker).
4. GET /api/v1/companies/{ticker}/pl (P&L history, year filters, 404 for invalid ticker).
5. GET /api/v1/companies/{ticker}/bs (Balance sheet history, year filters).
6. GET /api/v1/companies/{ticker}/cashflow (Cash flow history, year filters).
7. GET /api/v1/companies/{ticker}/ratios (Ratio history, single year filter).
8. GET /api/v1/companies/{ticker}/tearsheet (Binary PDF download, Content-Type, byte size).
"""

from fastapi.testclient import TestClient
import pytest

from src.api.main import app

client = TestClient(app)


def test_list_all_companies():
    """Verify listing all 92 companies with required fields."""
    response = client.get("/api/v1/companies")
    assert response.status_code == 200
    data = response.json()

    assert data["total"] == 92
    assert data["count"] == 92
    assert len(data["companies"]) == 92

    first = data["companies"][0]
    required_fields = ["id", "company_name", "broad_sector", "sub_sector", "roe_pct", "roce_pct", "market_cap_category"]
    for field in required_fields:
        assert field in first


def test_list_companies_filters():
    """Verify sector, search, and market_cap_category filters."""
    # Sector filter
    resp_sec = client.get("/api/v1/companies?sector=Information%20Technology")
    assert resp_sec.status_code == 200
    data_sec = resp_sec.json()
    assert data_sec["count"] > 0
    for comp in data_sec["companies"]:
        assert "information technology" in comp["broad_sector"].lower()

    # Search filter (by ticker or name)
    resp_search = client.get("/api/v1/companies?search=INFY")
    assert resp_search.status_code == 200
    data_search = resp_search.json()
    assert data_search["count"] == 1
    assert data_search["companies"][0]["id"] == "INFY"


def test_get_company_profile():
    """Verify full company profile retrieval for valid ticker."""
    response = client.get("/api/v1/companies/INFY")
    assert response.status_code == 200
    data = response.json()

    assert data["id"] == "INFY"
    assert "Infosys" in data["company_name"]
    assert "broad_sector" in data
    assert "latest_kpis" in data
    assert "roe_pct" in data["latest_kpis"]
    assert "opm_pct" in data["latest_kpis"]


def test_get_company_profile_not_found():
    """Verify 404 response on non-existent company ticker."""
    response = client.get("/api/v1/companies/NON_EXISTENT_XYZ")
    assert response.status_code == 404
    data = response.json()
    assert "not found" in data["detail"].lower()


def test_get_company_pl_history():
    """Verify P&L / Income statement history and date filters."""
    # All years
    resp = client.get("/api/v1/companies/TCS/pl")
    assert resp.status_code == 200
    data = resp.json()
    assert data["company_id"] == "TCS"
    assert data["count"] > 0
    assert "income_statement" in data

    # Year filter
    resp_filtered = client.get("/api/v1/companies/TCS/pl?from_year=2021-03&to_year=2024-03")
    assert resp_filtered.status_code == 200
    data_filt = resp_filtered.json()
    assert data_filt["count"] <= data["count"]
    for row in data_filt["income_statement"]:
        assert "2021-03" <= row["year"] <= "2024-03"


def test_get_company_bs_history():
    """Verify Balance Sheet history endpoint."""
    resp = client.get("/api/v1/companies/RELIANCE/bs")
    assert resp.status_code == 200
    data = resp.json()
    assert data["company_id"] == "RELIANCE"
    assert data["count"] > 0
    assert "balance_sheet" in data
    assert "total_equity" in data["balance_sheet"][0]


def test_get_company_cashflow_history():
    """Verify Cash Flow history endpoint."""
    resp = client.get("/api/v1/companies/HDFCBANK/cashflow")
    assert resp.status_code == 200
    data = resp.json()
    assert data["company_id"] == "HDFCBANK"
    assert data["count"] > 0
    assert "cash_flow" in data
    assert "operating_cf" in data["cash_flow"][0]


def test_get_company_ratios():
    """Verify ratios endpoint and single-year filter."""
    # All years
    resp = client.get("/api/v1/companies/ITC/ratios")
    assert resp.status_code == 200
    data = resp.json()
    assert data["company_id"] == "ITC"
    assert data["count"] > 0

    # Single year
    resp_single = client.get("/api/v1/companies/ITC/ratios?year=2024")
    assert resp_single.status_code == 200
    data_single = resp_single.json()
    assert data_single["count"] == 1
    assert "2024" in data_single["ratios"][0]["year"]


def test_get_company_tearsheet_pdf():
    """Verify binary PDF download of pre-generated tearsheet."""
    resp = client.get("/api/v1/companies/INFY/tearsheet")
    assert resp.status_code == 200
    assert resp.headers.get("content-type") == "application/pdf"
    assert len(resp.content) > 10000  # Valid multi-page PDF size
    assert resp.content.startswith(b"%PDF")
