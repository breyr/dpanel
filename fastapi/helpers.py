import json
from aioredis import Redis
from fastapi import Request
import aiodocker
from aiodocker.exceptions import DockerError
from aiodocker.docker import DockerContainer, DockerImages
import time
import enum

# setup logging for docker container
import sys
import logging

logging.basicConfig(
    stream=sys.stdout,
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)


class ObjectType(enum.Enum):
    CONTAINER = "container"
    IMAGE = "image"
    VOLUME = "volume"


ASYNC_DOCKER_CLIENT = aiodocker.Docker()
DOCKER_IMAGES = aiodocker.docker.DockerImages(ASYNC_DOCKER_CLIENT)

# "State":{
#       "Status":"exited",
#       "Running":false,
#       "Paused":false,
#       "Restarting":false,
#       "OOMKilled":false,
#       "Dead":false,
#       "Pid":0,
#       "ExitCode":137,
#       "Error":"",
#       "StartedAt":"2024-03-26T02:23:41.645905711Z",
#       "FinishedAt":"2024-03-26T02:23:51.87034755Z"
#    }


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


async def get_container_details(container: DockerContainer):
    logging.info(f"Attempting to get details for {container}")
    return await container.show()


async def get_container_stats(container: DockerContainer):
    return await container.stats(stream = True)


async def pause_container(container: DockerContainer):
    container_details = await get_container_details(container)
    if container_details["State"]["Running"]:
        await container.pause()
        return {"message": "success", "objectId": container_details["Id"]}
    # already paused
    return {"message": "error", "objectId": container_details["Id"]}


async def resume_container(container: DockerContainer):
    container_details = await get_container_details(container)
    if container_details["State"]["Paused"]:
        await container.unpause()
        return {"message": "success", "objectId": container_details["Id"]}
    # already in a running state
    return {"message": "error", "objectId": container_details["Id"]}


async def start_container(container: DockerContainer):
    container_details = await get_container_details(container)
    if container_details["State"]["Status"] == "exited":
        await container.start()
        return {"message": "success", "objectId": container.id}
    # already in a running state
    return {"message": "error", "objectId": container.id}


async def stop_container(container: DockerContainer):
    container_details = await get_container_details(container)
    if container_details["State"]["Running"] or container_details["State"]["Paused"]:
        await container.stop()
        return {"message": "success", "objectId": container_details["Id"]}
    # already exited
    return {"message": "error", "objectId": container_details["Id"]}


async def restart_container(container: DockerContainer):
    # The container must be in started state. This means that the container must be up and running for at least 10 seconds. This shall prevent docker from restarting the container unnecessarily in case it has not even started successfully.
    container_details = await get_container_details(container)
    if container_details["State"]["Running"] or container_details["State"]["Paused"]:
        await container.restart()
        return {"message": "success", "objectId": container_details["Id"]}
    # not running or paused to restart
    return {"message": "error", "objectId": container_details["Id"]}


async def kill_container(container: DockerContainer):
    # container must be paused or running to be killed
    container_details = await get_container_details(container)
    if container_details["State"]["Running"] or container_details["State"]["Paused"]:
        await container.kill()
        return {"message": "success", "objectId": container_details["Id"]}
    # not running or paused to be killed
    return {"message": "error", "objectId": container_details["Id"]}


async def delete_container(container: DockerContainer):
    # delete shouldn't go off of status because it wouldn't exist!
    try:
        logging.info(f"Attempting to delete container: {container}")
        # stop running container before deletion
        container_details = await get_container_details(container)
        if (
            container_details["State"]["Running"]
            or container_details["State"]["Paused"]
        ):
            if container_details["State"]["Status"] != "exited":
                logging.info(f"Attempting to stop running container: {container}")
                await container.stop()
                logging.info(f"Stoped running container: {container}")
        await container.delete()
        logging.info(f"Deleted container: {container}")
    except DockerError as e:
        # already deleted
        return {"message": "error", "objectId": container_details["Id"]}
    return {"message": "success", "objectId": container_details["Id"]}


async def delete_image(id: str):
    # delete any images forcefully
    try:
        await DOCKER_IMAGES.delete(name=id)
    except DockerError as e:
        # already deleted
        return {"message": "error", "objectId": id[:12]}
    return {"message": "success", "objectId": id[:12]}
