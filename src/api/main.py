"""src/api/main.py — FastAPI Application Entrypoint (Day 38).

Sprint 6, Day 38

Implements:
1. FastAPI application instance with OpenAPI metadata and documentation.
2. SQLite connection management and dependency injection.
3. CORS middleware allowing all origins (internal usage).
4. Request logging middleware logging method, path, status, and response time.
5. All 8 modular routers mounted under prefix /api/v1:
   - /api/v1/health
   - /api/v1/companies
   - /api/v1/screener
   - /api/v1/sectors
   - /api/v1/peers
   - /api/v1/valuation
   - /api/v1/portfolio
   - /api/v1/documents

Usage:
    uvicorn src.api.main:app --reload --port 8000
"""

from __future__ import annotations

import logging
import sqlite3
import time
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import AsyncGenerator, Generator

from fastapi import APIRouter, FastAPI, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from src.api.routers.companies import router as companies_router
from src.api.routers.documents import router as documents_router
from src.api.routers.health import get_db_path, router as health_router, set_start_time
from src.api.routers.peers import router as peers_router
from src.api.routers.portfolio import router as portfolio_router
from src.api.routers.screener import router as screener_router
from src.api.routers.sectors import router as sectors_router
from src.api.routers.valuation import router as valuation_router

# ── Logging Configuration ──────────────────────────────────────────
logger = logging.getLogger("src.api")
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] [%(name)s] %(message)s",
)

# ── Project Paths & Constants ──────────────────────────────────────
PROJECT_ROOT = Path(__file__).resolve().parents[2]
API_VERSION = "1.0.0"
API_PREFIX = "/api/v1"


# ── SQLite Database Dependency ─────────────────────────────────────
def get_db() -> Generator[sqlite3.Connection, None, None]:
    """Provide a SQLite connection with row factory enabled."""
    db_path = get_db_path()
    conn = sqlite3.connect(str(db_path), check_same_thread=False)
    conn.row_factory = sqlite3.Row
    try:
        yield conn
    finally:
        conn.close()


# ── Lifespan Context Manager ───────────────────────────────────────
@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Application startup and shutdown lifespan management."""
    start_time = datetime.now(timezone.utc)
    set_start_time(start_time)
    logger.info("Starting Nifty 100 Financial Intelligence API v%s...", API_VERSION)
    db_path = get_db_path()
    logger.info("Active SQLite database: %s (exists=%s)", db_path, db_path.exists())
    yield
    logger.info("Shutting down Nifty 100 Financial Intelligence API...")


# ── FastAPI App Creation ───────────────────────────────────────────
app = FastAPI(
    title="Nifty 100 Financial Intelligence API",
    description=(
        "Production-ready REST API providing fundamental analysis, screener queries, "
        "intrinsic valuations, peer comparisons, KMeans financial clusters, and PDF reporting "
        "for the Nifty 100 index constituents."
    ),
    version=API_VERSION,
    docs_url="/docs",
    redoc_url="/redoc",
    openapi_url="/openapi.json",
    lifespan=lifespan,
)


# ── 1. CORS Middleware (Allow All Origins) ─────────────────────────
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ── 2. Request Logging Middleware ──────────────────────────────────
@app.middleware("http")
async def log_requests(request: Request, call_next) -> Response:
    """Log HTTP method, path, status code, and execution time for every incoming request."""
    start_time = time.perf_counter()
    response: Response = await call_next(request)
    duration_ms = (time.perf_counter() - start_time) * 1000.0

    # Add execution time header
    response.headers["X-Process-Time"] = f"{duration_ms:.2f}ms"

    logger.info(
        "%s %s - %d (%.2fms)",
        request.method,
        request.url.path,
        response.status_code,
        duration_ms,
    )
    return response


# ── 3. Router Registration under /api/v1 ───────────────────────────
v1_router = APIRouter(prefix=API_PREFIX)

v1_router.include_router(health_router)
v1_router.include_router(companies_router)
v1_router.include_router(screener_router)
v1_router.include_router(sectors_router)
v1_router.include_router(peers_router)
v1_router.include_router(valuation_router)
v1_router.include_router(portfolio_router)
v1_router.include_router(documents_router)

app.include_router(v1_router)


# ── Root Welcome Endpoint ──────────────────────────────────────────
@app.get("/", summary="API Root & Index", tags=["General"])
async def root() -> dict[str, str]:
    """Root endpoint with service info and links to documentation and health check."""
    return {
        "service": "Nifty 100 Financial Intelligence API",
        "version": API_VERSION,
        "docs_url": "/docs",
        "health_check": f"{API_PREFIX}/health",
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("src.api.main:app", host="0.0.0.0", port=8000, reload=True)
