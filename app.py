from flask import Flask, render_template, jsonify, request, flash, redirect, url_for
import docker
import secrets
import json


app = Flask(__name__)
app.secret_key = secrets.token_bytes(16)
client = docker.from_env()


@app.route("/")
def index():
    # get containers
    containers = client.containers.list(all=True)
    return render_template("containers.html",  current_page='containers')


@app.route("/get_containers")
def get_containers():
    containers = client.containers.list(all=True)
    return jsonify([container.attrs for container in containers])


# creating a container, not running it
@app.route("/containers", methods=['POST'])
def create_container():
    try:
        # get desired image from form
        image = request.form.get('image')
        # create container
        container = client.containers.create(image, command="/bin/bash")
        flash(f"Container {container.short_id} created successfully", "success")
        return redirect(url_for('index'))
    except docker.errors.ImageNotFound:
        flash("Image not found", "error")
        return redirect(url_for('index'))
    

# delete containers
@app.route("/delete", methods=['DELETE'])
def delete_container():
    pass


# prune system
@app.route("/prune", methods=['POST'])
def prune_system():
    try: 
        pruned_containers = client.containers.prune()
        # client.images.prune()
        # client.networks.prune()
        # client.volumes.prune()
        num_deleted = len(pruned_containers.get('ContainersDeleted', []))
        space_reclaimed = pruned_containers.get('SpaceReclaimed', 0)
        flash(f"System pruned successfully: {num_deleted} containers deleted, {space_reclaimed} space reclaimed", "success")
        return redirect(url_for('index'))
    except docker.errors.APIError:
        flash("API error, please try again", "danger")
        return redirect(url_for('index'))

@app.route("/images")
def images():
    return render_template("images.html", current_page='images')


@app.route("/volumes")
def volumes():
    return render_template("volumes.html", current_page='volumes')


@app.route("/info/<containerId>")
def info(containerId):
    # get container information
    return client.containers.get(container_id=containerId).attrs


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=80, debug=True)
