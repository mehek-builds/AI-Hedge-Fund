"""Settings router — read/write system_settings table."""

from __future__ import annotations

from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from api.models.database import SystemSetting, get_db
from api.models.schemas import SettingOut, SettingsUpdate
from api.services.auth import get_current_user

router = APIRouter(prefix="/settings", tags=["settings"])


@router.get("", response_model=list[SettingOut])
async def get_settings(
    db: AsyncSession = Depends(get_db),
    _user: str = Depends(get_current_user),
) -> list[SettingOut]:
    """Return all system settings."""
    result = await db.execute(select(SystemSetting).order_by(SystemSetting.key))
    rows = result.scalars().all()
    return [SettingOut(key=r.key, value=r.value, updated_at=r.updated_at) for r in rows]


@router.post("", response_model=SettingOut)
async def update_setting(
    body: SettingsUpdate,
    db: AsyncSession = Depends(get_db),
    _user: str = Depends(get_current_user),
) -> SettingOut:
    """Create or update a system setting."""
    result = await db.execute(
        select(SystemSetting).where(SystemSetting.key == body.key)
    )
    row = result.scalar_one_or_none()

    now = datetime.now(timezone.utc)
    if row is None:
        row = SystemSetting(key=body.key, value=body.value, updated_at=now)
        db.add(row)
    else:
        row.value = body.value
        row.updated_at = now

    await db.flush()
    await db.refresh(row)
    return SettingOut(key=row.key, value=row.value, updated_at=row.updated_at)
