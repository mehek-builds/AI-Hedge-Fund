"""Alerting API endpoints."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel

from api.db.database import get_db

router = APIRouter(prefix="/alerts", tags=["alerts"])


# ── Request/response models ──────────────────────────────────────────────────

class AlertOut(BaseModel):
    id: str
    event_type: str
    ticker: Optional[str]
    title: str
    body: str
    priority: str   # high | medium | low
    channels: list[str]
    delivered: bool
    created_at: datetime


class AlertRuleIn(BaseModel):
    event_type: str
    enabled: bool
    channels: list[str]   # ["slack", "email", "both"]


class AlertRulesOut(BaseModel):
    rules: list[dict]


class TestAlertIn(BaseModel):
    event_type: str
    channel: str = "slack"


# ── Endpoints ────────────────────────────────────────────────────────────────

@router.get("/", response_model=list[AlertOut])
async def list_alerts(
    limit: int = Query(50, le=200),
    event_type: Optional[str] = None,
    db=Depends(get_db),
):
    query = "SELECT * FROM alert_log"
    params: dict = {"limit": limit}
    if event_type:
        query += " WHERE event_type = :event_type"
        params["event_type"] = event_type
    query += " ORDER BY created_at DESC LIMIT :limit"
    rows = await db.fetch_all(query, params)
    return [dict(r) for r in rows]


@router.get("/rules", response_model=AlertRulesOut)
async def get_alert_rules(db=Depends(get_db)):
    rows = await db.fetch_all("SELECT * FROM alert_rules ORDER BY event_type")
    return AlertRulesOut(rules=[dict(r) for r in rows])


@router.put("/rules")
async def update_alert_rules(rules: list[AlertRuleIn], db=Depends(get_db)):
    for rule in rules:
        await db.execute(
            """
            INSERT INTO alert_rules (event_type, enabled, channels, updated_at)
            VALUES (:event_type, :enabled, :channels::jsonb, NOW())
            ON CONFLICT (event_type) DO UPDATE
              SET enabled = EXCLUDED.enabled,
                  channels = EXCLUDED.channels,
                  updated_at = NOW()
            """,
            {
                "event_type": rule.event_type,
                "enabled": rule.enabled,
                "channels": f'["{rule.channels[0]}"]' if len(rule.channels) == 1 else str(rule.channels).replace("'", '"'),
            },
        )
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
