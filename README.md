# DPanel

DPanel is a web interface leveraging FastAPI, Redis, Go PubSub, and Nginx to manage Docker processes, including containers, images, and volumes, with real-time statistics.

<!-- Main Image -->
![Main Page](resources/cropped/main-small.png)

## Features

### Key Uses

- **Container Management**: Start, stop, kill, restart, pause, resume, and remove containers.
- **Prune Selectively**: Easily prune containers, images, and volumes, depending on your needs.
- **Customize New Containers**: Create and run containers with custom configurations with networks, env variables, and volumes.
- **Image Management**: Pull and remove images all in one window, without commands.
- **Live Statistics**: View real-time statistics for containers, including CPU, memory, and network usage.
- **Upload and Compose**: Upload Docker Compose files and run them with a single click, and save for later use.

### Flexibility

- **Localhost**: Run DPanel on your local machine.
- **Domain Name**: Connect to a LAN accessible server and access it from DNS.
- **Reverse TCP**: Use Cloudflared to tunnel DPanel to a public domain.

### Web Interface

<div style="display: flex; justify-content: space-between;">
    <img src="resources/styled/main-page.png" style="width: 49%;">
    <img src="resources/styled/secondary-page.png" style="width: 49%;">
</div>

<div style="display: flex; justify-content: space-between; margin-top: 10px;">
    <img src="resources/styled/create-container.png" style="width: 32%;">
    <img src="resources/styled/advanced-container.png" style="width: 32%;">
    <img src="resources/styled/upload-compose.png" style="width: 32%;">
</div>


### Architecture

- **Solid line**: connections and requests
- **Dashed line**: publish-subscribe paths*

<div style="display: flex; justify-content: space-between; margin-top: 10px;">
    <img src="resources/styled/architecture.png" style="width: 49%;">
    <img src="resources/styled/goroutes.png" style="width: 49%;">
</div>

## Usage

### Running Locally

1. Navigate to http://localhost:5002 on a browser.

### Running over LAN

1. Navigate to https://0.0.0.0 on a browser.

### Running over Cloudflared

1. Navigate to https://dpanel.domain.com on a browser.

## Installation

Copy and run the following compose file:

```yaml
version: "3.9"

services:
  pubsub:
    image: breyr/dpanel-pubsub-go
    volumes:
      - /var/run/docker.sock:/var/run/docker.sock
    restart: on-failure
    depends_on:
      - redis
    extra_hosts:
      - "host.docker.internal:host-gateway"
  fastapi:
    image: breyr/dpanel-fastapi
    ports:
      - 5002:5002
    volumes:
      - /var/run/docker.sock:/var/run/docker.sock
      - composefiles:/app/composefiles
    restart: on-failure
    depends_on:
      - redis
    extra_hosts:
      - "host.docker.internal:host-gateway"
  redis:
    image: redis:latest
    ports:
      - 6379:6379
    extra_hosts:
      - "host.docker.internal:host-gateway"

volumes:
  composefiles:
```
