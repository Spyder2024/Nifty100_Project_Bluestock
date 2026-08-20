"""tests/api/test_screener_peers_sectors.py — Unit tests for Day 40 API endpoints.

Tests:
1. GET /api/v1/screener (ranking, multi-metric filtering, 400 for invalid inputs).
2. GET /api/v1/sectors (medians for roe, pe, de, company count).
3. GET /api/v1/sectors/{sector}/companies (companies in sector, 404 on invalid sector).
4. GET /api/v1/peers/{group_name} (10-metric percentiles, 404 on unknown group).
5. GET /api/v1/companies/{ticker}/peers/compare (8-axis radar comparison).
6. GET /api/v1/market-cap/{ticker} (historical multiples 2019-2024, 404 on unknown ticker).
7. GET /api/v1/portfolio/stats (P10 to P90 percentile distributions).
8. GET /api/v1/companies/{ticker}/documents (annual report links and validity flags).
9. OpenAPI & Postman export artifacts exist and have valid JSON content.
"""

import json
from pathlib import Path
from fastapi.testclient import TestClient

from src.api.main import app

client = TestClient(app)
PROJECT_ROOT = Path(__file__).resolve().parents[2]


def test_screener_valid_and_ranking():
    """Verify screener filtering and ranking output."""
    resp = client.get(
        "/api/v1/screener?min_roe=15&max_de=1.0&min_rev_cagr_5yr=10&limit=5"
    )
    assert resp.status_code == 200
    data = resp.json()
    assert "results" in data
    assert data["total_matched"] > 0
    assert len(data["results"]) <= 5
    for item in data["results"]:
        assert item["roe"] >= 15.0
        assert item["debt_to_equity"] <= 1.0
        assert item["revenue_cagr_5yr"] >= 10.0
        assert "rank" in item


def test_screener_invalid_param_400():
    """Verify HTTP 400 response on invalid parameters."""
    resp_roe = client.get("/api/v1/screener?min_roe=2000")
    assert resp_roe.status_code == 400
    assert "invalid" in resp_roe.json()["detail"].lower()

    resp_de = client.get("/api/v1/screener?max_de=-2")
    assert resp_de.status_code == 400


def test_sectors_overview():
    """Verify sectors endpoint returns company count and medians."""
    resp = client.get("/api/v1/sectors")
    assert resp.status_code == 200
    data = resp.json()
    assert data["total_sectors"] >= 10
    first = data["sectors"][0]
    assert "sector_name" in first
    assert "company_count" in first
    assert "median_roe" in first
    assert "median_de" in first


def test_sector_companies_and_404():
    """Verify sector companies retrieval and 404 on unknown sector."""
    resp_ok = client.get("/api/v1/sectors/Information%20Technology/companies")
    assert resp_ok.status_code == 200
    data_ok = resp_ok.json()
    assert data_ok["company_count"] >= 5
    assert len(data_ok["companies"]) == data_ok["company_count"]

    resp_err = client.get("/api/v1/sectors/NON_EXISTENT_SECTOR_ABC/companies")
    assert resp_err.status_code == 404


def test_peer_group_percentiles_and_404():
    """Verify peer group 10-metric percentiles and 404 on unknown group."""
    resp_ok = client.get("/api/v1/peers/IT")
    assert resp_ok.status_code == 200
    data_ok = resp_ok.json()
    assert "peer_group" in data_ok
    assert len(data_ok["metrics_analyzed"]) == 10
    assert len(data_ok["companies"]) > 0

    resp_err = client.get("/api/v1/peers/UNKNOWN_PEER_GROUP_XYZ")
    assert resp_err.status_code == 404


def test_radar_peer_compare():
    """Verify 8-axis radar comparison endpoint."""
    resp = client.get("/api/v1/companies/INFY/peers/compare")
    assert resp.status_code == 200
    data = resp.json()
    assert data["company_id"] == "INFY"
    assert "benchmark_company" in data
    assert len(data["axes"]) == 8
    assert len(data["company_percentiles"]) == 8
    assert len(data["peer_group_average"]) == 8


def test_market_cap_historical_multiples():
    """Verify historical multiples for 2019-2024 and 404 for unknown ticker."""
    resp_ok = client.get("/api/v1/market-cap/INFY")
    assert resp_ok.status_code == 200
    data_ok = resp_ok.json()
    assert data_ok["total_years"] >= 5
    assert "pe_ratio" in data_ok["multiples"][0]
    assert "pb_ratio" in data_ok["multiples"][0]

    resp_err = client.get("/api/v1/market-cap/UNKNOWN_TICKER_XYZ")
    assert resp_err.status_code == 404


def test_portfolio_stats():
    """Verify portfolio percentile distribution table."""
    resp = client.get("/api/v1/portfolio/stats")
    assert resp.status_code == 200
    data = resp.json()
    assert data["total_metrics"] == 10
    for stat in data["statistics"]:
        assert "P10" in stat
        assert "P50" in stat
        assert "P90" in stat
        assert stat["P10"] <= stat["P50"] <= stat["P90"]


def test_company_documents():
    """Verify annual report document links and validity flags."""
    resp = client.get("/api/v1/companies/INFY/documents")
    assert resp.status_code == 200
    data = resp.json()
    assert data["total_documents"] > 0
    first = data["documents"][0]
    assert "url" in first
    assert "is_url_valid" in first
    assert isinstance(first["is_url_valid"], bool)


def test_openapi_and_postman_artifacts():
    """Verify generated OpenAPI and Postman collection files."""
    openapi_file = PROJECT_ROOT / "docs" / "openapi.json"
    postman_file = PROJECT_ROOT / "docs" / "postman_collection.json"

    assert openapi_file.exists()
    assert postman_file.exists()

    with open(openapi_file, encoding="utf-8") as f:
        spec = json.load(f)
        assert spec["openapi"].startswith("3.")
        assert "/api/v1/screener" in spec["paths"]
        assert "/api/v1/sectors" in spec["paths"]
        assert "/api/v1/peers/{group_name}" in spec["paths"]

    with open(postman_file, encoding="utf-8") as f:
        postman = json.load(f)
        assert postman["info"]["name"] == "Nifty 100 Financial Intelligence API"
        assert len(postman["item"]) > 0
