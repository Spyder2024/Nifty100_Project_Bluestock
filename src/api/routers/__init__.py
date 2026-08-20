"""src/api/routers/__init__.py — API Routers Package.

Sprint 6, Day 40
"""

from src.api.routers.companies import router as companies_router
from src.api.routers.documents import router as documents_router
from src.api.routers.health import router as health_router
from src.api.routers.market_cap import router as market_cap_router
from src.api.routers.peers import router as peers_router
from src.api.routers.portfolio import router as portfolio_router
from src.api.routers.screener import router as screener_router
from src.api.routers.sectors import router as sectors_router
from src.api.routers.valuation import router as valuation_router

__all__ = [
    "health_router",
    "companies_router",
    "screener_router",
    "sectors_router",
    "peers_router",
    "valuation_router",
    "portfolio_router",
    "documents_router",
    "market_cap_router",
]
