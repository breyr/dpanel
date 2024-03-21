from flask import (
    Flask,
    Response,
    render_template,
    jsonify,
    request,
    Response,
)
import secrets
from typing import Literal
from helpers import publish_message_data, DOCKER_CLIENT, REDIS_CLIENT
from docker import errors
from time import time

# Create the Flask app instance
app = Flask(__name__)
app.secret_key = secrets.token_bytes(16)


# ========= BASIC ROUTES =========
# routes prefixed by /


@app.route("/")
def index() -> Response:
    return render_template("containers.html", current_page="containers")


@app.route("/images")
def images() -> Response:
    return render_template("images.html", current_page="images")


@app.route("/volumes")
def volumes() -> Response:
    return render_template("volumes.html", current_page="volumes")


# ========= ACTION ROUTES =========
# routes prefixed by /actions/


@app.route("/actions/listcontainers")
def list_containers() -> Response:
    containers = DOCKER_CLIENT.containers.list(all=True)
    return jsonify([container.attrs for container in containers])


@app.route("/actions/info/<string:container_id>")
def info(container_id: str) -> Response:
    # get container information
    return DOCKER_CLIENT.containers.get(container_id=container_id).attrs


@app.route("/actions/stats/<string:container_id>")
def stats(container_id):
    return render_template("stats.html", id=container_id)


@app.route("/actions/delete", methods=["POST"])
def delete_containers() -> (
    tuple[Response, Literal[200]] | tuple[Response, Literal[400]]
):
    """
    Deletes one or more Docker containers.

    This function handles POST requests to the "/delete" route. It expects a JSON body with a key "ids" that contains a list of Docker container IDs to be deleted.

    If the deletion is successful, it publishes a success message and returns a JSON response with a message and a status code of 200.

    If there's an API error during the deletion process, it publishes an error message and returns a JSON response with a message and a status code of 400.

    Returns:
        tuple: A tuple containing a Flask Response object and an HTTP status code (200 or 400).
    """
    try:
        data = request.get_json()
        ids = data["ids"]
        for id in ids:
            # delete the container
            container = DOCKER_CLIENT.containers.get(id)
            # forcibly kills and removes container
            container.remove(v=False, link=False, force=True)
        publish_message_data(f"Containers deleted: {len(ids)}", "success")
        return jsonify({"message": "Containers deleted successfully"}), 200
    except errors.APIError:
        publish_message_data("API error, please try again", "danger")
        return jsonify({"message": "API Error"}), 400


@app.route("/actions/start", methods=["POST"])
def start_container() -> tuple[Response, Literal[200]] | tuple[Response, Literal[400]]:
    """
    Starts one or more Docker containers.

    This function handles POST requests to the "/start" route. It expects a JSON body with a key "ids" that contains a list of Docker container IDs to be started.

    For each container ID, it checks if the container is already running. If it's not, it tries to start the container. If the container is already running or if there's an API error during the start process, it adds the container ID to a list of error IDs.

    If no containers were started, it publishes a danger message with the error IDs. If some containers were started, it publishes a success message with the number of containers started and a danger message with the error IDs (if any).

    Regardless of whether any containers were started, it returns a JSON response with a message and a status code of 200.

    If there's an exception during the process, it publishes a danger message and returns a JSON response with a message and a status code of 400.

    Returns:
        tuple: A tuple containing a Flask Response object and an HTTP status code (200 or 400).
    """
    try:
        data = request.get_json()
        ids = data["ids"]
        error_ids = []
        for id in ids:
            container = DOCKER_CLIENT.containers.get(id)
            if container.status == "running":
                error_ids.append(id[:12])
            else:
                try:
                    # start the container
                    container.start()
                except errors.APIError as e:
                    error_ids.append(id[:12])
        # no containers were started
        if len(ids) - len(error_ids) == 0:
            publish_message_data(f"Containers already started: {error_ids}", "danger")
        else:
            publish_message_data(
                f"Containers started: {len(ids) - len(error_ids)}", "success"
            )
            # publish error ids if any
            if error_ids:
                publish_message_data(
                    f"Containers already started: {error_ids}", "danger"
                )
        return jsonify({"message": "Containers started successfully"}), 200
    except Exception as e:
        publish_message_data("API error, please try again", "danger")
        return jsonify({"message": "API Error"}), 400


@app.route("/actions/stop", methods=["POST"])
def stop_containers() -> tuple[Response, Literal[200]] | tuple[Response, Literal[400]]:
    """
    Stops one or more Docker containers.

    This function handles POST requests to the "/stop" route. It expects a JSON body with a key "ids" that contains a list of Docker container IDs to be stopped.

    For each container ID, it checks if the container is already stopped. If it's not, it tries to stop the container. If the container is already stopped or if there's an API error during the stop process, it adds the container ID to a list of error IDs.

    It publishes success and danger messages based on the containers stopped and returns a JSON response with a message and a status code of 200 or 400 based on the operation's success.

    Returns:
        tuple: A tuple containing a Flask Response object and an HTTP status code (200 or 400).
    """
    try:
        data = request.get_json()
        ids = data["ids"]
        error_ids = []
        for id in ids:
            container = DOCKER_CLIENT.containers.get(id)
            if container.status == "exited":
                error_ids.append(id[:12])
            else:
                try:
                    # stop the container
                    container.stop()
                except errors.APIError as e:
                    error_ids.append(id[:12])
        # no containers were stopped
        if len(ids) - len(error_ids) == 0:
            publish_message_data(f"Containers already stopped: {error_ids}", "danger")
        else:
            publish_message_data(
                f"Containers stopped: {len(ids) - len(error_ids)}", "success"
            )
            # publish error ids if any
            if error_ids:
                publish_message_data(
                    f"Containers already stopped: {error_ids}", "danger"
                )
        return jsonify({"message": "Containers stopped successfully"}), 200
    except Exception as e:
        publish_message_data("API error, please try again", "danger")
        return jsonify({"message": "API Error"}), 400


@app.route("/actions/kill", methods=["POST"])
def kill_containers() -> tuple[Response, Literal[200]] | tuple[Response, Literal[400]]:
    """
    Kills one or more Docker containers.

    This function handles POST requests to the "/kill" route. It expects a JSON body with a key "ids" that contains a list of Docker container IDs to be killed.

    For each container ID, it checks if the container is already exited. If it's not, it tries to kill the container. If the container is already exited or if there's an API error during the kill process, it adds the container ID to a list of error IDs.

    It publishes success and danger messages based on the containers killed and returns a JSON response with a message and a status code of 200 or 400 based on the operation's success.

    Returns:
        tuple: A tuple containing a Flask Response object and an HTTP status code (200 or 400).
    """
    try:
        data = request.get_json()
        ids = data["ids"]
        error_ids = []
        for id in ids:
            container = DOCKER_CLIENT.containers.get(id)
            if container.status == "exited":
                error_ids.append(id[:12])
            else:
                try:
                    # stop the container
                    container.kill()
                except errors.APIError as e:
                    error_ids.append(id[:12])
        # no containers were stopped
        if len(ids) - len(error_ids) == 0:
            publish_message_data(f"Containers already killed: {error_ids}", "danger")
        else:
            publish_message_data(
                f"Containers killed: {len(ids) - len(error_ids)}", "success"
            )
            # publish error ids if any
            if error_ids:
                publish_message_data(
                    f"Containers already killed: {error_ids}", "danger"
                )
        return jsonify({"message": "Containers killed successfully"}), 200
    except Exception as e:
        publish_message_data("API error, please try again", "danger")
        return jsonify({"message": "API Error"}), 400


@app.route("/actions/restart", methods=["POST"])
def restart_containers() -> (
    tuple[Response, Literal[200]] | tuple[Response, Literal[400]]
):
    """
    Restarts one or more Docker containers.

    This function handles POST requests to the "/restart" route. It expects a JSON body with a key "ids" that contains a list of Docker container IDs to be restarted.

    For each container ID, it tries to restart the container. If there's an API error during the restart process, it ignores the error and continues with the next ID.

    It publishes a success message with the number of containers restarted and returns a JSON response with a message and a status code of 200.

    If there's an exception during the process, it publishes a danger message and returns a JSON response with a message and a status code of 400.

    Returns:
        tuple: A tuple containing a Flask Response object and an HTTP status code (200 or 400).
    """
    try:
        data = request.get_json()
        ids = data["ids"]
        for id in ids:
            container = DOCKER_CLIENT.containers.get(id)
            try:
                # restart the container
                container.restart()
            except errors.APIError as e:
                pass
        publish_message_data(f"Containers restarted: {len(ids)}", "success")
        return jsonify({"message": "Containers restarted successfully"}), 200
    except Exception as e:
        publish_message_data("API error, please try again", "danger")
        return jsonify({"message": "API Error"}), 400


@app.route("/actions/pause", methods=["POST"])
def pause_containers() -> tuple[Response, Literal[200]] | tuple[Response, Literal[400]]:
    """
    Pauses one or more Docker containers.

    This function handles POST requests to the "/pause" route. It expects a JSON body with a key "ids" that contains a list of Docker container IDs to be paused.

    For each container ID, it checks if the container is already paused. If it's not, it tries to pause the container. If the container is already paused or if there's an API error during the pause process, it adds the container ID to a list of error IDs.

    It publishes success and danger messages based on the containers paused and returns a JSON response with a message and a status code of 200 or 400 based on the operation's success.

    Returns:
        tuple: A tuple containing a Flask Response object and an HTTP status code (200 or 400).
    """
    try:
        data = request.get_json()
        ids = data["ids"]
        error_ids = []
        for id in ids:
            container = DOCKER_CLIENT.containers.get(id)
            if container.status == "paused":
                error_ids.append(id[:12])
            else:
                try:
                    # stop the container
                    container.pause()
                except errors.APIError as e:
                    error_ids.append(id[:12])
        # no containers were stopped
        if len(ids) - len(error_ids) == 0:
            publish_message_data(f"Containers already paused: {error_ids}", "danger")
        else:
            publish_message_data(
                f"Containers paused: {len(ids) - len(error_ids)}", "success"
            )
            # publish any error ids
            if error_ids:
                publish_message_data(
                    f"Containers already paused: {error_ids}", "danger"
                )
        return jsonify({"message": "Containers paused successfully"}), 200
    except Exception as e:
        publish_message_data("API error, please try again", "danger")
        return jsonify({"message": "API Error"}), 400


@app.route("/actions/resume", methods=["POST"])
def resume_containers() -> (
    tuple[Response, Literal[200]] | tuple[Response, Literal[400]]
):
    """
    Resumes one or more paused Docker containers.

    This function handles POST requests to the "/resume" route. It expects a JSON body with a key "ids" that contains a list of Docker container IDs to be resumed.

    For each container ID, it checks if the container is already running. If it's not, it tries to resume the container. If the container is already running or if there's an API error during the resume process, it adds the container ID to a list of error IDs.

    It publishes success and danger messages based on the containers resumed and returns a JSON response with a message and a status code of 200 or 400 based on the operation's success.

    Returns:
        tuple: A tuple containing a Flask Response object and an HTTP status code (200 or 400).
    """
    try:
        data = request.get_json()
        ids = data["ids"]
        error_ids = []
        for id in ids:
            container = DOCKER_CLIENT.containers.get(id)
            if container.status == "running":
                error_ids.append(id[:12])
            else:
                try:
                    # stop the container
                    container.unpause()
                except errors.APIError as e:
                    error_ids.append(id[:12])
        # no containers were stopped
        if len(ids) - len(error_ids) == 0:
            publish_message_data(f"Containers already running: {error_ids}", "danger")
        else:
            publish_message_data(
                f"Containers resumed: {len(ids) - len(error_ids)}", "success"
            )
            # print error ids if any
            if error_ids:
                publish_message_data(
                    f"Containers already running: {error_ids}", "danger"
                )
        return jsonify({"message": "Containers resumed successfully"}), 200
    except Exception as e:
        publish_message_data("API error, please try again", "danger")
        return jsonify({"message": "API Error"}), 400


@app.route("/actions/prune", methods=["POST"])
def prune_system() -> tuple[Response, Literal[200]] | tuple[Response, Literal[400]]:
    """
    Prunes Docker system.

    This function handles POST requests to the "/prune" route. It tries to prune Docker containers, which removes all stopped containers, all unused networks, and all dangling images.

    If the prune operation is successful, it publishes a success message with the number of containers deleted and the space reclaimed, and returns a JSON response with a message and a status code of 200.

    If there's an API error during the prune operation, it publishes a danger message and returns a JSON response with a message and a status code of 400.

    Returns:
        tuple: A tuple containing a Flask Response object and an HTTP status code (200 or 400).
    """
    try:
        pruned_containers = DOCKER_CLIENT.containers.prune()
        # client.images.prune()
        # client.networks.prune()
        # client.volumes.prune()
        containers_deleted = pruned_containers.get("ContainersDeleted")
        if containers_deleted is not None:
            num_deleted = len(containers_deleted)
        else:
            num_deleted = 0
        space_reclaimed = pruned_containers.get("SpaceReclaimed", 0)
        publish_message_data(
            f"System pruned successfully: {num_deleted} containers deleted, {space_reclaimed} space reclaimed",
            "success",
        )
        return jsonify({"message": "prune successfull"}), 200
    except errors.APIError:
        publish_message_data("API error, please try again", "danger")
        return jsonify({"message": "API Error"}), 400


# ========= STREAMING ROUTES =========
# routes prefixed by /streaming/


@app.route("/streaming/homepage")
def homepage() -> Response:
    """
    Streams events to the homepage.

    This function subscribes to the "containers_homepage" channel on Redis and listens for messages. It yields each message as a Server-Sent Event (SSE), which can be consumed by the frontend to update the homepage in real-time.

    If no messages are received for 60 seconds, it stops listening and closes the connection.

    When the response is closed (e.g., when the client disconnects), it unsubscribes from the channel and closes the Redis pubsub connection.

    Returns:
        Response: A Flask Response object that streams Server-Sent Events.
    """
    pubsub = REDIS_CLIENT.pubsub()
    pubsub.subscribe("containers_homepage")

    def event_stream():
        start_time = time()
        for message in pubsub.listen():
            elapsed_time = time() - start_time
            if elapsed_time >= 60:
                break  # close connection if no messages received for 60 seconds
            if message["type"] == "message":
                yield f"data: {message['data'].decode('utf-8')}\n\n"

    res = Response(event_stream(), content_type="text/event-stream")

    def close():
        pubsub.unsubscribe(f"containers_homepage")
        pubsub.close()

    res.call_on_close(close)

    return res


@app.route("/streaming/stats/<string:container_id>")
def container_stats(container_id: str) -> Response:
    """
    Streams container metrics events to the client.

    This function subscribes to a Redis channel specific to the given container ID and listens for messages. It yields each message as a Server-Sent Event (SSE), which can be consumed by the frontend to update the container metrics in real-time.

    If no messages are received for 60 seconds, it stops listening and closes the connection.

    When the response is closed (e.g., when the client disconnects), it unsubscribes from the channel and closes the Redis pubsub connection.

    Args:
        container_id (str): The ID of the container to stream metrics for.

    Returns:
        Response: A Flask Response object that streams Server-Sent Events.
    """

    pubsub = REDIS_CLIENT.pubsub()
    pubsub.subscribe(f"container_metrics_{container_id}")

    def event_stream():
        start_time = time()
        for message in pubsub.listen():
            elapsed_time = time() - start_time
            if elapsed_time >= 60:
                break  # close connection if no messages received for 60 seconds
            if message["type"] == "message":
                yield f"data: {message['data'].decode('utf-8')}\n\n"

    res = Response(event_stream(), content_type="text/event-stream")

    def close():
        pubsub.unsubscribe(f"container_metrics_{container_id}")
        pubsub.close()

    res.call_on_close(close)

    return res


@app.route("/streaming/messages")
def messages() -> Response:
    """
    Streams messages from the "flask_messages" Redis channel to the client.

    This function subscribes to the "flask_messages" channel on Redis and listens for messages. It yields each message as a Server-Sent Event (SSE), which can be consumed by the frontend to update in real-time.

    If no messages are received for 60 seconds, it stops listening and closes the connection.

    When the response is closed (e.g., when the client disconnects), it unsubscribes from the channel and closes the Redis pubsub connection.

    Returns:
        Response: A Flask Response object that streams Server-Sent Events.
    """
    pubsub = REDIS_CLIENT.pubsub()
    # subscribe to specific id
    pubsub.subscribe("flask_messages")

    def event_stream():
        start_time = time()
        for message in pubsub.listen():
            elapsed_time = time() - start_time
            if elapsed_time >= 60:
                break  # close connection if no messages received for 60 seconds
            if message["type"] == "message":
                yield f"data: {message['data'].decode('utf-8')}\n\n"

    res = Response(event_stream(), content_type="text/event-stream")

    def close():
        pubsub.unsubscribe("flask_messages")
        pubsub.close()

    res.call_on_close(close)

    return res


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5001, debug=True)
