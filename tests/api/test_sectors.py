"""tests/api/test_sectors.py — Sector Analytics Endpoints Unit Tests (Day 42).

Sprint 7, Day 42

Tests:
1. GET /api/v1/sectors and /sectors returns all sectors with company counts and median KPIs.
2. GET /api/v1/sectors/IT and /sectors/IT returns companies from IT sector only.
3. GET /api/v1/sectors/Information Technology/companies returns IT constituents.
4. GET /api/v1/sectors/INVALID returns HTTP 404 Not Found.
"""

from fastapi.testclient import TestClient

from src.api.main import app

client = TestClient(app)


def test_list_all_sectors():
    """Verify GET /sectors returns all sectors with median KPIs."""
    for path in ["/api/v1/sectors", "/sectors"]:
        resp = client.get(path)
        assert resp.status_code == 200
        data = resp.json()
        assert data["total_sectors"] >= 10
        assert len(data["sectors"]) == data["total_sectors"]

        for sec in data["sectors"]:
            assert "sector_name" in sec
            assert "company_count" in sec
            assert sec["company_count"] > 0
            assert "median_roe" in sec
            assert "median_de" in sec


def test_get_sector_it_companies():
    """Verify /sectors/IT and /api/v1/sectors/IT return companies from IT sector only."""
    for path in [
        "/api/v1/sectors/IT",
        "/sectors/IT",
        "/api/v1/sectors/Information%20Technology",
    ]:
        resp = client.get(path)
        assert resp.status_code == 200
        data = resp.json()
        assert "Information Technology" in data["sector"]
        assert data["company_count"] == 5
        tickers = [c["company_id"] for c in data["companies"]]
        for expected in ["INFY", "TCS", "HCLTECH", "LTIM", "TECHM"]:
            assert expected in tickers


def test_get_sector_not_found():
    """Verify GET /sectors/INVALID returns HTTP 404."""
    for path in ["/api/v1/sectors/NON_EXISTENT_SECTOR", "/sectors/NON_EXISTENT_SECTOR"]:
        resp = client.get(path)
        assert resp.status_code == 404
        assert "not found" in resp.json()["detail"].lower()
