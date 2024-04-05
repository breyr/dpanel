import json
from aioredis import Redis
from fastapi import Request
import time
import enum


class ObjectType(enum.Enum):
    CONTAINER = "container"
    IMAGE = "image"
    VOLUME = "volume"


def convert_from_bytes(bytes) -> str:
    size_in_mb = bytes / 1048576
    size_in_gb = size_in_mb / 1024
    return (
        f"{round(size_in_mb, 2)} MB" if size_in_gb < 1 else f"{round(size_in_mb, 2)} GB"
    )


async def subscribe_to_channel(req: Request, chan: str, redis: Redis):
    pubsub = redis.pubsub()
    # will fail if you pass a channel that doesn't exist
    await pubsub.subscribe(chan)
    async for message in pubsub.listen():
        if await req.is_disconnected():
            await pubsub.close()
            break
        if message["type"] == "message" and message["data"] != 1:
            yield f"{message['data'].decode('utf-8')}\n\n"


async def publish_message_data(message: str, category: str, redis: Redis):
    # gets consumed by frontend via toasts
    # need to pass alert text, category (error, success), and time when the message is posted
    await redis.publish(
        "server_messages",
        json.dumps({"text": message, "category": category, "timeSent": time.time()}),
    )
