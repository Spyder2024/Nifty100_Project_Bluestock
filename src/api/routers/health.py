"""src/api/routers/health.py — Health Check Endpoint.

Sprint 6, Day 38

GET /api/v1/health:
- Returns server status
- Database row counts for all database tables
- Uptime in seconds
- API version string
- ISO timestamp
"""

from __future__ import annotations

import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict

from fastapi import APIRouter

router = APIRouter(prefix="/health", tags=["Health"])

# Module-level start time will be injected from main.py or default to current time
_START_TIME = datetime.now(timezone.utc)


def set_start_time(start_time: datetime) -> None:
    """Set server start time for accurate uptime calculation."""
    global _START_TIME
    _START_TIME = start_time


def get_start_time() -> datetime:
    """Return the server start time."""
    return _START_TIME


def get_db_path() -> Path:
    """Resolve active database path."""
    project_root = Path(__file__).resolve().parents[3]
    output_db = project_root / "output" / "nifty100.db"
    if output_db.exists():
        return output_db
    fallback_db = project_root / "db" / "nifty100.db"
    if fallback_db.exists():
        return fallback_db
    return output_db


def query_db_table_counts(db_path: Path) -> Dict[str, int]:
    """Query row counts for all user tables in SQLite database."""
    if not db_path.exists():
        return {}

    counts: Dict[str, int] = {}
    conn = sqlite3.connect(str(db_path))
    try:
        tables = [
            r[0]
            for r in conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'"
            ).fetchall()
        ]
        for tbl in tables:
            try:
                cnt = conn.execute(f"SELECT COUNT(*) FROM {tbl}").fetchone()[0]
                counts[tbl] = int(cnt)
            except Exception:
                counts[tbl] = 0
    finally:
        conn.close()

    return counts


@router.get("", summary="System Health & Database Status")
async def health_check() -> Dict[str, Any]:
    """Return health status, database row counts, uptime, and version."""
    db_path = get_db_path()
    db_counts = query_db_table_counts(db_path)

    now = datetime.now(timezone.utc)
    uptime = round((now - _START_TIME).total_seconds(), 2)

    return {
        "status": "ok",
        "version": "1.0.0",
        "uptime_seconds": uptime,
        "database_connected": bool(db_path.exists() and db_counts),
        "db_path": str(db_path.name),
        "db_row_counts": db_counts,
        "timestamp": now.isoformat(),
    }
