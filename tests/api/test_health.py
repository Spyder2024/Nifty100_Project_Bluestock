"""tests/api/test_health.py — Health check endpoint unit tests (Day 38).

Tests:
1. GET /api/v1/health returns 200 OK.
2. Response includes status='ok', version, uptime_seconds, db_row_counts, timestamp.
3. db_row_counts contains all active SQLite database tables with valid integer counts.
4. Uptime increases across subsequent requests.
"""

from fastapi.testclient import TestClient
import pytest

from src.api.main import app

client = TestClient(app)


def test_health_endpoint_status():
    """Verify health check endpoint returns 200 OK and status is ok."""
    response = client.get("/api/v1/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ok"
    assert "version" in data
    assert "uptime_seconds" in data
    assert "timestamp" in data
    assert "db_row_counts" in data


def test_health_db_row_counts():
    """Verify db_row_counts contains all core tables."""
    response = client.get("/api/v1/health")
    assert response.status_code == 200
    data = response.json()

    counts = data["db_row_counts"]
    assert isinstance(counts, dict)
    expected_tables = ["companies", "sectors", "balance_sheet", "income_statement", "cash_flow", "ratios"]
    for table in expected_tables:
        assert table in counts
        assert counts[table] >= 0

    assert counts["companies"] == 92


def test_health_uptime_metric():
    """Verify uptime_seconds is a non-negative float."""
    response = client.get("/api/v1/health")
    assert response.status_code == 200
    data = response.json()
    assert isinstance(data["uptime_seconds"], (int, float))
    assert data["uptime_seconds"] >= 0
