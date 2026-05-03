"""Alert dispatcher — SendGrid email + Slack webhook with rate limiting."""

from __future__ import annotations

import json
import os
import time
import uuid
from datetime import datetime, timezone
from typing import Optional

import httpx
from loguru import logger
from sqlalchemy import create_engine, text

from worker.celery_app import celery_app

DATABASE_URL_SYNC = os.environ.get(
    "DATABASE_URL_SYNC",
    "postgresql+psycopg2://postgres:postgres@db:5432/pead",
)
SENDGRID_API_KEY = os.environ.get("SENDGRID_API_KEY", "")
SLACK_WEBHOOK_URL = os.environ.get("SLACK_WEBHOOK_URL", "")
ALERT_FROM_EMAIL = os.environ.get("ALERT_FROM_EMAIL", "alerts@pead.local")
ALERT_TO_EMAIL = os.environ.get("ALERT_TO_EMAIL", "")

# Rate limit: one alert per (event_type, ticker) per N seconds
COOLDOWN_SECONDS = int(os.environ.get("ALERT_COOLDOWN_SECONDS", "300"))

_engine = None
_rate_cache: dict[str, float] = {}   # key → last_sent_ts


def _get_engine():
    global _engine
    if _engine is None:
        _engine = create_engine(DATABASE_URL_SYNC, pool_pre_ping=True)
    return _engine


def _rate_limited(event_type: str, ticker: Optional[str]) -> bool:
    key = f"{event_type}:{ticker or '_'}"
    last = _rate_cache.get(key, 0.0)
    if time.time() - last < COOLDOWN_SECONDS:
        return True
    _rate_cache[key] = time.time()
    return False


def _get_rule(event_type: str) -> tuple[bool, list[str]]:
    """Return (enabled, channels) from alert_rules table."""
    try:
        engine = _get_engine()
        with engine.connect() as conn:
            row = conn.execute(
                text("SELECT enabled, channels FROM alert_rules WHERE event_type = :et"),
                {"et": event_type},
            ).fetchone()
        if row is None:
            return True, ["slack"]
        channels = row[1] if isinstance(row[1], list) else json.loads(row[1])
        return bool(row[0]), channels
    except Exception:
        return True, ["slack"]


def _send_slack(title: str, message: str, priority: str, ticker: Optional[str]) -> bool:
    if not SLACK_WEBHOOK_URL:
        logger.warning("SLACK_WEBHOOK_URL not set — skipping Slack alert")
        return False
    emoji = {"high": ":red_circle:", "medium": ":large_yellow_circle:", "low": ":large_green_circle:"}.get(priority, ":white_circle:")
    ticker_line = f"*Ticker:* `{ticker}`\n" if ticker else ""
    payload = {
        "text": f"{emoji} *{title}*\n{ticker_line}{message}",
    }
    try:
        resp = httpx.post(SLACK_WEBHOOK_URL, json=payload, timeout=10)
        return resp.status_code == 200
    except Exception as exc:
        logger.error(f"Slack delivery failed: {exc}")
        return False


def _send_email(title: str, message: str, ticker: Optional[str]) -> bool:
    if not SENDGRID_API_KEY or not ALERT_TO_EMAIL:
        logger.warning("SendGrid not configured — skipping email alert")
        return False
    subject = f"[PEAD] {title}" + (f" — {ticker}" if ticker else "")
    payload = {
        "personalizations": [{"to": [{"email": ALERT_TO_EMAIL}]}],
        "from": {"email": ALERT_FROM_EMAIL},
        "subject": subject,
        "content": [{"type": "text/plain", "value": message}],
    }
    try:
        resp = httpx.post(
            "https://api.sendgrid.com/v3/mail/send",
            headers={"Authorization": f"Bearer {SENDGRID_API_KEY}", "Content-Type": "application/json"},
            json=payload,
            timeout=15,
        )
        return resp.status_code in (200, 202)
    except Exception as exc:
        logger.error(f"SendGrid delivery failed: {exc}")
        return False


@celery_app.task(name="worker.tasks.alerts.dispatch_alert", bind=True, max_retries=3)
def dispatch_alert(
    self,
    event_type: str,
    title: str,
    message: str,
    ticker: Optional[str] = None,
    priority: str = "medium",
    channels: Optional[list[str]] = None,
) -> dict:
    """
    Dispatch an alert via configured channels with rate limiting.

    event_type: one of the 9 registered alert types
    channels:   override rule channels if provided
    """
    # Check rule config
    enabled, rule_channels = _get_rule(event_type)
    if not enabled:
        return {"status": "disabled", "event_type": event_type}

    # Rate limit check
    if _rate_limited(event_type, ticker):
        logger.debug(f"Alert rate-limited: {event_type}/{ticker}")
        return {"status": "rate_limited"}

    active_channels = channels or rule_channels
    if "both" in active_channels:
        active_channels = ["slack", "email"]

    delivered = False
    error: Optional[str] = None

    for ch in active_channels:
        try:
            if ch == "slack":
                ok = _send_slack(title, message, priority, ticker)
                delivered = delivered or ok
            elif ch == "email":
                ok = _send_email(title, message, ticker)
                delivered = delivered or ok
        except Exception as exc:
            error = str(exc)
            logger.error(f"Alert channel {ch} failed: {exc}")

    # Log to DB
    alert_id = str(uuid.uuid4())
    now = datetime.now(timezone.utc)
    try:
        engine = _get_engine()
        with engine.begin() as conn:
            conn.execute(
                text(
                    """
                    INSERT INTO alert_log
                        (id, event_type, ticker, title, body, priority, channels, delivered, error, created_at)
                    VALUES
                        (:id, :event_type, :ticker, :title, :body, :priority, :channels::jsonb, :delivered, :error, :created_at)
                    """
                ),
                {
                    "id": alert_id,
                    "event_type": event_type,
                    "ticker": ticker,
                    "title": title,
                    "body": message,
                    "priority": priority,
                    "channels": json.dumps(active_channels),
                    "delivered": delivered,
                    "error": error,
                    "created_at": now,
                },
            )
    except Exception as exc:
        logger.error(f"Failed to log alert to DB: {exc}")

    if not delivered and error:
        raise self.retry(exc=Exception(error), countdown=30)

    return {"status": "ok" if delivered else "failed", "alert_id": alert_id, "channels": active_channels}
