import docker, redis, json

DOCKER_CLIENT = docker.from_env()
REDIS_CLIENT = redis.StrictRedis(host="host.docker.internal", port=6379, db=0)


def publish_message_data(message: str, category: str):
    REDIS_CLIENT.publish(
        "flask_messages", json.dumps({"text": message, "category": category})
    )
