"""Redis-backed fixed-window rate limiter for alert dispatch.

Key format: alert_rate:{event_type}:{epoch_hour}
- epoch_hour = int(time.time()) // 3600  (integer, resets at top of each hour)
- TTL = 3600 seconds
- Max 3 deliveries per event_type per hour window

Fixed-window boundary behavior: a burst straddling the top of an hour
may allow up to 6 deliveries in 2 seconds (3 at :59:59, 3 at :00:01).
This is acceptable per the locked decision; SC5 tests a 10-event burst
within a single window, not a boundary burst.

Atomicity: INCR + conditional EXPIRE is the standard Redis pattern.
The EXPIRE is set only on count==1 (first write) which is safe because
if count > 1 the key already exists and already has an expiry.
"""
import time
import logging
from typing import Union

import redis

logger = logging.getLogger(__name__)

MAX_PER_HOUR: int = 3
WINDOW_SECONDS: int = 3600


def is_rate_limited(
    r: Union[redis.Redis, "redis.asyncio.Redis"],
    event_type: str,
    max_per_hour: int = MAX_PER_HOUR,
) -> bool:
    """Return True if this event_type has exceeded max_per_hour in the current window.

    Atomically increments the counter. Sets TTL on first write of each window.
    Returns False (not limited) for the first max_per_hour calls within a window.
    Returns True (limited) for all subsequent calls within the same window.

    Args:
        r: Synchronous redis.Redis client (from redis-py)
        event_type: One of VALID_EVENT_TYPES
        max_per_hour: Maximum deliveries per hour window (default 3)
    """
    window = int(time.time()) // 3600
    key = f"alert_rate:{event_type}:{window}"

    count = r.incr(key)
    if count == 1:
        # First write in this window: set expiry
        r.expire(key, WINDOW_SECONDS)

    if count > max_per_hour:
        logger.debug(
            "Rate limited: event_type=%s window=%d count=%d (max=%d)",
            event_type, window, count, max_per_hour,
        )
        return True

    return False
