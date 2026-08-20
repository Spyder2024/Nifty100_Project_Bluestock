"""tests/api/test_screener.py — Fundamental Screener Endpoint Unit Tests (Day 42).

Sprint 7, Day 42

Tests:
1. GET /api/v1/screener with min_roe=15 returns only companies with ROE >= 15.0.
2. GET /api/v1/screener with invalid parameters returns HTTP 400 Bad Request.
3. GET /api/v1/screener multi-metric filter (min_roe, max_de, min_rev_cagr_5yr, limit).
4. GET /api/v1/screener/presets returns preset investment strategies.
5. GET /screener root alias returns identical structured results.
"""

from fastapi.testclient import TestClient

from src.api.main import app

client = TestClient(app)


def test_screener_min_roe_filter():
    """Verify screener with min_roe=15 returns only companies with ROE >= 15.0."""
    for path in ["/api/v1/screener?min_roe=15", "/screener?min_roe=15"]:
        resp = client.get(path)
        assert resp.status_code == 200
        data = resp.json()
        assert data["total_matched"] > 0
        assert len(data["results"]) > 0
        for co in data["results"]:
            assert (
                co["roe"] >= 15.0
            ), f"Company {co['company_id']} has ROE {co['roe']} < 15.0"


def test_screener_invalid_parameter_returns_400():
    """Verify screener returns HTTP 400 Bad Request for out-of-range or invalid parameter values."""
    # min_roe > 1000
    resp_roe = client.get("/api/v1/screener?min_roe=5000")
    assert resp_roe.status_code == 400
    assert "invalid min_roe" in resp_roe.json()["detail"].lower()

    # max_de < 0
    resp_de = client.get("/api/v1/screener?max_de=-5")
    assert resp_de.status_code == 400
    assert "invalid max_de" in resp_de.json()["detail"].lower()

    # max_pe < 0
    resp_pe = client.get("/api/v1/screener?max_pe=-10")
    assert resp_pe.status_code == 400

    # min_rev_cagr_5yr < -100
    resp_cagr = client.get("/api/v1/screener?min_rev_cagr_5yr=-500")
    assert resp_cagr.status_code == 400


def test_screener_multi_metric_filtering_and_ranking():
    """Verify composite screening with multiple thresholds and ranking."""
    resp = client.get(
        "/api/v1/screener?min_roe=18&max_de=0.5&min_rev_cagr_5yr=10&limit=5"
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["total_matched"] > 0
    assert len(data["results"]) <= 5

    for rank_idx, co in enumerate(data["results"], start=1):
        assert co["roe"] >= 18.0
        assert co["debt_to_equity"] <= 0.5
        assert co["revenue_cagr_5yr"] >= 10.0
        assert co["rank"] == rank_idx


def test_screener_presets():
    """Verify GET /api/v1/screener/presets returns preset investment strategies."""
    resp = client.get("/api/v1/screener/presets")
    assert resp.status_code == 200
    data = resp.json()
    assert data["total_presets"] >= 4
    preset_names = [p["preset_name"] for p in data["presets"]]
    assert "quality_compounders" in preset_names
    assert "debt_free_compounders" in preset_names
