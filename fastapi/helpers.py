import json
from aioredis import Redis
from fastapi import Request
import aiodocker
from aiodocker.exceptions import DockerError
from aiodocker.docker import DockerContainer

ASYNC_DOCKER_CLIENT = aiodocker.Docker()

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
    await redis.publish(
        "server_messages", json.dumps({"text": message, "category": category})
    )


async def get_container_details(container: DockerContainer):
    return await container.show()


async def pause_container(container: DockerContainer):
    container_details = await get_container_details(container)
    if container_details["State"]["Running"]:
        await container.pause()
        return {"message": "success", "containerId": container_details["Id"]}
    # already paused
    return {"message": "error", "containerId": container_details["Id"]}


async def resume_container(container: DockerContainer):
    container_details = await get_container_details(container)
    if container_details["State"]["Paused"]:
        await container.unpause()
        return {"message": "success", "containerId": container_details["Id"]}
    # already in a running state
    return {"message": "error", "containerId": container_details["Id"]}


async def start_container(container: DockerContainer):
    container_details = await get_container_details(container)
    if container_details["State"]["Status"] == "exited":
        await container.start()
        return {"message": "success", "containerId": container.id}
    # already in a running state
    return {"message": "error", "containerId": container.id}


async def stop_container(container: DockerContainer):
    container_details = await get_container_details(container)
    if container_details["State"]["Running"] or container_details["State"]["Paused"]:
        await container.stop()
        return {"message": "success", "containerId": container_details["Id"]}
    # already exited
    return {"message": "error", "containerId": container_details["Id"]}


async def restart_container(container: DockerContainer):
    # The container must be in started state. This means that the container must be up and running for at least 10 seconds. This shall prevent docker from restarting the container unnecessarily in case it has not even started successfully.
    container_details = await get_container_details(container)
    if container_details["State"]["Running"] or container_details["State"]["Paused"]:
        await container.restart()
        return {"message": "success", "containerId": container_details["Id"]}
    # not running or paused to restart
    return {"message": "error", "containerId": container_details["Id"]}


async def kill_container(container: DockerContainer):
    # container must be paused or running to be killed
    container_details = await get_container_details(container)
    if container_details["State"]["Running"] or container_details["State"]["Paused"]:
        await container.kill()
        return {"message": "success", "containerId": container_details["Id"]}
    # not running or paused to be killed
    return {"message": "error", "containerId": container_details["Id"]}


async def delete_container(container: DockerContainer):
    # delete shouldn't go off of status because it wouldn't exist!
    try:
        await container.remove(v=False, link=False, force=True)
    except DockerError as e:
        # already deleted
        return {"message": "error", "containerId": container.short_id}
    return {"message": "success", "containerId": container.short_id}
