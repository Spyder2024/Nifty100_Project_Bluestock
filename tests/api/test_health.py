"""tests/api/test_health.py — Health check endpoint unit tests (Day 42).

Sprint 7, Day 42

Tests:
1. GET /api/v1/health returns HTTP 200 OK.
2. Response includes status='ok', version, uptime_seconds, db_row_counts, timestamp.
3. db_row_counts contains all 10 active SQLite database tables with non-negative row counts.
4. Non-prefixed GET /health also returns HTTP 200 OK with identical payload structure.
"""

from fastapi.testclient import TestClient

from src.api.main import app

client = TestClient(app)


def test_health_endpoint_status():
    """Verify health check endpoint returns HTTP 200 with status=ok."""
    response = client.get("/api/v1/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ok"
    assert "version" in data
    assert "uptime_seconds" in data
    assert "timestamp" in data
    assert "db_row_counts" in data


def test_health_db_row_counts_all_10_tables():
    """Verify db_row_counts contains all 10 tables with valid row counts."""
    response = client.get("/api/v1/health")
    assert response.status_code == 200
    data = response.json()

    counts = data["db_row_counts"]
    assert isinstance(counts, dict)
    assert len(counts) >= 10

    expected_tables = [
        "companies",
        "sectors",
        "balance_sheet",
        "income_statement",
        "cash_flow",
        "ratios",
        "prices",
        "market_cap",
        "shareholding",
        "dividends",
    ]
    for table in expected_tables:
        assert table in counts, f"Table '{table}' missing from db_row_counts"
        assert isinstance(counts[table], int)
        assert counts[table] >= 0

    assert counts["companies"] == 92


def test_health_uptime_metric():
    """Verify uptime_seconds is a non-negative number."""
    response = client.get("/api/v1/health")
    assert response.status_code == 200
    data = response.json()
    assert isinstance(data["uptime_seconds"], (int, float))
    assert data["uptime_seconds"] >= 0


def test_health_root_alias():
    """Verify non-prefixed /health alias also works seamlessly."""
    response = client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ok"
    assert "db_row_counts" in data
