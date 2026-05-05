import asyncio

import redis.asyncio as aioredis
from fastapi import APIRouter
from fastapi.responses import StreamingResponse

from app.config import settings

router = APIRouter()

CHANNELS = ["signals", "positions", "rl_state", "alerts"]

HEARTBEAT_INTERVAL = 25.0  # seconds


async def event_generator():
    client = aioredis.from_url(settings.REDIS_PUB_URL, decode_responses=True)
    pubsub = client.pubsub()
    await pubsub.subscribe(*CHANNELS)

    last_heartbeat = asyncio.get_event_loop().time()

    try:
        while True:
            now = asyncio.get_event_loop().time()
            if now - last_heartbeat >= HEARTBEAT_INTERVAL:
                yield ": heartbeat\n\n"
                last_heartbeat = now

            message = await asyncio.wait_for(pubsub.get_message(ignore_subscribe_messages=True), timeout=1.0)
            if message is not None:
                channel = message.get("channel", "")
                data = message.get("data", "")
                if isinstance(data, bytes):
                    data = data.decode()
                yield f"event: {channel}\ndata: {data}\n\n"
            else:
                await asyncio.sleep(0.05)
    except asyncio.CancelledError:
        pass
    finally:
        await pubsub.unsubscribe(*CHANNELS)
        await client.aclose()


@router.get("/events")
async def sse_events():
    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
        },
    )
