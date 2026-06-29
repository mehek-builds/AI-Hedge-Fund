"""Alerting API endpoints."""

from __future__ import annotations

import json
from datetime import datetime
from typing import Any, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from api.models.database import get_db

router = APIRouter(prefix="/alerts", tags=["alerts"])


class AlertOut(BaseModel):
    id: str
    event_type: str
    ticker: Optional[str] = None
    title: str
    body: str
    priority: str
    channels: list[str]
    delivered: bool
    created_at: datetime


class AlertRuleIn(BaseModel):
    event_type: str
    enabled: bool
    channels: list[str]


class AlertRulesOut(BaseModel):
    rules: list[dict]


class TestAlertIn(BaseModel):
    event_type: str
    channel: str = "slack"


@router.get("/", response_model=list[AlertOut])
async def list_alerts(
    limit: int = Query(50, le=200),
    event_type: Optional[str] = None,
    db: AsyncSession = Depends(get_db),
):
    if event_type:
        q = text("SELECT * FROM alert_log WHERE event_type = :event_type ORDER BY created_at DESC LIMIT :limit")
        result = await db.execute(q, {"event_type": event_type, "limit": limit})
    else:
        q = text("SELECT * FROM alert_log ORDER BY created_at DESC LIMIT :limit")
        result = await db.execute(q, {"limit": limit})
    rows = result.mappings().all()
    return [
        AlertOut(
            id=str(r["id"]),
            event_type=r["event_type"],
            ticker=r.get("ticker"),
            title=r["title"],
            body=r["body"],
            priority=r["priority"],
            channels=r.get("channels") or [],
            delivered=bool(r.get("delivered", False)),
            created_at=r["created_at"],
        )
        for r in rows
    ]


@router.get("/rules", response_model=AlertRulesOut)
async def get_alert_rules(db: AsyncSession = Depends(get_db)):
    result = await db.execute(text("SELECT * FROM alert_rules ORDER BY event_type"))
    rows = result.mappings().all()
    return AlertRulesOut(rules=[dict(r) for r in rows])


@router.put("/rules")
async def update_alert_rules(rules: list[AlertRuleIn], db: AsyncSession = Depends(get_db)):
    for rule in rules:
        await db.execute(
            text("""
            INSERT INTO alert_rules (event_type, enabled, channels, updated_at)
            VALUES (:event_type, :enabled, :channels::jsonb, NOW())
            ON CONFLICT (event_type) DO UPDATE
              SET enabled = EXCLUDED.enabled,
                  channels = EXCLUDED.channels,
                  updated_at = NOW()
            """),
            {
                "event_type": rule.event_type,
                "enabled": rule.enabled,
                "channels": json.dumps(rule.channels),
            },
        )
    await db.commit()
    return {"status": "ok", "updated": len(rules)}


@router.post("/test")
async def send_test_alert(body: TestAlertIn):
    try:
        from worker.tasks.alerts import dispatch_alert
        dispatch_alert.delay(
            event_type=body.event_type,
            title=f"Test alert: {body.event_type}",
            message="This is a test alert from the PEAD system.",
            ticker=None,
            priority="low",
            channels=[body.channel],
        )
        return {"status": "dispatched"}
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))
