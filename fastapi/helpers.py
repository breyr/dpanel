import docker
from docker.models.containers import Container
import json
from aioredis import Redis
from fastapi import Request
from docker.errors import APIError

DOCKER_CLIENT = docker.from_env()


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
    await redis.publish(
        "server_messages", json.dumps({"text": message, "category": category})
    )


def pause_container(container: Container):
    if container.status == "running":
        container.pause()
        return {"message": "success", "containerId": container.short_id}
    # already exited
    return {"message": "error", "containerId": container.short_id}


def resume_container(container: Container):
    if container.status == "paused":
        container.unpase()
        return {"message": "success", "containerId": container.short_id}
    # already exited
    return {"message": "error", "containerId": container.short_id}


def start_container(container: Container):
    if container.status == "exited":
        container.start()
        return {"message": "success", "containerId": container.short_id}
    # already exited
    return {"message": "error", "containerId": container.short_id}


def stop_container(container: Container):
    if container.status == "running" or container.status == "paused":
        container.stop()
        return {"message": "success", "containerId": container.short_id}
    # already exited
    return {"message": "error", "containerId": container.short_id}


def restart_container(container: Container):
    try:
        container.restart()
    except APIError as e:
        # already restarted
        return {"message": "error", "containerId": container.short_id}
    return {"message": "success", "containerId": container.short_id}


def kill_container(container: Container):
    try:
        container.kill()
    except APIError as e:
        # already killed
        return {"message": "error", "containerId": container.short_id}
    return {"message": "success", "containerId": container.short_id}
