"""tests/api/test_main.py — FastAPI application scaffolding and router integration tests (Day 38).

Tests:
1. Root endpoint metadata.
2. OpenAPI documentation (/docs, /openapi.json).
3. CORS middleware headers.
4. Request logging execution time header (X-Process-Time).
5. All 8 modular routers accessible under /api/v1 prefix.
"""

from fastapi.testclient import TestClient
import pytest

from src.api.main import app

client = TestClient(app)


def test_root_endpoint():
    """Verify root endpoint returns API description and version."""
    response = client.get("/")
    assert response.status_code == 200
    data = response.json()
    assert "service" in data
    assert "version" in data
    assert data["docs_url"] == "/docs"
    assert data["health_check"] == "/api/v1/health"


def test_openapi_docs_accessible():
    """Verify Swagger UI /docs and openapi.json are accessible."""
    docs_resp = client.get("/docs")
    assert docs_resp.status_code == 200

    openapi_resp = client.get("/openapi.json")
    assert openapi_resp.status_code == 200
    schema = openapi_resp.json()
    assert schema["info"]["title"] == "Nifty 100 Financial Intelligence API"
    assert "/api/v1/health" in schema["paths"]
    assert "/api/v1/companies" in schema["paths"]


def test_cors_headers():
    """Verify CORS headers allow cross-origin requests."""
    response = client.options(
        "/api/v1/health",
        headers={
            "Origin": "http://localhost:3000",
            "Access-Control-Request-Method": "GET",
        },
    )
    assert response.status_code == 200
    assert response.headers.get("access-control-allow-origin") in ["*", "http://localhost:3000"]
    assert response.headers.get("access-control-allow-credentials") == "true"


def test_request_logging_header():
    """Verify custom execution time header is attached by logging middleware."""
    response = client.get("/api/v1/health")
    assert response.status_code == 200
    assert "x-process-time" in response.headers
    assert "ms" in response.headers["x-process-time"]


def test_all_routers_mounted():
    """Verify all 8 v1 routers return valid responses."""
    routes_to_test = [
        ("/api/v1/health", 200),
        ("/api/v1/companies?limit=2", 200),
        ("/api/v1/screener?limit=2", 200),
        ("/api/v1/screener/presets", 200),
        ("/api/v1/sectors", 200),
        ("/api/v1/peers/INFY", 200),
        ("/api/v1/valuation", 200),
        ("/api/v1/portfolio/stats", 200),
        ("/api/v1/portfolio/clusters", 200),
        ("/api/v1/portfolio/outliers", 200),
        ("/api/v1/documents", 200),
    ]

    for path, expected_status in routes_to_test:
        resp = client.get(path)
        assert resp.status_code == expected_status, f"Route {path} failed with status {resp.status_code}"
