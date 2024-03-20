from flask import (
    Flask,
    render_template,
    jsonify,
    request,
    redirect,
    url_for,
    Response,
)
import docker, secrets, redis, json


app = Flask(__name__)
app.secret_key = secrets.token_bytes(16)
client = docker.from_env()
r = redis.StrictRedis(host="host.docker.internal", port=6379, db=0)


# for publishing messages, needs to be used within the Flask app
def publish_message_data(message, category):
    r.publish("flask_messages", json.dumps({"text": message, "category": category}))


@app.route("/")
def index():
    return render_template("containers.html", current_page="containers")


@app.route("/get_containers")
def get_containers():
    containers = client.containers.list(all=True)
    return jsonify([container.attrs for container in containers])


# NOT USING THIS ENDPOIT, CREATE WILL NOT WORK
# creating a container, not running it
@app.route("/containers", methods=["POST"])
def create_container():
    try:
        # get desired image from form
        image = request.form.get("image")
        # create container
        container = client.containers.create(image)
        publish_message_data(
            f"Container {container.short_id} created successfully", "success"
        )
        return redirect(url_for("index"))
    except docker.errors.ImageNotFound:
        # try pulling the image and creating
        try:
            image = client.images.pull(image, tag="latest")
            container = client.containers.create(image.id)
            publish_message_data(
                f"Container {container.short_id} created successfully", "success"
            )
            return redirect(url_for("index"))
        except docker.errors.APIError:
            publish_message_data("API error, please try again", "danger")
            return redirect(url_for("index"))


# delete containers
@app.route("/delete", methods=["POST"])
def delete_container():
    try:
        data = request.get_json()
        ids = data["ids"]
        for id in ids:
            # delete the container
            container = client.containers.get(id)
            # forcibly kills and removes container
            container.remove(v=False, link=False, force=True)
        publish_message_data(f"Containers deleted: {len(ids)}", "success")
        return jsonify({"message": "Containers deleted successfully"}), 200
    except docker.errors.APIError:
        publish_message_data("API error, please try again", "danger")
        return jsonify({"message": "API Error"}), 400


# start containers
@app.route("/start", methods=["POST"])
def start_container():
    try:
        data = request.get_json()
        ids = data["ids"]
        error_ids = []
        for id in ids:
            container = client.containers.get(id)
            if container.status == "running":
                error_ids.append(id[:12])
            else:
                try:
                    # start the container
                    container.start()
                except docker.errors.APIError as e:
                    error_ids.append(id[:12])
        # no containers were started
        if len(ids) - len(error_ids) == 0:
            publish_message_data(f"Containers already started: {error_ids}", "danger")
        else:
            publish_message_data(
                f"Containers started: {len(ids) - len(error_ids)}", "success"
            )
            # print error ids if any
            if error_ids:
                publish_message_data(
                    f"Containers already started: {error_ids}", "danger"
                )
        return jsonify({"message": "Containers started successfully"}), 200
    except Exception as e:
        publish_message_data("API error, please try again", "danger")
        return jsonify({"message": "API Error"}), 400


# stop containers
@app.route("/stop", methods=["POST"])
def stop_container():
    try:
        data = request.get_json()
        ids = data["ids"]
        error_ids = []
        for id in ids:
            container = client.containers.get(id)
            if container.status == "exited":
                error_ids.append(id[:12])
            else:
                try:
                    # stop the container
                    container.stop()
                except docker.error.APIError as e:
                    error_ids.append(id[:12])
        # no containers were stopped
        if len(ids) - len(error_ids) == 0:
            publish_message_data(f"Containers already stopped: {error_ids}", "danger")
        else:
            publish_message_data(
                f"Containers stopped: {len(ids) - len(error_ids)}", "success"
            )
            # print error ids if any
            if error_ids:
                publish_message_data(
                    f"Containers already stopped: {error_ids}", "danger"
                )
        return jsonify({"message": "Containers stopped successfully"}), 200
    except Exception as e:
        publish_message_data("API error, please try again", "danger")
        return jsonify({"message": "API Error"}), 400


# kill containers
@app.route("/kill", methods=["POST"])
def kill_container():
    try:
        data = request.get_json()
        ids = data["ids"]
        error_ids = []
        for id in ids:
            container = client.containers.get(id)
            if container.status == "exited":
                error_ids.append(id[:12])
            else:
                try:
                    # stop the container
                    container.kill()
                except docker.error.APIError as e:
                    error_ids.append(id[:12])
        # no containers were stopped
        if len(ids) - len(error_ids) == 0:
            publish_message_data(f"Containers already killed: {error_ids}", "danger")
        else:
            publish_message_data(
                f"Containers killed: {len(ids) - len(error_ids)}", "success"
            )
            # print error ids if any
            if error_ids:
                publish_message_data(
                    f"Containers already killed: {error_ids}", "danger"
                )
        return jsonify({"message": "Containers killed successfully"}), 200
    except Exception as e:
        publish_message_data("API error, please try again", "danger")
        return jsonify({"message": "API Error"}), 400


# restart containers
@app.route("/restart", methods=["POST"])
def restart_container():
    try:
        data = request.get_json()
        ids = data["ids"]
        for id in ids:
            container = client.containers.get(id)
            try:
                # restart the container
                container.restart()
            except docker.error.APIError as e:
                pass
        publish_message_data(f"Containers restarted: {len(ids)}", "success")
        return jsonify({"message": "Containers restarted successfully"}), 200
    except Exception as e:
        publish_message_data("API error, please try again", "danger")
        return jsonify({"message": "API Error"}), 400


# pause containers
@app.route("/pause", methods=["POST"])
def pause_container():
    try:
        data = request.get_json()
        ids = data["ids"]
        error_ids = []
        for id in ids:
            container = client.containers.get(id)
            if container.status == "paused":
                error_ids.append(id[:12])
            else:
                try:
                    # stop the container
                    container.pause()
                except docker.error.APIError as e:
                    error_ids.append(id[:12])
        # no containers were stopped
        if len(ids) - len(error_ids) == 0:
            publish_message_data(f"Containers already paused: {error_ids}", "danger")
        else:
            publish_message_data(
                f"Containers paused: {len(ids) - len(error_ids)}", "success"
            )
            # print error ids if any
            if error_ids:
                publish_message_data(
                    f"Containers already paused: {error_ids}", "danger"
                )
        return jsonify({"message": "Containers paused successfully"}), 200
    except Exception as e:
        publish_message_data("API error, please try again", "danger")
        return jsonify({"message": "API Error"}), 400


# resume containers
@app.route("/resume", methods=["POST"])
def resume_container():
    try:
        data = request.get_json()
        ids = data["ids"]
        error_ids = []
        for id in ids:
            container = client.containers.get(id)
            if container.status == "running":
                error_ids.append(id[:12])
            else:
                try:
                    # stop the container
                    container.unpause()
                except docker.error.APIError as e:
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


# prune system
@app.route("/prune", methods=["POST"])
def prune_system():
    try:
        pruned_containers = client.containers.prune()
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
        return "", 200
    except docker.errors.APIError:
        publish_message_data("API error, please try again", "danger")
        return "", 400


# homepage stream
@app.route("/homepage_stream")
def homepage_stream():
    def event_stream():
        pubsub = r.pubsub()
        pubsub.subscribe("containers_homepage")
        for message in pubsub.listen():
            if message["type"] == "message":
                yield f"data: {message['data'].decode('utf-8')}\n\n"

    return Response(event_stream(), content_type="text/event-stream")


# container stats stream
@app.route("/container_stream/<container_id>")
def container_stream(container_id):
    def event_stream():
        pubsub = r.pubsub()
        # subscribe to specific id
        pubsub.subscribe(f"container_metrics_{container_id}")
        for message in pubsub.listen():
            if message["type"] == "message":
                yield f"data: {message['data'].decode('utf-8')}\n\n"

    return Response(event_stream(), content_type="text/event-stream")


# get messages, returns server messages created by publish_message_data()
@app.route("/messages")
def messages():
    def event_stream():
        pubsub = r.pubsub()
        # subscribe to specific id
        pubsub.subscribe("flask_messages")
        for message in pubsub.listen():
            if message["type"] == "message":
                yield f"data: {message['data'].decode('utf-8')}\n\n"

    return Response(event_stream(), content_type="text/event-stream")


# template rendering for stats page
@app.route("/stats/<container_id>")
def stats(container_id):
    return render_template("stats.html", id=container_id)


@app.route("/images")
def images():
    return render_template("images.html", current_page="images")


@app.route("/volumes")
def volumes():
    return render_template("volumes.html", current_page="volumes")


@app.route("/info/<containerId>")
def info(containerId):
    # get container information
    return client.containers.get(container_id=containerId).attrs


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5001, debug=True)
