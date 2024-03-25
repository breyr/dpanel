from fastapi import FastAPI, Request, HTTPException
from sse_starlette import EventSourceResponse
from fastapi.requests import Request
from fastapi.responses import JSONResponse, Response
from fastapi.middleware.cors import CORSMiddleware
import aioredis
from aioredis import Redis
import json
from models import ContainerData
import docker
from docker.errors import APIError

# Define global variables
redis: Redis = None
DOCKER_CLIENT = docker.from_env()

app = FastAPI()

origins = ["http://localhost:3000", "http://localhost:5002"]

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


async def subscribeToChannel(req: Request, chan: str):
    pubsub = redis.pubsub()
    # will fail if you pass a channel that doesn't exist
    await pubsub.subscribe(chan)
    async for message in pubsub.listen():
        if await req.is_disconnected():
            await pubsub.close()
            break
        if message["type"] == "message" and message["data"] != 1:
            yield f"{message['data'].decode('utf-8')}\n\n"


def publish_message_data(message: str, category: str):
    redis.publish(
        "server_messages", json.dumps({"text": message, "category": category})
    )


# ======== ENDPOINTS =========


@app.get("/api/streams/containerlist")
async def container_list(req: Request):
    return EventSourceResponse(subscribeToChannel(req, "containers_list"))


@app.get("/api/streams/servermessages")
async def container_list(req: Request):
    return EventSourceResponse(subscribeToChannel(req, "server_messages"))


@app.post("/api/containers/start")
def start_containers(req: Request):
    pass


@app.post("/api/containers/pause")
def pause_containers(req: Request):
    pass
