from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from sse_starlette import EventSourceResponse
import asyncio
import aioredis
import logging

app = FastAPI(docs_url="/api/docs")
_log = logging.getLogger(__name__)
_log.setLevel(logging.INFO)

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

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Allows all origins
    allow_credentials=True,
    allow_methods=["*"],  # Allows all methods
    allow_headers=["*"],  # Allows all headers
)


@app.get("/api/streams/containerlist")
async def containers_info_stream(req: Request):
    global redis
    pubsub = redis.pubsub()
    await pubsub.subscribe("containers_homepage")

    async def event_stream():
        while True:
            disconnected = await req.is_disconnected()
            if disconnected:
                break
            message = await pubsub.get_message()
            if message and message["data"] != 1:
                yield f"data: {message['data'].decode('utf-8')}\n\n"

    return EventSourceResponse(event_stream())
