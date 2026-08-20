"""tests/integration/test_performance.py — Performance & Load SLA Unit Tests (Day 43).

Sprint 7, Day 43

Verifies:
1. 10 Concurrent Screener API calls complete in under 10.0 seconds total wall time.
2. Dashboard Company Profile load time across 5 tickers (TCS, INFY, RELIANCE, HDFCBANK, TITAN) is under 3.0 seconds each.
3. Database performance indexes exist and are actively recognized by SQLite.
"""

from pathlib import Path
import pytest
from src.analytics.optimize_db import verify_database_indexes
from src.analytics.perf_benchmark import (
    run_concurrent_screener_load_test,
    run_dashboard_profile_benchmark,
)


def test_concurrent_screener_load_under_10_seconds():
    """Verify 10 concurrent screener API requests complete within 10 seconds."""
    results = run_concurrent_screener_load_test(num_requests=10, max_workers=10)
    assert results["passed"] is True
    assert results["total_wall_time_s"] < 10.0
    assert results["num_requests"] == 10
    assert len(results["individual_latencies_ms"]) == 10


def test_company_profile_load_under_3_seconds():
    """Verify company profile load times on 5 tickers are each under 3.0 seconds."""
    tickers = ["TCS", "INFY", "RELIANCE", "HDFCBANK", "TITAN"]
    results = run_dashboard_profile_benchmark(tickers=tickers)
    assert results["all_passed"] is True
    assert results["avg_load_time_s"] < 3.0
    for r in results["results"]:
        assert r["passed"] is True
        assert r["total_load_time_s"] < 3.0
        assert r["api_status"] == 200


def test_sqlite_performance_indexes_active():
    """Verify that user-defined performance indexes exist on key analytical tables."""
    indexes = verify_database_indexes()
    assert len(indexes) >= 10

    # Key indexed tables
    indexed_tables = set(indexes.values())
    for expected_table in ["ratios", "income_statement", "balance_sheet", "cash_flow", "companies"]:
        assert expected_table in indexed_tables
