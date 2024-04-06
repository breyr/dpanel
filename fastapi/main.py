from fastapi import FastAPI, Request
from sse_starlette import EventSourceResponse
from fastapi.requests import Request
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
import aioredis
from aioredis import Redis
from aiodocker.exceptions import DockerError
from typing import Callable, List
from python_on_whales import DockerClient, DockerException
import asyncio
import aiofiles
import os
import json
from helpers import (
    convert_from_bytes,
    subscribe_to_channel,
    publish_message_data,
    ObjectType,
)
from logger import Logger
from docker_utils import DockerManager

# Define global variables
redis: Redis = None
logger = Logger(__name__)
docker_manager = DockerManager()

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
        config = data.get("config", "")
        error_ids_msgs = []
        success_ids_msgs = []
        logger.info(
            f"\nRequest Data: {data}\nIds: {ids}\nImage to pull: {from_image}\nImage tag: {tag}\n"
        )

        async def perform_action_and_handle_error(
            id: str, publish_image: str = None, tag: str = None
        ):
            if object_type == ObjectType.CONTAINER:
                # if create a new container, have to pass config from request
                if config:
                    res = await action(config)
                    logger.info(f"Result from creating new container")
                else:
                    container = await docker_manager.async_client.containers.get(id)
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
        if config:
            tasks.append(perform_action_and_handle_error(None))
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


@app.get("/api/streams/composefiles")
async def list_files():
    async def event_stream():
        while True:
            files = os.listdir("./composefiles")
            files = [os.path.splitext(file)[0] for file in files]
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


@app.get("/api/streams/containermetrics")
async def container_stat(req: Request):
    return EventSourceResponse(subscribe_to_channel(req, "container_metrics", redis))


@app.get("/api/containers/info/{container_id}")
def info(container_id: str):
    # get container information
    # this function does not need to be async because get() is not asynchronous
    return docker_manager.sync_client.containers.get(container_id=container_id).attrs


@app.post("/api/system/prune")
async def prune_system(req: Request):
    data = await req.json()
    objects_to_prune: List[str] = data["objectsToPrune"]
    logger.info(f"Objects: {objects_to_prune}")
    try:
        res = {}
        for obj in objects_to_prune:
            if obj == "containers":
                pruned_containers = docker_manager.sync_client.containers.prune()
                res["Containers"] = pruned_containers
            elif obj == "images":
                pruned_images = docker_manager.sync_client.images.prune()
                res["Images"] = pruned_images
            elif obj == "volumes":
                pruned_volumes = docker_manager.sync_client.volumes.prune()
                res["Volumes"] = pruned_volumes
            elif obj == "networks":
                pruned_networks = docker_manager.sync_clientT.networks.prune()
                res["Networks"] = pruned_networks
                break

        # res['containers'] -> list or None ['ContainersDeleted], ['SpaceReclaimed']
        # res['images'] -> list or None ['ImagesDeleted'], ['SpaceReclaimed']
        # res['volumes'] -> list or None ['VolumesDelete'], ['SpaceReclaimed']
        # res['networks'] -> list or None ['NetworksDeleted']
        async def schedule_messages(object_type: str, res: dict, redis):
            # get number of objects deleted
            logger.info(f"Scheduling message for object: {object_type} after pruning")
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


@app.post("/api/containers/run")
async def run_container(req: Request):
    return await perform_action(
        req,
        docker_manager.run_container,
        ObjectType.CONTAINER,
        "Container created and running",
        "Container failed to create and run",
    )


@app.post("/api/containers/start")
async def start_containers(req: Request):
    return await perform_action(
        req,
        docker_manager.start_container,
        ObjectType.CONTAINER,
        "Containers started",
        "Containers already started",
    )


@app.post("/api/containers/stop")
async def stop_containers(req: Request):
    return await perform_action(
        req,
        docker_manager.stop_container,
        ObjectType.CONTAINER,
        "Containers stopped",
        "Containers already stopped",
    )


@app.post("/api/containers/kill")
async def kill_containers(req: Request):
    return await perform_action(
        req,
        docker_manager.kill_container,
        ObjectType.CONTAINER,
        "Containers killed",
        "Containers already killed",
    )


@app.post("/api/containers/restart")
async def restart_containers(req: Request):
    return await perform_action(
        req,
        docker_manager.restart_container,
        ObjectType.CONTAINER,
        "Containers restarted",
        "Containers already restarted",
    )


@app.post("/api/containers/pause")
async def pause_containers(req: Request):
    return await perform_action(
        req,
        docker_manager.pause_container,
        ObjectType.CONTAINER,
        "Containers paused",
        "Containers already paused",
    )


@app.post("/api/containers/resume")
async def resume_containers(req: Request):
    return await perform_action(
        req,
        docker_manager.resume_container,
        ObjectType.CONTAINER,
        "Containers resumed",
        "Containers already resumed",
    )


@app.post("/api/containers/delete")
async def delete_containers(req: Request):
    return await perform_action(
        req,
        docker_manager.delete_container,
        ObjectType.CONTAINER,
        "Containers deleted",
        "Containers already deleted",
    )


@app.post("/api/images/delete")
async def delete_images(req: Request):
    return await perform_action(
        req,
        docker_manager.delete_image,
        ObjectType.IMAGE,
        success_msg="Images deleted",
        error_msg="Error, check if containers are running",
    )


@app.post("/api/images/pull")
async def pull_images(req: Request):
    return await perform_action(
        req,
        docker_manager.pull_image,
        ObjectType.IMAGE,
        success_msg="Image pulled",
        error_msg="Error",
    )


@app.post("/api/compose/upload")
async def upload_file(req: Request):
    try:
        data = await req.json()
        project_name = data.get("projectName")
        yaml_contents = data.get("yamlContents")

        # Create a new file with the project name as the filename and .yml as the extension
        async with aiofiles.open(
            f"./composefiles/{project_name}.yaml", "w"
        ) as out_file:
            await out_file.write(yaml_contents)

        await publish_message_data(
            f"Uploaded: {project_name}.yaml", "Success", redis=redis
        )
        return JSONResponse(
            content={"message": f"Successfully uploaded {project_name}.yaml"},
            status_code=200,
        )
    except Exception as e:
        await publish_message_data(
            f"API error, please try again: {e}", "Error", redis=redis
        )
        return JSONResponse(
            content={"message": "Error processing uploaded file"}, status_code=400
        )


@app.post("/api/compose/delete")
async def delete_compose_file(req: Request):
    data = await req.json()
    logger.info(f"File to delete: {data}")
    file_to_delete = data.get("projectName")
    try:
        os.remove(f"./composefiles/{file_to_delete}.yaml")
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


@app.post("/api/compose/up")
async def run_compose_file(req: Request):
    data = await req.json()
    # get path of file to run
    file_to_run = data.get("projectName")
    file_path = f"./composefiles/{file_to_run}.yaml"
    # project name is the name of the file
    project_name = file_to_run.split(".")[0]
    try:
        # create docker client
        logger.info("Attempting to compose up")
        docker = DockerClient(
            compose_files=[file_path], compose_project_name=project_name
        )
        docker.compose.up(detach=True)
        await publish_message_data(
            f"Compose up successful: {file_to_run}", "Success", redis=redis
        )
        return JSONResponse(
            content={"message": f"Compose up successful: {file_to_run}"},
            status_code=200,
        )
    except DockerException as e:
        await publish_message_data(
            f"API error, please try again: {e}", "Error", redis=redis
        )
        return JSONResponse(
            content={"message": f"Docker compose error: {e}"}, status_code=400
        )


@app.post("/api/compose/down")
async def compose_down(req: Request):
    data = await req.json()
    # get path of file to run
    file_to_run = data.get("projectName")
    file_path = f"./composefiles/{file_to_run}.yaml"
    # project name is the name of the file
    project_name = file_to_run.split(".")[0]
    # read the project name from the Docker Compose file
    try:
        # create docker client
        logger.info("Attempting to compose up")
        docker = DockerClient(
            compose_files=[file_path], compose_project_name=project_name
        )
        docker.compose.down()
        await publish_message_data(
            f"Compose down successful: {file_to_run}", "Success", redis=redis
        )
        return JSONResponse(
            content={"message": f"Compose down successful: {file_to_run}"},
            status_code=200,
        )
    except DockerException as e:
        await publish_message_data(
            f"API error, please try again: {e}", "Error", redis=redis
        )
        return JSONResponse(
            content={"message": f"Docker compose error: {e}"}, status_code=400
        )
