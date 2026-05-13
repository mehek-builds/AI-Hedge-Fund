from typing import Optional

from fastapi import APIRouter
from pydantic import BaseModel

from app.config import settings

router = APIRouter()


class SettingsPatch(BaseModel):
    ENABLE_SHORT_SIDE: Optional[bool] = None
    STOP_LOSS_PCT: Optional[float] = None
    TAKE_PROFIT_PCT: Optional[float] = None


@router.get("/settings")
async def get_settings():
    """Return current runtime trading settings."""
    return {
        "ENABLE_SHORT_SIDE": settings.ENABLE_SHORT_SIDE,
        "STOP_LOSS_PCT": settings.STOP_LOSS_PCT,
        "TAKE_PROFIT_PCT": settings.TAKE_PROFIT_PCT,
    }


@router.patch("/settings")
async def patch_settings(patch: SettingsPatch):
    """Update trading settings in-memory (no restart required)."""
    if patch.ENABLE_SHORT_SIDE is not None:
        settings.ENABLE_SHORT_SIDE = patch.ENABLE_SHORT_SIDE
    if patch.STOP_LOSS_PCT is not None:
        settings.STOP_LOSS_PCT = patch.STOP_LOSS_PCT
    if patch.TAKE_PROFIT_PCT is not None:
        settings.TAKE_PROFIT_PCT = patch.TAKE_PROFIT_PCT
    return {
        "ENABLE_SHORT_SIDE": settings.ENABLE_SHORT_SIDE,
        "STOP_LOSS_PCT": settings.STOP_LOSS_PCT,
        "TAKE_PROFIT_PCT": settings.TAKE_PROFIT_PCT,
    }
