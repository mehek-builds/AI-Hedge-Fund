import logging
import os
from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.database import engine
from app.flows._db import SyncSessionLocal
from app.routers import health, stream
from app.routers import orders

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Gate check: hard block if no backtest_gate_pass row exists.
    # Called AFTER engine is initialized (inside async with) to ensure DB pool ready.
    # Skip in test mode via SKIP_GATE_CHECK=1 env var.
    if not os.environ.get("SKIP_GATE_CHECK"):
        from app.backtest.alerts import check_phase7_gate

        with SyncSessionLocal() as session:
            gate_ok = check_phase7_gate(session)

        if not gate_ok:
            raise RuntimeError(
                "Phase 7 startup BLOCKED: no backtest_gate_pass found in backtest_runs. "
                "Run Phase 6 backtest and achieve Sharpe > 1.0 before starting Phase 7."
            )

        logger.info("Phase 7 gate check passed. Service starting.")

    yield
    await engine.dispose()


app = FastAPI(title="PEAD Trading System", lifespan=lifespan)

app.include_router(health.router)
app.include_router(stream.router, prefix="/stream")
app.include_router(orders.router, prefix="/api/v1")
