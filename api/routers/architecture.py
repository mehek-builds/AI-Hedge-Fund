"""Portfolio architecture API endpoints — ERP, GV, Mag7, completion portfolio."""

from __future__ import annotations

from typing import Any, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from api.db.database import get_db

router = APIRouter(prefix="/architecture", tags=["architecture"])


# ── Response models ──────────────────────────────────────────────────────────

class ERPOut(BaseModel):
    earnings_yield: Optional[float]
    real_10y_yield: Optional[float]
    erp_spread: Optional[float]
    erp_compressed: bool
    global_size_cap: float
    as_of: Optional[str]


class GrowthValueOut(BaseModel):
    vug_pe: Optional[float]
    vtv_pe: Optional[float]
    ratio: Optional[float]
    stretched: bool
    as_of: Optional[str]


class CompletionOut(BaseModel):
    active_betas: dict[str, float]
    target_betas: dict[str, float]
    deviations: dict[str, float]
    recommended_etf: str
    sleeve_pct_nav: float
    max_deviation: float


class PortfolioArchOut(BaseModel):
    erp: ERPOut
    growth_value: GrowthValueOut
    completion: Optional[CompletionOut]
    mag7_aggregate_pct: Optional[float]
    mag7_cap: float
    sector_caps: dict[str, float]


# ── Endpoints ────────────────────────────────────────────────────────────────

@router.get("/", response_model=PortfolioArchOut)
async def get_architecture(db=Depends(get_db)):
    """Return current portfolio architecture state."""
    row = await db.fetch_one(
        """
        SELECT erp_spread, erp_compressed, gv_ratio, gv_stretched,
               earnings_yield, real_10y_yield, vug_pe, vtv_pe, time
        FROM macro_state
        ORDER BY time DESC LIMIT 1
        """
    )

    if row is None:
        raise HTTPException(status_code=503, detail="No macro state available")

    r = dict(row)
    erp_spread = float(r.get("erp_spread") or 0.0)
    erp_compressed = bool(r.get("erp_compressed", False))

    erp = ERPOut(
        earnings_yield=r.get("earnings_yield"),
        real_10y_yield=r.get("real_10y_yield"),
        erp_spread=erp_spread,
        erp_compressed=erp_compressed,
        global_size_cap=0.8 if erp_compressed else 1.0,
        as_of=r["time"].isoformat() if r.get("time") else None,
    )

    gv_ratio = float(r.get("gv_ratio") or 1.0)
    gv_stretched = bool(r.get("gv_stretched", False))

    gv = GrowthValueOut(
        vug_pe=r.get("vug_pe"),
        vtv_pe=r.get("vtv_pe"),
        ratio=gv_ratio,
        stretched=gv_stretched,
        as_of=r["time"].isoformat() if r.get("time") else None,
    )

    # Mag7 aggregate
    mag7_row = await db.fetch_one(
        """
        SELECT SUM(ABS(shares * current_price)) / NULLIF(nav.nav, 0) AS mag7_pct
        FROM positions p
        CROSS JOIN (SELECT SUM(ABS(shares * entry_price)) AS nav FROM positions WHERE status = 'open') nav
        WHERE p.status = 'open'
          AND p.ticker IN ('AAPL','MSFT','NVDA','AMZN','META','GOOGL','GOOG','TSLA')
        """
    )
    mag7_pct = float((mag7_row or {}).get("mag7_pct") or 0.0)

    # Completion portfolio (latest from DB if stored)
    completion_row = await db.fetch_one(
        "SELECT * FROM completion_portfolio ORDER BY computed_at DESC LIMIT 1"
    )
    completion = None
    if completion_row:
        cr = dict(completion_row)
        completion = CompletionOut(
            active_betas=cr.get("active_betas") or {},
            target_betas={"mkt_rf": 1.0, "smb": 0.0, "hml": 0.0, "rmw": 0.0, "cma": 0.0},
            deviations=cr.get("deviations") or {},
            recommended_etf=cr.get("recommended_etf") or "SPY",
            sleeve_pct_nav=float(cr.get("sleeve_pct_nav") or 0.0),
            max_deviation=float(cr.get("max_deviation") or 0.0),
        )

    return PortfolioArchOut(
        erp=erp,
        growth_value=gv,
        completion=completion,
        mag7_aggregate_pct=mag7_pct,
        mag7_cap=0.12,
        sector_caps={"default": 0.30},
    )
