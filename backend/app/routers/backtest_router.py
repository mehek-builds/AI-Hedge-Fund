from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db

router = APIRouter()


def _serialize_run(r) -> dict:
    return {
        "run_id": r.run_id,
        "created_at": r.created_at.isoformat() if r.created_at else None,
        "name": r.name,
        "status": r.status,
        "macro_gate_open": r.macro_gate_open,
        "sharpe_ratio": float(r.sharpe_ratio) if r.sharpe_ratio is not None else None,
        "total_return": float(r.total_return) if r.total_return is not None else None,
        "max_drawdown": float(r.max_drawdown) if r.max_drawdown is not None else None,
        "params": r.params,
        "results": r.results,
    }


@router.get("/backtest/runs")
async def list_backtest_runs(db: AsyncSession = Depends(get_db)):
    """Return all backtest runs ordered by most recent first."""
    result = await db.execute(
        text(
            """
            SELECT
                run_id, created_at, name, status, macro_gate_open,
                sharpe_ratio, total_return, max_drawdown, params, results
            FROM backtest_runs
            ORDER BY created_at DESC
            """
        )
    )
    rows = result.fetchall()
    return [_serialize_run(r) for r in rows]


@router.get("/backtest/runs/{run_id}")
async def get_backtest_run(run_id: str, db: AsyncSession = Depends(get_db)):
    """Return a single backtest run by ID."""
    result = await db.execute(
        text(
            """
            SELECT
                run_id, created_at, name, status, macro_gate_open,
                sharpe_ratio, total_return, max_drawdown, params, results
            FROM backtest_runs
            WHERE run_id = :run_id
            """
        ),
        {"run_id": run_id},
    )
    row = result.fetchone()
    if row is None:
        raise HTTPException(status_code=404, detail="Backtest run not found")
    return _serialize_run(row)
