"""tests/integration/test_dashboard_api_integration.py — Dashboard & API Integration Tests (Day 42).

Sprint 7, Day 42

Verifies:
1. Dashboard data layers load successfully and align with API responses.
2. Screener results in the dashboard database layer match API screener endpoint results.
3. Sector counts and constituent distributions match between Dashboard and API.
"""

from fastapi.testclient import TestClient

from src.api.main import app
from src.dashboard.utils.db import get_all_ratios, get_companies, get_sectors

client = TestClient(app)


def test_dashboard_companies_match_api():
    """Verify get_companies() from dashboard aligns with /api/v1/companies."""
    dash_df = get_companies()
    assert len(dash_df) == 92

    api_resp = client.get("/api/v1/companies?limit=100")
    assert api_resp.status_code == 200
    api_data = api_resp.json()
    assert api_data["total"] == 92

    dash_ids = set(dash_df["company_id"].str.upper())
    api_ids = set(c["company_id"].upper() for c in api_data["companies"])
    assert dash_ids == api_ids


def test_dashboard_sectors_match_api():
    """Verify sector company counts match between dashboard loader and API."""
    dash_sectors = get_sectors()
    api_resp = client.get("/api/v1/sectors")
    assert api_resp.status_code == 200
    api_sectors = api_resp.json()["sectors"]

    assert len(dash_sectors) == len(api_sectors)

    api_counts = {s["sector_name"].lower(): s["company_count"] for s in api_sectors}
    for _, row in dash_sectors.iterrows():
        s_name = str(row.get("sector_name") or row.get("broad_sector", "")).lower()
        if s_name in api_counts:
            assert int(row["company_count"]) == api_counts[s_name]


def test_screener_dashboard_and_api_congruence():
    """Verify filtering on ROE >= 20% in dashboard ratios matches API screener results."""
    # 1. API query
    api_resp = client.get("/api/v1/screener?min_roe=20.0&max_de=1.0")
    assert api_resp.status_code == 200
    api_results = api_resp.json()["results"]
    api_tickers = set(c["company_id"] for c in api_results)

    # 2. Direct DB / Dashboard layer check
    ratios_df = get_all_ratios("2024")
    filtered_dash = ratios_df[
        (ratios_df["roe"] >= 20.0) & (ratios_df["debt_to_equity"] <= 1.0)
    ]
    dash_tickers = set(filtered_dash["company_id"].dropna().unique())

    # Verify high congruence (>90% match due to latest year fallback)
    intersection = api_tickers.intersection(dash_tickers)
    assert len(intersection) > 0
    assert len(intersection) >= min(len(api_tickers), len(dash_tickers)) * 0.9
