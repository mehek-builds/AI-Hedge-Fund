"""Tests for FR-7.4 (alert delivery) and FR-8.3/8.4 (Redis pub/sub).

Uses mock SendGrid, Slack, Redis, and AsyncSession to avoid real network/DB calls.
"""
import json
from unittest.mock import AsyncMock, MagicMock, patch
import uuid

import pytest
import pytest_asyncio

from app.models.alerts import VALID_EVENT_TYPES


def _make_mock_db():
    """Return an AsyncMock simulating AsyncSession with add/flush/commit."""
    db = AsyncMock()
    db.add = MagicMock()
    db.flush = AsyncMock()
    db.commit = AsyncMock()
    return db


def _make_mock_redis(is_limited: bool = False):
    """Return a mock Redis client. is_limited controls rate limiter behavior."""
    r = MagicMock()
    # INCR returns 1 (first call, not limited) or 4 (limited)
    r.incr.return_value = 4 if is_limited else 1
    r.expire = MagicMock()
    r.publish = MagicMock()
    return r


@pytest.mark.asyncio
async def test_sendgrid_called_for_all_9_event_types():
    """FR-7.4: SendGridAPIClient.send() called for each of the 9 event types."""
    from app.alerting.dispatcher import dispatch_alert

    for event_type in VALID_EVENT_TYPES:
        db = _make_mock_db()
        r = _make_mock_redis(is_limited=False)

        with (
            patch("app.alerting.dispatcher.SendGridAPIClient") as mock_sg_class,
            patch("app.alerting.dispatcher.settings") as mock_settings,
            patch("httpx.AsyncClient") as mock_httpx,
        ):
            mock_settings.SENDGRID_API_KEY = "test_key"
            mock_settings.SENDGRID_TO_EMAIL = "test@example.com"
            mock_settings.SENDGRID_FROM_EMAIL = "alerts@pead.com"
            mock_settings.SLACK_WEBHOOK_URL = ""  # disable Slack for this test
            mock_sg_instance = MagicMock()
            mock_sg_class.return_value = mock_sg_instance

            alert = await dispatch_alert(event_type, {"symbol": "AAPL"}, db, r)

            mock_sg_instance.send.assert_called_once()
            call_args = mock_sg_instance.send.call_args[0][0]
            assert event_type in str(call_args.subject)


@pytest.mark.asyncio
async def test_slack_called_for_all_9_event_types():
    """FR-7.4: Slack webhook POST called for each non-rate-limited alert."""
    from app.alerting.dispatcher import dispatch_alert

    for event_type in VALID_EVENT_TYPES:
        db = _make_mock_db()
        r = _make_mock_redis(is_limited=False)

        with (
            patch("app.alerting.dispatcher.settings") as mock_settings,
            patch("app.alerting.dispatcher.SendGridAPIClient"),
            patch("httpx.AsyncClient") as mock_httpx_class,
        ):
            mock_settings.SENDGRID_API_KEY = ""  # disable SendGrid
            mock_settings.SLACK_WEBHOOK_URL = "https://hooks.slack.com/test"
            mock_settings.SENDGRID_FROM_EMAIL = ""
            mock_settings.SENDGRID_TO_EMAIL = ""

            mock_client = AsyncMock()
            mock_httpx_class.return_value.__aenter__ = AsyncMock(return_value=mock_client)
            mock_httpx_class.return_value.__aexit__ = AsyncMock(return_value=False)
            mock_client.post = AsyncMock(return_value=MagicMock(raise_for_status=MagicMock()))

            await dispatch_alert(event_type, {}, db, r)

            mock_client.post.assert_called_once()
            call_kwargs = mock_client.post.call_args[1]
            # render_slack_text uppercases and replaces underscores with spaces
            assert event_type.replace("_", " ").upper() in call_kwargs["json"]["text"]


@pytest.mark.asyncio
async def test_alert_persisted_to_db():
    """FR-8.1: Alert row added to session with correct fields."""
    from app.alerting.dispatcher import dispatch_alert
    from app.models.alerts import Alert

    db = _make_mock_db()
    r = _make_mock_redis(is_limited=False)

    with (
        patch("app.alerting.dispatcher.settings") as mock_settings,
        patch("app.alerting.dispatcher.SendGridAPIClient") as mock_sg,
    ):
        mock_settings.SENDGRID_API_KEY = "key"
        mock_settings.SENDGRID_TO_EMAIL = "t@t.com"
        mock_settings.SENDGRID_FROM_EMAIL = "a@a.com"
        mock_settings.SLACK_WEBHOOK_URL = ""
        mock_sg.return_value.send = MagicMock()

        alert = await dispatch_alert("order_filled", {"symbol": "TSLA"}, db, r)

        db.add.assert_called_once()
        added_obj = db.add.call_args[0][0]
        assert isinstance(added_obj, Alert)
        assert added_obj.event_type == "order_filled"
        assert added_obj.payload == {"symbol": "TSLA"}
        db.commit.assert_called_once()


@pytest.mark.asyncio
async def test_redis_publish():
    """FR-8.3/8.4: Redis publish called with channel='alerts' and event_type in payload."""
    from app.alerting.dispatcher import dispatch_alert

    db = _make_mock_db()
    r = _make_mock_redis(is_limited=False)

    with (
        patch("app.alerting.dispatcher.settings") as mock_settings,
        patch("app.alerting.dispatcher.SendGridAPIClient"),
    ):
        mock_settings.SENDGRID_API_KEY = ""
        mock_settings.SENDGRID_TO_EMAIL = ""
        mock_settings.SENDGRID_FROM_EMAIL = ""
        mock_settings.SLACK_WEBHOOK_URL = ""

        await dispatch_alert("signal_generated", {"signal_id": "abc"}, db, r)

        r.publish.assert_called_once()
        channel_arg, data_arg = r.publish.call_args[0]
        assert channel_arg == "alerts"
        published = json.loads(data_arg)
        assert published["event_type"] == "signal_generated"
        assert published["payload"]["signal_id"] == "abc"


@pytest.mark.asyncio
async def test_delivery_failure_logged_not_raised():
    """Delivery mode: SendGrid failure is logged; no exception propagates to caller."""
    from app.alerting.dispatcher import dispatch_alert

    db = _make_mock_db()
    r = _make_mock_redis(is_limited=False)

    with (
        patch("app.alerting.dispatcher.settings") as mock_settings,
        patch("app.alerting.dispatcher.SendGridAPIClient") as mock_sg,
    ):
        mock_settings.SENDGRID_API_KEY = "key"
        mock_settings.SENDGRID_TO_EMAIL = "t@t.com"
        mock_settings.SENDGRID_FROM_EMAIL = "a@a.com"
        mock_settings.SLACK_WEBHOOK_URL = ""
        mock_sg.return_value.send.side_effect = Exception("SendGrid API error")

        # Must NOT raise
        alert = await dispatch_alert("thesis_broken", {}, db, r)

        assert alert.delivered_sendgrid is False
        db.commit.assert_called_once()
