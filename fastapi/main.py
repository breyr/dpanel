from fastapi import FastAPI, Request
from sse_starlette import EventSourceResponse
from fastapi.requests import Request
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
import aioredis
from aioredis import Redis
from aiodocker.exceptions import DockerError
from typing import Callable
import asyncio
from helpers import (
    ASYNC_DOCKER_CLIENT,
    pause_container,
    subscribe_to_channel,
    publish_message_data,
    start_container,
    stop_container,
    kill_container,
    restart_container,
    resume_container,
    delete_container,
    delete_image,
    pull_image,
    ObjectType,
)

# setup logging for docker container
import sys
import logging

logging.basicConfig(
    stream=sys.stdout,
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)

# Define global variables
redis: Redis = None

app = FastAPI()

origins = ["http://localhost:3000"]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,  # Allows all origins
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
    req: Request,
    action: Callable,
    object_type: ObjectType,
    success_msg: str,
    error_msg: str,
):
    try:
        data = await req.json()
        ids = data.get("ids", [])
        from_image = data.get("image", "")
        tag = data.get("tag", "")
        error_ids = []
        success_ids = []

        async def perform_action_and_handle_error(
            id: str, from_image: str = None, tag: str = None
        ):
            # logging.info(f"Performing action for container with id: {id}")
            if object_type == ObjectType.CONTAINER:
                container = await ASYNC_DOCKER_CLIENT.containers.get(id)
                # logging.info(f"{container} container for {id}")
                res = await action(container)
                # logging.info(f"finished action for {id}")
            elif object_type == ObjectType.IMAGE:
                if id:
                    # for deletion
                    res = await action(id)
                if from_image:
                    # for pulling
                    res = await action(from_image=from_image, tag=tag)
            if res["message"] == "error":
                # race condition?
                # substring 0-12 for short id
                error_ids.append(res["objectId"][:12])
            elif res["message"] == "success":
                success_ids.append(res["objectId"][:12])

        # create list of taska and use asyncio.gather to run them concurrently
        if ids:
            tasks = [perform_action_and_handle_error(id) for id in ids]
        else:
            # for actions that don't require an id
            tasks = [perform_action_and_handle_error(from_image=from_image, tag=tag)]
        # the * is list unpacking
        await asyncio.gather(*tasks)

        # no containers had the action performed
        if len(ids) - len(error_ids) == 0:
            tasks = [
                publish_message_data(
                    f"{error_msg} ({len(error_ids)}): {error_ids}",
                    "Error",
                    redis=redis,
                )
            ]
        else:
            tasks = [
                publish_message_data(
                    f"{success_msg} ({len(ids) - len(error_ids)}):  {success_ids}",
                    "Success",
                    redis=redis,
                )
            ]
            # publish any error ids
            if error_ids:
                tasks.append(
                    publish_message_data(
                        f"{error_msg}: {error_ids}", "Error", redis=redis
                    )
                )
        await asyncio.gather(*tasks)
        return JSONResponse(content={"message": f"{success_msg}"}, status_code=200)
    except Exception as e:
        await publish_message_data("API error, please try again", "Error", redis=redis)
        return JSONResponse(content={"message": "API error"}, status_code=400)


# ======== ENDPOINTS =========


@app.get("/api/streams/containerlist")
async def container_list(req: Request):
    # passes subscribe_to_channel async generator to consume the messages it yields
    return EventSourceResponse(subscribe_to_channel(req, "containers_list", redis))


@app.get("/api/streams/servermessages")
async def server_messages(req: Request):
    # passes subscribe_to_channel async generator to consume the messages it yields
    return EventSourceResponse(subscribe_to_channel(req, "server_messages", redis))


@app.get("/api/streams/imagelist")
async def image_list(req: Request):
    return EventSourceResponse(subscribe_to_channel(req, "images_list", redis))


@app.get("/api/containers/info/{container_id}")
def info(container_id: str):
    # get container information
    # this function does not need to be async because get() is not asynchronous
    return ASYNC_DOCKER_CLIENT.containers.get(container_id=container_id).attrs


@app.post("/api/system/prune")
async def prune_system(req: Request):
    try:
        # TODO: ASYNC call, prune doesnt exist in aiodocker
        pruned_containers = ASYNC_DOCKER_CLIENT.containers.prune()
        # client.images.prune()
        # client.networks.prune()
        # client.volumes.prune()
        containers_deleted = pruned_containers.get("ContainersDeleted")
        num_deleted = len(containers_deleted) if containers_deleted is not None else 0
        space_reclaimed = pruned_containers.get("SpaceReclaimed", 0)
        await publish_message_data(
            f"System pruned successfully: {num_deleted} containers deleted, {space_reclaimed} space reclaimed",
            "Success",
            redis=redis,
        )
        return JSONResponse(
            content={"message": "System prune successfull"}, status_code=200
        )
    except DockerError as e:
        await publish_message_data("API error, please try again", "Error", redis=redis)
        return JSONResponse(content={"message": "API error"}, status_code=400)


@app.post("/api/containers/start")
async def start_containers(req: Request):
    return await perform_action(
        req,
        start_container,
        ObjectType.CONTAINER,
        "Containers started",
        "Containers already started",
    )


@app.post("/api/containers/stop")
async def stop_containers(req: Request):
    return await perform_action(
        req,
        stop_container,
        ObjectType.CONTAINER,
        "Containers stopped",
        "Containers already stopped",
    )


@app.post("/api/containers/kill")
async def kill_containers(req: Request):
    return await perform_action(
        req,
        kill_container,
        ObjectType.CONTAINER,
        "Containers killed",
        "Containers already killed",
    )


@app.post("/api/containers/restart")
async def restart_containers(req: Request):
    return await perform_action(
        req,
        restart_container,
        ObjectType.CONTAINER,
        "Containers restarted",
        "Containers already restarted",
    )


@app.post("/api/containers/pause")
async def pause_containers(req: Request):
    return await perform_action(
        req,
        pause_container,
        ObjectType.CONTAINER,
        "Containers paused",
        "Containers already paused",
    )


@app.post("/api/containers/resume")
async def resume_containers(req: Request):
    return await perform_action(
        req,
        resume_container,
        ObjectType.CONTAINER,
        "Containers resumed",
        "Containers already resumed",
    )


@app.post("/api/containers/delete")
async def delete_containers(req: Request):
    return await perform_action(
        req,
        delete_container,
        ObjectType.CONTAINER,
        "Containers deleted",
        "Containers already deleted",
    )


@app.post("/api/images/delete")
async def delete_images(req: Request):
    return await perform_action(
        req,
        delete_image,
        ObjectType.IMAGE,
        success_msg="Images deleted",
        error_msg="Images already delted",
    )


@app.post("/api/images/pull")
async def pull_images(req: Request):
    return await perform_action(
        req,
        pull_image,
        ObjectType.IMAGE,
        success_msg="Images deleted",
        error_msg="Images already delted",
    )
