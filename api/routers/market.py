"""Market data router — yield curve and inflation via FRED."""

from __future__ import annotations

import os
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, status
from loguru import logger

from api.models.schemas import InflationData, YieldCurvePoint
from api.services.auth import get_current_user

router = APIRouter(prefix="/market", tags=["market"])

# FRED series IDs for the yield curve
YIELD_CURVE_SERIES: list[tuple[str, str, bool]] = [
    ("1M",  "DGS1MO",  False),
    ("3M",  "DGS3MO",  False),
    ("6M",  "DGS6MO",  False),
    ("1Y",  "DGS1",    False),
    ("2Y",  "DGS2",    False),
    ("5Y",  "DGS5",    False),
    ("10Y", "DGS10",   False),
    ("20Y", "DGS20",   False),
    ("30Y", "DGS30",   False),
    # Real / TIPS
    ("5Y Real",  "DFII5",  True),
    ("10Y Real", "DFII10", True),
    ("20Y Real", "DFII20", True),
    ("30Y Real", "DFII30", True),
]

FRED_API_KEY = os.environ.get("FRED_API_KEY", "")


def _get_fred():
    if not FRED_API_KEY:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="FRED_API_KEY not configured",
        )
    from fredapi import Fred
    return Fred(api_key=FRED_API_KEY)


@router.get("/yield-curve", response_model=list[YieldCurvePoint])
async def get_yield_curve(
    _user: str = Depends(get_current_user),
) -> list[YieldCurvePoint]:
    """Fetch the latest yield curve and real rate data from FRED."""
    fred = _get_fred()
    points: list[YieldCurvePoint] = []

    for label, series_id, is_real in YIELD_CURVE_SERIES:
        try:
            series = fred.get_series(series_id)
            rate: Optional[float] = None
            if not series.empty:
                last = series.dropna()
                if not last.empty:
                    rate = float(last.iloc[-1])
            points.append(YieldCurvePoint(label=label, series_id=series_id, rate=rate, real=is_real))
        except Exception as exc:
            logger.warning(f"FRED fetch failed for {series_id}: {exc}")
            points.append(YieldCurvePoint(label=label, series_id=series_id, rate=None, real=is_real))

    return points


@router.get("/inflation", response_model=InflationData)
async def get_inflation(
    _user: str = Depends(get_current_user),
) -> InflationData:
    """Return Core PCE and CPI YoY from FRED."""
    fred = _get_fred()

    def _yoy(series_id: str) -> Optional[float]:
        try:
            s = fred.get_series(series_id)
            s = s.dropna()
            if len(s) < 13:
                return None
            latest = float(s.iloc[-1])
            year_ago = float(s.iloc[-13])
            if year_ago == 0:
                return None
            return round((latest / year_ago - 1) * 100, 2)
        except Exception as exc:
            logger.warning(f"FRED YoY failed for {series_id}: {exc}")
            return None

    core_pce = _yoy("PCEPILFE")
    cpi = _yoy("CPIAUCSL")

    import datetime

    return InflationData(
        core_pce_yoy=core_pce,
        cpi_yoy=cpi,
        as_of=datetime.date.today().isoformat(),
    )
