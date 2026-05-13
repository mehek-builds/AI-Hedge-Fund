"""Tests for FR-7.5: Redis rate limiting (max 3/hr, fixed window).

Uses a mock Redis client to avoid requiring a live Redis connection.
"""
import time
from unittest.mock import MagicMock, call, patch

import pytest

from app.alerting.rate_limiter import is_rate_limited, MAX_PER_HOUR


def _make_mock_redis(initial_count=0):
    """Return a mock Redis client with INCR that auto-increments from initial_count."""
    r = MagicMock()
    counter = {"value": initial_count}

    def incr_side_effect(key):
        counter["value"] += 1
        return counter["value"]

    r.incr.side_effect = incr_side_effect
    return r, counter


def test_burst_10_events_yields_3_deliveries():
    """FR-7.5: 10 same-type events in 5 min result in exactly 3 deliveries."""
    r = MagicMock()
    # Each call to incr returns 1, 2, 3, 4, 5, 6, 7, 8, 9, 10
    r.incr.side_effect = list(range(1, 11))

    results = [is_rate_limited(r, "signal_generated") for _ in range(10)]

    # First 3 not limited (count 1, 2, 3 <= max_per_hour=3)
    assert results[:3] == [False, False, False]
    # Remaining 7 are limited (count 4-10 > 3)
    assert results[3:] == [True] * 7
    # Exactly 3 deliveries (not limited)
    assert results.count(False) == 3


def test_rate_limit_resets_next_hour():
    """FR-7.5: Counter resets at top of next hour (new key, new window)."""
    with patch("app.alerting.rate_limiter.time") as mock_time:
        # Hour N: window = 123456
        mock_time.time.return_value = 123456 * 3600.0

        r = MagicMock()
        r.incr.side_effect = [1, 2, 3, 4]  # 3 allowed, 4th limited

        assert is_rate_limited(r, "order_filled") is False  # count=1
        assert is_rate_limited(r, "order_filled") is False  # count=2
        assert is_rate_limited(r, "order_filled") is False  # count=3
        assert is_rate_limited(r, "order_filled") is True   # count=4 (limited)

        # Hour N+1: window = 123457 -> fresh key
        mock_time.time.return_value = 123457 * 3600.0
        r.incr.side_effect = [1]  # fresh counter
        assert is_rate_limited(r, "order_filled") is False  # count=1 in new window


def test_rate_limit_key_includes_epoch_hour():
    """FR-7.5: Redis key matches alert_rate:{event_type}:{epoch_hour}."""
    with patch("app.alerting.rate_limiter.time") as mock_time:
        mock_time.time.return_value = 500 * 3600.0  # epoch_hour = 500

        r = MagicMock()
        r.incr.return_value = 1

        is_rate_limited(r, "stop_triggered")

        expected_key = "alert_rate:stop_triggered:500"
        r.incr.assert_called_once_with(expected_key)
