"""Wave 0 stubs for FR-7.5 (rate limiting: max 3/hr, burst test).

These tests FAIL until Plan 07-03 implements alerting/rate_limiter.py.
"""
import pytest


def test_burst_10_events_yields_3_deliveries():
    """FR-7.5: 10 same-type events in 5 min result in exactly 3 deliveries.

    Uses a mock Redis client. Simulates 10 sequential is_rate_limited() calls
    for the same event_type within the same epoch_hour window.
    Expected: first 3 calls return False (not limited), calls 4-10 return True.
    """
    pytest.fail(
        "STUB: implement after rate_limiter.py exists (Plan 07-03). "
        "Expected: calls 1-3 to is_rate_limited(r, 'signal_generated') return False; "
        "calls 4-10 return True. Key format: alert_rate:signal_generated:{window}."
    )


def test_rate_limit_resets_next_hour():
    """FR-7.5: Counter resets at top of next hour (fixed window)."""
    pytest.fail(
        "STUB: implement after rate_limiter.py exists (Plan 07-03). "
        "Expected: after 3 deliveries in hour N, incrementing window to N+1 "
        "produces a new key and is_rate_limited returns False again."
    )


def test_rate_limit_key_includes_epoch_hour():
    """FR-7.5: Redis key includes :{epoch_hour} suffix (per locked decision)."""
    pytest.fail(
        "STUB: implement after rate_limiter.py exists (Plan 07-03). "
        "Expected: is_rate_limited() calls r.incr(key) where key matches "
        "pattern alert_rate:{event_type}:{integer_epoch_hour}."
    )
