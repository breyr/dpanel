from fastapi import FastAPI, Request
from sse_starlette import EventSourceResponse
from fastapi.requests import Request
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
import aioredis
from aioredis import Redis
from aiodocker.exceptions import DockerError
from typing import Callable, List
import asyncio
from helpers import (
    ASYNC_DOCKER_CLIENT,
    SYNC_DOCKER_CLIENT,
    convert_from_bytes,
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
        error_ids_msgs = []
        success_ids_msgs = []
        logging.info(
            f"\nRequest Data: {data}\nIds: {ids}\nImage to pull: {from_image}\nImage tag: {tag}\n"
        )

        async def perform_action_and_handle_error(
            id: str, publish_image: str = None, tag: str = None
        ):
            if object_type == ObjectType.CONTAINER:
                container = await ASYNC_DOCKER_CLIENT.containers.get(id)
                res = await action(container)
            elif object_type == ObjectType.IMAGE:
                # for pulling an image
                if publish_image:
                    res = await action(publish_image, tag)
                else:
                    # for deleting an image
                    res = await action(id)
            return res

        tasks = []
        # create list of tasks and use asyncio.gather to run them concurrently
        if ids:
            tasks.extend([perform_action_and_handle_error(id) for id in ids])
        if from_image:
            tasks.append(perform_action_and_handle_error(None, from_image, tag))

        # the * is list unpacking
        results = await asyncio.gather(*tasks)

        for res in results:
            if res["type"] == "error":
                if "statusCode" in res:
                    # get message from DockerError
                    error_ids_msgs.append(res["message"])
                else:
                    # get short id of object's full id
                    error_ids_msgs.append(res["objectId"][:12])
            elif res["type"] == "success":
                if "message" in res and "status" in res["message"]:
                    # append result from pulling an image
                    success_ids_msgs.append(res["message"]["status"])
                else:
                    success_ids_msgs.append(res["objectId"][:12])

        publish_tasks = []
        if success_ids_msgs:
            publish_tasks.append(
                publish_message_data(
                    f"{success_msg} ({len(success_ids_msgs)}):  {success_ids_msgs}",
                    "Success",
                    redis=redis,
                )
            )

        if error_ids_msgs:
            publish_tasks.append(
                publish_message_data(
                    f"{error_msg}: {error_ids_msgs}", "Error", redis=redis
                )
            )

        await asyncio.gather(*publish_tasks)

        if error_ids_msgs:
            return JSONResponse(
                content={"message": f"{error_msg}: {error_ids_msgs}"}, status_code=400
            )
        else:
            return JSONResponse(content={"message": f"{success_msg}"}, status_code=200)
    except Exception as e:
        await publish_message_data(
            f"API error, please try again: {e}", "Error", redis=redis
        )
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
    data = await req.json()
    objects_to_prune: List[str] = data["objectsToPrune"]
    logging.info(f"Objects: {objects_to_prune}")
    try:
        res = {}
        for obj in objects_to_prune:
            if obj == "containers":
                pruned_containers = SYNC_DOCKER_CLIENT.containers.prune()
                res["Containers"] = pruned_containers
            elif obj == "images":
                pruned_images = SYNC_DOCKER_CLIENT.images.prune()
                res["Images"] = pruned_images
            elif obj == "volumes":
                pruned_volumes = SYNC_DOCKER_CLIENT.volumes.prune()
                res["Volumes"] = pruned_volumes
            elif obj == "networks":
                # Add your code for "Networks" here
                pruned_networks = SYNC_DOCKER_CLIENT.networks.prune()
                res["Networks"] = pruned_networks
                break

        # res['containers'] -> list or None ['ContainersDeleted], ['SpaceReclaimed']
        # res['images'] -> list or None ['ImagesDeleted'], ['SpaceReclaimed']
        # res['volumes'] -> list or None ['VolumesDelete'], ['SpaceReclaimed']
        # res['networks'] -> list or None ['NetworksDeleted']
        async def schedule_messages(object_type: str, res: dict, redis):
            # get number of objects deleted
            logging.info(f"Scheduling message for object: {object_type} after pruning")
            num_deleted = (
                0
                if res[object_type][f"{object_type}Deleted"] is None
                else len(res[object_type][f"{object_type}Deleted"])
            )
            space_reclaimed = (
                0
                if object_type == "Networks"
                else convert_from_bytes(res[object_type]["SpaceReclaimed"])
            )
            await publish_message_data(
                f"{object_type} pruned successfully: {num_deleted} deleted, {space_reclaimed} space reclaimed",
                "Success",
                redis=redis,
            )

        # schedules message sending based on keys in result dict from pruning
        tasks = [schedule_messages(key, res, redis) for key in res.keys()]
        await asyncio.gather(*tasks)

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
        error_msg="Error, check if containers are running",
    )


@app.post("/api/images/pull")
async def pull_images(req: Request):
    return await perform_action(
        req,
        pull_image,
        ObjectType.IMAGE,
        success_msg="Image pulled",
        error_msg="Error",
    )
