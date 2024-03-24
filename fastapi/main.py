from fastapi import FastAPI
from sse_starlette import EventSourceResponse
from fastapi.requests import Request
from fastapi.middleware.cors import CORSMiddleware
import aioredis

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Define global variables
redis = None


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


async def subscribeContainerList(req: Request):
    pubsub = redis.pubsub()
    await pubsub.subscribe("containers_homepage")
    async for message in pubsub.listen():
        if await req.is_disconnected():
            await pubsub.close()
            break
        if message["type"] == "message" and message["data"] != 1:
            yield f"data: {message['data'].decode('utf-8')}\n\n"


@app.get("/api/streams/containerlist")
async def container_list(req: Request):
    return EventSourceResponse(subscribeContainerList(req))
