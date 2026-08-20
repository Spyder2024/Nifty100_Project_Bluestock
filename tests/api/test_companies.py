"""tests/api/test_companies.py — Company Data Endpoints Unit Tests (Day 42).

Sprint 7, Day 42

Tests:
1. GET /companies returns 92 records (and /api/v1/companies).
2. GET /companies/TCS returns correct profile and latest financial KPIs.
3. GET /companies/INVALID returns HTTP 404 Not Found.
4. GET /companies/{ticker}/pl returns P&L history array.
5. GET /companies/{ticker}/bs returns Balance Sheet history array.
6. GET /companies/{ticker}/cashflow returns Cash Flow history array.
7. GET /companies/{ticker}/ratios returns computed KPI ratios.
8. GET /companies/{ticker}/tearsheet returns pre-generated PDF.
9. GET /companies/{ticker}/documents returns annual report links.
10. GET /companies/{ticker}/peers/compare returns 8-axis radar comparison.
"""

from fastapi.testclient import TestClient
import pytest

from src.api.main import app

client = TestClient(app)


def test_list_all_companies_returns_92_records():
    """Verify GET /companies and GET /api/v1/companies return 92 company records."""
    for path in ["/api/v1/companies", "/companies"]:
        resp = client.get(path)
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 92
        assert len(data["companies"]) == 92
        first = data["companies"][0]
        assert "company_id" in first
        assert "company_name" in first
        assert "broad_sector" in first


def test_get_company_profile_tcs():
    """Verify GET /companies/TCS and /api/v1/companies/TCS return correct profile data."""
    for path in ["/api/v1/companies/TCS", "/companies/TCS"]:
        resp = client.get(path)
        assert resp.status_code == 200
        data = resp.json()
        assert data["company_id"] == "TCS"
        assert "Tata Consultancy Services" in data["company_name"]
        assert "Information Technology" in data["broad_sector"]
        assert "latest_ratios" in data
        assert "latest_income_statement" in data


def test_get_company_profile_not_found():
    """Verify GET /companies/INVALID returns HTTP 404."""
    for path in ["/api/v1/companies/INVALID_TICKER_XYZ", "/companies/INVALID_TICKER_XYZ"]:
        resp = client.get(path)
        assert resp.status_code == 404
        assert "not found" in resp.json()["detail"].lower()


def test_get_company_pl_history():
    """Verify GET /api/v1/companies/INFY/pl returns multi-year P&L history."""
    resp = client.get("/api/v1/companies/INFY/pl")
    assert resp.status_code == 200
    data = resp.json()
    assert data["company_id"] == "INFY"
    assert data["count"] >= 5
    assert len(data["income_statement"]) == data["count"]


def test_get_company_bs_history():
    """Verify GET /api/v1/companies/INFY/bs returns balance sheet history."""
    resp = client.get("/api/v1/companies/INFY/bs")
    assert resp.status_code == 200
    data = resp.json()
    assert data["company_id"] == "INFY"
    assert data["count"] >= 5
    assert "total_assets" in data["balance_sheet"][0]


def test_get_company_cashflow_history():
    """Verify GET /api/v1/companies/INFY/cashflow returns cash flow history."""
    resp = client.get("/api/v1/companies/INFY/cashflow")
    assert resp.status_code == 200
    data = resp.json()
    assert data["company_id"] == "INFY"
    assert data["count"] >= 5
    assert "operating_cf" in data["cash_flow"][0]


def test_get_company_ratios():
    """Verify GET /api/v1/companies/INFY/ratios returns computed KPI ratios."""
    resp = client.get("/api/v1/companies/INFY/ratios")
    assert resp.status_code == 200
    data = resp.json()
    assert data["company_id"] == "INFY"
    assert len(data["ratios"]) >= 5


def test_get_company_tearsheet_pdf():
    """Verify GET /api/v1/companies/INFY/tearsheet returns binary PDF."""
    resp = client.get("/api/v1/companies/INFY/tearsheet")
    assert resp.status_code == 200
    assert resp.headers["content-type"] == "application/pdf"
    assert len(resp.content) > 1000


def test_get_company_documents():
    """Verify GET /api/v1/companies/INFY/documents returns annual report links."""
    resp = client.get("/api/v1/companies/INFY/documents")
    assert resp.status_code == 200
    data = resp.json()
    assert data["company_id"] == "INFY"
    assert data["total_documents"] > 0
    assert "url" in data["documents"][0]
    assert data["documents"][0]["is_url_valid"] is True


def test_get_company_peer_compare():
    """Verify GET /api/v1/companies/INFY/peers/compare returns 8-axis radar data."""
    resp = client.get("/api/v1/companies/INFY/peers/compare")
    assert resp.status_code == 200
    data = resp.json()
    assert data["company_id"] == "INFY"
    assert "peer_group" in data
    assert len(data["axes"]) == 8
