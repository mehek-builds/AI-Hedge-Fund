"""Redis wrapper for caching macro regime and portfolio snapshots."""

from __future__ import annotations

import json
import os
from typing import Optional

import redis as redis_lib
from loguru import logger

REDIS_URL = os.environ.get("REDIS_URL", "redis://redis:6379/0")


class RedisClient:
    """Thin Redis wrapper for PEAD system caching and pub/sub."""

    _MACRO_KEY = "pead:macro_regime"
    _PORTFOLIO_KEY = "pead:portfolio_snapshot"

    def __init__(self, url: Optional[str] = None):
        self._url = url or REDIS_URL
        self._client = redis_lib.from_url(self._url, decode_responses=True)
        logger.info(f"RedisClient connected to {self._url}")

    # ------------------------------------------------------------------
    # Macro regime cache
    # ------------------------------------------------------------------

    def get_macro_regime(self) -> Optional[dict]:
        """Return cached macro regime dict or None if missing/expired."""
        raw = self._client.get(self._MACRO_KEY)
        if raw is None:
            return None
        try:
            return json.loads(raw)
        except json.JSONDecodeError:
            logger.warning("Corrupt macro regime cache — ignoring")
            return None

    def set_macro_regime(self, data: dict, ttl: int = 3600) -> None:
        """Cache macro regime dict with TTL in seconds (default 1 hour)."""
        self._client.setex(self._MACRO_KEY, ttl, json.dumps(data, default=str))

    # ------------------------------------------------------------------
    # Portfolio snapshot cache
    # ------------------------------------------------------------------

    def get_portfolio_snapshot(self) -> Optional[dict]:
        """Return cached portfolio snapshot or None if missing/expired."""
        raw = self._client.get(self._PORTFOLIO_KEY)
        if raw is None:
            return None
        try:
            return json.loads(raw)
        except json.JSONDecodeError:
            logger.warning("Corrupt portfolio snapshot cache — ignoring")
            return None

    def set_portfolio_snapshot(self, data: dict, ttl: int = 300) -> None:
        """Cache portfolio snapshot with TTL in seconds (default 5 min)."""
        self._client.setex(self._PORTFOLIO_KEY, ttl, json.dumps(data, default=str))

    # ------------------------------------------------------------------
    # Pub/sub
    # ------------------------------------------------------------------

    def publish(self, channel: str, data: dict) -> None:
        """Publish a JSON message to a Redis channel."""
        self._client.publish(channel, json.dumps(data, default=str))

    # ------------------------------------------------------------------
    # Generic helpers
    # ------------------------------------------------------------------

    def get(self, key: str) -> Optional[str]:
        return self._client.get(key)

    def set(self, key: str, value: str, ttl: Optional[int] = None) -> None:
        if ttl:
            self._client.setex(key, ttl, value)
        else:
            self._client.set(key, value)

    def delete(self, key: str) -> None:
        self._client.delete(key)

    def ping(self) -> bool:
        try:
            return self._client.ping()
        except Exception:
            return False


# Module-level singleton
_redis_client: Optional[RedisClient] = None


def get_redis_client() -> RedisClient:
    global _redis_client
    if _redis_client is None:
        _redis_client = RedisClient()
    return _redis_client
