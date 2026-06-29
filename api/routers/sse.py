"""Server-Sent Events router — real-time push from Redis pub/sub to browser clients."""

from __future__ import annotations

import asyncio
import json
from typing import AsyncGenerator

from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse

from api.services.auth import get_current_user
from api.services.redis_client import get_redis_client

router = APIRouter(prefix="/stream", tags=["sse"])

HEARTBEAT_INTERVAL = 15  # seconds


async def _event_generator(channel: str) -> AsyncGenerator[str, None]:
    """Subscribe to a Redis pub/sub channel and yield SSE-formatted strings."""
    redis = get_redis_client()
    pubsub = redis.client.pubsub()
    await asyncio.get_event_loop().run_in_executor(None, pubsub.subscribe, channel)

    last_id = 0
    try:
        while True:
            # Poll for a message with a short timeout so we can interleave heartbeats
            message = await asyncio.get_event_loop().run_in_executor(
                None, lambda: pubsub.get_message(ignore_subscribe_messages=True, timeout=0.1)
            )
            if message and message.get("type") == "message":
                last_id += 1
                data = message["data"]
                if isinstance(data, bytes):
                    data = data.decode()
                yield f"id: {last_id}\ndata: {data}\n\n"
            else:
                # Heartbeat every HEARTBEAT_INTERVAL seconds prevents proxy timeouts
                yield f": heartbeat\n\n"
                await asyncio.sleep(HEARTBEAT_INTERVAL)
    finally:
        await asyncio.get_event_loop().run_in_executor(None, pubsub.unsubscribe, channel)
        await asyncio.get_event_loop().run_in_executor(None, pubsub.close)


@router.get("")
async def stream_dashboard(
    _user: str = Depends(get_current_user),
) -> StreamingResponse:
    """SSE endpoint — subscribes to dashboard.summary Redis channel."""
    return StreamingResponse(
        _event_generator("dashboard.summary"),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",  # disable Nginx buffering
            "Connection": "keep-alive",
        },
    )


@router.get("/signals")
async def stream_signals(
    _user: str = Depends(get_current_user),
) -> StreamingResponse:
    """SSE endpoint — subscribes to signals.new Redis channel."""
    return StreamingResponse(
        _event_generator("signals.new"),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
            "Connection": "keep-alive",
        },
    )


@router.get("/alerts")
async def stream_alerts(
    _user: str = Depends(get_current_user),
) -> StreamingResponse:
    """SSE endpoint — subscribes to alerts.fired Redis channel."""
    return StreamingResponse(
        _event_generator("alerts.fired"),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
            "Connection": "keep-alive",
        },
    )
