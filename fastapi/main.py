from fastapi import FastAPI, Request, File, UploadFile
from sse_starlette import EventSourceResponse
from fastapi.requests import Request
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
import aioredis
from aioredis import Redis
from aiodocker.exceptions import DockerError
from typing import Callable
import asyncio
import aiofiles
import os
import json
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


@app.post("/api/upload/compose")
async def upload_file(file: UploadFile = File(...)):
    try:
        contents = await file.read()

        # Write file to /composefiles directory
        # wb - write binary, contents will be rewritten
        async with aiofiles.open(f"/composefiles/{file.filename}", "wb") as out_file:
            await out_file.write(contents)

        await publish_message_data(f"Uploaded: {file.filename}", "Success", redis=redis)
        return JSONResponse(
            content={"message": f"Successfully uploaded {file.filename}"},
            status_code=200,
        )
    except Exception as e:
        await publish_message_data(
            f"API error, please try again: {e}", "Error", redis=redis
        )
        return JSONResponse(
            content={"message": "Error processing uploaded file"}, status_code=400
        )


@app.get("/api/streams/composefiles")
async def list_files():
    async def event_stream():
        while True:
            files = os.listdir("/composefiles")
            yield f"{json.dumps({'files': files})}\n\n"
            await asyncio.sleep(1)

    return EventSourceResponse(event_stream())


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


@app.post("/api/compose/delete")
async def delete_compose_file(req: Request):
    data = await req.json()
    logging.info(f"File to delete: {data}")
    file_to_delete = data.get("fileName")
    try:
        os.remove(f"/composefiles/{file_to_delete}")
        await publish_message_data(
            f"Successfully deleted {file_to_delete}", "Success", redis=redis
        )
        return JSONResponse(
            content={"message": f"Successfully deleted {file_to_delete}"},
            status_code=200,
        )
    except Exception as e:
        await publish_message_data(
            f"API error, please try again: {e}", "Error", redis=redis
        )
        return JSONResponse(
            content={"message": f"Error deleting file: {e}"}, status_code=400
        )
