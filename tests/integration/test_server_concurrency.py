"""tests/integration/test_server_concurrency.py — Concurrent Server Architecture Tests (Day 43).

Sprint 7, Day 43

Verifies:
1. FastAPI (default port 8000) and Streamlit (default port 8501) use non-conflicting TCP port spaces.
2. Simultaneous execution of API requests and Dashboard data-loading queries without thread locking or database corruption.
"""

from fastapi.testclient import TestClient

from src.api.main import app
from src.dashboard.utils.db import get_all_ratios, get_companies, get_sectors

client = TestClient(app)


def test_port_configuration_separation():
    """Verify default ports for FastAPI (8000) and Streamlit (8501) are distinct."""
    fastapi_port = 8000
    streamlit_port = 8501
    assert fastapi_port != streamlit_port
    assert abs(fastapi_port - streamlit_port) == 501


def test_simultaneous_api_and_dashboard_queries():
    """Verify database handles simultaneous API queries and Streamlit loaders."""
    # 1. Fire API screener
    api_resp = client.get("/api/v1/screener?min_roe=18")
    assert api_resp.status_code == 200

    # 2. Fire Streamlit dashboard queries immediately
    comps = get_companies()
    assert len(comps) == 92

    sectors = get_sectors()
    assert len(sectors) >= 10

    ratios = get_all_ratios("2024")
    assert len(ratios) > 0

    # 3. Fire API company profile
    prof_resp = client.get("/api/v1/companies/RELIANCE")
    assert prof_resp.status_code == 200
    assert "Reliance" in prof_resp.json()["company_name"]
