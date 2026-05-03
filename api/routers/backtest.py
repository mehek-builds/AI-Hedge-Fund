"""Backtest Explorer API endpoints."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy import text

from api.db.database import get_db

router = APIRouter(prefix="/backtest", tags=["backtest"])


# ── Request/response models ──────────────────────────────────────────────────

class BacktestConfigIn(BaseModel):
    start_date: str
    end_date: str
    initial_nav: float = 1_000_000.0
    min_signal_threshold: float = 1.0
    min_quality_score: float = 0.65
    slippage_bps: float = 12.5
    enable_shorts: bool = False
    enable_portfolio_arch: bool = True
    run_label: Optional[str] = None


class BacktestRunOut(BaseModel):
    id: str
    label: Optional[str]
    start_date: str
    end_date: str
    status: str
    created_at: datetime
    total_return: Optional[float] = None
    sharpe_ratio: Optional[float] = None
    max_drawdown: Optional[float] = None
    win_rate: Optional[float] = None
    ir_vs_naive: Optional[float] = None
    total_trades: Optional[int] = None
    config: Optional[dict] = None


class BacktestTradeOut(BaseModel):
    id: str
    run_id: str
    ticker: str
    direction: str
    entry_date: datetime
    exit_date: Optional[datetime]
    entry_price: float
    exit_price: Optional[float]
    position_size: float
    realized_pnl: Optional[float]
    ff5_alpha: Optional[float]
    hold_days: Optional[int]
    exit_reason: Optional[str]


# ── Endpoints ────────────────────────────────────────────────────────────────

@router.get("/runs", response_model=list[BacktestRunOut])
async def list_runs(
    limit: int = Query(20, le=100),
    db=Depends(get_db),
):
    rows = await db.fetch_all(
        """
        SELECT id, label, start_date, end_date, status, created_at,
               total_return, sharpe_ratio, max_drawdown, win_rate,
               ir_vs_naive, total_trades, config
        FROM backtest_runs
        ORDER BY created_at DESC
        LIMIT :limit
        """,
        {"limit": limit},
    )
    return [dict(r) for r in rows]


@router.get("/runs/{run_id}", response_model=BacktestRunOut)
async def get_run(run_id: str, db=Depends(get_db)):
    row = await db.fetch_one(
        "SELECT * FROM backtest_runs WHERE id = :id",
        {"id": run_id},
    )
    if row is None:
        raise HTTPException(status_code=404, detail="Run not found")
    return dict(row)


@router.get("/runs/{run_id}/trades", response_model=list[BacktestTradeOut])
async def get_run_trades(run_id: str, db=Depends(get_db)):
    rows = await db.fetch_all(
        "SELECT * FROM backtest_trades WHERE run_id = :run_id ORDER BY entry_date ASC",
        {"run_id": run_id},
    )
    return [dict(r) for r in rows]


@router.post("/runs", response_model=BacktestRunOut, status_code=202)
async def trigger_run(cfg: BacktestConfigIn, db=Depends(get_db)):
    run_id = str(uuid.uuid4())
    now = datetime.now(timezone.utc)
    label = cfg.run_label or f"run-{now.strftime('%Y%m%d-%H%M%S')}"

    await db.execute(
        """
        INSERT INTO backtest_runs (id, label, start_date, end_date, status, config, created_at)
        VALUES (:id, :label, :start_date, :end_date, 'queued', :config::jsonb, :created_at)
        """,
        {
            "id": run_id,
            "label": label,
            "start_date": cfg.start_date,
            "end_date": cfg.end_date,
            "config": cfg.model_dump_json(),
            "created_at": now,
        },
    )

    # Dispatch Celery task
    try:
        from worker.tasks.backtest import run_backtest
        run_backtest.delay(run_id, cfg.model_dump())
    except Exception:
        pass  # task dispatch is best-effort; status polling shows queued

    return BacktestRunOut(
        id=run_id,
        label=label,
        start_date=cfg.start_date,
        end_date=cfg.end_date,
        status="queued",
        created_at=now,
    )
