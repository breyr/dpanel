# docker_utils holds async and sync clients as well as all actions being preformed
# TODO: add python on whales

import aiodocker
from aiodocker.exceptions import DockerError
import docker
from aiodocker.docker import DockerContainer
from logger import Logger


class DockerManager:
    def __init__(self):
        self.async_client = aiodocker.Docker()
        self.sync_client = docker.from_env()
        self.images_interface = aiodocker.docker.DockerImages(self.async_client)
        self.logger = Logger(__name__)

    async def get_container_details(self, container: DockerContainer):
        self.logger.info(f"Attempting to get details for {container}")
        return await container.show()

    async def pause_container(self, container: DockerContainer):
        container_details = await self.get_container_details(container)
        if container_details["State"]["Running"]:
            await container.pause()
            return {"type": "success", "objectId": container_details["Id"]}
        # already paused
        return {"type": "error", "objectId": container_details["Id"]}

    async def resume_container(self, container: DockerContainer):
        container_details = await self.get_container_details(container)
        if container_details["State"]["Paused"]:
            await container.unpause()
            return {"type": "success", "objectId": container_details["Id"]}
        # already in a running state
        return {"type": "error", "objectId": container_details["Id"]}

    async def start_container(self, container: DockerContainer):
        container_details = await self.get_container_details(container)
        if container_details["State"]["Status"] == "exited":
            await container.start()
            return {"type": "success", "objectId": container.id}
        # already in a running state
        return {"type": "error", "objectId": container.id}

    async def stop_container(self, container: DockerContainer):
        container_details = await self.get_container_details(container)
        if (
            container_details["State"]["Running"]
            or container_details["State"]["Paused"]
        ):
            await container.stop()
            return {"type": "success", "objectId": container_details["Id"]}
        # already exited
        return {"type": "error", "objectId": container_details["Id"]}

    async def restart_container(self, container: DockerContainer):
        # The container must be in started state. This means that the container must be up and running for at least 10 seconds. This shall prevent docker from restarting the container unnecessarily in case it has not even started successfully.
        container_details = await self.get_container_details(container)
        if (
            container_details["State"]["Running"]
            or container_details["State"]["Paused"]
        ):
            await container.restart()
            return {"type": "success", "objectId": container_details["Id"]}
        # not running or paused to restart
        return {"type": "error", "objectId": container_details["Id"]}

    async def kill_container(self, container: DockerContainer):
        # container must be paused or running to be killed
        container_details = await self.get_container_details(container)
        if (
            container_details["State"]["Running"]
            or container_details["State"]["Paused"]
        ):
            await container.kill()
            return {"type": "success", "objectId": container_details["Id"]}
        # not running or paused to be killed
        return {"type": "error", "objectId": container_details["Id"]}

    async def delete_container(self, container: DockerContainer):
        # delete shouldn't go off of status because it wouldn't exist!
        try:
            self.logger.info(f"Attempting to delete container: {container}")
            # stop running container before deletion
            container_details = await self.get_container_details(container)
            if (
                container_details["State"]["Running"]
                or container_details["State"]["Paused"]
            ):
                if container_details["State"]["Status"] != "exited":
                    self.logger.info(
                        f"Attempting to stop running container: {container}"
                    )
                    await container.stop()
                    self.logger.info(f"Stoped running container: {container}")
            await container.delete()
            self.logger.info(f"Deleted container: {container}")
        except DockerError as e:
            # already deleted
            return {"type": "error", "objectId": container_details["Id"]}
        return {"type": "success", "objectId": container_details["Id"]}

    async def delete_image(self, id: str):
        # delete any images forcefully
        try:
            await self.images_interface.delete(name=id)
        except DockerError as e:
            # already deleted
            return {"type": "error", "objectId": id}
        return {"type": "success", "objectId": id}

    async def pull_image(self, from_image: str, tag: str):
        # pull the image
        try:
            # if tag is an empty string, use latest
            tag = tag if tag else "latest"
            res = await self.images_interface.pull(from_image=from_image, tag=tag)
            self.logger.info(res)
        except DockerError as e:
            return {"type": "error", "statusCode": e.status, "message": e.message}
        return {"type": "success", "message": res[-1]}
