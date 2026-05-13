"""Alert dispatcher: persists Alert row, rate-checks, delivers via SendGrid + Slack,
publishes to Redis pub/sub channel 'alerts'.

Delivery is fire-and-forget: SendGrid and Slack failures are logged but never
raised to the caller (locked decision - must not block trade execution).

Redis channel 'alerts' is already subscribed by backend/app/routers/stream.py
for SSE delivery to the Phase 8 dashboard.
"""
import json
import logging
from typing import Any

import redis
from sendgrid import SendGridAPIClient
from sendgrid.helpers.mail import Mail
from sqlalchemy.ext.asyncio import AsyncSession

from app.alerting.rate_limiter import is_rate_limited
from app.alerting.templates import render_email_html, render_slack_text
from app.config import settings
from app.models.alerts import Alert, VALID_EVENT_TYPES

logger = logging.getLogger(__name__)

# Redis pub/sub channel - matches stream.py subscription
ALERTS_CHANNEL = "alerts"


async def dispatch_alert(
    event_type: str,
    payload: dict[str, Any] | None,
    db: AsyncSession,
    redis_client: redis.Redis,
) -> Alert:
    """Persist, rate-check, and deliver an alert.

    Steps:
    1. Validate event_type is one of the 9 known types
    2. Check rate limit (Redis INCR/EXPIRE fixed window)
    3. Persist Alert row to DB (always - even if rate limited)
    4. If not rate limited: deliver via SendGrid + Slack (fire-and-forget)
    5. Publish to Redis 'alerts' pub/sub channel (always, for SSE dashboard)
    6. Update Alert row delivery status; commit

    Args:
        event_type: One of VALID_EVENT_TYPES
        payload: Event-specific data (symbol, order_id, etc.) - stored as JSONB
        db: Async SQLAlchemy session (caller is responsible for lifecycle)
        redis_client: Sync redis.Redis client for rate limiting and pub/sub

    Returns:
        The persisted Alert ORM object
    """
    if event_type not in VALID_EVENT_TYPES:
        raise ValueError(
            f"Unknown event_type '{event_type}'. "
            f"Must be one of: {VALID_EVENT_TYPES}"
        )

    # Rate limit check (fixed window, max 3/hr per event_type)
    limited = is_rate_limited(redis_client, event_type)

    # Always persist the alert (SC6: all alerts persisted, including suppressed ones)
    alert = Alert(
        event_type=event_type,
        payload=payload,
        rate_limited=limited,
        delivered_sendgrid=False,
        delivered_slack=False,
    )
    db.add(alert)
    await db.flush()  # get the UUID without full commit

    if limited:
        logger.info(
            "Alert rate-limited (persisted, not delivered): event_type=%s", event_type
        )
    else:
        # Fire-and-forget delivery: log failures, never raise
        sendgrid_ok = await _send_sendgrid(event_type, payload)
        slack_ok = await _send_slack(event_type, payload)

        alert.delivered_sendgrid = sendgrid_ok
        alert.delivered_slack = slack_ok

    # Always publish to Redis for live dashboard (FR-8.3, FR-8.4)
    _publish_redis(redis_client, event_type, payload, alert)

    await db.commit()
    logger.info(
        "Alert dispatched: event_type=%s rate_limited=%s sendgrid=%s slack=%s",
        event_type, limited,
        alert.delivered_sendgrid, alert.delivered_slack,
    )
    return alert


async def _send_sendgrid(event_type: str, payload: dict[str, Any] | None) -> bool:
    """Send email via SendGrid. Returns True on success, False on failure."""
    if not settings.SENDGRID_API_KEY or not settings.SENDGRID_TO_EMAIL:
        logger.warning(
            "SendGrid not configured (SENDGRID_API_KEY or SENDGRID_TO_EMAIL empty); "
            "skipping email delivery for %s", event_type
        )
        return False

    try:
        html_body = render_email_html(event_type, payload)
        message = Mail(
            from_email=settings.SENDGRID_FROM_EMAIL,
            to_emails=settings.SENDGRID_TO_EMAIL,
            subject=f"[PEAD] {event_type}",
            html_content=html_body,
        )
        sg = SendGridAPIClient(settings.SENDGRID_API_KEY)
        sg.send(message)
        return True
    except Exception as exc:
        logger.error("SendGrid delivery failed for %s: %s", event_type, exc)
        return False


async def _send_slack(event_type: str, payload: dict[str, Any] | None) -> bool:
    """Send Slack webhook POST. Returns True on success, False on failure."""
    if not settings.SLACK_WEBHOOK_URL:
        logger.warning(
            "SLACK_WEBHOOK_URL not configured; skipping Slack delivery for %s",
            event_type,
        )
        return False

    try:
        import httpx
        text_body = render_slack_text(event_type, payload)
        async with httpx.AsyncClient() as client:
            resp = await client.post(
                settings.SLACK_WEBHOOK_URL,
                json={"text": text_body},
                timeout=10.0,
            )
            resp.raise_for_status()
        return True
    except Exception as exc:
        logger.error("Slack delivery failed for %s: %s", event_type, exc)
        return False


def _publish_redis(
    r: redis.Redis,
    event_type: str,
    payload: dict[str, Any] | None,
    alert: Alert,
) -> None:
    """Publish alert to Redis 'alerts' pub/sub channel.

    Published to REDIS_PUB_URL (same URL stream.py subscribes to).
    Payload includes event_type, alert_id, and event data for SSE.
    """
    try:
        message = json.dumps(
            {
                "event_type": event_type,
                "alert_id": str(alert.id),
                "payload": payload or {},
            },
            default=str,
        )
        r.publish(ALERTS_CHANNEL, message)
    except Exception as exc:
        logger.error("Redis publish failed for %s: %s", event_type, exc)
