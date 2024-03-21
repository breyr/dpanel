# This file is used for multithreading publishing tasks

import redis, docker, json, time, threading
import typing

DOCKER_CLIENT = docker.from_env()
REDIS_CLIENT = redis.StrictRedis(host="host.docker.internal", port=6379, db=0)


def publish_homepage_data():
    # TODO: add data for images and volumes and anythign else on the homepage
    containers = DOCKER_CLIENT.containers.list(all=True)
    containers_json = json.dumps([container.attrs for container in containers])
    REDIS_CLIENT.publish(f"containers_homepage", containers_json)


def start_publishing_homepage_data():
    while True:
        publish_homepage_data()
        time.sleep(1)


def publish_container_stats():
    for container in DOCKER_CLIENT.containers.list():
        stats = container.stats(stream=False)
        stats_json = json.dumps(stats)
        REDIS_CLIENT.publish(f"container_metrics_{container.id}", stats_json)


def start_publishing_container_stats():
    while True:
        # every 5 seconds publish stats
        publish_container_stats()
        time.sleep(5)


# background thread for publishing stats
# Setting daemon to False for your threads would indeed prevent the Python interpreter from exiting until these threads have completed. However, since your threads are running infinite loops, they will never complete, and so your Python script will run indefinitely.
threading.Thread(target=start_publishing_container_stats, daemon=False).start()
threading.Thread(target=start_publishing_homepage_data, daemon=False).start()
