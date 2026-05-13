from typing import Optional

from fastapi import APIRouter
from pydantic import BaseModel, field_validator

from app.config import settings

router = APIRouter()

_DEFAULT_SETTINGS = {
    "ENABLE_SHORT_SIDE": False,
    "STOP_LOSS_PCT": 0.02,
    "TAKE_PROFIT_PCT": 0.04,
    "max_alerts_per_hour": 10,
}


def _current_settings_dict() -> dict:
    return {
        "ENABLE_SHORT_SIDE": settings.ENABLE_SHORT_SIDE,
        "STOP_LOSS_PCT": settings.STOP_LOSS_PCT,
        "TAKE_PROFIT_PCT": settings.TAKE_PROFIT_PCT,
        "max_alerts_per_hour": settings.MAX_ALERTS_PER_HOUR,
    }


class SettingsPatch(BaseModel):
    ENABLE_SHORT_SIDE: Optional[bool] = None
    STOP_LOSS_PCT: Optional[float] = None
    TAKE_PROFIT_PCT: Optional[float] = None
    max_alerts_per_hour: Optional[int] = None

    @field_validator("STOP_LOSS_PCT")
    @classmethod
    def validate_stop_loss(cls, v: Optional[float]) -> Optional[float]:
        if v is not None and not (0.001 <= v <= 0.50):
            raise ValueError("STOP_LOSS_PCT must be between 0.001 and 0.50")
        return v

    @field_validator("TAKE_PROFIT_PCT")
    @classmethod
    def validate_take_profit(cls, v: Optional[float]) -> Optional[float]:
        if v is not None and not (0.001 <= v <= 1.00):
            raise ValueError("TAKE_PROFIT_PCT must be between 0.001 and 1.00")
        return v

    @field_validator("max_alerts_per_hour")
    @classmethod
    def validate_max_alerts(cls, v: Optional[int]) -> Optional[int]:
        if v is not None and not (1 <= v <= 100):
            raise ValueError("max_alerts_per_hour must be between 1 and 100")
        return v


@router.get("/settings")
async def get_settings():
    """Return current runtime trading settings."""
    return _current_settings_dict()


@router.patch("/settings")
async def patch_settings(patch: SettingsPatch):
    """Update trading settings in-memory (no restart required)."""
    if patch.ENABLE_SHORT_SIDE is not None:
        settings.ENABLE_SHORT_SIDE = patch.ENABLE_SHORT_SIDE
    if patch.STOP_LOSS_PCT is not None:
        settings.STOP_LOSS_PCT = patch.STOP_LOSS_PCT
    if patch.TAKE_PROFIT_PCT is not None:
        settings.TAKE_PROFIT_PCT = patch.TAKE_PROFIT_PCT
    if patch.max_alerts_per_hour is not None:
        settings.MAX_ALERTS_PER_HOUR = patch.max_alerts_per_hour
    return _current_settings_dict()


@router.post("/settings/reset")
async def reset_settings():
    """Reset all trading settings to hardcoded safe defaults."""
    settings.ENABLE_SHORT_SIDE = _DEFAULT_SETTINGS["ENABLE_SHORT_SIDE"]
    settings.STOP_LOSS_PCT = _DEFAULT_SETTINGS["STOP_LOSS_PCT"]
    settings.TAKE_PROFIT_PCT = _DEFAULT_SETTINGS["TAKE_PROFIT_PCT"]
    settings.MAX_ALERTS_PER_HOUR = _DEFAULT_SETTINGS["max_alerts_per_hour"]
    return _current_settings_dict()
