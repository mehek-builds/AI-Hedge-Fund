from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.database import engine
from app.routers import health, stream
from app.routers import (
    dashboard,
    positions_router,
    signals_router,
    alerts_router,
    backtest_router,
    settings_router,
    macro_router,
    rl_router,
)


@asynccontextmanager
async def lifespan(app: FastAPI):
    yield
    await engine.dispose()


app = FastAPI(title="PEAD Trading System", lifespan=lifespan)

app.include_router(health.router)
app.include_router(stream.router, prefix="/api/v1")

# Dashboard & core data endpoints
app.include_router(dashboard.router, prefix="/api/v1")
app.include_router(positions_router.router, prefix="/api/v1")
app.include_router(signals_router.router, prefix="/api/v1")
app.include_router(alerts_router.router, prefix="/api/v1")
app.include_router(backtest_router.router, prefix="/api/v1")
app.include_router(settings_router.router, prefix="/api/v1")
app.include_router(macro_router.router, prefix="/api/v1")
app.include_router(rl_router.router, prefix="/api/v1")
