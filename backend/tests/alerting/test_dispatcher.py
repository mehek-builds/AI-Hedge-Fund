"""Wave 0 stubs for FR-7.4 (alert delivery) and FR-8.3/8.4 (Redis pub/sub).

These tests FAIL until Plan 07-03 implements alerting/dispatcher.py.
"""
import pytest


def test_sendgrid_called_for_all_9_event_types():
    """FR-7.4: SendGridAPIClient.send() is called once for each of the 9 event types."""
    pytest.fail(
        "STUB: implement after dispatcher.py exists (Plan 07-03). "
        "Expected: for each event_type in VALID_EVENT_TYPES, dispatch_alert() calls "
        "SendGridAPIClient.send() with html_content containing the event_type."
    )


def test_slack_called_for_all_9_event_types():
    """FR-7.4: Slack webhook POST called for each non-rate-limited alert."""
    pytest.fail(
        "STUB: implement after dispatcher.py exists (Plan 07-03). "
        "Expected: httpx.AsyncClient.post() called to SLACK_WEBHOOK_URL for each event."
    )


def test_alert_persisted_to_db():
    """FR-8.1: Alert row inserted to alerts table on dispatch."""
    pytest.fail(
        "STUB: implement after dispatcher.py exists (Plan 07-03). "
        "Expected: dispatch_alert() inserts one Alert row with correct event_type "
        "and delivered_sendgrid=True, delivered_slack=True when delivery succeeds."
    )


def test_redis_publish():
    """FR-8.3/8.4: Alert JSON published to Redis 'alerts' pub/sub channel."""
    pytest.fail(
        "STUB: implement after dispatcher.py exists (Plan 07-03). "
        "Expected: dispatch_alert() calls redis.publish('alerts', json_payload) "
        "where json_payload includes event_type and payload fields."
    )


def test_delivery_failure_logged_not_raised():
    """Delivery mode: SendGrid failure is logged; no exception propagates to caller."""
    pytest.fail(
        "STUB: implement after dispatcher.py exists (Plan 07-03). "
        "Expected: when SendGridAPIClient.send() raises Exception, "
        "dispatch_alert() logs the error and does NOT re-raise."
    )
