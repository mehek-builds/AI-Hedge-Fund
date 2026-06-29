"""FastAPI application entry point."""

from __future__ import annotations

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from loguru import logger

from api.routers import auth, macro, market, orders, portfolio, positions, rl, settings, signals
from api.routers import backtest, alerts, architecture, sse, dashboard

app = FastAPI(
    title="PEAD Trading System API",
    version="1.0.0",
    description="REST API for the Post-Earnings-Announcement-Drift trading system.",
)

# ---------------------------------------------------------------------------
# CORS
# ---------------------------------------------------------------------------

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://localhost:3001"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ---------------------------------------------------------------------------
# Routers
# ---------------------------------------------------------------------------

API_PREFIX = "/api/v1"

app.include_router(auth.router, prefix=API_PREFIX)
app.include_router(portfolio.router, prefix=API_PREFIX)
app.include_router(positions.router, prefix=API_PREFIX)
app.include_router(signals.router, prefix=API_PREFIX)
app.include_router(macro.router, prefix=API_PREFIX)
app.include_router(rl.router, prefix=API_PREFIX)
app.include_router(market.router, prefix=API_PREFIX)
app.include_router(orders.router, prefix=API_PREFIX)
app.include_router(settings.router, prefix=API_PREFIX)
app.include_router(backtest.router, prefix=API_PREFIX)
app.include_router(alerts.router, prefix=API_PREFIX)
app.include_router(architecture.router, prefix=API_PREFIX)
app.include_router(sse.router, prefix=API_PREFIX)
app.include_router(dashboard.router, prefix=API_PREFIX)

# ---------------------------------------------------------------------------
# Health check
# ---------------------------------------------------------------------------


@app.get("/health", tags=["health"])
async def health_check() -> dict:
    """Liveness probe."""
    return {"status": "ok"}


# ---------------------------------------------------------------------------
# Startup / shutdown
# ---------------------------------------------------------------------------


@app.on_event("startup")
async def on_startup() -> None:
    logger.info("PEAD API starting up")


@app.on_event("shutdown")
async def on_shutdown() -> None:
    logger.info("PEAD API shutting down")
