from fastapi import FastAPI, Request
from sse_starlette import EventSourceResponse
from fastapi.requests import Request
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
import aioredis
from aioredis import Redis
import json
from docker.errors import APIError
from typing import Callable
from helpers import (
    DOCKER_CLIENT,
    pause_container,
    subscribe_to_channel,
    publish_message_data,
    start_container,
    stop_container,
    kill_container,
    restart_container,
    resume_container,
)

# Define global variables
redis: Redis = None

app = FastAPI()

origins = ["http://localhost:3000"]

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Allows all origins
    allow_credentials=True,
    allow_methods=["*"],  # Allows all methods
    allow_headers=["*"],  # Allows all headers
)


# Function to setup aioredis
async def setup_redis():
    global redis
    redis = await aioredis.from_url("redis://redis")


# Function to close the Redis connection pool
async def close_redis():
    global redis
    if redis:
        await redis.close()
        await redis.wait_closed()


# Register startup event handler
app.add_event_handler("startup", setup_redis)
# Register shutdown event handler
app.add_event_handler("shutdown", close_redis)


# ======== HELPERS =========


async def perform_action(
    req: Request, action: Callable, success_msg: str, error_msg: str
):
    try:
        data = await req.json()
        ids = data["ids"]
        error_ids = []
        for id in ids:
            container = DOCKER_CLIENT.containers.get(id)
            res = action(container)
            if res["message"] == "error":
                error_ids.append(res["containerId"])
        # no containers had the action performed
        if len(ids) - len(error_ids) == 0:
            await publish_message_data(
                f"{error_msg}: {error_ids}", "danger", redis=redis
            )
        else:
            await publish_message_data(
                f"{success_msg}: {len(ids) - len(error_ids)}", "success", redis=redis
            )
            # publish any error ids
            if error_ids:
                await publish_message_data(
                    f"{error_msg}: {error_ids}", "danger", redis=redis
                )
        return JSONResponse(content={"message": f"{success_msg}"}, status_code=200)
    except Exception as e:
        await publish_message_data("API error, please try again", "danger", redis=redis)
        return JSONResponse(content={"message": "API error"}, status_code=400)


# ======== ENDPOINTS =========


@app.get("/api/streams/containerlist")
async def container_list(req: Request):
    return EventSourceResponse(subscribe_to_channel(req, "containers_list", redis))


@app.get("/api/streams/servermessages")
async def container_list(req: Request):
    return EventSourceResponse(subscribe_to_channel(req, "server_messages", redis))


@app.post("/api/containers/start")
async def start_containers(req: Request):
    return await perform_action(
        req, start_container, "Containers started", "Containers already started"
    )


@app.post("/api/containers/stop")
async def pause_containers(req: Request):
    return await perform_action(
        req, stop_container, "Containers stopped", "Containers already stopped"
    )


@app.post("/api/containers/kill")
async def kill_containers(req: Request):
    return await perform_action(
        req, kill_container, "Containers killed", "Containers already killed"
    )


@app.post("/api/containers/restart")
async def restart_containers(req: Request):
    return await perform_action(
        req, restart_container, "Containers restarted", "Containers already restarted"
    )


@app.post("/api/containers/pause")
async def pause_containers(req: Request):
    return await perform_action(
        req, pause_container, "Containers paused", "Containers already paused"
    )


@app.post("/api/containers/resume")
async def resume_containers(req: Request):
    return await perform_action(
        req, resume_container, "Containers resumed", "Containers already resumed"
    )
